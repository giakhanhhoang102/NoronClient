#!/usr/bin/env python3
"""
Test đơn giản để kiểm tra Captcha plugin
"""

import sys
import os
import json

# Thêm flowlite vào Python path
sys.path.insert(0, '/Users/daoduykhanh/Documents/Project/NORONCLIENT')

from flowlite.plugins import SQLiteWrapper, CaptchaWrapper

def test_captcha_plugin_directly():
    """Test trực tiếp Captcha plugin"""
    
    print("=== Testing Captcha Plugin Directly ===")
    
    # Tạo instance của plugins
    sqlite_wrapper = SQLiteWrapper()
    captcha_wrapper = CaptchaWrapper()
    
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
    
    # Tạo context giả
    class MockContext:
        def __init__(self):
            self.uuid = "test-uuid-123"
            self.data = test_data
            self.session = test_session
            self.vars = type('Vars', (), {})()
            self.vars.captcha = captcha_wrapper
            self.vars.sqlite = sqlite_wrapper
    
    ctx = MockContext()
    
    print(f"Test data: {test_data}")
    print(f"Test session: {test_session}")
    print(f"Flow ID: {ctx.uuid}")
    print()
    
    try:
        # Test Captcha plugin
        print("Calling captcha.generate_and_hold_captcha...")
        
        result = ctx.vars.captcha.generate_and_hold_captcha(
            flow_id=ctx.uuid,
            auth="S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5",
            site="walmart",
            proxyregion="us",
            region="com",
            proxy=test_session["proxy"]
        )
        
        print("=== Captcha Plugin Result ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        # Kiểm tra kết quả
        if result.get("success"):
            print("\n✅ Captcha plugin completed successfully!")
            print(f"✅ Cookie: {result.get('cookie', '')[:50]}...")
            print(f"✅ UserAgent: {result.get('UserAgent', '')}")
            print(f"✅ Data: {result.get('data', '')[:50]}...")
        else:
            print(f"\n❌ Captcha plugin failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_captcha_plugin_directly()
