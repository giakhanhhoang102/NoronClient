# Captcha Plugin cho FlowLite

Plugin Captcha cho phép generate cookies từ Parallax API và lưu trữ vào database SQLite.

## Cài đặt

Plugin đã được tích hợp sẵn vào FlowLite, không cần cài đặt thêm.

## Cách sử dụng

### 1. Import plugin

```python
from flowlite.plugins.captcha_wrapper import captcha_wrapper
```

### 2. Generate cookies

```python
# Generate cookies từ Parallax API
result = captcha_wrapper.generate_cookies(
    auth="your_auth_key",
    site="walmart",
    proxyregion="us",
    region="com",
    proxy="http://user:pass@host:port",
    flow_id=1,  # optional
    max_retries=3
)

if result["success"]:
    print(f"Cookie: {result['cookie']}")
    print(f"VID: {result['vid']}")
    print(f"CTS: {result['cts']}")
    print(f"UserAgent: {result['UserAgent']}")
    print(f"Data: {result['data']}")
else:
    print(f"Error: {result['error']}")
```

### 3. Generate và Hold Captcha (Recommended)

```python
# Generate cookies và sau đó gọi holdcaptcha
result = captcha_wrapper.generate_and_hold_captcha(
    auth="your_auth_key",
    site="walmart",
    proxyregion="us",
    region="com",
    proxy="http://user:pass@host:port",
    flow_id=1,  # optional
    max_retries=3
)

if result["success"]:
    print(f"Final Cookie: {result['cookie']}")
    print(f"VID: {result['vid']}")
    print(f"CTS: {result['cts']}")
    print(f"SecHeader: {result['secHeader']}")
    print(f"UserAgent: {result['UserAgent']}")
    print(f"FlaggedPOW: {result['flaggedPOW']}")
    print(f"Final Data: {result['data']}")
else:
    print(f"Error: {result['error']}")
```

### 4. Hold Captcha riêng lẻ

```python
# Gọi holdcaptcha với data từ generate
hold_result = captcha_wrapper.hold_captcha(
    auth="your_auth_key",
    site="walmart",
    proxyregion="us",
    region="com",
    proxy="http://user:pass@host:port",
    data="data_from_generate",
    pxhold_id=1  # optional
)
```

### 3. Lấy dữ liệu pxhold

```python
# Lấy dữ liệu pxhold theo ID
pxhold_data = captcha_wrapper.get_pxhold_data(pxhold_id)

# Lấy tất cả pxhold của flow
flow_pxhold = captcha_wrapper.get_pxhold_by_flow(flow_id)

# Lấy pxhold thành công gần nhất
successful_pxhold = captcha_wrapper.get_successful_pxhold(flow_id)
```

### 4. Dọn dẹp dữ liệu

```python
# Xóa các pxhold records thất bại cũ hơn 7 ngày
captcha_wrapper.cleanup_failed_pxhold(days=7)
```

## API Reference

### `generate_cookies()`

Generate cookies từ Parallax API với retry logic.

**Parameters:**
- `auth` (str): Authentication key
- `site` (str): Website (e.g., "walmart", "youtube")
- `proxyregion` (str): Proxy region ("eu" or "us")
- `region` (str): Site region (e.g., "com", "fr", "ch")
- `proxy` (str): Proxy URL
- `flow_id` (int, optional): ID của flow
- `max_retries` (int): Số lần retry tối đa (default: 3)

**Returns:**
```python
{
    "success": bool,
    "pxhold_id": int,
    "cookie": str,
    "vid": str,
    "cts": str,
    "isFlagged": bool,
    "isMaybeFlagged": bool,
    "UserAgent": str,
    "data": str,
    "attempt": int
}
```

### `get_pxhold_data(pxhold_id)`

Lấy dữ liệu pxhold theo ID.

**Parameters:**
- `pxhold_id` (int): ID của pxhold record

**Returns:**
Dictionary chứa dữ liệu pxhold hoặc None nếu không tìm thấy.

### `get_pxhold_by_flow(flow_id)`

Lấy tất cả pxhold records của một flow.

**Parameters:**
- `flow_id` (int): ID của flow

**Returns:**
List các pxhold records.

### `get_successful_pxhold(flow_id)`

Lấy pxhold record thành công gần nhất của flow.

**Parameters:**
- `flow_id` (int): ID của flow

**Returns:**
Dictionary chứa pxhold data thành công hoặc None nếu không có.

### `cleanup_failed_pxhold(days)`

Dọn dẹp các pxhold records thất bại cũ.

**Parameters:**
- `days` (int): Số ngày (default: 7)

## Cấu trúc Database

### Bảng `pxhold`
- `id`: Primary key
- `flow_id`: Foreign key đến flows
- `auth`: Authentication key
- `site`: Website name
- `proxyregion`: Proxy region
- `region`: Site region
- `proxy`: Proxy URL
- `cookie`: Generated cookie
- `vid`: VID value
- `cts`: CTS value
- `isFlagged`: Flagged status
- `isMaybeFlagged`: Maybe flagged status
- `UserAgent`: User agent string
- `data`: Data string for next step
- `error`: Error status
- `error_message`: Error message
- `retry_count`: Number of retries
- `created_at`: Creation timestamp
- `updated_at`: Update timestamp

## Ví dụ tích hợp vào Flow

```python
from flowlite import Flow, step, finalize
from flowlite.plugins.captcha_wrapper import captcha_wrapper

flow = Flow("walmart")

@step("generate_captcha_cookies")
def generate_captcha_cookies(ctx):
    """Generate cookies từ Parallax API"""
    
    # Lấy proxy từ session
    proxy = ctx.session.get("proxy", "")
    
    result = captcha_wrapper.generate_cookies(
        auth="S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5",
        site="walmart",
        proxyregion="us",
        region="com",
        proxy=proxy,
        flow_id=ctx.get("flow_id"),
        max_retries=3
    )
    
    if result["success"]:
        # Lưu kết quả vào context
        ctx.px3_cookie = result["cookie"]
        ctx.pxvid = result["vid"]
        ctx.pxcts = result["cts"]
        ctx.pxhd = result.get("pxhd", "")
        ctx.user_agent = result["UserAgent"]
        ctx.parallax_data = result["data"]
        ctx.pxhold_id = result["pxhold_id"]
        
        print(f"DEBUG - Generated cookies successfully")
        print(f"DEBUG - PX3: {ctx.px3_cookie}")
        print(f"DEBUG - PXVID: {ctx.pxvid}")
        print(f"DEBUG - PXCTS: {ctx.pxcts}")
    else:
        ctx.status = "BAN"
        raise AssertionError(f"BAN: Failed to generate cookies: {result['error']}")

@finalize
def done(ctx):
    """Kết thúc flow và trả về kết quả"""
    return {
        "status": ctx.get("status", "UNKNOWN"),
        "px3_cookie": ctx.get("px3_cookie"),
        "pxvid": ctx.get("pxvid"),
        "pxcts": ctx.get("pxcts"),
        "pxhd": ctx.get("pxhd"),
        "user_agent": ctx.get("user_agent"),
        "parallax_data": ctx.get("parallax_data"),
        "pxhold_id": ctx.get("pxhold_id")
    }
```

## Lưu ý

- Plugin tự động retry tối đa 3 lần nếu API trả về error
- Tất cả requests được lưu vào database để tracking
- Cookies chỉ có thể sử dụng với IP đã generate
- Cần có proxy hợp lệ để generate cookies
- Plugin hỗ trợ cleanup dữ liệu cũ để tránh database quá lớn
