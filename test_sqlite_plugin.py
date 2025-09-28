#!/usr/bin/env python3
"""
Test script cho SQLite plugin
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flowlite.plugins.sqlite_wrapper import sqlite_wrapper


def test_sqlite_plugin():
    """Test các chức năng của SQLite plugin"""
    
    print("=== Testing SQLite Plugin ===\n")
    
    # 1. Lưu flow data
    print("1. Lưu flow data...")
    flow_id = sqlite_wrapper.save_flow(
        flow_name="walmart",
        session_id="test_session_123",
        status="RUNNING",
        data={
            "CCNUM": "4111111111111111",
            "MM": "12",
            "YYYY": "2025",
            "CCV": "123"
        }
    )
    print(f"   Flow ID: {flow_id}\n")
    
    # 2. Lưu variables
    print("2. Lưu variables...")
    variables = {
        "PIEKEY": "abc123def456",
        "key_id": "12345678",
        "protected_s": "encrypted_s_value",
        "protected_q": "encrypted_q_value",
        "protected_mac": "mac_value",
        "Ua": "Mozilla/5.0...",
        "sechua": "Chrome/91.0...",
        "pxhd": "pxhd_value",
        "paradata": "paradata_value"
    }
    sqlite_wrapper.save_variables(flow_id, variables)
    print("   Variables saved\n")
    
    # 3. Lưu HTTP traces
    print("3. Lưu HTTP traces...")
    sqlite_wrapper.save_http_trace(flow_id, "GET", "https://api.example.com", 200, 150.5)
    sqlite_wrapper.save_http_trace(flow_id, "POST", "https://api.example.com/submit", 201, 300.2)
    print("   HTTP traces saved\n")
    
    # 4. Lấy flow data
    print("4. Lấy flow data...")
    flow_data = sqlite_wrapper.get_flow(flow_id)
    print(f"   Flow data: {flow_data}\n")
    
    # 5. Lấy variables
    print("5. Lấy variables...")
    saved_variables = sqlite_wrapper.get_variables(flow_id)
    print(f"   Variables: {saved_variables}\n")
    
    # 6. Lấy HTTP traces
    print("6. Lấy HTTP traces...")
    traces = sqlite_wrapper.get_http_traces(flow_id)
    print(f"   HTTP traces: {traces}\n")
    
    # 7. Cập nhật flow status
    print("7. Cập nhật flow status...")
    sqlite_wrapper.update_flow(flow_id, "COMPLETED", {
        "result": "SUCCESS",
        "final_data": "processed_data"
    })
    print("   Flow status updated\n")
    
    # 8. Lấy flows theo tên
    print("8. Lấy flows theo tên...")
    flows = sqlite_wrapper.get_flows_by_name("walmart", limit=5)
    print(f"   Found {len(flows)} walmart flows")
    for flow in flows:
        print(f"   - ID: {flow['id']}, Status: {flow['status']}, Created: {flow['created_at']}")
    
    print("\n=== Test completed ===")


if __name__ == "__main__":
    test_sqlite_plugin()
