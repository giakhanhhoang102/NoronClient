(function () {
    function normalizeMonth(m) {
      m = String(m).trim();
      if (!/^\d{1,2}$/.test(m)) throw Error("Tháng 1–2 chữ số");
      const n = parseInt(m, 10);
      if (n < 1 || n > 12) throw Error("Tháng 1..12");
      return n;
    }
    const input = MM;                 // đổi tại đây
    const val = normalizeMonth(input);
  
    if (typeof globalThis !== "undefined") {
      globalThis.NMM = val;
      console.log("globalThis.NMM =", globalThis.NMM);
    }
    if (typeof window !== "undefined") {
      window.NMM = val;                 // trình duyệt
      console.log("window.NMM =", window.NMM);
    }
    if (typeof global !== "undefined") {
      global.NMM = val;                 // Node.js
      console.log("global.NMM =", global.NMM);
    }
  })();
  
  
  
  
  
  
  
  
  