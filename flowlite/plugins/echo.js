// plugins/echo.js
function main() {
    let arg = {};
    try { arg = JSON.parse(process.argv[2] || "{}"); } catch {}
    const out = { ok: true, echo: arg, ts: Date.now() };
    process.stdout.write(JSON.stringify(out));
  }
  main();
  