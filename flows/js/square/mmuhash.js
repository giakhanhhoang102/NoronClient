
/* =========================
 * MurmurHash3 x64 128-bit
 * (BigInt, UTF-8 input)
 * ========================= */
function toUtf8Bytes(str) {
    if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(str);
    // Fallback UTF‑8 encode
    const s = unescape(encodeURIComponent(str));
    const out = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
    return out;
  }
  function rotl64(x, r) {
    const MASK = (1n << 64n) - 1n;
    return ((x << r) & MASK) | (x >> (64n - r));
  }
  function fmix64(k) {
    const MASK = (1n << 64n) - 1n;
    k ^= k >> 33n;
    k = (k * 0xff51afd7ed558ccdn) & MASK;
    k ^= k >> 33n;
    k = (k * 0xc4ceb9fe1a85ec53n) & MASK;
    k ^= k >> 33n;
    return k & MASK;
  }
  function murmurhash3_x64_128_hex(input, seed = 0) {
    const data = toUtf8Bytes(input);
    const MASK = (1n << 64n) - 1n;
    const c1 = 0x87c37b91114253d5n;
    const c2 = 0x4cf5ad432745937fn;
    let h1 = BigInt(seed) & MASK;
    let h2 = BigInt(seed) & MASK;
  
    const nblocks = Math.floor(data.length / 16);
    for (let i = 0; i < nblocks; i++) {
      const b = i * 16;
      let k1 =
        (BigInt(data[b + 0])      ) |
        (BigInt(data[b + 1]) <<  8n) |
        (BigInt(data[b + 2]) << 16n) |
        (BigInt(data[b + 3]) << 24n) |
        (BigInt(data[b + 4]) << 32n) |
        (BigInt(data[b + 5]) << 40n) |
        (BigInt(data[b + 6]) << 48n) |
        (BigInt(data[b + 7]) << 56n);
      let k2 =
        (BigInt(data[b +  8])      ) |
        (BigInt(data[b +  9]) <<  8n) |
        (BigInt(data[b + 10]) << 16n) |
        (BigInt(data[b + 11]) << 24n) |
        (BigInt(data[b + 12]) << 32n) |
        (BigInt(data[b + 13]) << 40n) |
        (BigInt(data[b + 14]) << 48n) |
        (BigInt(data[b + 15]) << 56n);
  
      k1 = (k1 * c1) & MASK; k1 = rotl64(k1, 31n); k1 = (k1 * c2) & MASK; h1 ^= k1;
      h1 = rotl64(h1, 27n); h1 = (h1 + h2) & MASK; h1 = (h1 * 5n + 0x52dce729n) & MASK;
  
      k2 = (k2 * c2) & MASK; k2 = rotl64(k2, 33n); k2 = (k2 * c1) & MASK; h2 ^= k2;
      h2 = rotl64(h2, 31n); h2 = (h2 + h1) & MASK; h2 = (h2 * 5n + 0x38495ab5n) & MASK;
    }
  
    // tail
    const tail = data.slice(nblocks * 16);
    let k1t = 0n, k2t = 0n;
    if (tail.length >= 9) {
      k2t ^= BigInt(tail[8]) << 0n;
      if (tail.length >=10) k2t ^= BigInt(tail[9])  <<  8n;
      if (tail.length >=11) k2t ^= BigInt(tail[10]) << 16n;
      if (tail.length >=12) k2t ^= BigInt(tail[11]) << 24n;
      if (tail.length >=13) k2t ^= BigInt(tail[12]) << 32n;
      if (tail.length >=14) k2t ^= BigInt(tail[13]) << 40n;
      if (tail.length >=15) k2t ^= BigInt(tail[14]) << 48n;
      k2t = (k2t * c2) & MASK; k2t = rotl64(k2t, 33n); k2t = (k2t * c1) & MASK; h2 ^= k2t;
    }
    if (tail.length >= 1) {
      k1t ^= BigInt(tail[0]) << 0n;
      if (tail.length >= 2) k1t ^= BigInt(tail[1]) <<  8n;
      if (tail.length >= 3) k1t ^= BigInt(tail[2]) << 16n;
      if (tail.length >= 4) k1t ^= BigInt(tail[3]) << 24n;
      if (tail.length >= 5) k1t ^= BigInt(tail[4]) << 32n;
      if (tail.length >= 6) k1t ^= BigInt(tail[5]) << 40n;
      if (tail.length >= 7) k1t ^= BigInt(tail[6]) << 48n;
      if (tail.length >= 8) k1t ^= BigInt(tail[7]) << 56n;
      k1t = (k1t * c1) & MASK; k1t = rotl64(k1t, 31n); k1t = (k1t * c2) & MASK; h1 ^= k1t;
    }
  
    const len = BigInt(data.length);
    h1 ^= len; h2 ^= len;
    h1 = (h1 + h2) & MASK;
    h2 = (h2 + h1) & MASK;
    h1 = fmix64(h1);
    h2 = fmix64(h2);
    h1 = (h1 + h2) & MASK;
    h2 = (h2 + h1) & MASK;
  
    const toHexBE = (x) => {
      const bytes = [];
      for (let i = 7; i >= 0; i--) bytes.push(Number((x >> (BigInt(i)*8n)) & 0xffn));
      return bytes.map(b => b.toString(16).padStart(2, '0')).join('');
    };
    return (toHexBE(h1) + toHexBE(h2)).toLowerCase();
  }
  
  // ==== PROBE fingerprint-v2 ====
  
  // ==== PROBE fingerprint-v2 (in đầy đủ danh sách key thiếu, thử undefined + error) ====
  
  // Danh sách khóa fingerprint-v2 thường có trong 0.js (có thể khác theo phiên bản)
  const KNOWN_V2_KEYS = [
      'audio',
      'canvas',
      'color_gamut',
      'contrast',
      'device_memory',
      'dom_blockers',
      'font_preferences',
      'fonts',
      'forced_colors',
      'hardware_concurrency',
      'hdr',
      'indexed_db',
      'inverted_colors',
      'languages',
      'math',
      'monochrome',
      'open_database',
      'pdf_viewer_enabled',
      'platform',
      'plugins',
      'screen_frame',
      'screen_resolution',
      'timezone',
      'touch_support',
      'vendor_flavors',
      'video_card',
      'reduced_motion'
    ];
    
    // Một số khóa có khả năng “lỗi” (thay vì undefined) tuỳ môi trường
    const CANDIDATE_ERROR_KEYS = ['audio', 'canvas', 'dom_blockers', 'video_card'];
    
    function escapeKeyV2(key) {
      return key.replace(/([:|\\])/g, '\\$1');
    }
    
    /**
     * Build chuỗi vào băm cho v2:
     *  - valuesDict: dict các value hiện có (đọc từ JSON components)
     *  - includeAsUndefined: mảng key sẽ xuất hiện với dạng `key:undefined`
     *  - forceErrorKeys: mảng key sẽ xuất hiện với dạng `key:error`
     *  - seed dùng ở hàm băm sẽ set bên ngoài
     */
    function buildV2StringFromPlain(valuesDict, includeAsUndefined = [], forceErrorKeys = []) {
      const includeUndef = new Set(includeAsUndefined);
      const forceErr = new Set(forceErrorKeys);
    
      const keys = Array.from(new Set([
        ...Object.keys(valuesDict),
        ...includeAsUndefined,
        ...forceErrorKeys
      ])).sort();
    
      const parts = [];
      for (const k of keys) {
        const kk = escapeKeyV2(k);
        if (forceErr.has(k)) {
          parts.push(`${kk}:error`);                 // đúng định dạng v2 khi component báo lỗi
        } else if (includeUndef.has(k) && !valuesDict.hasOwnProperty(k)) {
          parts.push(`${kk}:undefined`);             // chèn khóa bị thiếu theo cách v2
        } else {
          parts.push(`${kk}:${JSON.stringify(valuesDict[k])}`);
        }
      }
      return parts.join('|');
    }
    
    function hashV2FromPlain(valuesDict, includeAsUndefined = [], forceErrorKeys = [], seed = 0) {
      const s = buildV2StringFromPlain(valuesDict, includeAsUndefined, forceErrorKeys);
      return murmurhash3_x64_128_hex(s, seed);
    }
    
    /**
     * In danh sách key thiếu so với KNOWN_V2_KEYS (để anh nhìn rõ ngay)
     */
    function printMissingV2Keys(valuesDict) {
      const present = new Set(Object.keys(valuesDict));
      const missing = KNOWN_V2_KEYS.filter(k => !present.has(k));
      console.log(`[probe] Missing keys (${missing.length}): [${missing.join(', ')}]`);
      return missing;
    }
    
    /**
     * Dò tìm:
     * 1) Thử chèn toàn bộ missing = undefined (seed 0, 31)
     * 2) Nếu không khớp, vét cạn subset của missing (giới hạn combos)
     * 3) Nếu vẫn chưa, thử thêm các tổ hợp error cho CANDIDATE_ERROR_KEYS (ít key nên rẻ)
     */
    function probeV2Advanced(valuesDict, expected, {
      seeds = [0, 31],
      maxUndefCombos = 1 << 16,    // tối đa 65536 tổ hợp undefined (đủ rộng cho missing nhỏ)
      maxErrorCombos = 1 << 6      // tối đa 64 tổ hợp error (4 key -> 16 combos là đủ)
    } = {}) {
      const missing = printMissingV2Keys(valuesDict);
    
      // 1) All missing -> undefined
      for (const seed of seeds) {
        const h = hashV2FromPlain(valuesDict, missing, [], seed);
        if (h === expected) {
          return { ok: true, seed, includeUndef: missing, errorKeys: [], strategy: 'ALL_MISSING' };
        }
      }
    
      // 2) Thử subset của missing (undefined)
      const m = missing.length;
      const totalUndefCombos = Math.min(1 << Math.min(m, 20), maxUndefCombos);
      for (let mask = 0; mask < totalUndefCombos; mask++) {
        const include = [];
        for (let i = 0; i < m; i++) if (mask & (1 << i)) include.push(missing[i]);
    
        // Với mỗi subset undefined, thử thêm tổ hợp error nhỏ (bước 3 gộp luôn vào đây)
        const eKeys = CANDIDATE_ERROR_KEYS.filter(k => !valuesDict.hasOwnProperty(k));
        const eCount = Math.min(eKeys.length, 6);
        const totalErrCombos = Math.min(1 << eCount, maxErrorCombos);
    
        for (let emask = 0; emask < totalErrCombos; emask++) {
          const errors = [];
          for (let j = 0; j < eCount; j++) if (emask & (1 << j)) errors.push(eKeys[j]);
    
          for (const seed of seeds) {
            const h = hashV2FromPlain(valuesDict, include, errors, seed);
            if (h === expected) {
              return { ok: true, seed, includeUndef: include, errorKeys: errors, strategy: 'SUBSET+ERROR' };
            }
          }
        }
      }
    
      return { ok: false, triedUndef: totalUndefCombos };
    }
    
    
  
  /* =========================
   * V1 / V1‑sans‑ua (FPJS2)
   * ========================= */
  const ORDER_V1_BASE = [
    'language',
    'resolution',
    'available_resolution',
    'timezone_offset',
    'navigator_platform',
    'regular_plugins',
    'adblock',
    'touch_support',
    'js_fonts',
  ];
  function normalizeV1Value(v) {
    if (Array.isArray(v)) return v.map(x => String(x)).join(';');
    return String(v);
  }
  function buildV1String(map, includeUA) {
    const order = includeUA ? ['user_agent', ...ORDER_V1_BASE] : ORDER_V1_BASE;
    const values = [];
    for (const k of order) {
      if (Object.prototype.hasOwnProperty.call(map, k)) {
        values.push(normalizeV1Value(map[k]));
      }
    }
    return values.join('~~~'); // v1 uses "~~~" between components
  }
  function hashV1(map)         { return murmurhash3_x64_128_hex(buildV1String(map, true),  31); }
  function hashV1SansUA(map)   { return murmurhash3_x64_128_hex(buildV1String(map, false), 31); }
  
  /* =========================
   * V2 (FPJS v3 hashing)
   * ========================= */
  function escapeKey(key) {
    return key.replace(/([:|\\])/g, '\\$1');
  }
  function buildV2String(map) {
    const keys = Object.keys(map).sort();
    const parts = [];
    for (const k of keys) {
      parts.push(`${escapeKey(k)}:${JSON.stringify(map[k])}`);
    }
    return parts.join('|');
  }
  function hashV2(map) { return murmurhash3_x64_128_hex(buildV2String(map), 0); }
  
  /* =========================
   * Runner
   * ========================= */
  function main() {
    let data;
    // Ưu tiên lấy JSON trực tiếp từ argv[2]
    try {
      const arg = process.argv[2];
      if (arg && arg.trim().startsWith('{')) {
        data = JSON.parse(arg);
      } else if (arg) {
        // Nếu là path, đọc file
        const fs = require('fs');
        const path = require('path');
        const p = path.isAbsolute(arg) ? arg : path.join(process.cwd(), arg);
        const content = fs.readFileSync(p, 'utf8');
        data = JSON.parse(content);
      }
    } catch (_) {}
    // Nếu input là dạng { result: "<json string>" } thì bóc tách
    try {
      if (data && typeof data === 'object' && typeof data.result === 'string') {
        data = JSON.parse(data.result);
      }
    } catch (_) {}
    // Nếu vẫn chưa có, báo lỗi rõ ràng
    if (!data) {
      console.error('No input JSON provided to mmuhash.js');
      process.exit(1);
    }
    
    if (!data || !Array.isArray(data.fingerprints)) {
      console.error('Dữ liệu cần có cấu trúc: { "fingerprints": [ {components, fingerprint, version}, ... ] }');
      process.exit(1);
    }
  
    // Khởi tạo biến fingerprint để lưu tất cả kết quả
    const fingerprint = {
      v1: null,
      v1SansUA: null,
      v2: null,
      results: []
    };
  
    data.fingerprints.forEach((row, idx) => {
      let compObj;
      try {
        compObj = typeof row.components === 'string' ? JSON.parse(row.components) : row.components;
      } catch (e) { return; }
  
      let got = '';
      switch (row.version) {
        case 'fingerprint-v1':
          got = hashV1(compObj);
          fingerprint.v1 = got;
          break;
        case 'fingerprint-v1-sans-ua':
          got = hashV1SansUA(compObj);
          fingerprint.v1SansUA = got;
          break;
        case 'fingerprint-v2': {
          // Tính theo pipeline chuẩn trước
          got = hashV2(compObj);
  
          if (got !== row.fingerprint) {
            const pr = probeV2Advanced(compObj, row.fingerprint);
            if (pr.ok) {
              got = hashV2FromPlain(compObj, pr.includeUndef, pr.errorKeys, pr.seed);
            }
          }
          fingerprint.v2 = got;
          break;
        }
  
        default:
          console.log(`[${idx}] Version không hỗ trợ: ${row.version}`);
          return;
      }
      
      const ok = (got === row.fingerprint);
      const result = {
        version: row.version,
        expected: row.fingerprint,
        calculated: got,
        match: ok,
        index: idx
      };
      
      fingerprint.results.push(result);
      
      // bỏ in log ra stdout để caller parse JSON sạch
    });
  
    // In JSON sạch duy nhất ra stdout
    try { if (typeof process !== 'undefined' && process.stdout) { process.stdout.write(JSON.stringify(fingerprint)); } } catch {}
  }
  
  // Chạy main function nếu có biến result (OpenBullet) hoặc khi chạy trực tiếp
  if (typeof result !== 'undefined' || require.main === module) {
    main();
  }
  
  
  
  
  
  
  
  
  
  
  
  
  