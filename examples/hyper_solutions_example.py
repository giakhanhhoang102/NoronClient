"""
Ví dụ sử dụng Hyper Solutions Plugin trong FlowLite
"""

from flowlite import Flow, step, finalize
from flowlite.plugins.hyper_solutions import HyperSolutionsPlugin
import json

# Tạo flow mới
flow = Flow("hyper_solutions_example")

# Thêm Hyper Solutions plugin
flow.use(HyperSolutionsPlugin, 
         api_key="your_api_key_here",
         bypass_sites=["walmart", "amazon"],
         auto_bypass=True)

@step("test_hyper_solutions")
def test_hyper_solutions(ctx):
    """Test Hyper Solutions plugin"""
    
    # Lấy plugin từ context
    hyper_plugin = ctx.get("hyper_solutions")
    
    if not hyper_plugin:
        raise Exception("Hyper Solutions plugin not found")
    
    # Test tạo sensor data cho Walmart
    result = hyper_plugin.generate_sensor_data(
        site="walmart",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        proxy=ctx.get("session_proxy")
    )
    
    print(f"Hyper Solutions result: {json.dumps(result, indent=2)}")
    
    # Lưu kết quả vào context
    ctx.hyper_result = result

@step("test_bypass_protection")
def test_bypass_protection(ctx):
    """Test bypass protection cho request"""
    
    hyper_plugin = ctx.get("hyper_solutions")
    
    # Test bypass cho URL Walmart
    bypass_result = hyper_plugin.bypass_protection(
        site="walmart",
        url="https://www.walmart.com/checkout",
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9"
        },
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        proxy=ctx.get("session_proxy")
    )
    
    print(f"Bypass result: {json.dumps(bypass_result, indent=2)}")
    
    ctx.bypass_result = bypass_result

@finalize
def done(ctx):
    """Kết thúc flow"""
    return {
        "success": True,
        "hyper_result": ctx.get("hyper_result"),
        "bypass_result": ctx.get("bypass_result")
    }

# Đăng ký flow
flow.register(globals())

if __name__ == "__main__":
    # Test data
    test_data = {
        "session_proxy": "http://user:pass@proxy.example.com:8080"
    }
    
    # Chạy flow
    result = flow.run(data=test_data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
