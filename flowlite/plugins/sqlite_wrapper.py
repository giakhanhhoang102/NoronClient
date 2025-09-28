"""
SQLite Wrapper Plugin for FlowLite
Tích hợp SQLite plugin vào FlowLite framework
"""

from .base import BasePlugin
from .sqlite import get_sqlite_plugin
from typing import Any, Dict, List, Optional


class SQLiteWrapper(BasePlugin):
    """
    Wrapper plugin để sử dụng SQLite trong FlowLite
    """
    
    def __init__(self):
        super().__init__()
        self._sqlite = None
    
    @property
    def sqlite(self):
        """Lazy load SQLite plugin"""
        if self._sqlite is None:
            self._sqlite = get_sqlite_plugin()
        return self._sqlite
    
    def save_flow(self, flow_name: str, session_id: str = None, 
                  status: str = "RUNNING", data: Dict[str, Any] = None) -> int:
        """
        Lưu dữ liệu flow
        
        Args:
            flow_name: Tên flow
            session_id: ID session
            status: Trạng thái flow
            data: Dữ liệu flow
            
        Returns:
            ID của flow vừa tạo
        """
        return self.sqlite.save_flow_data(flow_name, session_id, status, data)
    
    def update_flow(self, flow_id: int, status: str, data: Dict[str, Any] = None):
        """
        Cập nhật flow
        
        Args:
            flow_id: ID của flow
            status: Trạng thái mới
            data: Dữ liệu mới
        """
        self.sqlite.update_flow_status(flow_id, status, data)
    
    def save_variables(self, flow_id: int, variables: Dict[str, Any]):
        """
        Lưu các biến của flow
        
        Args:
            flow_id: ID của flow
            variables: Dictionary chứa các biến
        """
        self.sqlite.save_variables(flow_id, variables)
    
    def save_http_trace(self, flow_id: int, method: str, url: str, 
                       status_code: int, response_time: float):
        """
        Lưu HTTP trace
        
        Args:
            flow_id: ID của flow
            method: HTTP method
            url: URL
            status_code: Status code
            response_time: Thời gian response (ms)
        """
        self.sqlite.save_http_trace(flow_id, method, url, status_code, response_time)
    
    def get_flow(self, flow_id: int) -> Optional[Dict[str, Any]]:
        """
        Lấy dữ liệu flow
        
        Args:
            flow_id: ID của flow
            
        Returns:
            Dictionary chứa dữ liệu flow
        """
        return self.sqlite.get_flow_data(flow_id)
    
    def get_variables(self, flow_id: int) -> Dict[str, Any]:
        """
        Lấy các biến của flow
        
        Args:
            flow_id: ID của flow
            
        Returns:
            Dictionary chứa các biến
        """
        return self.sqlite.get_flow_variables(flow_id)
    
    def get_http_traces(self, flow_id: int) -> List[Dict[str, Any]]:
        """
        Lấy HTTP traces của flow
        
        Args:
            flow_id: ID của flow
            
        Returns:
            List các HTTP traces
        """
        return self.sqlite.get_flow_http_traces(flow_id)
    
    def get_flows_by_name(self, flow_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Lấy danh sách flows theo tên
        
        Args:
            flow_name: Tên flow
            limit: Số lượng tối đa
            
        Returns:
            List các flows
        """
        return self.sqlite.get_flows_by_name(flow_name, limit)
    
    def delete_flow(self, flow_id: int):
        """
        Xóa flow
        
        Args:
            flow_id: ID của flow
        """
        self.sqlite.delete_flow(flow_id)
    
    def cleanup(self, days: int = 30):
        """
        Dọn dẹp dữ liệu cũ
        
        Args:
            days: Số ngày
        """
        self.sqlite.cleanup_old_data(days)


# Tạo instance global
sqlite_wrapper = SQLiteWrapper()
