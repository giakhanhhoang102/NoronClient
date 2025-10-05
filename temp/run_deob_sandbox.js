// run_deob_sandbox_wrap_qi.js
// Safe sandbox to run obfuscated akeya.js and intercept assignments into qI's internal object
// Usage: node run_deob_sandbox_wrap_qi.js
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const AK_PATH = path.join(__dirname, 'akeya.js');
const OUT_PATH = path.join(__dirname, 'qI_capture.json');

if(!fs.existsSync(AK_PATH)) {
  console.error('akeya.js not found in current directory. Put akeya.js here and re-run.');
  process.exit(1);
}

let code = fs.readFileSync(AK_PATH, 'utf8');

// Heuristic: find the qI() function definition and inject proxy-wrapping into it.
// We search for pattern like:
// function qI(){var qkE=Object['create']({});qI=function(){return qkE;};return qkE;}
// and replace body to create a Proxy around qkE before returning it.
const qiPattern = /function\s+qI\s*\(\s*\)\s*\{\s*var\s+([A-Za-z0-9_$]+)\s*=\s*(?:Object\[['"]create['"]\]\s*\(\s*\{\s*\)\s*|Object\[['"]create['"]\]\s*\(\s*[^\)]*\)|\[\s*\]\s*|{}\s*|\(\)\s*).*?\;\s*qI\s*=\s*function\s*\(\)\s*\{\s*return\s+\1\s*;\s*\}\s*;\s*return\s+\1\s*;\s*\}/s;

if(qiPattern.test(code)) {
  code = code.replace(qiPattern, function(m, objName) {
    // Build injected body: create original container, wrap with Proxy to capture sets, store in global __captured_qi_obj,
    // then set qI to return proxied object.
    const injected = `
function qI(){
  var ${objName} = Object['create']({});
  // Wrap the internal object immediately with a Proxy so any subsequent assignments are intercepted.
  try{
    var __raw_qi_obj = ${objName};
    var __qi_captured = {};
    var proxy = new Proxy(__raw_qi_obj, {
      set: function(target, prop, value) {
        try {
          var summary;
          if (typeof value === 'function') {
            var body = value.toString();
            if (body.length > 20000) body = body.slice(0,20000) + '...<truncated>';
            summary = { type: 'function', length: value.length, body: body };
          } else {
            summary = { type: typeof value, value: (typeof value === 'string' && value.length>200 ? value.slice(0,200)+'...' : value) };
          }
          // Record under a global capture area
          if(!globalThis.__qI_captured_list) globalThis.__qI_captured_list = [];
          globalThis.__qI_captured_list.push({ prop: String(prop), summary: summary });
          __qi_captured[String(prop)] = summary;
        } catch(e) {}
        target[prop] = value;
        return true;
      },
      get: function(t,p){ return t[p]; }
    });
    // expose capture object for later retrieval
    globalThis.__captured_qi_obj = proxy;
    ${objName} = proxy;
  } catch(e) {
    // fallback: keep original object if proxy fails
    globalThis.__captured_qi_obj = ${objName};
  }
  qI = function(){ return ${objName}; };
  return ${objName};
}
`;
    return injected;
  });
  // Save a backup of original code just in case
  try { fs.writeFileSync(path.join(__dirname,'akeya.js.bak'), fs.readFileSync(AK_PATH,'utf8')); } catch(e){}
} else {
  // If not found, we will still attempt to define a global wrapper after the code runs
  console.warn('qI pattern not found — will run code and attempt post-hoc wrapping.');
}

// Prepare captured container to write later
const captured = { qI_props: {}, assignments: [] };

// Safe sandbox globals (stubs). Intentionally minimal to avoid network/IO.
const sandbox = {
  console: { log: ()=>{}, error: ()=>{}, warn: ()=>{} },
  window: {},
  document: {
    createElement: function(){ return {}; },
    cookie: "",
    createTextNode: function(){ return {}; },
    body: {}
  },
  navigator: { userAgent: 'node-sandbox', platform: 'linux' },
  location: { href: '', protocol: 'http:', host: '' },
  XMLHttpRequest: function(){ this.open = function(){}; this.send = function(){}; this.setRequestHeader = function(){}; },
  WebSocket: function(){ },
  Image: function(){ this.src=''; },
  fetch: function(){ return Promise.resolve({ ok:true, text:()=>'' }); },
  setTimeout: setTimeout,
  setInterval: setInterval,
  clearTimeout: clearTimeout,
  clearInterval: clearInterval,
  Tf: {},
  global: {}
};

// make common aliases
sandbox.global = sandbox;
sandbox.self = sandbox;
sandbox.window = sandbox;
sandbox.document = sandbox;
sandbox.Tf = sandbox;

const context = vm.createContext(sandbox);

// Run the code with a timeout (increase a bit to allow init)
try {
  vm.runInContext(code, context, { timeout: 20000 });
} catch (e) {
  // swallow runtime errors but continue to capture any assignments that happened
  // console.error('Script execution error (ignored):', e && e.toString && e.toString());
}

// Retrieve captured assignments from globalThis.__qI_captured_list if present
try {
  const capList = context.__qI_captured_list || (context.global && context.global.__qI_captured_list) || (global && global.__qI_captured_list);
  if (Array.isArray(capList)) {
    capList.forEach(function(item){
      if (!captured.qI_props[item.prop]) {
        captured.qI_props[item.prop] = item.summary;
      }
      captured.assignments.push(item);
    });
  }
  // Also try to inspect __captured_qi_obj to see keys already present
  const obj = context.__captured_qi_obj || (context.global && context.global.__captured_qi_obj);
  if(obj && typeof obj === 'object') {
    try {
      var keys = Object.keys(obj);
      keys.forEach(function(k){
        if(!captured.qI_props[k]) {
          var v = obj[k];
          if (typeof v === 'function') {
            var body = v.toString();
            if (body.length > 20000) body = body.slice(0,20000) + '...<truncated>';
            captured.qI_props[k] = { type: 'function', length: v.length, body: body };
          } else {
            captured.qI_props[k] = { type: typeof v, value: (typeof v === 'string' && v.length>200 ? v.slice(0,200)+'...' : v) };
          }
        }
      });
    } catch(e) {}
  }
} catch(e) { /* ignore */ }

// Save captured info
try {
  fs.writeFileSync(OUT_PATH, JSON.stringify(captured, null, 2), 'utf8');
  console.log('Captured assignments written to', OUT_PATH);
} catch (e) {
  console.error('Error writing capture:', e && e.toString && e.toString());
}
