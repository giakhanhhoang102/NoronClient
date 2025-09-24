from flowlite import Flow, step, finalize, expect, http
from flowlite.plugins import CurlDump, MaskCookies  # hoặc dùng tên "curl_dump"/"mask_cookies"

flow = Flow("http_test").debug(trace=True)

# Cách 1: dùng class
flow.use(MaskCookies, mask=["x-custom-secret"])
flow.use(CurlDump, dir="./logs/curl", include_response=True, max_body=4096)

# Cách 2: dùng tên (nhờ @register_plugin)
# flow.use("mask_cookies", mask=["x-custom-secret"])
# flow.use("curl_dump", dir="./logs/curl", include_response=True, max_body=4096)

@step("fetch_uuid")
def fetch_uuid(ctx):
    r = http.get("https://httpbingo.org/uuid") \
            .accept("application/json") \
            .accept_encoding("identity") \
            .via_requests(no_proxy=True) \
            .label("get_uuid") \
            .send()
    ctx.uuid = r.json().get("uuid")
    expect.truthy(ctx.uuid)

@finalize
def done(ctx):
    return {
        "uuid": ctx.uuid,
        "curl_dir": "logs/curl/http_test",  # nơi cURL được ghi (vì split_by_flow=True)
        "task_trace_len": len(ctx.meta.get("task_trace", [])),
        "http_trace_len": len(ctx.meta.get("http_trace", [])),
    }

flow.register(globals())
