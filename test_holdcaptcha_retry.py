#!/usr/bin/env python3
"""
Test script cho Holdcaptcha Retry Logic
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowlite.plugins.captcha_wrapper import captcha_wrapper


def test_holdcaptcha_retry():
    """Test retry logic cho holdcaptcha"""
    
    print("=== Testing Holdcaptcha Retry Logic ===\n")
    
    # Test data
    auth = "S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5"
    site = "walmart"
    proxyregion = "us"
    region = "com"
    proxy = "http://user-spzg23evgb-sessionduration-5:jeug12+n8UOXa8eThw@us.decodo.com:10001"
    flow_id = 3  # Sử dụng flow_id khác để test
    
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
        print("   Generate failed, cannot test holdcaptcha retry")
        return
    
    pxhold_id = gen_result["pxhold_id"]
    data = gen_result["data"]
    
    # Test 2: Holdcaptcha với retry (sẽ thất bại vì data đã sử dụng)
    print("2. Testing holdcaptcha with retry (should fail)...")
    hold_result = captcha_wrapper.hold_captcha(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        data=data,  # Sử dụng data đã sử dụng
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
    else:
        print("   PXHold record was deleted (as expected)")
    print()
    
    # Test 4: Test generate_and_hold_captcha với retry
    print("4. Testing generate_and_hold_captcha with retry...")
    full_result = captcha_wrapper.generate_and_hold_captcha(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=flow_id,
        max_retries=3
    )
    
    print(f"   Full result: {full_result}")
    print()
    
    if full_result.get("success"):
        final_pxhold_id = full_result.get("pxhold_id")
        
        # Test 5: Kiểm tra pxhold record cuối cùng
        print("5. Checking final pxhold record...")
        final_pxhold = captcha_wrapper.get_pxhold_data(final_pxhold_id)
        if final_pxhold:
            print(f"   Final PXHold data:")
            print(f"   - ID: {final_pxhold['id']}")
            print(f"   - Cookie: {final_pxhold['cookie'][:100]}...")
            print(f"   - VID: {final_pxhold['vid']}")
            print(f"   - Error: {final_pxhold['error']}")
            print(f"   - Updated: {final_pxhold['updated_at']}")
        else:
            print("   No final pxhold record found")
    
    print("\n=== Test completed ===")


if __name__ == "__main__":
    test_holdcaptcha_retry()
