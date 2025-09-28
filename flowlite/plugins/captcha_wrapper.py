"""
Captcha Wrapper Plugin for FlowLite
Tích hợp Captcha plugin vào FlowLite framework
"""

from .base import BasePlugin
from .captcha import get_captcha_plugin
from typing import Dict, Any, Optional, List


class CaptchaWrapper(BasePlugin):
    """
    Wrapper plugin để sử dụng Captcha trong FlowLite
    """
    
    def __init__(self):
        super().__init__()
        self._captcha = None
    
    @property
    def captcha(self):
        """Lazy load Captcha plugin"""
        if self._captcha is None:
            self._captcha = get_captcha_plugin()
        return self._captcha
    
    def on_flow_start(self, ctx: Dict[str, Any]) -> None:
        """Gắn captcha instance vào ctx.vars để step có thể sử dụng"""
        # ctx.vars có thể là Context object, không phải dict
        if hasattr(ctx.get("vars"), "__dict__"):
            # Nếu là Context object, gán trực tiếp
            ctx.vars.captcha = self
        else:
            # Nếu là dict, xử lý như cũ
            vars_ns = ctx.get("vars") or {}
            vars_ns["captcha"] = self
            ctx["vars"] = vars_ns
    
    def generate_cookies(self, auth: str, site: str, proxyregion: str, 
                        region: str, proxy: str, flow_id: int = None, 
                        max_retries: int = 3) -> Dict[str, Any]:
        """
        Generate cookies từ Parallax API
        
        Args:
            auth: Authentication key
            site: Website (e.g., "youtube", "walmart")
            proxyregion: Proxy region ("eu" or "us")
            region: Site region (e.g., "com", "fr", "ch")
            proxy: Proxy URL
            flow_id: ID của flow (optional)
            max_retries: Số lần retry tối đa
            
        Returns:
            Dictionary chứa kết quả generate cookies
        """
        return self.captcha.generate_cookies(
            auth=auth,
            site=site,
            proxyregion=proxyregion,
            region=region,
            proxy=proxy,
            flow_id=flow_id,
            max_retries=max_retries
        )
    
    def get_pxhold_data(self, pxhold_id: int) -> Optional[Dict[str, Any]]:
        """
        Lấy dữ liệu pxhold theo ID
        
        Args:
            pxhold_id: ID của pxhold record
            
        Returns:
            Dictionary chứa dữ liệu pxhold
        """
        return self.captcha.get_pxhold_data(pxhold_id)
    
    def get_pxhold_by_flow(self, flow_id: int) -> List[Dict[str, Any]]:
        """
        Lấy tất cả pxhold data của một flow
        
        Args:
            flow_id: ID của flow
            
        Returns:
            List các pxhold records
        """
        return self.captcha.get_pxhold_by_flow(flow_id)
    
    def get_successful_pxhold(self, flow_id: int) -> Optional[Dict[str, Any]]:
        """
        Lấy pxhold data thành công gần nhất của flow
        
        Args:
            flow_id: ID của flow
            
        Returns:
            Dictionary chứa pxhold data thành công
        """
        return self.captcha.get_successful_pxhold(flow_id)
    
    def hold_captcha(self, auth: str, site: str, proxyregion: str, 
                    region: str, proxy: str, data: str, pxhold_id: int = None, 
                    max_retries: int = 2) -> Dict[str, Any]:
        """
        Gọi API holdcaptcha
        
        Args:
            auth: Authentication key
            site: Website (e.g., "walmart", "youtube")
            proxyregion: Proxy region ("eu" or "us")
            region: Site region (e.g., "com", "fr", "ch")
            proxy: Proxy URL
            data: Data từ generate cookies
            pxhold_id: ID của pxhold record để cập nhật
            max_retries: Số lần retry tối đa (default: 2)
            
        Returns:
            Dictionary chứa kết quả holdcaptcha
        """
        return self.captcha.hold_captcha(
            auth=auth,
            site=site,
            proxyregion=proxyregion,
            region=region,
            proxy=proxy,
            data=data,
            pxhold_id=pxhold_id,
            max_retries=max_retries
        )
    
    def generate_and_hold_captcha(self, auth: str, site: str, proxyregion: str, 
                                 region: str, proxy: str, flow_id: int = None, 
                                 max_retries: int = 3) -> Dict[str, Any]:
        """
        Generate cookies và sau đó gọi holdcaptcha
        
        Args:
            auth: Authentication key
            site: Website (e.g., "walmart", "youtube")
            proxyregion: Proxy region ("eu" or "us")
            region: Site region (e.g., "com", "fr", "ch")
            proxy: Proxy URL
            flow_id: ID của flow (optional)
            max_retries: Số lần retry tối đa cho generate cookies
            
        Returns:
            Dictionary chứa kết quả cuối cùng
        """
        return self.captcha.generate_and_hold_captcha(
            auth=auth,
            site=site,
            proxyregion=proxyregion,
            region=region,
            proxy=proxy,
            flow_id=flow_id,
            max_retries=max_retries
        )
    
    def delete_pxhold_record(self, pxhold_id: int):
        """
        Xóa pxhold record theo ID
        
        Args:
            pxhold_id: ID của pxhold record cần xóa
        """
        self.captcha.delete_pxhold_record(pxhold_id)
    
    def cleanup_failed_pxhold(self, days: int = 7):
        """
        Dọn dẹp các pxhold records thất bại cũ
        
        Args:
            days: Số ngày
        """
        self.captcha.cleanup_failed_pxhold(days)


# Tạo instance global
captcha_wrapper = CaptchaWrapper()
