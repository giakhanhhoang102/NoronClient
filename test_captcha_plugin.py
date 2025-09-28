#!/usr/bin/env python3
"""
Test script cho Captcha plugin
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowlite.plugins.captcha_wrapper import captcha_wrapper


def test_captcha_plugin():
    """Test các chức năng của Captcha plugin"""
    
    print("=== Testing Captcha Plugin ===\n")
    
    # Test data
    auth = "S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5"
    site = "walmart"
    proxyregion = "us"
    region = "com"
    proxy = "http://user-spzg23evgb-sessionduration-5:jeug12+n8UOXa8eThw@us.decodo.com:10001"
    flow_id = 1  # Giả sử có flow_id = 1
    
    print(f"Test parameters:")
    print(f"  Auth: {auth}")
    print(f"  Site: {site}")
    print(f"  Proxy Region: {proxyregion}")
    print(f"  Region: {region}")
    print(f"  Proxy: {proxy}")
    print(f"  Flow ID: {flow_id}")
    print()
    
    # 1. Test generate cookies
    print("1. Testing generate cookies...")
    result = captcha_wrapper.generate_cookies(
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
        
        # 2. Test get pxhold data
        print("2. Testing get pxhold data...")
        pxhold_data = captcha_wrapper.get_pxhold_data(pxhold_id)
        print(f"   PXHold data: {pxhold_data}")
        print()
        
        # 3. Test get pxhold by flow
        print("3. Testing get pxhold by flow...")
        flow_pxhold = captcha_wrapper.get_pxhold_by_flow(flow_id)
        print(f"   Found {len(flow_pxhold)} pxhold records for flow {flow_id}")
        for record in flow_pxhold:
            print(f"   - ID: {record['id']}, Error: {record['error']}, Created: {record['created_at']}")
        print()
        
        # 4. Test get successful pxhold
        print("4. Testing get successful pxhold...")
        successful_pxhold = captcha_wrapper.get_successful_pxhold(flow_id)
        if successful_pxhold:
            print(f"   Successful pxhold: {successful_pxhold}")
        else:
            print("   No successful pxhold found")
        print()
    
    # 5. Test cleanup
    print("5. Testing cleanup...")
    captcha_wrapper.cleanup_failed_pxhold(days=1)
    print("   Cleanup completed")
    
    print("\n=== Test completed ===")


if __name__ == "__main__":
    test_captcha_plugin()
