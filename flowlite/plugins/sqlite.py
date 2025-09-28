"""
SQLite Plugin for FlowLite
Lưu và truy xuất dữ liệu từ SQLite database
"""

import sqlite3
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union


class SQLitePlugin:
    def __init__(self, db_path: str = "flowlite/plugins/database/flowlite_data.db"):
        """
        Khởi tạo SQLite plugin
        
        Args:
            db_path: Đường dẫn đến file database SQLite
        """
        self.db_path = db_path
        self._initialized = False
    
    def _get_connection(self, timeout: int = 30, max_retries: int = 3):
        """Lấy kết nối database với timeout và retry"""
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=timeout)
                conn.execute("PRAGMA journal_mode=WAL")  # Sử dụng WAL mode để tránh lock
                return conn
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                    continue
                raise e
        raise sqlite3.OperationalError("Database is locked after all retries")

    def _ensure_initialized(self):
        """Đảm bảo database đã được khởi tạo"""
        if not self._initialized:
            self.init_database()
            self._initialized = True

    def init_database(self):
        """Khởi tạo database và tạo các bảng cần thiết"""
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Tạo bảng flows để lưu thông tin flow
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS flows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_name TEXT NOT NULL,
                session_id TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data TEXT  -- JSON data
            )
        ''')
        
        # Tạo bảng variables để lưu các biến
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS variables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_id INTEGER,
                variable_name TEXT NOT NULL,
                variable_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (flow_id) REFERENCES flows (id)
            )
        ''')
        
        # Tạo bảng http_traces để lưu HTTP requests
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS http_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_id INTEGER,
                method TEXT,
                url TEXT,
                status_code INTEGER,
                response_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (flow_id) REFERENCES flows (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_flow_data(self, flow_name: str, session_id: str = None, 
                      status: str = "RUNNING", data: Dict[str, Any] = None) -> int:
        """
        Lưu dữ liệu flow vào database
        
        Args:
            flow_name: Tên flow
            session_id: ID session
            status: Trạng thái flow
            data: Dữ liệu flow (dictionary)
            
        Returns:
            ID của flow vừa tạo
        """
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        data_json = json.dumps(data) if data else None
        
        cursor.execute('''
            INSERT INTO flows (flow_name, session_id, status, data)
            VALUES (?, ?, ?, ?)
        ''', (flow_name, session_id, status, data_json))
        
        flow_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return flow_id
    
    def update_flow_status(self, flow_id: int, status: str, data: Dict[str, Any] = None):
        """
        Cập nhật trạng thái flow
        
        Args:
            flow_id: ID của flow
            status: Trạng thái mới
            data: Dữ liệu mới
        """
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        data_json = json.dumps(data) if data else None
        
        cursor.execute('''
            UPDATE flows 
            SET status = ?, data = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (status, data_json, flow_id))
        
        conn.commit()
        conn.close()
    
    def save_variables(self, flow_id: int, variables: Dict[str, Any]):
        """
        Lưu các biến của flow
        
        Args:
            flow_id: ID của flow
            variables: Dictionary chứa các biến
        """
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Xóa các biến cũ của flow này
        cursor.execute('DELETE FROM variables WHERE flow_id = ?', (flow_id,))
        
        # Lưu các biến mới
        for name, value in variables.items():
            value_str = json.dumps(value) if not isinstance(value, (str, int, float, bool)) else str(value)
            cursor.execute('''
                INSERT INTO variables (flow_id, variable_name, variable_value)
                VALUES (?, ?, ?)
            ''', (flow_id, name, value_str))
        
        conn.commit()
        conn.close()
    
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
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO http_traces (flow_id, method, url, status_code, response_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (flow_id, method, url, status_code, response_time))
        
        conn.commit()
        conn.close()
    
    def get_flow_data(self, flow_id: int) -> Optional[Dict[str, Any]]:
        """
        Lấy dữ liệu flow theo ID
        
        Args:
            flow_id: ID của flow
            
        Returns:
            Dictionary chứa dữ liệu flow
        """
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM flows WHERE id = ?', (flow_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        columns = [description[0] for description in cursor.description]
        flow_data = dict(zip(columns, row))
        
        # Parse JSON data
        if flow_data.get('data'):
            flow_data['data'] = json.loads(flow_data['data'])
        
        conn.close()
        return flow_data
    
    def get_flow_variables(self, flow_id: int) -> Dict[str, Any]:
        """
        Lấy các biến của flow
        
        Args:
            flow_id: ID của flow
            
        Returns:
            Dictionary chứa các biến
        """
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT variable_name, variable_value 
            FROM variables 
            WHERE flow_id = ?
        ''', (flow_id,))
        
        rows = cursor.fetchall()
        variables = {}
        
        for name, value in rows:
            try:
                # Thử parse JSON trước
                variables[name] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Nếu không phải JSON, giữ nguyên string
                variables[name] = value
        
        conn.close()
        return variables
    
    def get_flow_http_traces(self, flow_id: int) -> List[Dict[str, Any]]:
        """
        Lấy HTTP traces của flow
        
        Args:
            flow_id: ID của flow
            
        Returns:
            List các HTTP traces
        """
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM http_traces 
            WHERE flow_id = ? 
            ORDER BY created_at
        ''', (flow_id,))
        
        columns = [description[0] for description in cursor.description]
        traces = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return traces
    
    def get_flows_by_name(self, flow_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Lấy danh sách flows theo tên
        
        Args:
            flow_name: Tên flow
            limit: Số lượng tối đa
            
        Returns:
            List các flows
        """
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM flows 
            WHERE flow_name = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (flow_name, limit))
        
        columns = [description[0] for description in cursor.description]
        flows = []
        
        for row in cursor.fetchall():
            flow_data = dict(zip(columns, row))
            if flow_data.get('data'):
                flow_data['data'] = json.loads(flow_data['data'])
            flows.append(flow_data)
        
        conn.close()
        return flows
    
    def delete_flow(self, flow_id: int):
        """
        Xóa flow và tất cả dữ liệu liên quan
        
        Args:
            flow_id: ID của flow
        """
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Xóa variables
        cursor.execute('DELETE FROM variables WHERE flow_id = ?', (flow_id,))
        
        # Xóa http_traces
        cursor.execute('DELETE FROM http_traces WHERE flow_id = ?', (flow_id,))
        
        # Xóa flow
        cursor.execute('DELETE FROM flows WHERE id = ?', (flow_id,))
        
        conn.commit()
        conn.close()
    
    def cleanup_old_data(self, days: int = 30):
        """
        Xóa dữ liệu cũ hơn N ngày
        
        Args:
            days: Số ngày
        """
        self._ensure_initialized()
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM flows 
            WHERE created_at < datetime('now', '-{} days')
        '''.format(days))
        
        conn.commit()
        conn.close()


# Tạo instance global (lazy initialization)
sqlite_plugin = None

def get_sqlite_plugin():
    """Lấy instance SQLite plugin với lazy initialization"""
    global sqlite_plugin
    if sqlite_plugin is None:
        sqlite_plugin = SQLitePlugin()
    return sqlite_plugin
