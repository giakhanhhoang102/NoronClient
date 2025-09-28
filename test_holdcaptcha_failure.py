#!/usr/bin/env python3
"""
Test script cho Holdcaptcha Failure và Delete Record
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowlite.plugins.captcha_wrapper import captcha_wrapper


def test_holdcaptcha_failure():
    """Test trường hợp holdcaptcha thất bại và xóa record"""
    
    print("=== Testing Holdcaptcha Failure and Delete Record ===\n")
    
    # Test data
    auth = "S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5"
    site = "walmart"
    proxyregion = "us"
    region = "com"
    proxy = "http://user-spzg23evgb-sessionduration-5:jeug12+n8UOXa8eThw@us.decodo.com:10001"
    flow_id = 4  # Sử dụng flow_id khác để test
    
    print(f"Test parameters:")
    print(f"  Auth: {auth}")
    print(f"  Site: {site}")
    print(f"  Proxy Region: {proxyregion}")
    print(f"  Region: {region}")
    print(f"  Proxy: {proxy}")
    print(f"  Flow ID: {flow_id}")
    print()
    
    # Test 1: Generate cookies trước
    print("1. Testing generate cookies...")
    gen_result = captcha_wrapper.generate_cookies(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=flow_id,
        max_retries=3
    )
    
    print(f"   Generate result: {gen_result}")
    print()
    
    if not gen_result["success"]:
        print("   Generate failed, cannot test holdcaptcha failure")
        return
    
    pxhold_id = gen_result["pxhold_id"]
    data = gen_result["data"]
    
    # Test 2: Holdcaptcha với data đã sử dụng nhiều lần (sẽ thất bại)
    print("2. Testing holdcaptcha with used data (should fail and delete record)...")
    
    # Sử dụng data đã sử dụng nhiều lần để force failure
    hold_result = captcha_wrapper.hold_captcha(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        data=data,  # Data đã sử dụng
        pxhold_id=pxhold_id,
        max_retries=2  # Retry 2 lần
    )
    
    print(f"   Holdcaptcha result: {hold_result}")
    print()
    
    # Test 3: Kiểm tra pxhold record có bị xóa không
    print("3. Checking if pxhold record was deleted...")
    pxhold_data = captcha_wrapper.get_pxhold_data(pxhold_id)
    if pxhold_data:
        print(f"   PXHold record still exists: {pxhold_data}")
        print("   ERROR: Record should have been deleted!")
    else:
        print("   ✅ PXHold record was deleted (as expected)")
    print()
    
    # Test 4: Test với auth key sai để force failure
    print("4. Testing with wrong auth key to force failure...")
    
    # Generate cookies với auth key đúng
    gen_result2 = captcha_wrapper.generate_cookies(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=flow_id,
        max_retries=1
    )
    
    if gen_result2["success"]:
        pxhold_id2 = gen_result2["pxhold_id"]
        data2 = gen_result2["data"]
        
        # Holdcaptcha với auth key sai
        hold_result2 = captcha_wrapper.hold_captcha(
            auth="WRONG_AUTH_KEY",  # Auth key sai
            site=site,
            proxyregion=proxyregion,
            region=region,
            proxy=proxy,
            data=data2,
            pxhold_id=pxhold_id2,
            max_retries=2
        )
        
        print(f"   Holdcaptcha with wrong auth result: {hold_result2}")
        
        # Kiểm tra record có bị xóa không
        pxhold_data2 = captcha_wrapper.get_pxhold_data(pxhold_id2)
        if pxhold_data2:
            print(f"   PXHold record still exists: {pxhold_data2}")
            print("   ERROR: Record should have been deleted!")
        else:
            print("   ✅ PXHold record was deleted (as expected)")
    
    print("\n=== Test completed ===")


if __name__ == "__main__":
    test_holdcaptcha_failure()
