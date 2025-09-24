# flows/hello.py
from flowlite import Flow, step, finalize, expect

# Tạo flow & bật trace (phần debug nâng cao sẽ thêm ở phần 2)
flow = Flow("hello").debug(trace=True)

@step("init")
def init(ctx):
    ctx.msg = "xin chào"
    expect.truthy(ctx.msg)

@step("upper")
def upper(ctx):
    ctx.up = ctx.msg.upper()

@finalize
def done(ctx):
    return {"msg": ctx.msg, "up": ctx.up}

# Đăng ký step trong module
flow.register(globals())

# Cho phép chạy trực tiếp để test nhanh (không cần FastAPI)
if __name__ == "__main__":
    import json
    out = flow.run(data={}, session={}, options={})
    print(json.dumps(out, ensure_ascii=False, indent=2))
