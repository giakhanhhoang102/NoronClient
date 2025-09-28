#!/usr/bin/env python3
"""
Test script để kiểm tra tích hợp Captcha plugin vào flow walmart.py
"""

import sys
import os
import json

# Thêm flowlite vào Python path
sys.path.insert(0, '/Users/daoduykhanh/Documents/Project/NORONCLIENT')

from flowlite import Flow, step, finalize, expect, http
from flowlite.plugins import CurlDump, MaskCookies, ParseBetweenStrings, SQLiteWrapper, CaptchaWrapper

def test_walmart_flow():
    """Test flow walmart với Captcha plugin"""
    
    # Tạo flow test
    flow = Flow("walmart_test").debug(trace=True)
    flow.use(MaskCookies)
    flow.use(ParseBetweenStrings)
    flow.use(SQLiteWrapper)
    flow.use(CaptchaWrapper)
    
    @step("init_input")
    def init_input(ctx):
        """Khởi tạo các biến input từ request"""
        ctx.CCNUM = ctx.data.get("CCNUM", "")
        ctx.MM = ctx.data.get("MM", "")
        ctx.YYYY = ctx.data.get("YYYY", "")
        ctx.CCV = ctx.data.get("CCV", "")
        
        expect.truthy(ctx.CCNUM, "CCNUM is required")
        expect.truthy(ctx.MM, "MM is required")
        expect.truthy(ctx.YYYY, "YYYY is required")
        expect.truthy(ctx.CCV, "CCV is required")

    @step("test_captcha_plugin")
    def test_captcha_plugin(ctx):
        """Test Captcha plugin integration"""
        # Lấy proxy từ session
        session_proxy = ctx.session.get("proxy", "")
        ctx.session_proxy = session_proxy
        print(f"DEBUG - Using proxy from session: {session_proxy}")
        
        # Chuẩn bị tham số cho Captcha plugin
        captcha_params = {
            "auth": "S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5",
            "site": "walmart",
            "proxyregion": "us",
            "region": "com",
            "proxy": session_proxy
        }
        
        print(f"DEBUG - Calling captcha plugin with params: {captcha_params}")
        
        # Gọi Captcha plugin
        result = ctx.vars.captcha.generate_and_hold_captcha(
            flow_id=ctx.uuid,
            **captcha_params
        )
        
        print(f"DEBUG - Captcha plugin result: {result}")
        
        if result.get("success"):
            # Cập nhật các giá trị từ kết quả plugin
            ctx.Ua = result.get("UserAgent", "")
            ctx.sechua = result.get("secHeader", "")
            ctx.pxhd = result.get("pxhd", "")
            ctx.paradata = result.get("data", "")
            
            # Lưu response đầy đủ
            ctx.holdcaptcha_response = {
                "error": False,
                "cookie": result.get("cookie", ""),
                "vid": result.get("vid", ""),
                "cts": result.get("cts", ""),
                "secHeader": result.get("secHeader", ""),
                "isMaybeFlagged": result.get("isMaybeFlagged", False),
                "UserAgent": result.get("UserAgent", ""),
                "flaggedPOW": result.get("flaggedPOW", False),
                "data": result.get("data", "")
            }
            
            print(f"DEBUG - Updated Ua: {ctx.Ua}")
            print(f"DEBUG - Updated sechua: {ctx.sechua}")
            print(f"DEBUG - Updated pxhd: {ctx.pxhd}")
            print(f"DEBUG - Updated paradata: {ctx.paradata}")
            
        else:
            # Xử lý lỗi
            error_msg = result.get("error", "Unknown captcha error")
            print(f"DEBUG - Captcha plugin failed: {error_msg}")
            ctx.status = "BAN"
            raise AssertionError(f"BAN: Captcha plugin failed: {error_msg}")

    @finalize
    def done(ctx):
        """Kết thúc flow và trả về kết quả"""
        return {
            "status": ctx.get("status", "UNKNOWN"),
            "uuid": ctx.get("uuid"),
            "CCNUM": ctx.CCNUM,
            "MM": ctx.MM,
            "YYYY": ctx.YYYY,
            "CCV": ctx.CCV,
            "Ua": ctx.get("Ua"),
            "sechua": ctx.get("sechua"),
            "pxhd": ctx.get("pxhd"),
            "paradata": ctx.get("paradata"),
            "session_proxy": ctx.get("session_proxy"),
            "holdcaptcha_response": ctx.get("holdcaptcha_response"),
            "captcha_plugin_used": True,
        }
    
    # Đăng ký flow
    flow.register(globals())
    
    # Test data
    test_data = {
        "CCNUM": "4111111111111111",
        "MM": "12", 
        "YYYY": "2025",
        "CCV": "123"
    }
    
    test_session = {
        "profile": "chrome_133",
        "proxy": "http://user-spzg23evgb-sessionduration-5:jeug12+n8UOXa8eThw@us.decodo.com:10001"
    }
    
    print("=== Testing Walmart Flow with Captcha Plugin Integration ===")
    print(f"Test data: {test_data}")
    print(f"Test session: {test_session}")
    print()
    
    try:
        # Chạy flow
        result = flow.run(data=test_data, session=test_session)
        
        print("=== Flow Result ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # Kiểm tra kết quả
        if result.get("success"):
            print("\n✅ Flow completed successfully!")
            if result.get("result", {}).get("captcha_plugin_used"):
                print("✅ Captcha plugin was used successfully!")
            else:
                print("❌ Captcha plugin was not used")
        else:
            print(f"\n❌ Flow failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_walmart_flow()
