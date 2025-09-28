#!/usr/bin/env python3
"""
Test script cho Holdcaptcha functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowlite.plugins.captcha_wrapper import captcha_wrapper


def test_holdcaptcha():
    """Test chức năng generate_and_hold_captcha"""
    
    print("=== Testing Holdcaptcha Functionality ===\n")
    
    # Test data
    auth = "S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5"
    site = "walmart"
    proxyregion = "us"
    region = "com"
    proxy = "http://user-spzg23evgb-sessionduration-5:jeug12+n8UOXa8eThw@us.decodo.com:10001"
    flow_id = 2  # Sử dụng flow_id khác để test
    
    print(f"Test parameters:")
    print(f"  Auth: {auth}")
    print(f"  Site: {site}")
    print(f"  Proxy Region: {proxyregion}")
    print(f"  Region: {region}")
    print(f"  Proxy: {proxy}")
    print(f"  Flow ID: {flow_id}")
    print()
    
    # Test generate_and_hold_captcha
    print("1. Testing generate_and_hold_captcha...")
    result = captcha_wrapper.generate_and_hold_captcha(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=flow_id,
        max_retries=3
    )
    
    print(f"   Result: {result}")
    print()
    
    if result.get("success"):
        pxhold_id = result.get("pxhold_id")
        
        # 2. Test get updated pxhold data
        print("2. Testing get updated pxhold data...")
        pxhold_data = captcha_wrapper.get_pxhold_data(pxhold_id)
        if pxhold_data:
            print(f"   Updated PXHold data:")
            print(f"   - Cookie: {pxhold_data['cookie'][:100]}...")
            print(f"   - VID: {pxhold_data['vid']}")
            print(f"   - CTS: {pxhold_data['cts']}")
            print(f"   - UserAgent: {pxhold_data['UserAgent']}")
            print(f"   - Error: {pxhold_data['error']}")
            print(f"   - Updated: {pxhold_data['updated_at']}")
        print()
        
        # 3. Test get successful pxhold
        print("3. Testing get successful pxhold...")
        successful_pxhold = captcha_wrapper.get_successful_pxhold(flow_id)
        if successful_pxhold:
            print(f"   Successful pxhold found:")
            print(f"   - ID: {successful_pxhold['id']}")
            print(f"   - Cookie: {successful_pxhold['cookie'][:100]}...")
            print(f"   - VID: {successful_pxhold['vid']}")
            print(f"   - CTS: {successful_pxhold['cts']}")
        else:
            print("   No successful pxhold found")
        print()
    
    # 4. Test individual hold_captcha (nếu có data từ generate)
    print("4. Testing individual hold_captcha...")
    if result.get("success") and result.get("data"):
        hold_result = captcha_wrapper.hold_captcha(
            auth=auth,
            site=site,
            proxyregion=proxyregion,
            region=region,
            proxy=proxy,
            data=result["data"],
            pxhold_id=pxhold_id
        )
        print(f"   Holdcaptcha result: {hold_result}")
    else:
        print("   Skipping individual hold_captcha test (no data available)")
    
    print("\n=== Test completed ===")


if __name__ == "__main__":
    test_holdcaptcha()
