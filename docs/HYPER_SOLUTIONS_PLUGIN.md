# Hyper Solutions Plugin cho FlowLite

## Tổng quan

Hyper Solutions Plugin tích hợp SDK Hyper-Solutions vào FlowLite framework để bypass bot protection trên các website.

## Cài đặt

### 1. Cài đặt dependencies
```bash
pip install hyper-sdk
```

### 2. Lấy API Key
- Truy cập [hypersolutions.co](https://hypersolutions.co)
- Tạo tài khoản và lấy API key
- Chọn gói phù hợp (Pay-as-you-go hoặc Subscription)

## Sử dụng

### 1. Cấu hình cơ bản

```python
from flowlite import Flow
from flowlite.plugins.hyper_solutions import HyperSolutionsPlugin

# Tạo flow
flow = Flow("my_flow")

# Thêm plugin
flow.use(HyperSolutionsPlugin, 
         api_key="your_api_key_here",
         bypass_sites=["walmart", "amazon"],
         auto_bypass=True)
```

### 2. Sử dụng trong step

```python
@step("my_step")
def my_step(ctx):
    # Lấy plugin từ context
    hyper_plugin = ctx.get("hyper_solutions")
    
    # Tạo sensor data
    result = hyper_plugin.generate_sensor_data(
        site="walmart",
        user_agent="Mozilla/5.0...",
        proxy=ctx.get("session_proxy")
    )
    
    if result["success"]:
        # Sử dụng sensor data
        sensor_data = result["sensor_data"]
        # ... xử lý tiếp
```

### 3. Bypass protection tự động

Plugin sẽ tự động bypass protection cho các site được cấu hình trong `bypass_sites` thông qua middleware `on_request`.

## API Methods

### `generate_sensor_data(site, user_agent=None, proxy=None, additional_params=None)`

Tạo sensor data để bypass bot protection.

**Parameters:**
- `site` (str): Tên site (e.g., "walmart", "amazon")
- `user_agent` (str, optional): User agent string
- `proxy` (str, optional): Proxy URL
- `additional_params` (dict, optional): Các tham số bổ sung

**Returns:**
```python
{
    "success": True,
    "sensor_data": {...},
    "sensor_context": {...},
    "site": "walmart"
}
```

### `get_fingerprint_data(site, user_agent=None, proxy=None)`

Lấy fingerprint data cho site cụ thể.

**Parameters:**
- `site` (str): Tên site
- `user_agent` (str, optional): User agent string
- `proxy` (str, optional): Proxy URL

**Returns:**
```python
{
    "success": True,
    "fingerprint": {...},
    "context": {...}
}
```

### `bypass_protection(site, url, headers=None, user_agent=None, proxy=None)`

Bypass protection cho request cụ thể.

**Parameters:**
- `site` (str): Tên site
- `url` (str): URL cần bypass
- `headers` (dict, optional): Headers hiện tại
- `user_agent` (str, optional): User agent
- `proxy` (str, optional): Proxy URL

**Returns:**
```python
{
    "success": True,
    "headers": {...},  # Headers đã được xử lý
    "sensor_data": {...},
    "context": {...}
}
```

## Cấu hình

### Plugin Configuration

```python
flow.use(HyperSolutionsPlugin, 
         api_key="your_api_key",
         bypass_sites=["walmart", "amazon", "target"],  # Sites cần bypass
         auto_bypass=True,  # Tự động bypass qua middleware
         retry_on_failure=True,  # Retry khi thất bại
         max_retries=3,  # Số lần retry tối đa
         timeout=30  # Timeout cho API calls
)
```

### Environment Variables

```bash
HYPER_SOLUTIONS_API_KEY=your_api_key_here
HYPER_SOLUTIONS_BYPASS_SITES=walmart,amazon,target
HYPER_SOLUTIONS_AUTO_BYPASS=true
```

## Ví dụ hoàn chỉnh

Xem file `examples/hyper_solutions_example.py` để có ví dụ chi tiết.

## Troubleshooting

### Lỗi thường gặp

1. **ImportError: hyper-sdk not installed**
   ```bash
   pip install hyper-sdk
   ```

2. **ValueError: API key is required**
   - Đảm bảo đã cung cấp API key khi khởi tạo plugin

3. **API calls failed**
   - Kiểm tra API key có hợp lệ không
   - Kiểm tra kết nối mạng
   - Kiểm tra quota API

### Debug

Bật logging để debug:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## License

Plugin này sử dụng Hyper-Solutions SDK, vui lòng tuân thủ license của họ.
