// ===================== iPhone Fingerprint Generator v2 =====================
// Đảm bảo các biến trùng nhau giữa V1, V1-sans-ua, V2 có giá trị giống nhau

// Khởi tạo biến ngay lập tức
var result = null;

// Utility Functions
function randomChoice(array) {
  return array[Math.floor(Math.random() * array.length)];
}

function randomInt(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randomFloat(min, max, decimals = 2) {
  return parseFloat((Math.random() * (max - min) + min).toFixed(decimals));
}

function randomBase64(length) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

function simpleHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(16);
}

function generateFingerprint(components, version) {
  const str = JSON.stringify(components);
  const hash = simpleHash(str);
  return hash.padStart(32, '0');
}

// Data Arrays
const USER_AGENTS = [
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.7 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.2 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.8 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.7 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.6 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.4 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.3 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.8 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.7 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.6 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 14_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.5 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 14_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.4 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 14_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.3 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 14_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.2 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 14_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 13_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.7 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 13_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.6 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 13_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.5 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 13_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.4 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 13_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.3 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.2 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 13_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 13_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 12_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.5 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 12_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.4 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 12_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.3 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.2 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 12_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 12_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 11_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.4 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 11_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.3 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 11_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.2 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 11_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.1 Mobile/15E148 Safari/604.1",
  "Mozilla/5.0 (iPhone; CPU iPhone OS 11_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/11.0 Mobile/15E148 Safari/604.1"
];

const LANGUAGES = [
  "en-US", "en-GB", "en-CA", "en-AU", "en-NZ",
  "es-ES", "es-MX", "es-AR", "es-CO", "es-PE",
  "fr-FR", "fr-CA", "fr-BE", "fr-CH",
  "de-DE", "de-AT", "de-CH",
  "it-IT", "it-CH",
  "pt-BR", "pt-PT",
  "ru-RU", "ru-BY", "ru-KZ",
  "zh-CN", "zh-TW", "zh-HK",
  "ja-JP", "ko-KR", "th-TH", "vi-VN"
];

const PLATFORMS = [
  "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone",
  "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone",
  "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone",
  "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone",
  "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone", "iPhone"
];

const SCREEN_RESOLUTIONS = [
  // iPhone resolutions (width x height)
  [375, 667],   // iPhone 6/7/8
  [414, 736],   // iPhone 6/7/8 Plus
  [375, 812],   // iPhone X/XS/11 Pro
  [414, 896],   // iPhone XR/11
  [390, 844],   // iPhone 12/13 mini
  [428, 926],   // iPhone 12/13 Pro Max
  [375, 667],   // iPhone SE (2nd gen)
  [390, 844],   // iPhone 14
  [428, 926],   // iPhone 14 Plus
  [393, 852],   // iPhone 14 Pro
  [430, 932],   // iPhone 14 Pro Max
  [393, 852],   // iPhone 15
  [430, 932],   // iPhone 15 Plus
  [393, 852],   // iPhone 15 Pro
  [430, 932],   // iPhone 15 Pro Max
  [375, 667],   // iPhone SE (3rd gen)
  [414, 736],   // iPhone 6s Plus
  [375, 667],   // iPhone 6s
  [414, 736],   // iPhone 7 Plus
  [375, 667],   // iPhone 7
  [414, 736],   // iPhone 8 Plus
  [375, 667],   // iPhone 8
  [375, 812],   // iPhone XS
  [414, 896],   // iPhone XS Max
  [375, 812],   // iPhone 11 Pro
  [414, 896],   // iPhone 11
  [390, 844],   // iPhone 12 mini
  [390, 844],   // iPhone 12
  [390, 844],   // iPhone 12 Pro
  [428, 926],   // iPhone 12 Pro Max
  [390, 844],   // iPhone 13 mini
  [390, 844],   // iPhone 13
  [390, 844],   // iPhone 13 Pro
  [428, 926],   // iPhone 13 Pro Max
  [375, 667],   // iPhone SE (1st gen)
  [320, 568],   // iPhone 5/5s/5c
  [320, 480],   // iPhone 4/4s
  [480, 320],   // iPhone 3G/3GS
  [375, 667],   // iPhone 6/7/8 (duplicate for variety)
  [414, 736],   // iPhone 6/7/8 Plus (duplicate for variety)
  [375, 812],   // iPhone X/XS/11 Pro (duplicate for variety)
  [414, 896],   // iPhone XR/11 (duplicate for variety)
  [390, 844],   // iPhone 12/13 mini (duplicate for variety)
  [428, 926],   // iPhone 12/13 Pro Max (duplicate for variety)
  [393, 852],   // iPhone 14 Pro (duplicate for variety)
  [430, 932]    // iPhone 14 Pro Max (duplicate for variety)
];

const COMMON_FONTS = [
  // iPhone/iOS system fonts
  "Arial", "Arial Hebrew", "Arial Rounded MT Bold", "Courier", "Courier New",
  "Georgia", "Helvetica", "Helvetica Neue", "Palatino", "Times", "Times New Roman",
  "Trebuchet MS", "Verdana", "Wingdings 2", "Wingdings 3", "American Typewriter",
  "Apple Color Emoji", "Apple SD Gothic Neo", "Avenir", "Avenir Next", "Avenir Next Condensed",
  "Baskerville", "Bodoni 72", "Bradley Hand", "Chalkboard SE", "Chalkduster",
  "Cochin", "Copperplate", "Damascus", "Devanagari Sangam MN", "Didot",
  "Futura", "Geeza Pro", "Gill Sans", "Gujarati Sangam MN", "Gurmukhi MN",
  "Hiragino Mincho ProN", "Hiragino Sans", "Hoefler Text", "Kailasa", "Kannada Sangam MN",
  "Malayalam Sangam MN", "Marion", "Marker Felt", "Menlo", "Mishafi",
  "Noteworthy", "Optima", "Oriya Sangam MN", "Papyrus", "Party LET",
  "PingFang HK", "PingFang SC", "PingFang TC", "Savoye LET", "Sinhala Sangam MN",
  "Snell Roundhand", "Symbol", "Tamil Sangam MN", "Telugu Sangam MN", "Thonburi",
  "Zapf Dingbats", "Zapfino"
];

const TIMEZONES = [
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "America/Toronto", "America/Vancouver", "America/Mexico_City", "America/Sao_Paulo",
  "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Rome", "Europe/Madrid",
  "Europe/Amsterdam", "Europe/Stockholm", "Europe/Vienna", "Europe/Zurich",
  "Asia/Tokyo", "Asia/Shanghai", "Asia/Seoul", "Asia/Singapore", "Asia/Hong_Kong",
  "Asia/Bangkok", "Asia/Jakarta", "Asia/Manila", "Asia/Kolkata", "Asia/Dubai",
  "Australia/Sydney", "Australia/Melbourne", "Australia/Perth", "Pacific/Auckland"
];

const COLOR_GAMUTS = ["srgb", "p3", "rec2020"];
const VIDEO_VENDORS = [
  "Apple Inc.", "Apple Inc.", "Apple Inc.", "Apple Inc.", "Apple Inc.",
  "Apple Inc.", "Apple Inc.", "Apple Inc.", "Apple Inc.", "Apple Inc."
];
const VIDEO_RENDERERS = [
  "Apple GPU", "Apple A17 Pro GPU", "Apple A16 Bionic GPU", "Apple A15 Bionic GPU",
  "Apple A14 Bionic GPU", "Apple A13 Bionic GPU", "Apple A12 Bionic GPU", "Apple A11 Bionic GPU",
  "Apple A10 Fusion GPU", "Apple A9 GPU", "Apple A8 GPU", "Apple A7 GPU",
  "Apple M3 GPU", "Apple M2 GPU", "Apple M1 GPU", "Apple M1 Pro GPU",
  "Apple M1 Max GPU", "Apple M1 Ultra GPU", "Apple M2 Pro GPU", "Apple M2 Max GPU",
  "Apple M2 Ultra GPU", "Apple M3 Pro GPU", "Apple M3 Max GPU", "Apple M3 Ultra GPU",
  "Apple GPU", "Apple GPU", "Apple GPU", "Apple GPU", "Apple GPU", "Apple GPU"
];

// Shared Data Generator - Tạo dữ liệu chung cho tất cả versions
function generateSharedData() {
  const timezone = randomChoice(TIMEZONES);
  return {
    userAgent: randomChoice(USER_AGENTS),
    language: randomChoice(LANGUAGES),
    platform: randomChoice(PLATFORMS),
    resolution: randomChoice(SCREEN_RESOLUTIONS),
    timezone: timezone,
    timezoneOffset: randomInt(-720, 720),
    maxTouchPoints: randomInt(5, 10),
    adblock: Math.random() > 0.7,
    indexedDB: Math.random() > 0.1,
    openDatabase: Math.random() > 0.3,
    colorGamut: randomChoice(COLOR_GAMUTS),
    invertedColors: Math.random() > 0.95,
    monochrome: Math.random() > 0.98 ? randomInt(1, 8) : 0,
    contrast: Math.random() > 0.95 ? randomInt(1, 3) : 0,
    reducedMotion: Math.random() > 0.9,
    hdr: Math.random() > 0.8,
    videoVendor: randomChoice(VIDEO_VENDORS),
    videoRenderer: randomChoice(VIDEO_RENDERERS),
    canvasGeometry: `data:image/png;base64,${randomBase64(200 * 50 * 4)}`,
    canvasText: `data:image/png;base64,${randomBase64(200 * 50 * 4)}`,
    audio: randomFloat(120, 130, 2)
  };
}

// Font Generator - Tạo fonts chung
function generateSharedFonts(sharedData) {
  const numFonts = randomInt(15, 35);
  const fonts = [];
  for (let i = 0; i < numFonts; i++) {
    const font = randomChoice(COMMON_FONTS);
    if (!fonts.includes(font)) {
      fonts.push(font);
    }
  }
  return fonts.sort();
}

// Math Generator - Tạo math values chung
function generateSharedMath() {
  return {
    acos: randomFloat(1.4, 1.5, 2),
    acosh: randomFloat(700, 720, 2),
    acoshPf: randomFloat(350, 360, 2),
    asin: randomFloat(0.1, 0.2, 2),
    asinh: randomFloat(0.8, 0.9, 2),
    asinhPf: randomFloat(0.8, 0.9, 2),
    atanh: randomFloat(0.5, 0.6, 2),
    atanhPf: randomFloat(0.5, 0.6, 2),
    atan: randomFloat(0.4, 0.5, 2),
    sin: randomFloat(0.8, 0.9, 2),
    sinh: randomFloat(1.1, 1.2, 2),
    sinhPf: randomFloat(2.5, 2.6, 2),
    cos: randomFloat(-0.8, -0.9, 2),
    cosh: randomFloat(1.5, 1.6, 2),
    coshPf: randomFloat(1.5, 1.6, 2),
    tan: randomFloat(-1.4, -1.5, 2),
    tanh: randomFloat(0.7, 0.8, 2),
    tanhPf: randomFloat(0.7, 0.8, 2),
    exp: randomFloat(2.7, 2.8, 2),
    expm1: randomFloat(1.7, 1.8, 2),
    expm1Pf: randomFloat(1.7, 1.8, 2),
    log1p: randomFloat(2.3, 2.4, 2),
    log1pPf: randomFloat(2.3, 2.4, 2),
    powPI: randomFloat(1.9e-50, 2.0e-50, 2)
  };
}

// Font Preferences Generator
function generateFontPreferences() {
  return {
    default: randomFloat(140, 160, 2),
    apple: randomFloat(145, 165, 2),
    serif: randomFloat(140, 160, 2),
    sans: randomFloat(135, 155, 2),
    mono: randomFloat(125, 140, 2),
    min: randomFloat(8, 12, 2),
    system: randomFloat(140, 160, 2)
  };
}

// Component Generators
function generateV1Components(sharedData, sharedFonts) {
  const touchSupport = [sharedData.maxTouchPoints, true, true];
  
  return {
    user_agent: sharedData.userAgent,
    language: sharedData.language,
    resolution: sharedData.resolution,
    available_resolution: sharedData.resolution,
    timezone_offset: sharedData.timezoneOffset,
    navigator_platform: sharedData.platform,
    regular_plugins: [],
    adblock: sharedData.adblock,
    touch_support: touchSupport,
    js_fonts: sharedFonts
  };
}

function generateV1SansUAComponents(sharedData, sharedFonts) {
  const v1 = generateV1Components(sharedData, sharedFonts);
  delete v1.user_agent;
  return v1;
}

function generateV2Components(sharedData, sharedFonts, sharedMath, fontPreferences) {
  const numFonts = randomInt(3, 8);
  const v2Fonts = sharedFonts.slice(0, numFonts);
  
  const touchSupport = {
    maxTouchPoints: sharedData.maxTouchPoints,
    touchEvent: true,
    touchStart: true
  };
  
  return {
    fonts: v2Fonts,
    dom_blockers: [],
    font_preferences: fontPreferences,
    audio: sharedData.audio,
    screen_frame: [0, 0, 0, 0],
    languages: [[sharedData.language], [sharedData.language]],
    screen_resolution: sharedData.resolution,
    timezone: sharedData.timezone,
    indexed_db: sharedData.indexedDB,
    open_database: sharedData.openDatabase,
    platform: sharedData.platform,
    plugins: [],
    canvas: {
      winding: true,
      geometry: sharedData.canvasGeometry,
      text: sharedData.canvasText
    },
    touch_support: touchSupport,
    vendor_flavors: [],
    color_gamut: sharedData.colorGamut,
    inverted_colors: sharedData.invertedColors,
    monochrome: sharedData.monochrome,
    contrast: sharedData.contrast,
    reduced_motion: sharedData.reducedMotion,
    hdr: sharedData.hdr,
    math: sharedMath,
    video_card: {
      vendor: sharedData.videoVendor,
      renderer: sharedData.videoRenderer
    }
  };
}

// Main Generator
function generateCompJson() {
  // Tạo dữ liệu chung cho tất cả versions
  const sharedData = generateSharedData();
  const sharedFonts = generateSharedFonts(sharedData);
  const sharedMath = generateSharedMath();
  const fontPreferences = generateFontPreferences();
  
  // Tạo components sử dụng dữ liệu chung
  const v1SansUA = generateV1SansUAComponents(sharedData, sharedFonts);
  const v1 = generateV1Components(sharedData, sharedFonts);
  const v2 = generateV2Components(sharedData, sharedFonts, sharedMath, fontPreferences);
  
  const v1SansUAFingerprint = generateFingerprint(v1SansUA, 'v1-sans-ua');
  const v1Fingerprint = generateFingerprint(v1, 'v1');
  const v2Fingerprint = generateFingerprint(v2, 'v2');
  
  return {
    fingerprints: [
      {
        components: JSON.stringify(v1),
        fingerprint: v1Fingerprint,
        version: "fingerprint-v1"
      },
      {
        components: JSON.stringify(v1SansUA),
        fingerprint: v1SansUAFingerprint,
        version: "fingerprint-v1-sans-ua"
      },
      {
        components: JSON.stringify(v2),
        fingerprint: v2Fingerprint,
        version: "fingerprint-v2"
      }
    ]
  };
}

// Generate and assign to global variable
const compData = generateCompJson();
result = JSON.stringify(compData, null, 2);

// Prefer clean JSON to stdout for caller
try { if (typeof process !== 'undefined' && process.stdout) { process.stdout.write(result); } } catch {}
