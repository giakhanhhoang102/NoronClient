from flowlite import Flow, step, finalize, expect, http

flow = Flow("tls_test").debug(trace=True).tls(base="http://127.0.0.1:3000", auth_header="X-Auth-Token")

@step("fetch_html_tls")
def fetch(ctx):
    # YÊU CẦU: truyền tls_auth_token khi gọi flow.run(...)
    # Nếu ctx.session.id chưa có -> builder sẽ tự gọi /init để tạo.
    r = http.get("https://httpbingo.org/html") \
            .accept("text/html") \
            .via_tls() \
            .send()
    t = r.text()
    expect.truthy("Moby-Dick" in t)

@finalize
def done(ctx):
    return {"http_trace_len": len(ctx.meta.get("http_trace", [])), "session_id": (ctx.session or {}).get("id")}

flow.register(globals())

if __name__ == "__main__":
    import json, os
    TLS_TOKEN = os.environ.get("TLS_TOKEN") or "PX-xxxx"
    out = flow.run(data={}, session={}, options={}, tls_auth_token=TLS_TOKEN)
    print(json.dumps(out, ensure_ascii=False, indent=2))
