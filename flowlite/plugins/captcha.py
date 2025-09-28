"""
Captcha Plugin for FlowLite
Xử lý captcha và generate cookies từ Parallax API
"""

import json
import time
import sqlite3
from typing import Dict, Any, Optional, Tuple
from .sqlite import get_sqlite_plugin


class CaptchaPlugin:
    def __init__(self):
        """Khởi tạo Captcha plugin"""
        self._sqlite = None
        self._initialized = False
    
    @property
    def sqlite(self):
        """Lazy load SQLite plugin"""
        if self._sqlite is None:
            self._sqlite = get_sqlite_plugin()
        return self._sqlite
    
    def _ensure_initialized(self):
        """Đảm bảo captcha tables đã được khởi tạo"""
        if not self._initialized:
            self.init_captcha_tables()
            self._initialized = True
    
    def init_captcha_tables(self):
        """Khởi tạo bảng pxhold cho captcha data"""
        # Không gọi _ensure_initialized() ở đây để tránh recursion
        conn = sqlite3.connect(self.sqlite.db_path)
        cursor = conn.cursor()
        
        # Tạo bảng pxhold để lưu captcha data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pxhold (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flow_id INTEGER,
                auth TEXT NOT NULL,
                site TEXT NOT NULL,
                proxyregion TEXT NOT NULL,
                region TEXT NOT NULL,
                proxy TEXT NOT NULL,
                cookie TEXT,
                vid TEXT,
                cts TEXT,
                isFlagged BOOLEAN DEFAULT 0,
                isMaybeFlagged BOOLEAN DEFAULT 0,
                UserAgent TEXT,
                data TEXT,
                pxhd TEXT,
                sechua TEXT,
                error BOOLEAN DEFAULT 0,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (flow_id) REFERENCES flows (id)
            )
        ''')
        
        # Thêm cột pxhd và sechua nếu chưa có (cho database cũ)
        try:
            cursor.execute('ALTER TABLE pxhold ADD COLUMN pxhd TEXT')
        except sqlite3.OperationalError:
            pass  # Cột đã tồn tại
        
        try:
            cursor.execute('ALTER TABLE pxhold ADD COLUMN sechua TEXT')
        except sqlite3.OperationalError:
            pass  # Cột đã tồn tại
        
        conn.commit()
        conn.close()
    
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
        self._ensure_initialized()
        
        import requests
        
        url = "https://api.parallaxsystems.io/gen"
        
        payload = {
            "auth": auth,
            "site": site,
            "proxyregion": proxyregion,
            "region": region,
            "proxy": proxy
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        for attempt in range(max_retries):
            try:
                # print(f"DEBUG - Captcha attempt {attempt + 1}/{max_retries}")
                # print(f"DEBUG - Payload: {payload}")
                
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                # print(f"DEBUG - API Response: {result}")
                
                # Debug: kiểm tra dữ liệu trước khi lưu
                # print(f"DEBUG - pxhd from API: {result.get('pxhd')}")
                # print(f"DEBUG - secHeader from API: {result.get('secHeader')}")
                
                # Lưu vào database
                pxhold_id = self.save_pxhold_data(
                    flow_id=flow_id,
                    auth=auth,
                    site=site,
                    proxyregion=proxyregion,
                    region=region,
                    proxy=proxy,
                    result=result,
                    retry_count=attempt
                )
                
                if not result.get("error", True):
                    # Thành công
                    # print(f"DEBUG - Cookies generated successfully on attempt {attempt + 1}")
                    return {
                        "success": True,
                        "pxhold_id": pxhold_id,
                        "cookie": result.get("cookie"),
                        "vid": result.get("vid"),
                        "cts": result.get("cts"),
                        "isFlagged": result.get("isFlagged", False),
                        "isMaybeFlagged": result.get("isMaybeFlagged", False),
                        "UserAgent": result.get("UserAgent"),
                        "data": result.get("data"),
                        "pxhd": result.get("pxhd"),
                        "sechua": result.get("secHeader"),
                        "attempt": attempt + 1
                    }
                else:
                    # Lỗi, thử lại
                    error_msg = result.get("cookie", "Unknown error")
                    # print(f"DEBUG - Error on attempt {attempt + 1}: {error_msg}")
                    
                    if attempt < max_retries - 1:
                        # Chờ một chút trước khi retry
                        time.sleep(2)
                    else:
                        # Hết lần retry
                        return {
                            "success": False,
                            "pxhold_id": pxhold_id,
                            "error": error_msg,
                            "attempts": max_retries
                        }
                        
            except requests.exceptions.RequestException as e:
                # print(f"DEBUG - Request error on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return {
                        "success": False,
                        "error": f"Request failed after {max_retries} attempts: {str(e)}",
                        "attempts": max_retries
                    }
            except Exception as e:
                # print(f"DEBUG - Unexpected error on attempt {attempt + 1}: {e}")
                
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return {
                        "success": False,
                        "error": f"Unexpected error after {max_retries} attempts: {str(e)}",
                        "attempts": max_retries
                    }
        
        return {
            "success": False,
            "error": "Max retries exceeded",
            "attempts": max_retries
        }
    
    def save_pxhold_data(self, flow_id: int, auth: str, site: str, 
                        proxyregion: str, region: str, proxy: str, 
                        result: Dict[str, Any], retry_count: int) -> int:
        """
        Lưu dữ liệu pxhold vào database
        
        Args:
            flow_id: ID của flow
            auth: Auth key
            site: Site name
            proxyregion: Proxy region
            region: Region
            proxy: Proxy URL
            result: API response result
            retry_count: Số lần retry
            
        Returns:
            ID của record vừa tạo
        """
        conn = sqlite3.connect(self.sqlite.db_path)
        cursor = conn.cursor()
        
        error = result.get("error", True)
        error_message = result.get("cookie", "") if error else None
        
        # Debug: kiểm tra dữ liệu trước khi lưu vào database
        # print(f"DEBUG - Saving pxhd: {result.get('pxhd')}")
        # print(f"DEBUG - Saving sechua (secHeader): {result.get('secHeader')}")
        
        cursor.execute('''
            INSERT INTO pxhold (
                flow_id, auth, site, proxyregion, region, proxy,
                cookie, vid, cts, isFlagged, isMaybeFlagged, UserAgent, data,
                pxhd, sechua, error, error_message, retry_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            flow_id, auth, site, proxyregion, region, proxy,
            result.get("cookie"), result.get("vid"), result.get("cts"),
            result.get("isFlagged", False), result.get("isMaybeFlagged", False),
            result.get("UserAgent"), result.get("data"),
            result.get("pxhd"), result.get("secHeader"),
            error, error_message, retry_count
        ))
        
        pxhold_id = cursor.lastrowid
        conn.commit()
        
        # Debug: kiểm tra dữ liệu đã lưu
        cursor.execute('SELECT pxhd, sechua FROM pxhold WHERE id = ?', (pxhold_id,))
        saved_data = cursor.fetchone()
        # print(f"DEBUG - Saved pxhd: {saved_data[0] if saved_data else 'None'}")
        # print(f"DEBUG - Saved sechua: {saved_data[1] if saved_data else 'None'}")
        
        conn.close()
        
        return pxhold_id
    
    def get_pxhold_data(self, pxhold_id: int) -> Optional[Dict[str, Any]]:
        """
        Lấy dữ liệu pxhold theo ID
        
        Args:
            pxhold_id: ID của pxhold record
            
        Returns:
            Dictionary chứa dữ liệu pxhold
        """
        conn = sqlite3.connect(self.sqlite.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM pxhold WHERE id = ?', (pxhold_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        columns = [description[0] for description in cursor.description]
        pxhold_data = dict(zip(columns, row))
        
        conn.close()
        return pxhold_data
    
    def get_pxhold_by_flow(self, flow_id: int) -> list:
        """
        Lấy tất cả pxhold data của một flow
        
        Args:
            flow_id: ID của flow
            
        Returns:
            List các pxhold records
        """
        conn = sqlite3.connect(self.sqlite.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM pxhold 
            WHERE flow_id = ? 
            ORDER BY created_at DESC
        ''', (flow_id,))
        
        columns = [description[0] for description in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return records
    
    def get_successful_pxhold(self, flow_id: int = None) -> Optional[Dict[str, Any]]:
        """
        Lấy pxhold data thành công gần nhất (random nếu không có flow_id)
        
        Args:
            flow_id: ID của flow (optional)
            
        Returns:
            Dictionary chứa pxhold data thành công
        """
        conn = sqlite3.connect(self.sqlite.db_path)
        cursor = conn.cursor()
        
        if flow_id:
            # Lấy theo flow_id cụ thể
            cursor.execute('''
                SELECT * FROM pxhold 
                WHERE flow_id = ? AND error = 0 
                ORDER BY created_at DESC 
                LIMIT 1
            ''', (flow_id,))
        else:
            # Lấy random 1 record thành công bất kỳ
            cursor.execute('''
                SELECT * FROM pxhold 
                WHERE error = 0 
                ORDER BY RANDOM() 
                LIMIT 1
            ''')
        
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        columns = [description[0] for description in cursor.description]
        pxhold_data = dict(zip(columns, row))
        
        conn.close()
        return pxhold_data
    
    def hold_captcha(self, auth: str, site: str, proxyregion: str, 
                    region: str, proxy: str, data: str, pxhold_id: int = None, 
                    max_retries: int = 2) -> Dict[str, Any]:
        """
        Gọi API holdcaptcha sau khi generate cookies thành công
        
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
        import requests
        
        url = "https://api.parallaxsystems.io/holdcaptcha"
        
        payload = {
            "auth": auth,
            "site": site,
            "proxyregion": proxyregion,
            "region": region,
            "proxy": proxy,
            "data": data
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        for attempt in range(max_retries + 1):
            try:
                # print(f"DEBUG - Holdcaptcha attempt {attempt + 1}/{max_retries + 1}")
                # print(f"DEBUG - Payload: {payload}")
                
                response = requests.post(url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                # print(f"DEBUG - Holdcaptcha API Response: {result}")
                
                if not result.get("error", True):
                    # Thành công, cập nhật pxhold record
                    if pxhold_id:
                        self.update_pxhold_with_holdcaptcha(pxhold_id, result)
                    
                    return {
                        "success": True,
                        "pxhold_id": pxhold_id,
                        "cookie": result.get("cookie"),
                        "vid": result.get("vid"),
                        "cts": result.get("cts"),
                        "secHeader": result.get("secHeader"),
                        "isMaybeFlagged": result.get("isMaybeFlagged", False),
                        "UserAgent": result.get("UserAgent"),
                        "flaggedPOW": result.get("flaggedPOW", False),
                        "data": result.get("data"),
                        "attempt": attempt + 1
                    }
                else:
                    # Lỗi, thử lại nếu chưa hết số lần retry
                    error_msg = result.get("cookie", "Unknown error")
                    # print(f"DEBUG - Holdcaptcha error on attempt {attempt + 1}: {error_msg}")
                    
                    if attempt < max_retries:
                        # print(f"DEBUG - Retrying holdcaptcha...")
                        continue
                    else:
                        # Hết số lần retry, xóa pxhold record và trả về lỗi
                        if pxhold_id:
                            self.delete_pxhold_record(pxhold_id)
                            # print(f"DEBUG - Deleted pxhold record {pxhold_id} due to holdcaptcha failure")
                        
                        return {
                            "success": False,
                            "pxhold_id": pxhold_id,
                            "error": f"Holdcaptcha failed after {max_retries + 1} attempts: {error_msg}",
                            "attempts": attempt + 1
                        }
                    
            except requests.exceptions.RequestException as e:
                # print(f"DEBUG - Holdcaptcha request error on attempt {attempt + 1}: {e}")
                if attempt < max_retries:
                    # print(f"DEBUG - Retrying holdcaptcha...")
                    continue
                else:
                    # Hết số lần retry, xóa pxhold record và trả về lỗi
                    if pxhold_id:
                        self.delete_pxhold_record(pxhold_id)
                        # print(f"DEBUG - Deleted pxhold record {pxhold_id} due to holdcaptcha failure")
                    
                    return {
                        "success": False,
                        "pxhold_id": pxhold_id,
                        "error": f"Request failed after {max_retries + 1} attempts: {str(e)}",
                        "attempts": attempt + 1
                    }
            except Exception as e:
                # print(f"DEBUG - Holdcaptcha unexpected error on attempt {attempt + 1}: {e}")
                if attempt < max_retries:
                    # print(f"DEBUG - Retrying holdcaptcha...")
                    continue
                else:
                    # Hết số lần retry, xóa pxhold record và trả về lỗi
                    if pxhold_id:
                        self.delete_pxhold_record(pxhold_id)
                        # print(f"DEBUG - Deleted pxhold record {pxhold_id} due to holdcaptcha failure")
                    
                    return {
                        "success": False,
                        "pxhold_id": pxhold_id,
                        "error": f"Unexpected error after {max_retries + 1} attempts: {str(e)}",
                        "attempts": attempt + 1
                    }
        
        # Fallback (không bao giờ đến đây)
        return {
            "success": False,
            "pxhold_id": pxhold_id,
            "error": "Unexpected fallback",
            "attempts": max_retries + 1
        }
    
    def update_pxhold_with_holdcaptcha(self, pxhold_id: int, holdcaptcha_result: Dict[str, Any]):
        """
        Cập nhật pxhold record với kết quả từ holdcaptcha
        
        Args:
            pxhold_id: ID của pxhold record
            holdcaptcha_result: Kết quả từ holdcaptcha API
        """
        conn = sqlite3.connect(self.sqlite.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE pxhold SET
                cookie = ?,
                vid = ?,
                cts = ?,
                isFlagged = ?,
                isMaybeFlagged = ?,
                UserAgent = ?,
                data = ?,
                error = ?,
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            holdcaptcha_result.get("cookie"),
            holdcaptcha_result.get("vid"),
            holdcaptcha_result.get("cts"),
            holdcaptcha_result.get("isFlagged", False),
            holdcaptcha_result.get("isMaybeFlagged", False),
            holdcaptcha_result.get("UserAgent"),
            holdcaptcha_result.get("data"),
            holdcaptcha_result.get("error", False),
            holdcaptcha_result.get("cookie") if holdcaptcha_result.get("error", False) else None,
            pxhold_id
        ))
        
        conn.commit()
        conn.close()
    
    def delete_pxhold_record(self, pxhold_id: int):
        """
        Xóa pxhold record theo ID
        
        Args:
            pxhold_id: ID của pxhold record cần xóa
        """
        conn = sqlite3.connect(self.sqlite.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM pxhold WHERE id = ?', (pxhold_id,))
        
        conn.commit()
        conn.close()
        # print(f"DEBUG - Deleted pxhold record {pxhold_id}")
    
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
        self._ensure_initialized()
        
        # Bước 0: Kiểm tra database trước
        # print(f"DEBUG - Step 0: Checking existing data in database for flow_id: {flow_id}")
        existing_pxhold = self.get_successful_pxhold(flow_id)
        
        if existing_pxhold and existing_pxhold.get("data"):
            # print("DEBUG - Found existing pxhold data, skipping generation...")
            # print(f"DEBUG - Existing pxhold ID: {existing_pxhold['id']}")
            # print(f"DEBUG - Existing data: {existing_pxhold['data'][:100]}...")
            
            # Sử dụng dữ liệu có sẵn để gọi holdcaptcha
            # print("DEBUG - Step 1: Using existing data for holdcaptcha...")
            hold_result = self.hold_captcha(
                auth=auth,
                site=site,
                proxyregion=proxyregion,
                region=region,
                proxy=proxy,
                data=existing_pxhold["data"],
                pxhold_id=existing_pxhold["id"],
                max_retries=2  # Retry 2 lần cho holdcaptcha
            )
            
            if hold_result["success"]:
                # Kết hợp kết quả từ existing data
                return {
                    "success": True,
                    "pxhold_id": existing_pxhold["id"],
                    "cookie": hold_result["cookie"],
                    "vid": hold_result["vid"],
                    "cts": hold_result["cts"],
                    "secHeader": hold_result.get("secHeader"),
                    "isFlagged": existing_pxhold.get("isFlagged", False),
                    "isMaybeFlagged": hold_result.get("isMaybeFlagged", False),
                    "UserAgent": hold_result["UserAgent"],
                    "flaggedPOW": hold_result.get("flaggedPOW", False),
                    "data": hold_result["data"],
                    "pxhd": existing_pxhold.get("pxhd"),
                    "sechua": existing_pxhold.get("sechua"),
                    "from_existing": True,
                    "generation_attempt": 0
                }
            else:
                # Holdcaptcha thất bại với existing data, xóa record cũ và generate mới
                # print("DEBUG - Holdcaptcha failed with existing data, deleting old record and generating new...")
                self.delete_pxhold_record(existing_pxhold["id"])
                
                # Fallback to normal generation
                return self._generate_and_hold_captcha_fallback(auth, site, proxyregion, region, proxy, flow_id, max_retries)
        else:
            # print("DEBUG - No existing data found, proceeding with generation...")
            return self._generate_and_hold_captcha_fallback(auth, site, proxyregion, region, proxy, flow_id, max_retries)
    
    def _generate_and_hold_captcha_fallback(self, auth: str, site: str, proxyregion: str, 
                                           region: str, proxy: str, flow_id: int = None, 
                                           max_retries: int = 3) -> Dict[str, Any]:
        """
        Fallback method để generate cookies và gọi holdcaptcha khi không có dữ liệu existing
        """
        # Bước 1: Generate cookies
        # print("DEBUG - Step 1: Generating cookies...")
        gen_result = self.generate_cookies(
            auth=auth,
            site=site,
            proxyregion=proxyregion,
            region=region,
            proxy=proxy,
            flow_id=flow_id,
            max_retries=max_retries
        )
        
        if not gen_result["success"]:
            return gen_result
        
        # Bước 2: Gọi holdcaptcha với data từ generate (với retry)
        # print("DEBUG - Step 2: Calling holdcaptcha...")
        hold_result = self.hold_captcha(
            auth=auth,
            site=site,
            proxyregion=proxyregion,
            region=region,
            proxy=proxy,
            data=gen_result["data"],
            pxhold_id=gen_result["pxhold_id"],
            max_retries=2  # Retry 2 lần cho holdcaptcha
        )
        
        if hold_result["success"]:
            # Kết hợp kết quả
            return {
                "success": True,
                "pxhold_id": gen_result["pxhold_id"],
                "cookie": hold_result["cookie"],
                "vid": hold_result["vid"],
                "cts": hold_result["cts"],
                "secHeader": hold_result.get("secHeader"),
                "isFlagged": gen_result.get("isFlagged", False),
                "isMaybeFlagged": hold_result.get("isMaybeFlagged", False),
                "UserAgent": hold_result["UserAgent"],
                "flaggedPOW": hold_result.get("flaggedPOW", False),
                "data": hold_result["data"],
                "pxhd": gen_result.get("pxhd"),
                "sechua": gen_result.get("sechua"),
                "from_existing": False,
                "generation_attempt": gen_result["attempt"]
            }
        else:
            # Holdcaptcha thất bại, trả về kết quả generate
            return {
                "success": False,
                "pxhold_id": gen_result["pxhold_id"],
                "generation_success": True,
                "holdcaptcha_error": hold_result["error"],
                "fallback_data": gen_result
            }
    
    def cleanup_failed_pxhold(self, days: int = 7):
        """
        Dọn dẹp các pxhold records thất bại cũ
        
        Args:
            days: Số ngày
        """
        conn = sqlite3.connect(self.sqlite.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM pxhold 
            WHERE error = 1 AND created_at < datetime('now', '-{} days')
        '''.format(days))
        
        conn.commit()
        conn.close()


# Tạo instance global (lazy initialization)
captcha_plugin = None

def get_captcha_plugin():
    """Lấy instance Captcha plugin với lazy initialization"""
    global captcha_plugin
    if captcha_plugin is None:
        captcha_plugin = CaptchaPlugin()
    return captcha_plugin
