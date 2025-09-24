from __future__ import annotations
import os, uuid

from flowlite import Flow, step, finalize, http, expect
from flowlite.plugins import CurlDump, MaskCookies


flow = Flow("cookie_test").debug(trace=True)

# Bật plugin log để dễ quan sát
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "curl"))
flow.use(MaskCookies)
flow.use(CurlDump, dir=LOG_DIR, include_response=True, split_by_flow=True)

WEBHOOK = os.environ.get("WEBHOOK_URL", "https://webhook.site/760abb50-0f3d-4ba2-a24c-a7dc4e55a49b")


@step("set_cookie_on_httpbingo")
def set_cookie_on_httpbingo(ctx):
    # Tạo giá trị cookie ngẫu nhiên và set trên httpbingo (server sẽ trả Set-Cookie)
    ctx.session_val = str(uuid.uuid4())[:12]
    r = (http.get(f"https://httpbingo.org/cookies/set?session={ctx.session_val}")
           .accept("application/json")
           .accept_encoding("identity")
           .label("set_cookie")
           .via_tls()
           .send())
    expect.eq(r.status, 200, "cannot set cookie on httpbingo")


@step("verify_cookie_on_httpbingo")
def verify_cookie_on_httpbingo(ctx):
    # Gọi lại endpoint cookies để xác nhận cookie đã được giữ bởi TLS session
    r = (http.get("https://httpbingo.org/cookies")
           .accept("application/json")
           .accept_encoding("identity")
           .label("verify_cookie")
           .via_tls()
           .send())
    txt = r.text() or ""
    expect.truthy(ctx.session_val in txt, "cookie not persisted in TLS session")
    ctx.cookies_echo = txt


@step("send_to_webhook")
def send_to_webhook(ctx):
    # Gửi payload tới webhook.site để bạn kiểm tra trực quan. Cookie httpbingo thuộc domain khác,
    # nên không tự kèm khi gọi webhook (theo chuẩn trình duyệt). Ta gửi giá trị qua body để bạn đối chiếu.
    payload = {
        "note": "Cookie persisted on httpbingo TLS session",
        "expected_cookie_session": ctx.session_val,
        "httpbingo_echo": ctx.cookies_echo,
    }
    r = (http.post(WEBHOOK)
           .content_type("application/json")
           .accept("application/json")
           .label("webhook_post")
           .via_tls()
           .body_text(__import__("json").dumps(payload))
           .send())
    ctx.webhook_status = r.status


@finalize
def done(ctx):
    return {
        "status": "OK",
        "webhook_status": ctx.webhook_status,
        "cookie_session": ctx.session_val,
        "http_traces": len(ctx.meta.get("http_trace") or []),
    }


flow.register(globals())

if __name__ == "__main__":
    import json
    out = flow.run(data={}, session={"profile":"chrome_133"}, options={"httpVersion":"h2"})
    print(json.dumps(out, ensure_ascii=False, indent=2))


