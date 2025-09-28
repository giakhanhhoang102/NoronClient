#!/usr/bin/env python3
"""
Test script cho Database Check trước khi gọi API gen
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowlite.plugins.captcha_wrapper import captcha_wrapper


def test_database_check():
    """Test kiểm tra database trước khi gọi API gen"""
    
    print("=== Testing Database Check Before API Gen ===\n")
    
    # Test data
    auth = "S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5"
    site = "walmart"
    proxyregion = "us"
    region = "com"
    proxy = "http://user-spzg23evgb-sessionduration-5:jeug12+n8UOXa8eThw@us.decodo.com:10001"
    flow_id = 5  # Sử dụng flow_id khác để test
    
    print(f"Test parameters:")
    print(f"  Auth: {auth}")
    print(f"  Site: {site}")
    print(f"  Proxy Region: {proxyregion}")
    print(f"  Region: {region}")
    print(f"  Proxy: {proxy}")
    print(f"  Flow ID: {flow_id}")
    print()
    
    # Test 1: Lần đầu tiên (không có data trong database)
    print("1. First call - No existing data in database...")
    result1 = captcha_wrapper.generate_and_hold_captcha(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=flow_id,
        max_retries=3
    )
    
    print(f"   Result 1: {result1}")
    print(f"   From existing: {result1.get('from_existing', False)}")
    print()
    
    # Test 2: Lần thứ hai (có data trong database)
    print("2. Second call - Should use existing data...")
    result2 = captcha_wrapper.generate_and_hold_captcha(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=flow_id,
        max_retries=3
    )
    
    print(f"   Result 2: {result2}")
    print(f"   From existing: {result2.get('from_existing', False)}")
    print()
    
    # Test 3: Lần thứ ba (có data trong database)
    print("3. Third call - Should use existing data again...")
    result3 = captcha_wrapper.generate_and_hold_captcha(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=flow_id,
        max_retries=3
    )
    
    print(f"   Result 3: {result3}")
    print(f"   From existing: {result3.get('from_existing', False)}")
    print()
    
    # Test 4: Kiểm tra với flow_id khác (không có data)
    print("4. Different flow_id - Should generate new data...")
    result4 = captcha_wrapper.generate_and_hold_captcha(
        auth=auth,
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=6,  # Flow ID khác
        max_retries=3
    )
    
    print(f"   Result 4: {result4}")
    print(f"   From existing: {result4.get('from_existing', False)}")
    print()
    
    # Test 5: Test với auth key sai để force failure và xóa data
    print("5. Wrong auth key - Should delete existing data and generate new...")
    result5 = captcha_wrapper.generate_and_hold_captcha(
        auth="WRONG_AUTH_KEY",  # Auth key sai
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=flow_id,
        max_retries=1
    )
    
    print(f"   Result 5: {result5}")
    print(f"   From existing: {result5.get('from_existing', False)}")
    print()
    
    # Test 6: Lần cuối (sau khi data bị xóa, nên generate mới)
    print("6. After deletion - Should generate new data...")
    result6 = captcha_wrapper.generate_and_hold_captcha(
        auth=auth,  # Auth key đúng
        site=site,
        proxyregion=proxyregion,
        region=region,
        proxy=proxy,
        flow_id=flow_id,
        max_retries=3
    )
    
    print(f"   Result 6: {result6}")
    print(f"   From existing: {result6.get('from_existing', False)}")
    print()
    
    print("=== Test completed ===")


if __name__ == "__main__":
    test_database_check()
