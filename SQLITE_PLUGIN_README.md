# SQLite Plugin cho FlowLite

Plugin SQLite cho phép lưu trữ và truy xuất dữ liệu flow vào database SQLite.

## Cài đặt

Plugin đã được tích hợp sẵn vào FlowLite, không cần cài đặt thêm.

## Cách sử dụng

### 1. Import plugin

```python
from flowlite.plugins.sqlite_wrapper import sqlite_wrapper
```

### 2. Lưu flow data

```python
# Lưu flow mới
flow_id = sqlite_wrapper.save_flow(
    flow_name="walmart",
    session_id="session_123",
    status="RUNNING",
    data={
        "CCNUM": "4111111111111111",
        "MM": "12",
        "YYYY": "2025",
        "CCV": "123"
    }
)
```

### 3. Lưu variables

```python
# Lưu các biến của flow
variables = {
    "PIEKEY": "abc123def456",
    "key_id": "12345678",
    "protected_s": "encrypted_s_value",
    "Ua": "Mozilla/5.0...",
    "pxhd": "pxhd_value"
}
sqlite_wrapper.save_variables(flow_id, variables)
```

### 4. Lưu HTTP traces

```python
# Lưu HTTP request traces
sqlite_wrapper.save_http_trace(
    flow_id=flow_id,
    method="GET",
    url="https://api.example.com",
    status_code=200,
    response_time=150.5
)
```

### 5. Truy xuất dữ liệu

```python
# Lấy flow data
flow_data = sqlite_wrapper.get_flow(flow_id)

# Lấy variables
variables = sqlite_wrapper.get_variables(flow_id)

# Lấy HTTP traces
traces = sqlite_wrapper.get_http_traces(flow_id)

# Lấy flows theo tên
flows = sqlite_wrapper.get_flows_by_name("walmart", limit=10)
```

### 6. Cập nhật flow

```python
# Cập nhật trạng thái flow
sqlite_wrapper.update_flow(
    flow_id=flow_id,
    status="COMPLETED",
    data={"result": "SUCCESS"}
)
```

### 7. Xóa flow

```python
# Xóa flow và tất cả dữ liệu liên quan
sqlite_wrapper.delete_flow(flow_id)
```

### 8. Dọn dẹp dữ liệu cũ

```python
# Xóa dữ liệu cũ hơn 30 ngày
sqlite_wrapper.cleanup(days=30)
```

## Cấu trúc Database

### Bảng `flows`
- `id`: Primary key
- `flow_name`: Tên flow
- `session_id`: ID session
- `status`: Trạng thái flow
- `created_at`: Thời gian tạo
- `updated_at`: Thời gian cập nhật
- `data`: Dữ liệu flow (JSON)

### Bảng `variables`
- `id`: Primary key
- `flow_id`: Foreign key đến flows
- `variable_name`: Tên biến
- `variable_value`: Giá trị biến
- `created_at`: Thời gian tạo

### Bảng `http_traces`
- `id`: Primary key
- `flow_id`: Foreign key đến flows
- `method`: HTTP method
- `url`: URL
- `status_code`: Status code
- `response_time`: Thời gian response (ms)
- `created_at`: Thời gian tạo

## Ví dụ tích hợp vào Flow

```python
from flowlite import Flow, step, finalize
from flowlite.plugins.sqlite_wrapper import sqlite_wrapper

flow = Flow("walmart")

@step("init_input")
def init_input(ctx):
    # Lưu flow vào database
    ctx.flow_id = sqlite_wrapper.save_flow(
        flow_name="walmart",
        session_id=ctx.session.get("session_id"),
        status="RUNNING",
        data=ctx.data
    )

@step("process_data")
def process_data(ctx):
    # Xử lý dữ liệu...
    result = {"processed": True}
    
    # Lưu variables
    sqlite_wrapper.save_variables(ctx.flow_id, {
        "result": result,
        "status": "SUCCESS"
    })

@finalize
def done(ctx):
    # Cập nhật trạng thái cuối
    sqlite_wrapper.update_flow(
        ctx.flow_id,
        status="COMPLETED",
        data=ctx.get_all_vars()
    )
    
    return {"flow_id": ctx.flow_id, "status": "COMPLETED"}
```

## Lưu ý

- Database file mặc định: `flowlite_data.db`
- Tất cả dữ liệu được lưu dưới dạng JSON
- Plugin tự động tạo database và tables nếu chưa tồn tại
- Hỗ trợ cleanup dữ liệu cũ để tránh database quá lớn
