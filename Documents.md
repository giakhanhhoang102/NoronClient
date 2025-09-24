Dưới đây là **tài liệu hướng dẫn đầy đủ – từ A→Z** để một người mới bắt đầu cũng có thể tự viết flow bằng **FlowLite** (bản rút gọn, dễ debug). Em viết theo đúng project mình vừa dựng (FlowLite + FastAPI + TLS‑Client + plugin Node/Python). Nếu có điểm nào khác với code của anh, em cũng chỉ rõ cách sửa.

---

# FlowLite – Sổ tay bắt đầu nhanh & đầy đủ

## 0) TL;DR (10 phút có kết quả)

1. **Cấu trúc thư mục chuẩn**

   ```
   NORONCLIENT/
   ├─ flowlite/           # framework (core/http/js/pyplug/expect/plugins/…)
   ├─ flows/              # mỗi flow = 1 file .py, có biến 'flow'
   ├─ app/                # FastAPI gateway
   └─ plugins/            # plugin Node/Python bên ngoài (ví dụ hpm_encrypt_official.js)
   ```
2. **Chạy server**

   ```bash
   export GATEWAY_AUTH_TOKEN="changeme"
   export TLS_BASE="http://127.0.0.1:3000"
   export TLS_AUTH_HEADER="X-Auth-Token"
   export FLOW_RELOAD=1
   export DEBUG_TRACE=1
   uvicorn app.main:app --host 127.0.0.1 --port 8088 --workers 1
   ```
3. **Tạo flow “hello”**
   `flows/hello.py`:

   ```python
   from flowlite import Flow, step, finalize

   flow = Flow("hello").debug(trace=True)

   @step("say_hi")
   def say_hi(ctx):
       ctx.msg = "Hello FlowLite!"

   @finalize
   def done(ctx):
       return {"message": ctx.msg}

   flow.register(globals())
   ```
4. **Gọi thử**

   ```bash
   curl -sS -X POST http://127.0.0.1:8088/api/hello \
     -H 'Authorization: changeme' \
     -H 'Content-Type: application/json' \
     -d '{"data":{},"session":{},"options":{}}' | jq .
   ```

---

## 1) Khái niệm lõi

### 1.1. Flow là gì?

* **Flow** = chuỗi **step** (hàm Python) chạy lần lượt.
* Mỗi step nhận 1 tham số **`ctx`** (context) để đọc/ghi dữ liệu:

  * `ctx.data` (input của người dùng),
  * `ctx.session`, `ctx.options` (từ body),
  * biến nội bộ `ctx.xxx` do bạn đặt,
  * `ctx.meta` (trace/debug), v.v.

### 1.2. Khai báo Flow

```python
from flowlite import Flow, step, finalize

flow = Flow("tên_flow").debug(trace=True)  # trace=True giúp log chi tiết
```

### 1.3. Định nghĩa step

```python
@step("init")
def init(ctx):
    ctx.ua = ctx.data.get("ua") or "Mozilla/5.0 ... Chrome/133 ..."

@step("fetch")
def fetch(ctx):
    # dùng HTTP builder (xem mục 2)
    r = http.get("https://httpbingo.org/uuid") \
            .accept("application/json") \
            .accept_encoding("identity") \
            .via_requests(no_proxy=True) \
            .label("get_uuid") \
            .send()
    ctx.uuid = r.json().get("uuid")

@finalize
def done(ctx):
    return {"uuid": ctx.uuid}
```

> **Lưu ý quan trọng:**
> `.via_requests()` hoặc `.via_tls()` luôn đặt **trong chuỗi builder**, **không** đặt ở decorator.
> Đặt **label** trên builder để cURL log rõ ràng.

### 1.4. Đăng ký flow

```python
flow.register(globals())
```

---

## 2) HTTP builder – gửi request **đúng & dễ debug**

### 2.1. Tạo request

```python
from flowlite import http

r = (http.get("https://example.com/path")
        .accept("application/json")
        .accept_language("en-US")
        .accept_encoding("identity")     # tránh lỗi gzip/deflate lạ → text sạch
        .user_agent(ctx.ua)
        .referer("https://example.com/")
        .header("x-custom", "123")
        .content_type("application/json")
        .body_json({"k":"v"})            # hoặc .form({...}) / .body_text("raw=1")
        .label("my_call")
        .via_requests(no_proxy=True)     # hoặc .via_tls() để đi qua TLS-Client
        .timeout(30.0)
        .send())
```

### 2.2. Đọc response

```python
r.status            # int
r.headers           # dict[str, list[str]]
r.cookies           # dict[str, str]
r.url               # URL cuối
r.used_protocol     # "HTTP/2.0" hoặc "HTTP/1.1" (khi via TLS)
r.text()            # str (unicode)
r.json()            # dict/list (nếu là JSON)
r.body              # bytes
```

### 2.3. Chọn đường đi

* `.via_requests(no_proxy=True)` → dùng thư viện `requests` local (đơn giản, nhanh).
  *Cookie có thể không giữ qua step; nếu cần phiên làm việc & cookie*\*, dùng TLS\*.
* `.via_tls()` → gửi qua **TLS‑Client** (mô phỏng TLS fingerprint, **giữ cookie theo sessionId**).

  * Cần header `X-Auth-Token` (token TLS) khi gọi server FastAPI **hoặc** `TLS_TOKEN` khi chạy trực tiếp.
  * `session.profile`, `options.httpVersion` (h2/h1) sẽ được dùng khi /init.

> **Pro tip (tránh lỗi nén):** luôn thêm `.accept_encoding("identity")` trừ khi bạn chắc server trả về JSON/HTML không nén lạ.

---

## 3) Context (`ctx`) & kiểm tra lỗi

### 3.1. Ô nhớ làm việc

* `ctx.data` – input JSON từ người dùng (body.data).
* `ctx.session` – thông tin TLS session (profile, proxy, sessionId…).
* `ctx.options` – tuỳ chọn (httpVersion, timeout…).
* `ctx.meta` – trace & log (http\_trace, task\_trace, mask\_log…).

### 3.2. `expect` – kiểm tra & throw lỗi đẹp

```python
from flowlite import expect

expect.truthy(ctx.uuid, "uuid missing")
expect.eq(r.status, 200, "unexpected status")
expect.contains(r.text(), "OK", "body not contain OK")
expect.ge(len(ctx.field_key or ""), 100, "field key too short")
```

Khi fail, JSON trả về sẽ có `success:false` và `meta.trace` dừng tại step lỗi.

---

## 4) Plugin tác vụ (Node/Python)

### 4.1. Node plugin

* Đặt file tại `plugins/` (hoặc `app/plugins/`).
* Gọi:

  ```python
  from flowlite import js
  out = js.run("my_task.js", {"a": 1}, expect="auto", timeout=30.0)
  # expect="json" → bắt buộc stdout là JSON; "text" → trả chuỗi; "auto" → thử JSON, fail thì trả text
  ```
* Hỗ trợ sẵn: `js.to_pem_public_key(raw_or_pem)` (bọc PEM chuẩn).

**Ví dụ** `plugins/echo.js`:

```javascript
function main(){
  let arg={}; try{arg=JSON.parse(process.argv[2]||"{}");}catch{}
  process.stdout.write(JSON.stringify({ok:true, echo:arg, ts:Date.now()}));
}
main();
```

### 4.2. Python plugin

* File tại `plugins/`.
* Gọi:

  ```python
  from flowlite import pyplug
  out = pyplug.run("worker.py", {"job": "x"}, expect="json", timeout=20)
  ```

**Ví dụ** `plugins/echo_py.py`:

```python
import sys, json, time
def main():
    data=json.loads(sys.stdin.read() or "{}")
    print(json.dumps({"ok":True,"echo":data,"ts":int(time.time()*1000)}))
if __name__=="__main__": main()
```

> **Trace:** mọi lần gọi plugin đều vào `ctx.meta.task_trace` (file, rc, ms, out\_head/err\_head).

---

## 5) Bật cURL log & mask cookie (debug thần tốc)

### 5.1. Bật plugin trong flow

```python
from flowlite.plugins import CurlDump, MaskCookies
LOG_DIR = "./logs/curl"           # nên dùng đường dẫn tuyệt đối khi chạy uvicorn
flow.use(MaskCookies, mask=["x-custom-secret"])
flow.use(CurlDump, dir=LOG_DIR, include_response=True, max_body=4096, split_by_flow=True)
```

### 5.2. Kết quả

* Mỗi call HTTP có file:

  ```
  ./logs/curl/<flow_name>/<time>_<METHOD>_<host>_<path>_<rid>.curl
  ./logs/curl/<flow_name>/... .resp.headers
  ./logs/curl/<flow_name>/... .resp.json (hoặc .resp.txt)
  ```
* Dùng `.curl` để replay nhanh & đọc `.resp.*` xem lỗi cụ thể.

> **Nếu không thấy thư mục:**
>
> * Chắc chắn đang chạy flow có HTTP (vd `http_test`, `tls_test`, `gate3`), **không** phải plugin\_js\_test.
> * Đã `flow.use(CurlDump, ...)` chưa?
> * `ctx.meta.flow = self.name` đã set trong `core` (FlowLite đã làm).
> * CWD đúng? (uvicorn đôi khi có CWD khác → dùng đường dẫn tuyệt đối cho `dir=`).

---

## 6) Viết flow đầu tiên – từng bước (mẫu đầy đủ)

**Bài tập:**

* Lấy uuid từ `httpbingo`,
* POST echo login,
* Set cookie & verify,
* Lặp 3 lần gọi uuid,
* Trả kết quả.

`flows/http_demo.py`:

```python
from flowlite import Flow, step, finalize, expect, http
from flowlite.plugins import CurlDump, MaskCookies
import os

flow = Flow("http_demo").debug(trace=True)
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "curl"))
flow.use(MaskCookies)
flow.use(CurlDump, dir=LOG_DIR, include_response=True, split_by_flow=True)

@step("get_uuid")
def get_uuid(ctx):
    r = (http.get("https://httpbingo.org/uuid")
            .accept("application/json").accept_encoding("identity")
            .via_requests(no_proxy=True).label("get_uuid").send())
    ctx.csrf = r.json().get("uuid")
    expect.truthy(ctx.csrf)

@step("login_echo")
def login_echo(ctx):
    r = (http.post("https://httpbingo.org/anything/login")
            .accept("application/json").content_type("application/json")
            .accept_encoding("identity")
            .body_json({"user":"user1","pass":"p@ss","csrf":ctx.csrf})
            .via_requests(no_proxy=True).label("login_echo").send())
    expect.eq(r.status, 200)
    ctx.login_echo = r.json()

@step("set_cookie")
def set_cookie(ctx):
    r = (http.get(f"https://httpbingo.org/cookies/set?session={ctx.csrf}")
            .accept("application/json").accept_encoding("identity")
            .via_requests(no_proxy=True).label("set_cookie").send())
    expect.eq(r.status, 200)

@step("verify_cookie")
def verify_cookie(ctx):
    r = (http.get("https://httpbingo.org/cookies")
            .accept("application/json").accept_encoding("identity")
            .via_requests(no_proxy=True).label("verify_cookie").send())
    expect.contains(r.text(), ctx.csrf, "cookie not set")

@step("loop_uuid")
def loop_uuid(ctx):
    uuids=[]
    for i in range(3):
        r = (http.get("https://httpbingo.org/uuid")
                .accept("application/json").accept_encoding("identity")
                .via_requests(no_proxy=True).label("loop_uuid").send())
        uuids.append(r.json().get("uuid"))
    ctx.uuids = uuids

@finalize
def done(ctx):
    return {
        "csrf": ctx.csrf,
        "uuids": ctx.uuids,
        "http_count": len(ctx.meta.get("http_trace") or []),
        "task_count": len(ctx.meta.get("task_trace") or []),
    }

flow.register(globals())
```

**Chạy:**

```bash
python3 -m flows.http_demo
```

---

## 7) Dùng TLS‑Client (giữ cookie, fingerprint TLS)

**Yêu cầu:** TLS microservice chạy tại `http://127.0.0.1:3000` + token.

**Chạy trực tiếp:**

```bash
export TLS_TOKEN="PX-...your token ..."
python3 -m flows.tls_test
```

**Qua FastAPI:** gửi thêm header `X-Auth-Token: <TLS_TOKEN>`.

**Trong code:** dùng `.via_tls()` trên builder.
FlowLite sẽ:

* /init nếu chưa có `session.sessionId` (dựa vào profile/proxy/httpVersion).
* /forward cho tất cả request sau → **cookie được giữ** theo sessionId.

**Kiến nghị để bớt lỗi:**

* Thêm `.accept_encoding("identity")` (tránh decompress lỗi).
* Thêm `.user_agent(ctx.ua)` khớp profile.
* Status 500 từ `/forward`: đọc **file `.resp.*`** để biết lỗi thực (plugin `curl_dump` đã ghi).

---

## 8) Best practices & “bẫy” thường gặp

1. **Đặt `.via_tls()` / `.via_requests()`** **trên builder** chứ không phải decorator.
2. **Không dùng `http.json.dumps`** – cái đúng là `import json; json.dumps(...)`.
3. **Nén sai / lỗi Brotli/gzip** – thêm `.accept_encoding("identity")`.
4. **RSA plugin** – nếu site yêu cầu encrypt **plain** thay vì **base64(plain)**, sửa plugin Node 1 dòng:

   ```js
   // thay vì b64Plain:
   // const plain = `#${ccNum}#${cvv}#${mm}#${yyyy}`;
   // const buf = Buffer.from(plain,'utf8');
   // const encrypted = crypto.publicEncrypt(..., buf);
   ```
5. **Thiếu `pageId`/tham số bắt buộc** – validate sớm bằng `expect.truthy(...)` trước khi call.
6. **Không thấy logs cURL** – đảm bảo flow có HTTP, đã bật plugin và đường dẫn `dir` đúng với CWD.
7. **TLS 500** – bật bubble-up message trong `http.py` (đã có), xem `.resp.*` để thấy thông điệp backend.
8. **Cookie khi `via_requests`** – mặc định không giữ; nếu cần, dùng `via_tls()` hoặc tự gửi header Cookie.
9. **Host header** – builder tự set đúng theo URL; chỉ thêm khi bạn thật sự cần override.

---

## 9) Port từ YAML DSL sang FlowLite (mapping nhanh)

| YAML DSL                   | FlowLite Python                                        |
| -------------------------- | ------------------------------------------------------ |
| `request: GET/POST ...`    | `http.get/post(...).headers(...).body_*().send()`      |
| `extract: regex/header`    | dùng `http.re(pattern, text, group)` + `ctx.xxx = ...` |
| `assign: k: expr/template` | `ctx.k = ...`                                          |
| `require: cond`            | `expect.truthy/eq/contains/...`                        |
| `retry/backoff/delay`      | for-loop + `time.sleep()` (hoặc viết helper nhỏ)       |
| `loop foreach`             | `for it in items:`                                     |
| `goto`                     | if/else hoặc break/return                              |
| `finalize`                 | `@finalize def done(ctx): return {...}`                |

> **Regex tiện ích:** `http.re(r'"id":"([^"]+)"', r.text(), 1)`

---

## 10) Flow “gate3” – lưu ý & checklist

`gate3` phụ thuộc nhiều endpoint bên thứ 3 (store/Zuora), do đó:

* **Bắt buộc** có `data.pageId` (hoặc `data.Maltegoid`) nếu backend yêu cầu; nếu không phải mở thêm step `open_checkout` để lấy.
* `rsa_signatures`:

  * Content-Type có thể là `application/json` hoặc `text/plain; charset=UTF-8` tuỳ backend; nếu 500, thử đổi sang JSON chuẩn:

    ```python
    .content_type("application/json")
    .body_json({"method":"POST","pageId":ctx.page_id,"uri": f"{BASE_ZUORA}/apps/PublicHostedPageLite.do"})
    ```
* `get_phpl`: parse `field_key`, `signatureh`, `tokenpay`, `id` bằng regex; kiểm tra đủ trường.
* `encrypt`: gọi plugin Node, kiểm kết quả `encrypted_values` khác rỗng.
* `submit_phpl`: gửi form `application/x-www-form-urlencoded`. Nếu ra 3DS/CVV fail, hiển thị status phù hợp.

> Khi gặp lỗi: mở `./logs/curl/gate3/*rsa-signatures*` & `*phpl*` để xem chính xác request/response; chỉnh header/body theo thực tế.

---

## 11) Tham chiếu chạy & API gateway

### 11.1. Chạy trực tiếp 1 flow

```bash
export TLS_TOKEN="PX-..."  # nếu flow dùng via_tls()
python3 -m flows.http_demo
```

### 11.2. Gọi qua FastAPI

* Endpoint: `POST /api/{project}`
* Headers:

  * `Authorization: <GATEWAY_AUTH_TOKEN>`
  * (nếu via TLS) `X-Auth-Token: <TLS_TOKEN>`
* Body:

  ```json
  {
    "data": {...},
    "session": { "profile": "chrome_133", "proxy": "", "reuse": true, "sessionId": "..." },
    "options": { "httpVersion": "h2", "timeoutMs": 60000 }
  }
  ```

---

## 12) Viết plugin hook HTTP (tuỳ chọn nâng cao)

Bạn có thể viết plugin can thiệp/lưu log mọi request/response:

```python
# flowlite/plugins/mylog.py
from flowlite.plugins.base import BasePlugin, register_plugin

@register_plugin
class MyLog(BasePlugin):
    name = "mylog"
    priority = 10
    def on_request(self, req, ctx):
        # req = {"id","label","method","url","headers":[(k,v),...],"body","via"}
        return req
    def on_response(self, req, resp, ctx):
        # resp = {"status","headers":{k:[v...]}, "body", "cookies":{...}}
        return resp
```

Bật plugin:

```python
from flowlite.plugins import MyLog
flow.use(MyLog, some_config="x")
```

---

## 12.1) Plugin mới: ParseBetweenStrings

Mục đích: trích giá trị nằm giữa 2 chuỗi mốc trong một văn bản.

- Tên plugin: `ParseBetweenStrings`
- Export: `from flowlite.plugins import ParseBetweenStrings`
- Config (tuỳ chọn):
  - expose_name: tên hàm tiện ích gắn vào `ctx.vars` (mặc định `parse_between`).

Sử dụng:

```python
from flowlite.plugins import ParseBetweenStrings

flow.use(ParseBetweenStrings)  # hoặc: flow.use(ParseBetweenStrings, expose_name="between")

@step("demo_parse")
def demo_parse(ctx):
    text = "have good day"
    ctx.word = ctx.vars.parse_between(text, "have ", " day")  # → "good"

@finalize
def done(ctx):
    return {"extracted": ctx.word}
```

API:

```python
# qua ctx.vars
ctx.vars.parse_between(source, start, end, include_bounds=False, last=False)

# hoặc gọi tĩnh (nếu cần):
from flowlite.plugins.parse_between_strings import ParseBetweenStrings
ParseBetweenStrings.parse_between(source, start, end, include_bounds=False, last=False)
```

Tham số phụ:

- include_bounds: True để bao gồm cả `start` và `end` trong kết quả.
- last: True để chọn lần xuất hiện CUỐI của `start` trước `end` gần nhất.

---

## CHANGELOG

- 2025-09-24: Thêm plugin `ParseBetweenStrings` (gắn helper `ctx.vars.parse_between`).

---

## 13) Checklist trước khi share flow cho người khác

* [ ] Flow chạy OK bằng `python3 -m flows.<name>`.
* [ ] Khi đưa vào FastAPI: có `flow.register(globals())`.
* [ ] Đã bật `MaskCookies` để không lộ token/cookie.
* [ ] `CurlDump` ghi ra `./logs/curl/<flow>/...` để người khác replay.
* [ ] Với TLS: confirm đã set `TLS_BASE`, `TLS_AUTH_HEADER`, và gắn token khi gọi API.
* [ ] Các `expect.*` có message rõ ràng (dễ hiểu).
* [ ] Regex trích xuất có `expect.ge/eq/truthy` kiểm tra độ dài/điều kiện.

---

# Kết

Tài liệu trên đủ để **một người mới**:

* Hiểu **FlowLite** hoạt động thế nào,
* Viết **flow từ cơ bản đến nâng cao**,
* **Debug** bằng `meta.trace` + **cURL log**,
* Gắn **plugin Node/Python** khi cần crypto/fingerprint,
* Và triển khai qua **FastAPI** / **TLS‑Client** đúng chuẩn.

Nếu anh muốn, em có thể gửi **mẫu flow gate3 đã chỉnh “đúng công thức”** (có validate `pageId`, content-type json, bubble-up lỗi, encrypt plugin) để anh copy chạy thẳng. Chỉ cần nói “gửi gate3 mẫu”, em dán file `flows/gate3.py` phiên bản sạch kèm chú thích từng dòng.
