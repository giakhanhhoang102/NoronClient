"""
Hyper Solutions SDK Plugin for FlowLite
Tích hợp Hyper-Solutions SDK để bypass bot protection
"""

from .base import BasePlugin
from typing import Dict, Any, Optional, List
import json
import logging

try:
    from hyper_sdk import Session, SensorInput
    HYPER_SDK_AVAILABLE = True
except ImportError:
    HYPER_SDK_AVAILABLE = False
    logging.warning("hyper-sdk not installed. Install with: pip install hyper-sdk")


class HyperSolutionsPlugin(BasePlugin):
    """
    Plugin tích hợp Hyper-Solutions SDK cho FlowLite
    Cung cấp khả năng bypass bot protection cho các site
    """
    
    name = "hyper_solutions"
    version = "1.0.0"
    priority = 50  # Chạy trước các plugin khác
    
    def __init__(self, api_key: str = None, **config: Any):
        super().__init__(**config)
        self.api_key = api_key or self.config.get("api_key")
        self.session = None
        self._initialized = False
        
        if not HYPER_SDK_AVAILABLE:
            raise ImportError("hyper-sdk is required but not installed")
        
        if not self.api_key:
            raise ValueError("API key is required for Hyper Solutions plugin")
    
    def _ensure_session(self):
        """Khởi tạo session nếu chưa có"""
        if not self._initialized:
            self.session = Session(self.api_key)
            self._initialized = True
    
    def on_flow_start(self, ctx: Dict[str, Any]) -> None:
        """Khởi tạo plugin khi flow bắt đầu"""
        self._ensure_session()
        # Gắn plugin vào context để các step có thể sử dụng
        ctx["hyper_solutions"] = self
    
    def generate_sensor_data(self, 
                           site: str,
                           user_agent: str = None,
                           proxy: str = None,
                           additional_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Tạo sensor data để bypass bot protection
        
        Args:
            site: Tên site (e.g., "walmart", "amazon", "target")
            user_agent: User agent string
            proxy: Proxy URL
            additional_params: Các tham số bổ sung
            
        Returns:
            Dict chứa sensor data và context
        """
        self._ensure_session()
        
        try:
            # Chuẩn bị input cho sensor
            sensor_input = SensorInput(
                site=site,
                user_agent=user_agent,
                proxy=proxy,
                **(additional_params or {})
            )
            
            # Tạo sensor data
            sensor_data, sensor_context = self.session.generate_sensor_data(sensor_input)
            
            return {
                "success": True,
                "sensor_data": sensor_data,
                "sensor_context": sensor_context,
                "site": site
            }
            
        except Exception as e:
            logging.error(f"Hyper Solutions sensor generation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "site": site
            }
    
    def get_fingerprint_data(self, 
                           site: str,
                           user_agent: str = None,
                           proxy: str = None) -> Dict[str, Any]:
        """
        Lấy fingerprint data cho site cụ thể
        
        Args:
            site: Tên site
            user_agent: User agent string
            proxy: Proxy URL
            
        Returns:
            Dict chứa fingerprint data
        """
        self._ensure_session()
        
        try:
            # Sử dụng sensor data để tạo fingerprint
            sensor_result = self.generate_sensor_data(site, user_agent, proxy)
            
            if sensor_result["success"]:
                return {
                    "success": True,
                    "fingerprint": sensor_result["sensor_data"],
                    "context": sensor_result["sensor_context"]
                }
            else:
                return sensor_result
                
        except Exception as e:
            logging.error(f"Hyper Solutions fingerprint generation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def bypass_protection(self, 
                        site: str,
                        url: str,
                        headers: Dict[str, str] = None,
                        user_agent: str = None,
                        proxy: str = None) -> Dict[str, Any]:
        """
        Bypass protection cho request cụ thể
        
        Args:
            site: Tên site
            url: URL cần bypass
            headers: Headers hiện tại
            user_agent: User agent
            proxy: Proxy URL
            
        Returns:
            Dict chứa headers và data đã được xử lý
        """
        self._ensure_session()
        
        try:
            # Lấy sensor data
            sensor_result = self.generate_sensor_data(site, user_agent, proxy)
            
            if not sensor_result["success"]:
                return sensor_result
            
            # Xử lý headers với sensor data
            processed_headers = headers or {}
            sensor_data = sensor_result["sensor_data"]
            
            # Thêm các headers cần thiết từ sensor data
            if isinstance(sensor_data, dict):
                for key, value in sensor_data.items():
                    if key.startswith("x-") or key.lower() in ["user-agent", "accept", "accept-language"]:
                        processed_headers[key] = str(value)
            
            return {
                "success": True,
                "headers": processed_headers,
                "sensor_data": sensor_data,
                "context": sensor_result["sensor_context"]
            }
            
        except Exception as e:
            logging.error(f"Hyper Solutions bypass failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def on_request(self, req: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Middleware xử lý request trước khi gửi
        Tự động bypass protection nếu được cấu hình
        """
        # Kiểm tra xem có cần bypass protection không
        bypass_sites = self.config.get("bypass_sites", [])
        url = req.get("url", "")
        
        # Xác định site từ URL
        site = None
        for bypass_site in bypass_sites:
            if bypass_site.lower() in url.lower():
                site = bypass_site
                break
        
        if site:
            # Lấy thông tin từ context
            user_agent = ctx.get("user_agent") or req.get("headers", {}).get("User-Agent")
            proxy = ctx.get("session_proxy")
            
            # Bypass protection
            bypass_result = self.bypass_protection(
                site=site,
                url=url,
                headers=req.get("headers", {}),
                user_agent=user_agent,
                proxy=proxy
            )
            
            if bypass_result["success"]:
                # Cập nhật headers với dữ liệu đã bypass
                req["headers"] = bypass_result["headers"]
                # Lưu sensor data vào context để sử dụng sau
                ctx[f"hyper_solutions_{site}"] = bypass_result
        
        return req
    
    def on_response(self, req: Dict[str, Any], resp: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Middleware xử lý response sau khi nhận
        Có thể thêm logic xử lý response nếu cần
        """
        return resp


# Factory function để tạo plugin
def create_hyper_solutions_plugin(api_key: str, **config) -> HyperSolutionsPlugin:
    """
    Factory function để tạo Hyper Solutions plugin
    
    Args:
        api_key: API key từ Hyper Solutions
        **config: Các cấu hình bổ sung
        
    Returns:
        HyperSolutionsPlugin instance
    """
    return HyperSolutionsPlugin(api_key=api_key, **config)
