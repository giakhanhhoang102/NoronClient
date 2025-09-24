// ===============================
// UUID v4 & v5 (RFC 4122) - Final
// ===============================

// ==== Cấu hình cho UUID v5 (đổi nếu cần) ====
const NAME = "example.com"; // tên dùng để tạo UUID v5
const NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"; // DNS namespace chuẩn (RFC 4122)

// ---- Helpers ----
const toHex2 = n => (n + 0x100).toString(16).slice(1);

function bytesToUuid(b) {
  return (
    toHex2(b[0]) + toHex2(b[1]) + toHex2(b[2]) + toHex2(b[3]) + "-" +
    toHex2(b[4]) + toHex2(b[5]) + "-" +
    toHex2(b[6]) + toHex2(b[7]) + "-" +
    toHex2(b[8]) + toHex2(b[9]) + "-" +
    toHex2(b[10]) + toHex2(b[11]) + toHex2(b[12]) + toHex2(b[13]) + toHex2(b[14]) + toHex2(b[15])
  );
}

function uuidToBytes(uuid) {
  const hex = String(uuid).replace(/-/g, "").toLowerCase();
  if (!/^[0-9a-f]{32}$/.test(hex)) throw new Error("Namespace UUID không hợp lệ");
  const out = new Uint8Array(16);
  for (let i = 0; i < 16; i++) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

function utf8Bytes(str) {
  if (typeof TextEncoder !== "undefined") return new TextEncoder().encode(str);
  const out = [];
  for (let i = 0; i < str.length; i++) {
    let c = str.charCodeAt(i);
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
    else if (c >= 0xd800 && c <= 0xdbff && i + 1 < str.length) {
      const c2 = str.charCodeAt(++i);
      const cp = 0x10000 + (((c & 0x3ff) << 10) | (c2 & 0x3ff));
      out.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3f), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
    } else out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
  }
  return new Uint8Array(out);
}

// ---- SHA-1 thuần JS, đồng bộ ----
function sha1(bytes) {
  function rol(n, b) { return ((n << b) | (n >>> (32 - b))) >>> 0; }
  const arr = Array.from(bytes);
  const bitLen = bytes.length * 8;

  // padding
  arr.push(0x80);
  while ((arr.length % 64) !== 56) arr.push(0x00);
  const hi = Math.floor(bitLen / 0x100000000) >>> 0;
  const lo = (bitLen >>> 0);
  arr.push((hi >>> 24) & 0xff, (hi >>> 16) & 0xff, (hi >>> 8) & 0xff, hi & 0xff);
  arr.push((lo >>> 24) & 0xff, (lo >>> 16) & 0xff, (lo >>> 8) & 0xff, lo & 0xff);

  // h init
  let h0 = 0x67452301 >>> 0,
      h1 = 0xEFCDAB89 >>> 0,
      h2 = 0x98BADCFE >>> 0,
      h3 = 0x10325476 >>> 0,
      h4 = 0xC3D2E1F0 >>> 0;

  for (let i = 0; i < arr.length; i += 64) {
    const w = new Array(80);
    for (let j = 0; j < 16; j++) {
      const off = i + j * 4;
      w[j] = ((arr[off] << 24) | (arr[off + 1] << 16) | (arr[off + 2] << 8) | (arr[off + 3])) >>> 0;
    }
    for (let j = 16; j < 80; j++) w[j] = rol(w[j - 3] ^ w[j - 8] ^ w[j - 14] ^ w[j - 16], 1) >>> 0;

    let a = h0, b = h1, c = h2, d = h3, e = h4;
    for (let j = 0; j < 80; j++) {
      let f, k;
      if (j < 20)      { f = (b & c) | ((~b) & d);             k = 0x5A827999; }
      else if (j < 40) { f = b ^ c ^ d;                        k = 0x6ED9EBA1; }
      else if (j < 60) { f = (b & c) | (b & d) | (c & d);      k = 0x8F1BBCDC; }
      else             { f = b ^ c ^ d;                        k = 0xCA62C1D6; }
      const temp = (rol(a, 5) + f + e + k + w[j]) >>> 0;
      e = d; d = c; c = rol(b, 30) >>> 0; b = a; a = temp;
    }
    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
  }

  const out = new Uint8Array(20);
  const hs = [h0, h1, h2, h3, h4];
  for (let i = 0; i < 5; i++) {
    out[i * 4 + 0] = (hs[i] >>> 24) & 0xff;
    out[i * 4 + 1] = (hs[i] >>> 16) & 0xff;
    out[i * 4 + 2] = (hs[i] >>> 8) & 0xff;
    out[i * 4 + 3] = (hs[i] & 0xff);
  }
  return out;
}

// ---- RNG 16 byte: ưu tiên CSPRNG, fallback an toàn ----
function getRandomBytes16() {
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    const rnd = new Uint8Array(16);
    crypto.getRandomValues(rnd);
    return rnd;
  }
  if (typeof require !== "undefined") {
    try {
      const nodeCrypto = require("crypto");
      return Uint8Array.from(nodeCrypto.randomBytes(16));
    } catch {}
  }
  // Fallback cuối (không CSPRNG)
  const rnd = new Uint8Array(16);
  for (let i = 0; i < 16; i++) rnd[i] = (Math.random() * 256) | 0;
  return rnd;
}

// ---- UUID v4 ----
function genUUIDv4() {
  const rnd = getRandomBytes16();
  rnd[6] = (rnd[6] & 0x0f) | 0x40; // version 4
  rnd[8] = (rnd[8] & 0x3f) | 0x80; // variant RFC 4122
  return bytesToUuid(rnd);
}

// ---- UUID v5 (SHA-1(namespace||name)) ----
function genUUIDv5(name, namespaceUuid) {
  const ns = uuidToBytes(namespaceUuid);
  const nameBytes = utf8Bytes(name);
  const input = new Uint8Array(ns.length + nameBytes.length);
  input.set(ns, 0);
  input.set(nameBytes, ns.length);

  const hash = sha1(input);       // 20 byte
  const bytes = hash.slice(0, 16); // lấy 16 byte đầu
  bytes[6] = (bytes[6] & 0x0f) | 0x50; // version 5
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // variant RFC 4122
  return bytesToUuid(bytes);
}

// ---- Sinh & gán biến theo yêu cầu ----
var uuidv4 = genUUIDv4();
var uuidv5 = genUUIDv5(NAME, NAMESPACE);

// ---- Gắn vào globalThis / window / global ----
try { globalThis.uuidv4 = uuidv4; globalThis.uuidv5 = uuidv5; } catch {}
if (typeof window !== "undefined" && window) {
  window.uuidv4 = uuidv4;
  window.uuidv5 = uuidv5;
}
if (typeof global !== "undefined" && global) {
  global.uuidv4 = uuidv4;
  global.uuidv5 = uuidv5;
}

// ---- Demo (tùy chọn) ----
console.log("uuidv4:", uuidv4);
console.log("uuidv5:", uuidv5);


















