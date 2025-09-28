from __future__ import annotations
import os, uuid, random

from flowlite import Flow, step, finalize, expect, http, js
from flowlite.plugins import CurlDump, MaskCookies


flow = Flow("square").debug(trace=True)

# Bật log để dễ debug
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "curl"))
flow.use(MaskCookies)
flow.use(CurlDump, dir=LOG_DIR, include_response=True, split_by_flow=True)


@step("init_input")
def init_input(ctx):
    d = ctx.data or {}
    ctx.ccnum = str(d.get("CCNUM", "")).replace(" ", "")
    ctx.mm    = str(d.get("MM", ""))
    ctx.yyyy  = str(d.get("YYYY", ""))
    ctx.ccv   = str(d.get("CCV", ""))
    # không ép buộc ngay, vì có thể test không cần thẻ


@step("init_helpers")
def init_helpers(ctx):
    # constant lists
    given_name = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","William","Elizabeth","David","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Charles","Karen","Christopher","Nancy","Daniel","Lisa","Matthew","Betty","Anthony","Margaret","Mark","Sandra","Donald","Ashley","Steven","Kimberly","Paul","Emily","Andrew","Donna","Joshua","Michelle","Kenneth","Dorothy","Kevin","Carol","Brian","Amanda","George","Melissa","Timothy","Deborah","Ronald","Stephanie","Edward","Rebecca","Jason","Laura","Jeffrey","Sharon","Ryan","Cynthia","Jacob","Kathleen","Gary","Amy","Nicholas","Shirley","Eric","Angela","Jonathan","Helen","Larry","Anna","Justin","Brenda","Scott","Pamela","Brandon","Nicole","Frank","Emma","Benjamin","Samantha","Gregory","Katherine","Raymond","Christine","Alexander","Debra","Patrick","Rachel","Jack","Catherine","Dennis","Carolyn","Jerry","Janet","Tyler","Maria","Aaron","Heather"]
    family_name = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez","Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin","Lee","Perez","Thompson","White","Harris","Sanchez","Clark","Ramirez","Lewis","Robinson","Walker","Young","Allen","King","Wright","Scott","Torres","Nguyen","Hill","Flores","Green","Adams","Nelson","Baker","Hall","Rivera","Campbell","Mitchell","Carter","Roberts","Gomez","Phillips","Evans","Turner","Diaz","Parker","Cruz","Edwards","Collins","Reyes","Stewart","Morris","Morales","Murphy","Cook","Rogers","Gutierrez","Ortiz","Morgan","Cooper","Peterson","Bailey","Reed","Kelly","Howard","Ramos","Kim","Cox","Ward","Richardson","Watson","Brooks","Chavez","Wood","James","Bennett","Gray","Mendoza","Ruiz","Hughes","Price","Alvarez","Castillo","Sanders","Patel","Myers","Long","Ross","Foster","Jimenez"]
    area_codes = ["212","213","312","305","617","206","702","512","404"]

    ctx.r_given_name = random.choice(given_name)
    ctx.r_family_name = random.choice(family_name)
    ctx.r_area_codes = random.choice(area_codes)
    ctx.ran_num = random.randint(2565265, 9565265)
    ctx.ran_5 = random.randint(11298, 91298)

    # normalize month NMM from MM
    mm = str(ctx.mm or "").strip()
    try:
        n = int(mm)
        expect.ge(n, 1)
        expect.ge(12, n)
        ctx.NMM = n
    except Exception:
        ctx.NMM = None


@step("init_js")
def init_js(ctx):
    # nmm.js
    try:
        v = js.run("flows/js/square/nmm.js", {"MM": ctx.mm}, expect="auto", timeout=10.0)
        s = str(v or "")
        m = http.re(r"(\d{1,2})", s, 1)
        if m:
            ctx.NMM = int(m)
    except Exception:
        pass

    # iphone.js → result (JSON)
    out = js.run("flows/js/square/iphone.js", {}, expect="text", timeout=20.0)
    ctx.result = str(out or "")

    # mmuhash.js → fingerprint JSON {v1,v1SansUA,v2}
    try:
        fp_out = js.run("flows/js/square/mmuhash.js", {"result": ctx.result}, expect="auto", timeout=20.0)
        import json as _json
        if isinstance(fp_out, str):
            try:
                fp = _json.loads(fp_out)
            except Exception:
                # cố gắng trích bằng regex từ text log
                v1 = http.re(r'"v1"\s*:\s*"([0-9a-fA-F]{32})"', fp_out, 1)
                v1s = http.re(r'"v1SansUA"\s*:\s*"([0-9a-fA-F]{32})"', fp_out, 1)
                v2 = http.re(r'"v2"\s*:\s*"([0-9a-fA-F]{32})"', fp_out, 1)
                fp = {"v1": v1, "v1SansUA": v1s, "v2": v2}
        else:
            fp = fp_out or {}
        ctx.fingerprint = fp
        ctx.fingerprintv1 = fp.get("v1")
        ctx.fingerprintv1SansUA = fp.get("v1SansUA")
        ctx.fingerprintv2 = fp.get("v2")
    except Exception:
        ctx.fingerprint = {}
        ctx.fingerprintv1 = None
        ctx.fingerprintv1SansUA = None
        ctx.fingerprintv2 = None

    # Parse components/ua/timezone/resolution
    import json as _json
    try:
        robj = _json.loads(ctx.result)
        fps = robj.get("fingerprints") or []
        def _c(i):
            try:
                return fps[i].get("components")
            except Exception:
                return None
        ctx.components0 = _c(0)
        ctx.components1 = _c(1)
        ctx.components2 = _c(2)
        # từ components0 lấy UA/timezone/resolution
        try:
            c0 = _json.loads(ctx.components0 or "{}")
            ctx.ua = c0.get("user_agent") or ctx.ua
            # timezone key trong V1 là "timezone_offset"
            ctx.timezone_offset = c0.get("timezone_offset")
            res = c0.get("resolution") or c0.get("available_resolution") or []
            if isinstance(res, list) and len(res) >= 2:
                ctx.screen_height = int(res[0]); ctx.screen_width = int(res[1])
        except Exception:
            # fallback regex trên result
            ctx.ua = ctx.ua or http.re(r'user_agent\\":\\"([^\\"]+)', ctx.result, 1)
            ctx.timezone_offset = ctx.timezone_offset or http.re(r'timezone_offset\\":(\-?\d+)', ctx.result, 1)
            sh = http.re(r'resolution.*?(\d+).*?(\d+)', ctx.result, 1)
            sw = http.re(r'resolution.*?(\d+).*?(\d+)', ctx.result, 2)
            if sh and sw:
                ctx.screen_height = int(sh); ctx.screen_width = int(sw)
    except Exception:
        pass

    # defaults tránh lỗi thiếu biến ở finalize
    if ctx.get("timezone_offset") is None:
        ctx.timezone_offset = 0
    if ctx.get("screen_height") is None:
        ctx.screen_height = 0
    if ctx.get("screen_width") is None:
        ctx.screen_width = 0

@step("get_line_square")
def get_line_square(ctx):
    url = "http://172.236.141.206:33668/getline/square.txt"
    ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"
    )
    r = (http.get(url)
           .header("user-agent", ua)
           .header("pragma", "no-cache")
           .accept("*/*")
           .header("accept-language", "en-US,en;q=0.8")
           .header("auth-key", "W6FBn0dIhAPsT8jsi2UnLXzMgtBb0YePNUk37T3pE4T07Tsuf7")
           .label("square-getline")
           .via_requests(no_proxy=True)
           .timeout(30.0)
           .send())

    txt = r.text() or ""
    # Keycheck: body phải chứa success":true
    expect.truthy("success\":true" in txt, "getline square not success")
    # Parse site từ message
    ctx.site = http.re(r'"message":"([^"]+)",', txt, 1)
    ctx.ua = ua


@step("go_square")
def go_square(ctx):
    expect.truthy(ctx.site, "missing site url from step1")
    r = (http.get(ctx.site)
           .accept("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
           .header("upgrade-insecure-requests", "1")
           .user_agent(ctx.ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/133 Safari/537.36")
           .header("accept-language", "en-us")
           .header("accept-encoding", "gzip, deflate, br")
           .header("connection", "keep-alive")
           .label("go-square")
           .via_tls()
           .timeout(60.0)
           .send())

    loc = r.header_one("location")
    ctx.Location = loc
    expect.truthy(loc, "missing redirect Location")
    ctx.merchant = http.re(r"/merchant/([^/]+)/", loc, 1)
    ctx.checkout = http.re(r"/checkout/([^/?#]+)", loc, 1)


@step("fetch_location")
def fetch_location(ctx):
    expect.truthy(ctx.Location, "missing Location")
    r = (http.get(ctx.Location)
           .accept("text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
           .user_agent(ctx.ua)
           .header("accept-language", "en-us")
           .header("accept-encoding", "gzip, deflate, br")
           .label("get-location")
           .via_tls()
           .timeout(60.0)
           .send())
    expect.eq(r.status, 200, "Location not 200")


@step("create_order")
def create_order(ctx):
    expect.truthy(ctx.merchant, "missing merchant")
    expect.truthy(ctx.checkout, "missing checkout")
    expect.truthy(ctx.Location, "missing referer Location")
    url = f"https://checkout.square.site/api/merchant/{ctx.merchant}/checkout/{ctx.checkout}"

    payload = {
        "buyerControlledPrice": {"amount": 100, "currency": "USD", "precision": 2},
        "subscriptionPlanId": None,
        "oneTimePayment": True,
        "itemCustomizations": []
    }

    r = (http.post(url)
           .accept("application/json, text/plain, */*")
           .content_type("application/json")
           .json(payload)
           .header("origin", "https://checkout.square.site")
           .header("accept-language", "en-us")
           .user_agent(ctx.ua or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/133 Safari/537.36")
           .header("referer", ctx.Location)
           .header("accept-encoding", "gzip, deflate, br")
           .label("square-create-order")
           .via_tls()
           .timeout(60.0)
           .send())
    if r.status != 200:
        ctx.status = "BAN"
        # dừng flow với trạng thái BAN
        raise AssertionError("BAN")
    ctx.status = "SUCCESS"
    # Lưu cả JSON và text để debug
    try:
        ctx.order_json = r.json()
    except Exception:
        ctx.order_json = None
    ctx.order_text = r.text()

    # Parse orderid, location_id, application_id
    ctx.orderid = None
    ctx.location_id = None
    ctx.application_id = None
    # Ưu tiên JSON
    try:
        if isinstance(ctx.order_json, dict):
            ctx.orderid = ctx.order_json.get("id") or ctx.order_json.get("orderId")
            ctx.location_id = ctx.order_json.get("location_id") or ctx.order_json.get("locationId")
            ctx.application_id = ctx.order_json.get("application_id") or ctx.order_json.get("applicationId")
    except Exception:
        pass
    # Fallback regex theo yêu cầu
    if not ctx.orderid:
        ctx.orderid = http.re(r'"id":"([^"]+)"', ctx.order_text or "", 1)
    if not ctx.location_id:
        ctx.location_id = http.re(r'"location_id":"([^"]+)"', ctx.order_text or "", 1)
    if not ctx.application_id:
        ctx.application_id = http.re(r'"application_id":"([^"]+)"', ctx.order_text or "", 1)


@step("mark_visited")
def mark_visited(ctx):
    expect.truthy(ctx.merchant, "missing merchant")
    expect.truthy(ctx.location_id, "missing location_id")
    expect.truthy(ctx.orderid, "missing orderid")
    expect.truthy(ctx.checkout, "missing checkout")

    url = f"https://checkout.square.site/api/merchant/{ctx.merchant}/location/{ctx.location_id}/order/{ctx.orderid}/visited"
    r = (http.patch(url)
           .accept("application/json, text/plain, */*")
           .header("origin", "https://checkout.square.site")
           .header("referer", f"https://checkout.square.site/merchant/{ctx.merchant}/checkout/{ctx.checkout}")
           .header("accept-encoding", "gzip, deflate, br")
           .header("accept-language", "en-us")
           .user_agent(ctx.ua)
           .body_text("")  # ensure Content-Length: 0
           .label("square-mark-visited")
           .via_tls()
           .timeout(60.0)
           .send())
    if r.status != 200:
        ctx.status = "BAN"


@step("get_bootstrap")
def get_bootstrap(ctx):
    expect.truthy(ctx.merchant, "missing merchant")
    expect.truthy(ctx.location_id, "missing location_id")
    expect.truthy(ctx.orderid, "missing orderid")
    expect.truthy(ctx.checkout, "missing checkout")

    url = f"https://checkout.square.site/api/soc-platform/merchant/{ctx.merchant}/location/{ctx.location_id}/order/{ctx.orderid}/bootstrap/en-us"
    r = (http.get(url)
           .header("accept-encoding", "gzip, deflate, br")
           .user_agent(ctx.ua)
           .header("accept-language", "en-us")
           .header("referer", f"https://checkout.square.site/merchant/{ctx.merchant}/checkout/{ctx.checkout}")
           .label("square-bootstrap")
           .via_tls()
           .timeout(60.0)
           .send())
    if r.status != 200:
        ctx.status = "BAN"
        raise AssertionError("BAN")
    body = r.text() or ""
    ctx.client_id = http.re(r'"client_id":"([^\"]+)"', body, 1)


@step("get_order_overview")
def get_order_overview(ctx):
    expect.truthy(ctx.merchant, "missing merchant")
    expect.truthy(ctx.location_id, "missing location_id")
    expect.truthy(ctx.orderid, "missing orderid")
    expect.truthy(ctx.checkout, "missing checkout")

    url = f"https://checkout.square.site/api/soc-platform/merchant/{ctx.merchant}/location/{ctx.location_id}/order/{ctx.orderid}/"
    r = (http.get(url)
           .accept("application/json, text/plain, */*")
           .header("accept-encoding", "gzip, deflate, br")
           .user_agent(ctx.ua)
           .header("accept-language", "en-us")
           .header("referer", f"https://checkout.square.site/merchant/{ctx.merchant}/checkout/{ctx.checkout}")
           .label("square-order-overview")
           .via_tls()
           .timeout(60.0)
           .send())
    if r.status != 200:
        ctx.status = "BAN"
        return
    body = r.text() or ""
    ctx.site_id = http.re(r'"site_id":"([^\"]+)"', body, 1)


@step("ping_square_sync")
def ping_square_sync(ctx):
    url = "https://checkout.square.site/app/square-sync/published/ping"
    r = (http.get(url)
           .accept("application/json, text/plain, */*")
           .header("accept-encoding", "gzip, deflate, br")
           .user_agent(ctx.ua)
           .header("accept-language", "en-us")
           .header("referer", f"https://checkout.square.site/merchant/{ctx.merchant}/checkout/{ctx.checkout}")
           .label("square-sync-ping")
           .via_tls()
           .timeout(60.0)
           .send())
    if r.status != 200:
        ctx.status = "BAN"
        return


@step("get_loyalty_programs")
def get_loyalty_programs(ctx):
    expect.truthy(ctx.merchant, "missing merchant")
    expect.truthy(ctx.orderid, "missing orderid")
    url = "https://checkout.square.site/app/accounts/v1/loyalty/programs"
    cookie_val = f"merchant:{ctx.merchant}:order:{ctx.orderid}:locale=en-us"
    r = (http.get(url)
           .header("cookie", cookie_val)
           .accept("application/json, text/plain, */*")
           .header("square-merchant-token", str(ctx.merchant))
           .header("accept-encoding", "gzip, deflate, br")
           .user_agent(ctx.ua)
           .header("accept-language", "en-us")
           .header("referer", f"https://checkout.square.site/merchant/{ctx.merchant}/checkout/{ctx.checkout}")
           .label("square-loyalty-programs")
           .via_tls()
           .timeout(60.0)
           .send())
    if r.status != 200:
        ctx.status = "BAN"
        return
    ctx.loyalty_programs = r.text()
    # Thử lấy customer_xsrf từ response này (theo thực tế nó được set ở đây)
    try:
        hdr_set_cookies = r.header("set-cookie") or []
        # lưu debug
        ctx.loyalty_cookies_debug = hdr_set_cookies
        ctx.loyalty_cookies_kv = r.cookies
        cx = None
        for c in hdr_set_cookies:
            m = http.re(r'(?i)customer[_-]xsrf=([^;]+)', c, 1)
            if m:
                cx = m; break
        if not cx and isinstance(r.cookies, dict):
            for k, v in r.cookies.items():
                kl = (k or "").lower()
                if kl in ("customer_xsrf", "customer-xsrf"):
                    cx = v; break
        if cx:
            ctx.customerxsrf = cx
            try:
                from urllib.parse import unquote_plus as _unqp
                ctx.decustomerxsrf = _unqp(cx)
            except Exception:
                ctx.decustomerxsrf = cx
    except Exception:
        pass


@step("hydrate_pci_connect")
def hydrate_pci_connect(ctx):
    expect.truthy(ctx.application_id, "missing application_id")
    expect.truthy(ctx.location_id, "missing location_id")
    url = (
        "https://pci-connect.squareup.com/payments/hydrate"
        f"?applicationId={http.urlencode(ctx.application_id)}"
        f"&hostname=checkout.square.site&locationId={http.urlencode(ctx.location_id)}&version=1.78.0"
    )
    r = (http.get(url)
           .accept("application/json")
           .content_type("application/json; charset=utf-8")
           .header("origin", "https://web.squarecdn.com")
           .header("accept-encoding", "gzip, deflate, br")
           .user_agent(ctx.ua)
           .header("referer", "https://web.squarecdn.com/")
           .header("accept-language", "en-us")
           .label("pci-connect-hydrate")
           .via_tls()
           .timeout(60.0)
           .send())
    if r.status != 200:
        ctx.status = "BAN"
        return
    body = r.text() or ""
    ctx.avt = http.re(r'"avt":"([^\"]+)"', body, 1)
    ctx.sessionId = http.re(r'"sessionId":"([^\"]+)"', body, 1)
    ctx.powPrefix = http.re(r'"powPrefix":"([^\"]+)"', body, 1)
    ctx.instanceId = http.re(r'"instanceId":"([^\"]+)"', body, 1)


@step("verify_phone")
def verify_phone(ctx):
    expect.truthy(ctx.merchant, "missing merchant")
    expect.truthy(ctx.site_id, "missing site_id (from get_order_overview)")
    expect.truthy(ctx.decustomerxsrf, "missing XSRF token from loyalty")
    phone = f"+1{ctx.r_area_codes}{ctx.ran_num}"
    url = "https://checkout.square.site/app/accounts/v1/verification?lang=en"
    payload = {
        "phone": phone,
        "site_id": ctx.site_id,
        "require_buyer_account": True
    }
    r = (http.post(url)
           .content_type("application/json")
           .accept("application/json, text/plain, */*")
           .header("square-merchant-token", str(ctx.merchant))
           .header("accept-encoding", "gzip, deflate, br")
           .header("x-xsrf-token", str(ctx.decustomerxsrf))
           .header("accept-language", "en-us")
           .header("origin", "https://checkout.square.site")
           .user_agent(ctx.ua)
           .header("referer", f"https://checkout.square.site/merchant/{ctx.merchant}/checkout/{ctx.checkout}")
           .json(payload)
           .label("square-verify-phone")
           .via_tls()
           .timeout(60.0)
           .send())
    txt = r.text() or ""
    if r.status == 200 and ("No buyer account found for the provided phone number" in txt):
        ctx.status = "SUCCESS"
    else:
        ctx.status = "BAN"
        # dừng theo logic
        # raise AssertionError("BAN")  # có thể bật nếu muốn dừng hẳn


@finalize
def done(ctx):
    return {
        "uuid": str(uuid.uuid4())[:8],
        "site": ctx.site,
        "http_traces": len(ctx.meta.get("http_trace") or []),
        "merchant": ctx.merchant,
        "checkout": ctx.checkout,
        # helpers
        "r_given_name": ctx.r_given_name,
        "r_family_name": ctx.r_family_name,
        "r_area_codes": ctx.r_area_codes,
        "ran_num": ctx.ran_num,
        "ran_5": ctx.ran_5,
        "NMM": ctx.NMM,
        # js parsed
        "ua": ctx.ua,
        "timezone_offset": ctx.timezone_offset,
        "screen_height": ctx.screen_height,
        "screen_width": ctx.screen_width,
        #"components0": ctx.components0,
        #"components1": ctx.components1,
        #"components2": ctx.components2,
        "fingerprintv1": ctx.fingerprintv1,
        "fingerprintv1SansUA": ctx.fingerprintv1SansUA,
        "fingerprintv2": ctx.fingerprintv2,
        "orderid": ctx.orderid,
        "location_id": ctx.location_id,
        "application_id": ctx.application_id,
        "client_id": ctx.client_id,
        "avt": ctx.avt,
        "sessionId": ctx.sessionId,
        "powPrefix": ctx.powPrefix,
        "instanceId": ctx.instanceId,
        "customerxsrf": ctx.customerxsrf,
        "decustomerxsrf": ctx.decustomerxsrf,
        "loyalty_programs": ctx.loyalty_programs,
    }


flow.register(globals())

if __name__ == "__main__":
    import json
    out = flow.run(data={}, session={"profile":"chrome_133"}, options={"httpVersion":"h2"})
    print(json.dumps(out, ensure_ascii=False, indent=2))


