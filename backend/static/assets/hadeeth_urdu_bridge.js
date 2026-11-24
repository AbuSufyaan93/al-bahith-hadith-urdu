/* ==========================================================================
   الباحث الحديثي — Salafi Urdu Localization & Rekhta Lexicon Runtime (v3)
   100% Lossless, CSP-Safe, Subpath-Aware Client Bridge for https://hadeeth.com/
   ========================================================================== */
(function () {
  "use strict";

  /* 0. Proxy Subpath Detection & Sandboxed-Iframe Safe Shims
     CRITICAL: Never unregister host ServiceWorkers or delete host CacheStorage,
     because cloud preview environments (e.g. *.scf.usercontent.goog) use a host
     ServiceWorker tunnel to proxy fetch() and navigation requests! */
  const SAFE_ORIGIN = (function () {
    try {
      if (window.location && window.location.origin && window.location.origin !== "null") {
        return window.location.origin;
      }
    } catch (_) {}
    return "";
  })();

  const csUrl = (function () {
    try {
      if (document.currentScript && document.currentScript.src) {
        return new URL(document.currentScript.src, SAFE_ORIGIN || "http://localhost");
      }
    } catch (_) {}
    try {
      return new URL(window.location.href);
    } catch (_) {
      return new URL("http://localhost/");
    }
  })();

  const BASE_PATH = /\/assets\/hadeeth_urdu_bridge\.js/.test(csUrl.pathname)
    ? csUrl.pathname.replace(/\/assets\/hadeeth_urdu_bridge\.js.*$/, "").replace(/\/$/, "")
    : "";
  const BASE_URL = (SAFE_ORIGIN || csUrl.origin) + BASE_PATH;
  window.__ALBAHITH_BASE_PATH__ = BASE_PATH;
  window.__ALBAHITH_BASE_URL__ = BASE_URL;
  window.__SVELTEKIT_PAYLOAD__ = {
    base: BASE_PATH,
    assets: BASE_PATH,
    version: "1794313800351",
  };

  // Safe Storage shim if third-party iframe cookies/storage are partitioned or blocked
  function ensureSafeStorage(propName) {
    try {
      const st = window[propName];
      const testKey = "__ab_test__";
      st.setItem(testKey, "1");
      st.removeItem(testKey);
      return;
    } catch (_) {
      const mem = new Map();
      const fake = {
        get length() { return mem.size; },
        clear() { mem.clear(); },
        getItem(k) { return mem.has(String(k)) ? mem.get(String(k)) : null; },
        key(i) { return Array.from(mem.keys())[i] || null; },
        removeItem(k) { mem.delete(String(k)); },
        setItem(k, v) { mem.set(String(k), String(v)); },
      };
      try {
        Object.defineProperty(window, propName, { configurable: true, get: () => fake });
      } catch (_) {}
    }
  }
  ensureSafeStorage("localStorage");
  ensureSafeStorage("sessionStorage");

  // Safe History pushState/replaceState shim so sandboxed iframes never throw SecurityError in SvelteKit router
  (function patchHistory() {
    for (const fnName of ["replaceState", "pushState"]) {
      const orig = History.prototype[fnName];
      if (typeof orig !== "function") continue;
      History.prototype[fnName] = function (state, unused, url) {
        try {
          return orig.call(this, state, unused, url);
        } catch (_) {
          try {
            return orig.call(this, state, unused);
          } catch (__) {
            return undefined;
          }
        }
      };
    }
  })();

  // Externalized Dark-Mode & Plausible Analytics stub (eliminates all inline <script> from index.html)
  try {
    const mode = localStorage.getItem("mode-watcher-mode");
    const isDark =
      mode === "dark" ||
      ((!mode || mode === "system") && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", !!isDark);
    document.documentElement.style.colorScheme = isDark ? "dark" : "light";
  } catch (_) {}
  window.plausible = window.plausible || function () {};
  window.plausible.init = window.plausible.init || function () {};

  const LANG_KEY = "albahith_lang";
  const FONT_KEY = "albahith_ur_font";
  const SCALE_KEY = "albahith_ur_scale";

  const FONTS_MAP = {
    jameel: '"JameelNooriNastaleeq", "NotoNastaliqUrdu", "MehrNastaliqWeb", "IBM Plex Sans Arabic", serif',
    noto: '"NotoNastaliqUrdu", "JameelNooriNastaleeq", "MehrNastaliqWeb", "IBM Plex Sans Arabic", serif',
    mehr: '"MehrNastaliqWeb", "NotoNastaliqUrdu", "JameelNooriNastaleeq", "IBM Plex Sans Arabic", serif',
    sakkal: '"SakkalMajallaBold", "IBM Plex Sans Arabic", serif',
    plex: '"IBM Plex Sans Arabic", sans-serif',
  };

  function isHomePath(pathname) {
    const p = (pathname || "/").replace(/\/$/, "") || "/";
    const b = BASE_PATH || "/";
    return p === b;
  }

  function stripBasePath(pathname) {
    const p = pathname || "/";
    if (BASE_PATH && p.startsWith(BASE_PATH)) {
      return p.slice(BASE_PATH.length) || "/";
    }
    return p;
  }

  function getSavedLang() {
    try {
      const u = new URL(window.location.href);
      const qLang = (u.searchParams.get("_lang") || "").trim().toLowerCase();
      if (qLang === "ar" || qLang === "ur") return qLang;
    } catch (_) {}
    try {
      const v = (localStorage.getItem(LANG_KEY) || "").trim().toLowerCase();
      if (v === "ar" || v === "ur") return v;
    } catch (_) {}
    return "ur";
  }

  function persistLangCookie(lang) {
    try {
      localStorage.setItem(LANG_KEY, lang);
    } catch (_) {}
    try {
      document.cookie = `albahith_lang=${lang}; path=/; max-age=31536000; SameSite=Lax`;
    } catch (_) {}
    document.documentElement.setAttribute("dir", "rtl");
    document.documentElement.setAttribute("lang", lang === "ur" ? "ur" : "ar");
    document.documentElement.setAttribute("data-albahith-lang", lang);
    document.title = lang === "ur" ? "الباحث الحديثي — اردو، عربي" : "الباحث الحديثي";
  }

  function applySavedTypography() {
    try {
      const fKey = localStorage.getItem(FONT_KEY) || "jameel";
      const scale = parseFloat(localStorage.getItem(SCALE_KEY) || "1") || 1;
      document.documentElement.style.setProperty("--ur-font-family", FONTS_MAP[fKey] || FONTS_MAP.jameel);
      document.documentElement.style.setProperty("--ur-font-scale", String(Math.min(1.35, Math.max(0.85, scale))));
    } catch (_) {}
  }

  let currentLang = getSavedLang();
  persistLangCookie(currentLang);
  applySavedTypography();

  /* ------------------------------------------------------------------------
   * 1. SvelteKit `devalue` Unflattener (Cloned Response Inspector)
   * ------------------------------------------------------------------------ */
  function unflattenDevalueArray(arr) {
    if (!Array.isArray(arr) || arr.length === 0) return null;
    const memo = new Map();
    function resolve(idx) {
      if (typeof idx !== "number" || idx < 0 || idx >= arr.length) return idx;
      if (memo.has(idx)) return memo.get(idx);
      const val = arr[idx];
      if (val === null || typeof val !== "object") return val;
      if (Array.isArray(val)) {
        if (val.length >= 2 && typeof val[0] === "string" && ["Date", "Set", "Map", "RegExp", "BigInt", "URL"].includes(val[0])) {
          return String(val[1]);
        }
        const outArr = [];
        memo.set(idx, outArr);
        for (let i = 0; i < val.length; i++) outArr.push(resolve(val[i]));
        return outArr;
      }
      const outObj = {};
      memo.set(idx, outObj);
      for (const k of Object.keys(val)) {
        outObj[k] = resolve(val[k]);
      }
      return outObj;
    }
    return resolve(0);
  }

  function decodeSvelteKitEnvelope(raw) {
    if (!raw || !Array.isArray(raw.nodes)) return null;
    for (let i = raw.nodes.length - 1; i >= 0; i--) {
      const n = raw.nodes[i];
      if (n && n.type === "data" && Array.isArray(n.data)) {
        const obj = unflattenDevalueArray(n.data);
        if (obj && typeof obj === "object" && Object.keys(obj).length > 0) {
          return obj;
        }
      }
    }
    return null;
  }

  /* ------------------------------------------------------------------------
   * 2. Non-Intrusive Subpath-Aware `window.fetch` Interceptor
   * ------------------------------------------------------------------------ */
  let lastNativeSearchTs = 0;
  const origFetch = window.fetch.bind(window);
  window.fetch = async function (input, init) {
    let urlStr = typeof input === "string" ? input : (input && input.url ? input.url : String(input));
    let nextInput = input;
    let nextInit = init ? Object.assign({}, init) : {};

    try {
      const isRelativeInput = typeof urlStr === "string" && urlStr.startsWith("/") && !urlStr.startsWith("//");
      const baseForParse = SAFE_ORIGIN || "http://localhost";
      const u = new URL(urlStr, baseForParse);
      const isSameOrigin = isRelativeInput || (Boolean(SAFE_ORIGIN) && u.origin === SAFE_ORIGIN);
      if (isSameOrigin) {
        if (BASE_PATH && !u.pathname.startsWith(BASE_PATH + "/") && u.pathname !== BASE_PATH) {
          if (u.pathname.startsWith("/api/") || u.pathname.startsWith("/assets/") || u.pathname.startsWith("/fonts/")) {
            u.pathname = BASE_PATH + u.pathname;
          }
        }
        const cleanPath = stripBasePath(u.pathname);
        const isHomeWire = (cleanPath === "/" || cleanPath === "" || cleanPath === "/api/v1/wire") && u.searchParams.has("action");
        if (isHomeWire && u.searchParams.get("action") === "search") {
          lastNativeSearchTs = Date.now();
          const fsBox = document.getElementById("albahith-failsafe-results");
          if (fsBox) fsBox.remove();
        }
        const isDataJson = cleanPath.endsWith("/__data.json") || cleanPath.endsWith("/sk-data.json");
        if (isHomeWire || isDataJson || cleanPath.startsWith("/api/") || (BASE_PATH && u.pathname !== urlStr)) {
          if (isHomeWire || isDataJson || cleanPath.startsWith("/api/")) {
            if (!u.searchParams.has("_lang")) {
              u.searchParams.set("_lang", currentLang);
            }
            const hdrs = new Headers(nextInit.headers || (typeof input === "object" && input && input.headers ? input.headers : undefined));
            hdrs.set("x-albahith-lang", currentLang);
            nextInit.headers = hdrs;
          }
          const rewritten = (isRelativeInput || !SAFE_ORIGIN)
            ? (u.pathname + u.search + u.hash)
            : u.toString();
          if (typeof input === "string" || input instanceof URL) {
            nextInput = rewritten;
          } else {
            nextInput = new Request(rewritten, nextInit);
          }
          urlStr = rewritten;
        }
      }
    } catch (_) {}

    const resp = await origFetch(nextInput, nextInit);

    try {
      if ((urlStr.includes("/__data.json") || urlStr.includes("/sk-data.json")) && resp.ok) {
        const cloned = resp.clone();
        cloned.json().then((rawJson) => {
          const decoded = decodeSvelteKitEnvelope(rawJson);
          if (decoded) {
            window.__ALBAHITH_ENC_DATA__ = decoded;
            scheduleEncyclopediaPass();
          }
        }).catch(() => {});
      }
    } catch (_) {}

    return resp;
  };

  /* ------------------------------------------------------------------------
   * 3. Complete Salafi Urdu UI Dictionary (100% Manhaj-us-Salaf Compliant)
   *    Note: Iconic `الباحث الحديثي` wordmark is intentionally preserved in Arabic
   *    calligraphy (`Kitab`) to match https://hadeeth.com/ 100% visually!
   * ------------------------------------------------------------------------ */
  const UI_EXACT_AR_TO_UR = {
    // Subtitles & Footers
    "بحث فوري في": "فوری تحقیقی تلاش:",
    "الموسوعة الحديثية بالدرر السنية": "موسوعۂ حدیثیہ (الدرر السنیہ)",
    "الموسوعة الحديثية": "موسوعۂ حدیثیہ",
    "الدرر السنية": "الدرر السنیہ",
    "بحث فوري للكشف عن صحة الحديث وحكم العلماء عليه": "صحتِ حدیث اور ائمہ و محدثین کے حکم کی فوری تحقیق",
    "تصفح كتب السنة النبوية وأبوابها وأحاديثها وأسانيدها وتراجم رواتها.": "کتبِ سنتِ نبویہ ﷺ، ابواب، احادیث، اسانید اور تراجمِ رواۃ کا جامع مطالعہ۔",
    "الباحث الحديثي · النصوص مستخرجة من «جامع السنة النبوية»": "الباحث الحديثي · متون ماخوذ از «جامع السنۃ النبویہ» مع مستند سلفی اردو ترجمہ",
    "الباحث الحديثي · النصوص مستخرجة من «الموسوعة الحديثية بالدرر السنية»": "الباحث الحديثي · متون ماخوذ از «الموسوعۃ الحدیثیہ بالدرر السنیہ» مع مستند سلفی اردو ترجمہ",

    // Top Navigation & Sections (`/(site)` & `/(home)` Drawer in `image_2.png`)
    "الأقسام": "شعبہ جات",
    "أقسام الموقع": "شعبہ جاتِ موسوعہ",
    "أقسام الموسوعة الحديثية": "شعبہ جاتِ موسوعہ حدیثیہ",
    "الكتب": "کتبِ حدیث",
    "كتب السنة": "کتبِ سنت",
    "كتب السنة الأصول": "اصولِ کتبِ سنت",
    "كتب السنة النبوية بأسانيدها ورواتها": "کتبِ سنتِ نبویہ ﷺ مع اسانید و رواۃ",
    "كتابًا من الأصول، مع التخريج وأحكام العلماء وتراجم الرواة.": "بنیادی کتبِ سنت، مع تخریج، احکامِ محدثین اور تراجمِ رواۃ۔",
    "الكتب الستة": "صحاحِ ستہ (الکتب الستہ)",
    "الصحاح والمستدركات": "صحاح و مستدرکات",
    "السنن": "کتبِ سنن",
    "الموطأ والمصنفات": "موطا اور مصنفات",
    "المسانيد": "کتبِ مسانید",
    "سائر الكتب": "دیگر کتبِ سنت",
    "كتب أخرى": "دیگر کتب",
    "الرواة": "رواۃِ حدیث",
    "تراجم رواة الحديث وطبقاتهم ومراتبهم.": "رواۃِ حدیث کے تراجم، طبقات اور جرح و تعدیل کے مراتب۔",
    "الموضوعات": "موضوعات",
    "الموضوعات الفرعية": "ذیلی موضوعات",
    "تصنيف الأحاديث على الموضوعات": "موضوعاتی تقسیمِ احادیث",
    "القرآن": "قرآنِ کریم",
    "القرآن الكريم": "قرآنِ کریم",
    "سور القرآن الكريم وآياتها، والأحاديث التي ورد فيها نصها، وتفسيرها.": "قرآنِ کریم کی سورتیں، آیات اور ان سے متعلقہ احادیث و ماثور تفسیر۔",
    "السور وآياتها، وبجانب كل سورة عدد الأحاديث التي ورد فيها نص من آياتها": "قرآنِ کریم کی سورتیں اور آیات، مع ہر سورت سے متعلقہ احادیث کی تعداد",
    "المعاجم": "معاجم و لغات",
    "معجم غريب الحديث ومعجم البلدان والأماكن الواردة في الأحاديث.": "معجم غریب الحدیث اور احادیث میں مذکور مقامات و بلدان کی تحقیق۔",
    "المزيد": "مزید علوم",
    "... المزيد": "... مزید دکھائیں",

    // `/more` Specialized Hadith Sciences Pages
    "الأطراف": "اطرافِ حدیث",
    "قائمة الأطراف": "فہرستِ اطراف",
    "الأطراف على المسانيد": "مسانید کے اعتبار سے اطراف",
    "أوائل الأحاديث في كتب السنة، مرتبة على حروف المعجم": "کتبِ سنت کی احادیث کے ابتدائی الفاظ (حروفِ تہجی کے مطابق)",
    "أوائل الأحاديث مرتبة على حروف المعجم، ومواضعها في الكتب": "احادیث کے ابتدائی الفاظ اور کتبِ سنت میں ان کے مقامات",
    "مصطلح الحديث": "مصطلح الحدیث",
    "علوم الحديث": "علومِ حدیث",
    "المصطلحات ومواضعها في كتب المصطلح، وأقوال العلماء فيها": "اصطلاحاتِ حدیث، کتبِ مصطلح میں ان کے مقامات اور اقوالِ ائمہ",
    "أقوال الأئمة في مسائل المصطلح": "مسائلِ مصطلح الحدیث میں ائمہ کے اقوال",
    "أقوال الأئمة في مصطلحات علوم الحديث، مرتبة على العلماء": "اصطلاحاتِ علومِ حدیث میں ائمہ محدثین کے اقوال",
    "ألفاظ الجرح والتعديل": "الفاظِ جرح و تعدیل",
    "الجرح والتعديل": "جرح و تعدیل",
    "ألفاظ الأئمة في الرواة، وعدد من وصف بكل لفظ": "رواۃ کے بارے میں ائمہ جرح و تعدیل کے الفاظ اور ان کا شمار",
    "ألفاظ الأئمة في الرواة، ومن قيلت فيه": "رواۃ کے متعلق ائمہ کے الفاظ اور ان کے مصادیق",
    "الرواة الذين قيل فيهم هذا اللفظ": "وہ رواۃ جن کے بارے میں یہ لفظ کہا گیا",
    "علل الأسانيد وتصنيفاتها": "عللِ اسانید اور ان کی اقسام",
    "تصنيف المصدر لأسانيد الأحاديث وما ذكره في رواتها، وصيغ التحمل بينهم.": "اسانیدِ حدیث کی درجہ بندی، احوالِ رواۃ اور صیغہ ہائے تحمل و اداء۔",
    "أحكام العلماء": "احکامِ محدثین",
    "أقوال العلماء": "اقوالِ ائمہ",
    "أقوال العلماء في الأحاديث": "احادیث پر ائمہ محدثین کے احکام",
    "أقوال العلماء في الحكم على الحديث": "صحت و ضعفِ حدیث میں اقوالِ ائمہ",
    "أقوال العلماء في علوم الحديث": "علومِ حدیث میں اقوالِ علمائے سلف",
    "أحكام الأئمة على الأحاديث، لكل إمام ما قاله وفي أي حديث": "احادیث پر ائمہ محدثین کے تحقیقی احکام کی تفصیل",
    "أحكام كل إمام على الأحاديث": "ہر امام کے احکامِ حدیث",
    "المحدثون الذين حكموا على الأحاديث، وأحكامهم": "احادیث پر حکم لگانے والے محدثینِ کرام اور ان کے احکام",
    "الكتب التي خرجت منها الأحاديث وأحكام المحدثين": "وہ کتب جن سے احادیث اور محدثین کے احکام اخذ کیے گئے ہیں",
    "رواة أحاديث الموسوعة الحديثية بالدرر السنية وأحاديث كل منهم": "موسوعہ حدیثیہ (الدرر السنیہ) کے رواۃ اور ہر راوی کی احادیث",
    "رواة أحاديث الموسوعة الحديثية بالدرر السنية ومحدثوها ومصادرها، وعدد أحاديث كل منهم": "موسوعہ حدیثیہ کے رواۃ، محدثین اور مصادر، مع تعدادِ احادیث",
    "مختلف الحديث ومشكله": "مختلف الحدیث اور مشکل الآثار",
    "الأحاديث التي ظاهرها التعارض، وبيان الطحاوي لها": "بظاہر متعارض احادیث کی تطبیق اور امام طحاوی رحمہ اللہ کی توضیح",
    "مسألة من شرح مشكل الآثار للطحاوي، لكل منها الأحاديث التي ظاهرها التعارض": "شرح مشکل الآثار للطحاوی کے مسائل اور بظاہر متعارض احادیث کی تطبیق",
    "بيان الطحاوي": "توضیحِ امام طحاوی رحمہ اللہ",
    "المتون المجمعة": "جمع شدہ متونِ حدیث",
    "المتن المجمّع من الروايات": "مختلف روایات سے جمع شدہ متن",
    "مقارنات المتون": "متونِ حدیث کا تقابلی مطالعہ",
    "نتيجة المقارنة": "نتیجۂ تقابل",
    "الكتاب الأول": "پہلی کتاب",
    "الكتاب الثاني": "دوسری کتاب",
    "الأحاديث الأصل": "بنیادی احادیث",
    "الأحاديث المخالفة": "مختلف الفاظ والی احادیث",
    "المتفق عليه والزوائد": "متفق علیہ اور زوائد",
    "المتفق عليه": "متفق علیہ",
    "زوائد": "زوائد",
    "ما اتفق عليه كتابان، وما انفرد به كل منهما": "جن احادیث پر دو کتابیں متفق ہیں اور جن میں ہر ایک منفرد ہے",
    "الأحاديث التي اتفق عليها كتابان، وما انفرد به كل منهما، بحسب مجموعات التخريج": "دو کتابوں کی متفق علیہ اور منفرد احادیث کا تقابلی اشاریہ",
    "أمثال الحديث": "امثالِ حدیثِ نبوی ﷺ",
    "الأحاديث التي جرت مجرى الأمثال": "ضرب الامثال کے طور پر وارد احادیثِ نبویہ ﷺ",
    "الأحاديث التي جرت مجرى الحكم والأمثال": "حکمت و ضرب المثل والی احادیثِ نبویہ ﷺ",
    "الفهارس": "فہارس و اشاریے",
    "الفهرس": "فہرست",
    "فهرس الكتب": "فہرستِ ابوابِ کتاب",
    "فهرس الكتب.": "فہرستِ ابوابِ کتاب۔",
    "فهرس الآيات": "فہرستِ آیات",
    "فهرس الشعر": "فہرستِ اشعار",
    "فهارس الآيات والأعلام والشعر": "آیات، اعلام اور اشعار کے اشاریے",
    "الآيات والأعلام والشعر الواردة في نصوص الكتب": "کتبِ سنت کے متون میں وارد آیات، شخصیات اور اشعار",
    "الإحصاءات": "احصائیات و اعداد و شمار",
    "أعداد الكتب والأحاديث والرواة والأسانيد": "کتب، احادیث، رواۃ اور اسانید کے جامع اعداد و شمار",
    "الجوامع": "جوامع",
    "الجوامع والفهارس": "جوامع اور اشاریہ جات",
    "الأطراف وعلوم الحديث والجوامع والفهارس والموسوعة الحديثية": "اطراف، علومِ حدیث، جوامع، فہارس اور موسوعہ حدیثیہ",
    "من النهاية في غريب الحديث ولسان العرب": "ماخوذ از «النہایہ فی غریب الحدیث» و «لسان العرب»",
    "من معجم البلدان ومعجم المعالم الجغرافية في السيرة النبوية": "ماخوذ از «معجم البلدان» و «معجم المعالم الجغرافیہ فی السیرۃ النبویہ»",
    "من جُمعت آثارهم من الصحابة والتابعين، مع عدد ما يقف إسناده عندهم من الموقوف أو المقطوع": "وہ صحابہ کرام و تابعین جن کے موقوف و مقطوع آثار جمع کیے گئے ہیں",
    "من رويت عنهم الآثار من الصحابة والتابعين": "جن صحابہ کرام و تابعین سے آثار مروی ہیں",
    "أحاديث كل راوٍ يقف عنده الإسناد: الصحابي في المرفوع والموقوف، والتابعي في المقطوع": "ہر راویِ منتہیٰ کی احادیث: مرفوع و موقوف میں صحابی اور مقطوع میں تابعی",
    "أحاديث كل صحابي وتابعي: المرفوع والموقوف والمقطوع": "ہر صحابی و تابعی کی مرفوع، موقوف اور مقطوع مرویات",

    // Home Search Filters, Presets & Options (`DbNwGjsa.js`)
    "بحث": "تلاش",
    "بحث:": "تلاش:",
    "البحث": "تلاش",
    "البحث في الكتب": "کتب میں تلاش",
    "نص البحث": "عبارتِ تلاش",
    "أمثلة:": "مثالیں:",
    "كلمات البحث": "الفاظِ تلاش...",
    "كلمات البحث...": "الفاظِ تلاش...",
    "اكتب كلمة أو عبارة": "کوئی لفظ یا جملہ درج کریں",
    "ابحث في الأحاديث والرواة": "احادیث اور رواۃ میں تلاش کریں",
    "ابحث في الأسماء": "اسماء میں تلاش کریں",
    "ابحث في الأسماء والكنى والألقاب": "نام، کنیت یا لقب سے تلاش کریں",
    "ابحث في الأطراف": "اطرافِ حدیث میں تلاش کریں",
    "ابحث في الألفاظ": "الفاظ میں تلاش کریں",
    "ابحث في الأمثال": "امثالِ حدیث میں تلاش کریں",
    "ابحث في الفهرس": "فہرست میں تلاش کریں",
    "ابحث عن صاحب المسند": "صاحبِ مسند صحابی تلاش کریں",
    "ابحث عن لفظ": "لفظ تلاش کریں",
    "ابحث عنه في النصوص": "متون میں تلاش کریں",
    "بحث في المعجم": "لغت و معجم میں تلاش",
    "تصفية البحث": "فلٹرز اور شرائطِ تلاش",
    "تصفية الأقوال": "اقوال کا فلٹر",
    "تصفية العلماء": "ائمہ و علماء کا فلٹر",
    "تصفية العلماء بالاسم": "نام سے عالم تلاش کریں",
    "أدوات البحث": "وسائلِ تلاش",
    "إزالة التصفية": "فلٹر ختم کریں",
    "خيارات شائعة": "منتخب تحقیقی فلٹرز",
    "الأحاديث الصحيحة": "صرف صحیح و ثابت احادیث",
    "الصحيحان": "صحیحین (بخاری و مسلم)",
    "الألباني": "تحقیقاتِ علامہ البانی رحمہ اللہ",
    "الأرنؤوط": "تحقیق شعیب ارناؤوط رحمہ اللہ",
    "حكم الحديث": "حکمِ حدیث",
    "خلاصة حكم المحدث": "خلاصۂ حکمِ محدث:",
    "أحاديث حكم المحدثون عليها بالصحة، ونحو ذلك": "صحیح المتن احادیث (جن کے متن کو محدثین نے صحیح یا حسن قرار دیا)",
    "أحاديث حكم المحدثون على أسانيدها بالصحة، ونحو ذلك": "صحیح الاسناد احادیث (جن کی سند کو محدثین نے صحیح یا حسن کہا)",
    "أحاديث حكم المحدثون عليها بالضعف، ونحو ذلك": "ضعیف المتن روایات (جن پر محدثین نے ضعف یا وضع کا حکم لگایا)",
    "أحاديث حكم المحدثون على أسانيدها بالضعف، ونحو ذلك": "ضعیف الاسناد روایات (جن کی سند پر محدثین نے ضعف کا حکم لگایا)",
    "المحدث": "محدث",
    "المحدثون": "محدثینِ کرام",
    "كل المحدثين": "تمام محدثین",
    "الكتاب": "کتاب",
    "كل الكتب": "تمام کتب",
    "كل المصادر": "تمام مصادر",
    "كل الأحكام": "تمام احکام",
    "كل الطبقات": "تمام طبقات",
    "كل المراتب": "تمام مراتب",
    "كل الفروع": "تمام شاخیں",
    "الراوي": "راوی",
    "الراوي:": "راوی:",
    "الراوي الأعلى": "راویِ اعلیٰ (صحابی / تابعی)",
    "الراوي الآخر": "دوسرا راوی",
    "اسم الراوي الآخر": "دوسرے راوی کا نام",
    "منتهى الحديث": "منتہائے حدیث",
    "الجميع": "سب (تمام اقسام)",
    "الكل": "سب",
    "جميع الأحاديث": "تمام احادیث",
    "الأحاديث المرفوعة": "مرفوع احادیثِ نبویہ ﷺ",
    "الأحاديث القدسية": "احادیثِ قدسیہ",
    "آثار الصحابة": "آثارِ صحابہ کرام رضی اللہ عنہم",
    "آثار التابعين": "آثارِ تابعین رحمہم اللہ",
    "آثار الصحابة والتابعين": "آثارِ صحابہ و تابعین",
    "شروح الأحاديث": "مشروح احادیث",
    "طريقة المطابقة": "طریقۂ مطابقت",
    "كل الكلمات بأي ترتيب": "تمام الفاظ (کسی بھی ترتیب سے)",
    "العبارة كما هي": "بعینہٖ مکمل جملہ",
    "نوع النتائج": "نتائج کی قسم",
    "الترتيب": "ترتیب",
    "حسب الاسم": "نام کے لحاظ سے",
    "الأكثر أحاديث": "کثرتِ احادیث کے لحاظ سے",

    // Hadith Card Actions, Modals & Details
    "الشرح": "شرحِ حدیث",
    "شرح الحديث": "شرحِ حدیث",
    "شرح حديث مشابه": "ملتی جلتی حدیث کی شرح",
    "هذا الشرح لحديث مشابه، وهذا نصه:": "یہ شرح ایک ملتی جلتی حدیث کی ہے، جس کا متن یہ ہے:",
    "يجري تحميل الشرح": "شرحِ حدیث لوڈ ہو رہی ہے...",
    "تعذر تحميل الشرح، حاول مجددًا": "شرح لوڈ کرنے میں دشواری ہوئی، دوبارہ کوشش کریں۔",
    "مصدر الشرح:": "ماخذِ شرح:",
    "المصدر": "ماخذ",
    "المصدر:": "ماخذ:",
    "المصادر": "مصادر",
    "مصادر أخرى": "دیگر مصادر",
    "المصنف": "مصنف",
    "الصفحة أو الرقم:": "صفحہ یا حدیث نمبر:",
    "العدد:": "تعداد:",
    "عدد النتائج:": "تعدادِ نتائج:",
    "غريب الحديث": "غریب الحدیث (مشکل الفاظ کے معانی)",
    "شرح غريب الألفاظ والتعريف بالأماكن الواردة في الأحاديث": "مشکل الفاظِ حدیث کی شرح اور مقامات کا تعارف",
    "التخريج": "تخريجِ حدیث",
    "أسانيد التخريج": "اسانیدِ تخریج",
    "عدد مجموعات التخريج": "مجموعہ ہائے تخریج کی تعداد",
    "شجرة الأسانيد": "شجرۂ اسانید",
    "أسانيد هذا الحديث": "اس حدیث کی اسانید",
    "أسانيد هذا الحديث مميزة.": "اس حدیث کی اسانید ممتاز و نمایاں ہیں۔",
    "الأسانيد": "اسانید",
    "أسانيد": "اسانید",
    "الإسناد": "سند",
    "اختيار الإسناد": "انتخابِ سند",
    "نوع الإسناد": "قسمِ سند",
    "الأحاديث حسب نوع الإسناد": "قسمِ سند کے لحاظ سے احادیث",
    "نطاق الأسانيد": "دائرۂ اسانید",
    "أنواع الأسانيد": "اسانید کی اقسام",
    "تصفية الأسانيد": "اسانید کا فلٹر",
    "من الراوي الأعلى إلى المصنف، والرقم عند التفرع عدد الأسانيد التي تمر به.": "راویِ اعلیٰ سے مصنف رحمہ اللہ تک شجرۂ سند؛ ہر شاخ کا عدد اس سے گزرنے والی اسانید کی تعداد بتاتا ہے۔",
    "هذه أوصاف نقلها المصدر من تراجم الرواة وطبّقها على الأسانيد، وليست حكمًا على الحديث.": "یہ اوصاف ماخذ نے تراجمِ رواۃ سے نقل کر کے اسانید پر منطبق کیے ہیں؛ یہ بذاتِ خود حدیث پر حتمی حکم نہیں۔",
    "أحاديث متشابهة": "ملتی جلتی احادیث و شواہد",
    "مواد متعلقة بالحديث": "حدیث سے متعلق علمی مواد",
    "مواد متعلقة بالآية": "آیت سے متعلق علمی مواد",
    "أحاديث ورد فيها نص من الآية.": "وہ احادیث جن میں اس آیت کا متن وارد ہوا ہے۔",
    "الشروح والخدمات": "شروح و حواشی",
    "فقرات الكتب الخادمة": "شروح و کتبِ خادمہ کے اقتباسات",
    "الكتب الخادمة (شروح وتراجم ومعاجم)": "کتبِ خادمہ (شروح، تراجم اور معاجم)",
    "كل الكتب مع الشروح والتراجم": "تمام کتب مع شروح و تراجم",
    "فتح الموضع في قارئ تراث": "اصل کتاب کا صفحہ کھولیں (قاریٔ تراث)",
    "هذا الموضع غير متاح في نسخة الكتاب.": "یہ مقام کتاب کے موجودہ نسخے میں دستیاب نہیں۔",
    "نص هذا الموضع غير متوفر في المصدر.": "اس مقام کا متن ماخذ میں دستیاب نہیں۔",
    "مقتطف من أول المادة؛ النص الكامل غير متوفر في المصدر.": "مادے کا ابتدائی اقتباس؛ مکمل متن ماخذ میں دستیاب نہیں۔",
    "صفحة الحديث": "صفحۂ حدیث",
    "صفحة الراوي": "صفحۂ راوی",
    "صفحة المحدث": "صفحۂ محدث",
    "نسخ": "نقل کریں",
    "نُسخ": "نقل ہو گیا!",
    "نسخ الحديث": "حدیث نقل کریں",
    "تم النسخ": "نقل ہو گیا!",
    "مشاركة": "شیئر کریں",
    "شارك": "شیئر کریں",
    "إخفاء": "چھپائیں",
    "توسيع الكل": "سب کھولیں",
    "عرض الكل": "سب دکھائیں",
    "عرض الأقوال كلها": "تمام اقوال دکھائیں",
    "عرض النص كاملًا": "مکمل متن دکھائیں",
    "النص كاملًا": "مکمل متن",
    "النص": "متن",
    "بلا تكرار": "بغیر تکرار کے",
    "أحاديثها بلا تكرار": "احادیث (بغیر تکرار کے)",
    "عرض أقل": "کم دکھائیں",
    "عرض الفرع": "شاخ کھولیں",
    "طي الفرع": "شاخ سمیٹیں",
    "طي الفروع": "شاخیں سمیٹیں",
    "عرض الترجمة كاملة": "مکمل ترجمۂ راوی دیکھیں",
    "طي الترجمة": "ترجمہ سمیٹیں",
    "التالي": "اگلا",
    "التالية": "اگلا",
    "السابق": "پچھلا",
    "السابقة": "پچھلا",
    "التنقل بين الآيات": "آیات کے درمیان منتقلی",
    "التنقل بين الأحاديث": "احادیث کے درمیان منتقلی",
    "التنقل بين السور": "سورتوں کے درمیان منتقلی",
    "العودة إلى الرئيسية": "صفحۂ اول پر واپس جائیں",
    "الصفحة": "صفحہ",
    "الجزء": "جلد / جزو",
    "الرقم": "حدیث نمبر",
    "الباب": "باب",
    "الأبواب": "ابواب",
    "الباب في الكتاب": "کتاب کا باب",
    "تعريف الكتاب": "تعارفِ کتاب",
    "عن الكتاب ومؤلفه": "کتاب اور مؤلف رحمہ اللہ کا تعارف",
    "ترجمة المؤلف": "تعارفِ مؤلف رحمہ اللہ",
    "مواضعه في كتب المصطلح": "کتبِ مصطلح میں اس کے مقامات",

    // Narrator Biographical Terms & Ranks
    "ترجمة الراوي": "ترجمہ و حالاتِ راوی",
    "ترجمته": "حالاتِ زندگی",
    "ترجمة": "ترجمہ",
    "الاسم": "نام",
    "الاسم كاملًا مع الأقوال فيه": "مکمل نام مع اقوالِ ائمہ",
    "الكنية": "کنیت",
    "اللقب": "لقب",
    "النسب": "نسبت",
    "الشهرة": "شہرت",
    "الطبقة": "طبقہ",
    "المرتبة عند ابن حجر": "حافظ ابن حجر رحمہ اللہ کے نزدیک مرتبہ",
    "مرتبته عند ابن حجر": "حافظ ابن حجر رحمہ اللہ کے نزدیک مرتبہ",
    "مرتبته عند الذهبي": "امام ذہبی رحمہ اللہ کے نزدیک مرتبہ",
    "من ألفاظ التقريب": "الفاظِ تقریب التہذیب میں سے",
    "ألفاظ التقريب فقط": "صرف الفاظِ تقریب التہذیب",
    "الولادة": "ولادت",
    "بلد الولادة": "مقامِ ولادت",
    "الوفاة": "وفات",
    "وفاة من": "سنِ وفات از",
    "بلد الوفاة": "مقامِ وفات",
    "بلد الإقامة": "مقامِ قیام",
    "الرحلات": "علمی اسفار",
    "المذهب": "فقہی منہج / مسلک",
    "القرابات": "رشتہ داریاں",
    "الشيوخ": "شیوخ (اساتذہ)",
    "شيوخ": "شیوخ",
    "شيوخه": "ان کے شیوخ",
    "وشيخه:": "اور ان کے شیخ:",
    "التلاميذ": "تلامذہ (شاگرد)",
    "تلاميذ": "تلامذہ",
    "تلاميذه": "ان کے تلامذہ",
    "والراوي عنه:": "اور ان سے روایت کرنے والے:",
    "الشيوخ والتلاميذ": "شیوخ اور تلامذہ",
    "شيوخ الراوي وتلاميذه": "راوی کے اساتذہ اور شاگرد",
    "المرويات": "مرویات",
    "مرويات": "مرویات",
    "مروياته": "ان کی مرویات",
    "آثاره:": "ان کے آثار:",
    "روايته في الكتب": "کتبِ سنت میں ان کی روایات",
    "أسانيده": "ان کی اسانید",
    "صيغ الاسم في الأسانيد": "اسانید میں نام کی مختلف صورتیں",
    "صيغ التحمل والأداء": "صیغہ ہائے تحمل و اداء",
    "أقوال الجرح والتعديل": "ائمہ جرح و تعدیل کے اقوال",
    "ألفاظ الأئمة فيه": "راوی کے متعلق ائمہ کے الفاظ",
    "مصادر الترجمة": "مصادرِ ترجمہ",
    "الرواة حسب الطبقة": "طبقات کے لحاظ سے رواۃ",
    "الرواة حسب مرتبتهم عند ابن حجر": "حافظ ابن حجر رحمہ اللہ کے مراتب کے لحاظ سے رواۃ",
    "الرواة المشتركون": "مشترک رواۃ",
    "أكثر الرواة اشتراكًا في الأسانيد": "اسانید میں سب سے زیادہ مشترک رواۃ",
    "عدد الأحاديث بينهما": "دونوں کے درمیان احادیث کی تعداد",
    "لا يجتمعان في إسناد واحد.": "دونوں کسی ایک سند میں جمع نہیں ہوئے۔",
    "الطرق التي تصل بينهما في الأسانيد، من الأسفل إلى الأعلى.": "دونوں رواۃ کو ملانے والے اسنادی طرق (نیچے سے اوپر کی جانب)۔",
    "مرفوع": "مرفوع",
    "مرفوع حكمًا": "حکماً مرفوع",
    "موقوف": "موقوف",
    "موقوف لفظًا، وله حكم المرفوع.": "لفظاً موقوف، حکماً مرفوع۔",
    "مقطوع": "مقطوع",
    "قدسي": "حدیثِ قدسی",
    "مرسل": "مرسل",
    "متصل": "متصل",
    "منقطع": "منقطع",
    "معضل": "معضل",
    "معلق": "معلق",
    "له حكم الرفع": "مرفوع کے حکم میں",
    "ينتهي إلى التابعي فمن بعده.": "تابعی یا اس کے بعد والے راوی پر منتہی ہوتی ہے۔",
    "ينتهي إلى الصحابي من قوله أو فعله.": "صحابیٔ رسول ﷺ کے قول یا فعل پر منتہی ہوتی ہے۔",
    "حذف المصنف من أول إسناده راويًا فأكثر.": "مصنف نے ابتدائے سند سے ایک یا زائد راوی حذف کیے ہیں۔",
    "صحابي": "صحابیٔ رسول ﷺ",
    "ثقة ثبت": "ثقہ ثبت (اعلیٰ درجۂ ثقاہت)",
    "ثقة حافظ": "ثقہ حافظ",
    "ثقة": "ثقہ",
    "صدوق": "صدوق",
    "صدوق يهم": "صدوق (کبھی وہم کا شکار)",
    "مقبول": "مقبول (متابعت میں)",
    "مقبول / لين": "مقبول / لین الحدیث",
    "لين الحديث": "لین الحدیث",
    "مستور": "مستور الحال",
    "مستور / مجهول الحال": "مستور / مجہول الحال",
    "مجهول": "مجہول",
    "ضعيف": "ضعیف",
    "متروك": "متروک الحدیث",
    "متهم بالكذب": "متہم بالکذب",
    "كذاب": "کذاب (وضاع)",
    "الأماكن": "مقامات و بلدان",
    "الأنبياء": "انبیائے کرام علیہم السلام",
    "الشعراء": "شعراء",
    "الرجال": "رجال",
    "النساء": "خواتین راویات",
    "الحروف": "حروفِ تہجی",
    "المسائل": "مسائل",
    "المدار": "مدارِ سند",
    "المثل": "ضرب المثل",
    "نوع اللفظ": "لفظ کی قسم",

    // Settings, Theme, Contact, Drawer (`image_2.png`) & Empty States
    "القائمة": "مینیو",
    "إعدادات": "ترتیبات",
    "الإصدار": "نسخہ (ورژن)",
    "المظهر": "ظاہری وضع",
    "الوضع الفاتح": "روشن وضع (Light)",
    "الوضع الداكن": "تاریک وضع (Dark)",
    "تبديل الوضع الليلي": "روشن / تاریک وضع تبدیل کریں",
    "فاتح": "روشن",
    "داكن": "تاریک",
    "راسلنا": "رابطہ کریں",
    "الاسم (اختياري)": "نام (اختیاری)",
    "الرسالة": "آپ کا پیغام",
    "إرسال": "ارسال کریں",
    "إلغاء": "منسوخ کریں",
    "أرسلت رسالتك": "آپ کا پیغام موصول ہو گیا، جزاکم اللہ خیراً۔",
    "اشترك": "شامل ہوں",
    "اشترك لتصلك أخبارنا": "علمی اپڈیٹس کے لیے شامل ہوں",
    "أرسلنا رسالة لتأكيد اشتراكك.": "تصدیقی پیغام بھیج دیا گیا ہے۔",
    "حصل خطأ أثناء الاشتراك": "اندراج کے دوران خطا پیش آئی۔",
    "تابعنا": "ہمارے روابط",
    "تليجرام": "ٹیلی گرام",
    "تويتر": "ٹوئٹر",
    "فيسبوك": "فیس بک",
    "تطوير": "تشکیل و ترقی",
    "رعاية": "سرپرستی",
    "نقاية": "نقایہ",
    "جمعية آيات الخيرية": "جمعیۃ آیات الخیریہ",
    "مشاريع «نقاية»": "منصوبہ جاتِ «نقایہ»",
    "لم تبحث بعد": "ابھی آپ نے تلاش شروع نہیں کی",
    "لا نتائج": "کوئی نتیجہ نہیں ملا",
    "لا يوجد.": "موجود نہیں۔",
    "لا توجد نتائج.": "کوئی نتیجہ نہیں ملا۔",
    "لا توجد أحاديث مطابقة.": "مطابق احادیث نہیں ملیں۔",
    "لا توجد أحاديث بهذه الشروط.": "ان شرائط کے ساتھ کوئی حدیث نہیں ملی۔",
    "لا توجد أحاديث في هذا الباب.": "اس باب میں کوئی حدیث درج نہیں۔",
    "لا توجد أحاديث في هذا القسم.": "اس قسم میں کوئی حدیث درج نہیں۔",
    "لا توجد أحاديث في هذا الموضوع.": "اس موضوع میں کوئی حدیث درج نہیں۔",
    "لا توجد أحاديث مرتبطة بهذا اللفظ.": "اس لفظ سے متعلق کوئی حدیث نہیں ملی۔",
    "لا توجد أحاديث ولا تفسير لهذه الآية.": "اس آیت کے تحت کوئی حدیث یا تفسیر درج نہیں۔",
    "لا توجد أسانيد بهذه الشروط.": "ان شرائط کے ساتھ کوئی سند نہیں ملی۔",
    "لا توجد أطراف بهذه الشروط.": "ان شرائط کے ساتھ کوئی طرف نہیں ملا۔",
    "لا توجد ألفاظ بهذه الشروط.": "ان شرائط کے ساتھ کوئی الفاظ نہیں ملے۔",
    "لا توجد ألفاظ مطابقة.": "کوئی مطابق لفظ نہیں ملا۔",
    "لا توجد أمثال مطابقة.": "کوئی مطابق مثل نہیں ملی۔",
    "لا توجد محتويات لهذا الكتاب.": "اس کتاب کی فہرست دستیاب نہیں۔",
    "لا توجد مداخل بهذه الشروط.": "ان شرائط کے ساتھ کوئی اندراج نہیں ملا۔",
    "لا توجد مرويات مرتبطة بأسانيد هذا الراوي.": "اس راوی کی اسانید سے متعلق مرویات نہیں ملیں۔",
    "لا توجد مواضع ولا أقوال لهذا المصطلح.": "اس اصطلاح کے مواضع یا اقوال درج نہیں۔",
    "لا توجد موضوعات مطابقة.": "کوئی مطابق موضوع نہیں ملا۔",
    "لا يوجد رواة مطابقون.": "کوئی مطابق راوی نہیں ملا۔",
    "لا يوجد رواة بهذه الشروط.": "ان شرائط کے ساتھ کوئی راوی نہیں ملا۔",
    "لا يوجد علماء بهذا الاسم.": "اس نام کے ساتھ کوئی عالم درج نہیں۔",
    "لم يرتبط هذا اللفظ براوٍ.": "یہ لفظ کسی راوی سے مربوط نہیں۔",
    "نص الترجمة غير متوفر.": "ترجمۂ راوی کا متن دستیاب نہیں۔",
    "الصفحة غير موجودة": "صفحہ موجود نہیں",
    "تعذر تحميل الصفحة": "صفحہ لوڈ کرنے میں دشواری پیش آئی",
    "حدثت مشكلة في البحث، تأكد من اتصال الشبكة أو حاول لاحقًا": "تلاش کے دوران رابطے میں رکاوٹ پیش آئی؛ براہِ کرم دوبارہ کوشش کریں۔",
    "حدث خلل أثناء تحميل هذه الصفحة. حاول مرة أخرى أو عد إلى الرئيسية لمتابعة التصفح.": "صفحہ لوڈ کرنے میں دشواری پیش آئی۔ دوبارہ کوشش کریں یا صفحۂ اول پر واپس جائیں۔",
    "حدث خطأ": "تکنیکی خطا پیش آئی",
    "حصل خطأ": "تکنیکی خطا پیش آئی",
    "نتائج البحث": "نتائجِ تلاش",
    "عدد الأحاديث": "تعدادِ احادیث",
    "عدد الرواة": "تعدادِ رواۃ",
    "عدد الأقوال": "تعدادِ اقوال",
    "الأحاديث": "احادیث",
    "الحديث": "حدیث",
    "التراجم": "تراجمِ رواۃ",
    "التفسير": "تفسیرِ آیات",
    "الآيات": "آیاتِ قرآنیہ",
    "الآية": "آیت",
    "سورة": "سورۃ",
  };

  function translateDynamicUiPhrase(s) {
    if (UI_EXACT_AR_TO_UR[s]) return UI_EXACT_AR_TO_UR[s];

    // Home results counter (`عدد النتائج: ٠` / `عدد النتائج: ١٬٢٣٤`)
    const mRes = s.match(/^عدد النتائج:\s*(.*)$/);
    if (mRes) {
      return `تعدادِ نتائج: ${mRes[1]}`;
    }

    // `/collections` dynamic subtitle (`٣٣ كتابًا من الأصول، مع التخريج وأحكام العلماء وتراجم الرواة.`)
    const mColSub = s.match(/^([٠-٩0-9٬,]+)\s+كتابًا من الأصول، مع التخريج وأحكام العلماء وتراجم الرواة\.?$/);
    if (mColSub) {
      return `${mColSub[1]} بنیادی کتبِ سنت، مع تخریج، احکامِ محدثین اور تراجمِ رواۃ۔`;
    }

    // Author + death year (`البخاري، ت ٢٥٦ هـ` or `(ت ٢٥٦ هـ)` or `ت ٢٥٦ هـ`)
    const mAuthDeath = s.match(/^(.+?)،\s*ت\s*([٠-٩0-9]+)\s*هـ$/);
    if (mAuthDeath) {
      return `${mAuthDeath[1]}، وفات ${mAuthDeath[2]}ھ`;
    }

    const mDeath = s.match(/^(\(?\s*)ت\s+([٠-٩0-9]+)\s*هـ(\s*\)?)$/);
    if (mDeath) {
      return `${mDeath[1]}وفات ${mDeath[2]}ھ${mDeath[3]}`;
    }

    // Count labels (`١٬٢٣٤ حديث`, `٣٣ كتابًا`, `٥٠٠ راوٍ`, `١٢٠ بابًا`)
    const mHadCnt = s.match(/^([٠-٩0-9٬,]+)\s+(حديثًا|حديثا|حديث|أحاديث)$/);
    if (mHadCnt) return `${mHadCnt[1]} احادیث`;

    const mBookCnt = s.match(/^([٠-٩0-9٬,]+)\s+(كتابًا|كتابا|كتاب|كتب)$/);
    if (mBookCnt) return `${mBookCnt[1]} کتب`;

    const mRawiCnt = s.match(/^([٠-٩0-9٬,]+)\s+(راويًا|راويا|راوٍ|راو|رواة)$/);
    if (mRawiCnt) return `${mRawiCnt[1]} رواۃ`;

    const mBabCnt = s.match(/^([٠-٩0-9٬,]+)\s+(بابًا|بابا|باب|أبواب)$/);
    if (mBabCnt) return `${mBabCnt[1]} ابواب`;

    const mQawlCnt = s.match(/^([٠-٩0-9٬,]+)\s+(قولًا|قولا|قول|أقوال)$/);
    if (mQawlCnt) return `${mQawlCnt[1]} اقوال`;

    const mTarafCnt = s.match(/^([٠-٩0-9٬,]+)\s+(طرفًا|طرفا|طرف|أطراف)$/);
    if (mTarafCnt) return `${mTarafCnt[1]} اطراف`;

    return null;
  }

  function isProtectedArabicContentNode(el) {
    if (!el || !el.closest) return false;
    return Boolean(
      el.closest(
        ".text-reading, .text-matn, .sharh-ar-body, .ur-hadith-block, .ur-sharh-block, .ur-enc-translation, #albahith-lexicon-overlay, #albahith-topbar, #albahith-font-popover, code, pre, script, style"
      )
    );
  }

  function localizeSubtree(root) {
    if (!root) return;
    const isUrdu = currentLang === "ur";

    // 1. Attributes (`placeholder`, `title`, `aria-label`) + W3C BiDi `dir="auto"` on inputs
    const biDiInputs = root.querySelectorAll ? root.querySelectorAll("input[type='search'], input[type='text'], textarea") : [];
    for (const inp of biDiInputs) {
      if (!inp.hasAttribute("dir")) inp.setAttribute("dir", "auto");
    }
    const attrEls = root.querySelectorAll
      ? root.querySelectorAll("[placeholder],[title],[aria-label]")
      : [];
    for (const el of attrEls) {
      if (el.closest("#albahith-lexicon-overlay, #albahith-topbar, #albahith-font-popover")) continue;
      for (const [attr, dataKey] of [
        ["placeholder", "origPlaceholder"],
        ["title", "origTitle"],
        ["aria-label", "origAriaLabel"],
      ]) {
        if (!el.hasAttribute(attr)) continue;
        const cur = el.getAttribute(attr) || "";
        if (isUrdu) {
          const orig = el.dataset[dataKey] || cur;
          const tr = translateDynamicUiPhrase(orig.trim());
          if (tr && cur !== tr) {
            if (!el.dataset[dataKey]) el.dataset[dataKey] = orig;
            el.setAttribute(attr, tr);
          }
        } else if (el.dataset[dataKey]) {
          el.setAttribute(attr, el.dataset[dataKey]);
        }
      }
    }

    // 2. Text Nodes
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
      const parent = node.parentElement;
      if (!parent) continue;
      const tag = parent.tagName;
      if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT" || tag === "TEXTAREA") continue;

      if (!isUrdu) {
        if (node.__origAr !== undefined && node.nodeValue !== node.__origAr) {
          node.nodeValue = node.__origAr;
        }
        if (parent.hasAttribute("data-ur-localized")) {
          parent.removeAttribute("data-ur-localized");
        }
        continue;
      }

      if (isProtectedArabicContentNode(parent)) {
        const rawTrim = (node.__origAr !== undefined ? node.__origAr : node.nodeValue || "").trim();
        if (!UI_EXACT_AR_TO_UR[rawTrim]) continue;
      }

      // Keep Home Arabic Hadith body (`li.svelte-adnwyt` main text) 100% pure vocalized Arabic in `Kitab`
      // while `.ur-hadith-block` directly underneath renders the full Salafi Urdu Nastaleeq translation!
      if (parent.closest("li.svelte-adnwyt") && !parent.closest(".h-info, button, .sharh")) {
        continue;
      }

      const baseText = node.__origAr !== undefined ? node.__origAr : (node.nodeValue || "");
      const trimmed = baseText.replace(/\s+/g, " ").trim();
      if (!trimmed || trimmed.length > 130) continue;

      // Handle dynamic `عدد النتائج: ...` updates from Svelte reactivity even after first localization
      if (node.__origAr !== undefined && trimmed.startsWith("عدد النتائج:")) {
        node.__origAr = baseText;
      }
      const currentTrimmed = (node.nodeValue || "").replace(/\s+/g, " ").trim();
      const sourceToTranslate = currentTrimmed.startsWith("عدد النتائج:")
        ? currentTrimmed
        : trimmed;

      const tr = translateDynamicUiPhrase(sourceToTranslate);
      if (tr) {
        if (node.__origAr === undefined || currentTrimmed.startsWith("عدد النتائج:")) {
          node.__origAr = currentTrimmed.startsWith("عدد النتائج:") ? node.nodeValue : baseText;
        }
        const lead = (baseText.match(/^\s*/) || [""])[0];
        const trail = (baseText.match(/\s*$/) || [""])[0];
        const nextVal = lead + tr + trail;
        if (node.nodeValue !== nextVal) {
          node.nodeValue = nextVal;
        }
        parent.setAttribute("data-ur-localized", "1");
      }
    }
  }

  /* ------------------------------------------------------------------------
   * 4. Encyclopedia (`/(site)/*`) Salafi Urdu Hadith & Book Enrichment
   * ------------------------------------------------------------------------ */
  function bareArabicFingerprint(str) {
    return String(str || "")
      .replace(/[\u064B-\u065F\u0670\u0640]/g, "")
      .replace(/[أإآٱ]/g, "ا")
      .replace(/ة/g, "ه")
      .replace(/ى/g, "ي")
      .replace(/[^\u0621-\u064A]/g, "")
      .slice(0, 42);
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function buildEncUrduCardHtml(urduText, sharhUrdu, badgeLabel) {
    const badge = badgeLabel
      ? `<span class="ur-enc-badge">${escapeHtml(badgeLabel)}</span><br>`
      : "";
    const sharhPart = sharhUrdu
      ? `<div class="ur-enc-sharh"><strong>شرح و فوائد:</strong> ${escapeHtml(sharhUrdu)}</div>`
      : "";
    return `${badge}<span>${escapeHtml(urduText)}</span>${sharhPart}`;
  }

  function injectAfterElement(targetEl, keyId, htmlContent) {
    if (!targetEl || !targetEl.parentNode) return;
    let existing = targetEl.nextElementSibling;
    if (existing && existing.classList && existing.classList.contains("ur-enc-translation")) {
      if (existing.dataset.urKey === keyId) return;
      existing.dataset.urKey = keyId;
      existing.innerHTML = htmlContent;
      return;
    }
    if (existing && existing.classList && existing.classList.contains("ur-tx-btn")) {
      existing.remove();
    }
    const div = document.createElement("div");
    div.className = "ur-enc-translation";
    div.dir = "rtl";
    div.dataset.urKey = keyId;
    div.innerHTML = htmlContent;
    targetEl.insertAdjacentElement("afterend", div);
  }

  function attachOnDemandTranslateBtn(targetEl, arText) {
    if (!targetEl || !targetEl.parentNode || !arText || arText.length < 18) return;
    const nxt = targetEl.nextElementSibling;
    if (nxt && nxt.classList && (nxt.classList.contains("ur-enc-translation") || nxt.classList.contains("ur-tx-btn"))) {
      return;
    }
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ur-tx-btn";
    btn.textContent = "اردو ترجمہ دیکھیں";
    btn.addEventListener("click", async (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      btn.disabled = true;
      btn.textContent = "اردو ترجمہ لوڈ ہو رہا ہے...";
      try {
        const r = await origFetch(`${BASE_PATH}/api/v1/translate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text_ar: arText, kind: "matn" }),
        });
        const j = await r.json();
        if (j && j.translated_ur) {
          injectAfterElement(
            targetEl,
            "live_" + bareArabicFingerprint(arText),
            buildEncUrduCardHtml(j.translated_ur, "", "سلفی اردو ترجمہ")
          );
        } else {
          btn.textContent = "دوبارہ کوشش کریں";
          btn.disabled = false;
        }
      } catch (_) {
        btn.textContent = "دوبارہ کوشش کریں";
        btn.disabled = false;
      }
    });
    targetEl.insertAdjacentElement("afterend", btn);
  }

  function applyEncyclopediaUrduEnrichment() {
    if (currentLang !== "ur") return;
    const data = window.__ALBAHITH_ENC_DATA__;
    if (!data || typeof data !== "object") return;

    const path = stripBasePath(window.location.pathname);

    // A. `/collections` 33 Canonical Books Grid
    if (path === "/collections" && Array.isArray(data.collections)) {
      const byTitle = new Map();
      for (const c of data.collections) {
        if (c && c.title && c.title_ur) {
          byTitle.set(c.title.trim(), c);
        }
      }
      const links = document.querySelectorAll('a[href*="/collections/"]');
      for (const a of links) {
        if (a.querySelector(".ur-col-sub")) continue;
        const hEl = a.querySelector(".font-serif");
        if (!hEl) continue;
        const tRaw = (hEl.textContent || "").trim();
        const meta = byTitle.get(tRaw);
        if (meta && meta.title_ur) {
          const sub = document.createElement("span");
          sub.className = "ur-col-sub";
          sub.textContent = meta.author_ur ? `${meta.title_ur} — ${meta.author_ur}` : meta.title_ur;
          hEl.insertAdjacentElement("afterend", sub);
        }
      }
    }

    // B. Single Encyclopedia Hadith (`/hadith/[id]`)
    if (data.hadith && data.hadith.content && data.hadith.content_urdu) {
      const fp = bareArabicFingerprint(data.hadith.content);
      const paras = document.querySelectorAll(".font-serif.text-reading");
      for (const p of paras) {
        if (bareArabicFingerprint(p.textContent) === fp || paras.length === 1) {
          injectAfterElement(
            p,
            "had_" + (data.hadith.id || fp),
            buildEncUrduCardHtml(
              data.hadith.content_urdu,
              data.hadith.sharh_urdu || "",
              data.hadith.urdu_source || "سلفی اردو ترجمہ"
            )
          );
          break;
        }
      }
    }

    // C. Single Dorar Hadith (`/dorar/hadith/[hash]`)
    if (data.hadith && data.hadith.hash && data.hadith.text_urdu) {
      const target = document.querySelector(".font-serif.text-reading");
      if (target) {
        const badge = data.hadith.hukm_ur
          ? `حکمِ حدیث: ${data.hadith.hukm_ur}`
          : "سلفی اردو ترجمہ";
        injectAfterElement(
          target,
          "dorar_" + data.hadith.hash,
          buildEncUrduCardHtml(data.hadith.text_urdu, data.hadith.sharh_urdu || "", badge)
        );
      }
    }

    // D. Paginated Hadiths List (`chapter`, `subject`, `narrator/hadiths`, `search`, `controversial`, `proverbs`, `quran`)
    if (Array.isArray(data.hadiths) && data.hadiths.length > 0) {
      const fpMap = new Map();
      for (const h of data.hadiths) {
        if (!h) continue;
        const ar = h.content || h.text || (Array.isArray(h.parts) ? h.parts.join("") : "");
        const ur = h.content_urdu || h.text_urdu || "";
        if (ar) {
          fpMap.set(bareArabicFingerprint(ar), { ar, ur, src: h.urdu_source || "سلفی اردو ترجمہ", id: h.id || "" });
        }
      }
      const blocks = document.querySelectorAll(".font-serif.text-reading, .font-serif.text-matn");
      for (const b of blocks) {
        if (b.closest("blockquote")) continue;
        const txt = (b.textContent || "").trim();
        if (txt.length < 16) continue;
        const fp = bareArabicFingerprint(txt);
        const hit = fpMap.get(fp);
        if (hit && hit.ur) {
          injectAfterElement(b, "lst_" + (hit.id || fp), buildEncUrduCardHtml(hit.ur, "", hit.src));
        } else if (txt.length >= 25) {
          attachOnDemandTranslateBtn(b, txt);
        }
      }
    }
  }

  let encTimer1 = null;
  let encTimer2 = null;
  function scheduleEncyclopediaPass() {
    clearTimeout(encTimer1);
    clearTimeout(encTimer2);
    encTimer1 = setTimeout(() => {
      syncHeaderPlacement();
      localizeSubtree(document.body);
      applyEncyclopediaUrduEnrichment();
    }, 55);
    encTimer2 = setTimeout(() => {
      syncHeaderPlacement();
      localizeSubtree(document.body);
      applyEncyclopediaUrduEnrichment();
    }, 260);
  }

  /* ------------------------------------------------------------------------
   * 5. Rekhta & Qari 283,601-Word Urdu-Arabic Lexicon Modal & Double-Click
   * ------------------------------------------------------------------------ */
  function openLexiconModal(initialWord) {
    const overlay = document.getElementById("albahith-lexicon-overlay");
    const inp = document.getElementById("albahith-lexicon-input");
    if (!overlay || !inp) return;
    overlay.hidden = false;
    if (initialWord) {
      inp.value = initialWord;
      runLexiconLookup(initialWord);
    } else {
      inp.focus();
    }
  }

  async function runLexiconLookup(word) {
    const body = document.getElementById("albahith-lexicon-body");
    if (!body) return;
    const q = String(word || "").trim();
    if (!q) {
      body.innerHTML = `<p style="text-align:center;color:var(--ab-muted);">کوئی بھی عربی یا اردو لفظ لکھ کر تلاش کریں (یا کسی بھی حدیث کے لفظ پر ڈبل کلک کریں)۔</p>`;
      return;
    }
    body.innerHTML = `<p style="text-align:center;color:var(--ab-muted);">«${escapeHtml(q)}» کی تحقیق جاری ہے...</p>`;
    try {
      const resp = await origFetch(`${BASE_PATH}/api/v1/lexicon/lookup?q=${encodeURIComponent(q)}&limit=20`);
      const data = await resp.json();
      const entries = data.entries || [];
      const gharib = data.gharib_matches || [];
      if (entries.length === 0 && gharib.length === 0) {
        body.innerHTML = `<p style="text-align:center;color:var(--ab-muted);">«${escapeHtml(q)}» کے لیے براہِ راست اندراج نہیں ملا۔ لفظ کا مجرد مادہ یا مفرد صورت لکھ کر دیکھیں۔</p>`;
        return;
      }
      const chunks = [];
      for (const g of gharib) {
        chunks.push(
          `<div class="ab-lx-item">
            <div><span class="ab-lx-word">${escapeHtml(g.word)}</span> <span class="ab-lx-root">[غریب الحدیث]</span></div>
            <div class="ab-lx-meaning">${escapeHtml(g.meaning_ur || g.meaning_ar)}</div>
          </div>`
        );
      }
      for (const e of entries) {
        const rootBadge = e.root_letters ? `<span class="ab-lx-root">مادہ: <bdi>${escapeHtml(e.root_letters)}</bdi></span>` : "";
        chunks.push(
          `<div class="ab-lx-item">
            <div><span class="ab-lx-word">${escapeHtml(e.word_ar || e.word_bare)}</span>${rootBadge}</div>
            <div class="ab-lx-meaning">${escapeHtml(e.meaning_ur || "")}</div>
          </div>`
        );
      }
      body.innerHTML = chunks.join("");
    } catch (_) {
      body.innerHTML = `<p style="text-align:center;color:var(--ab-muted);">لغت سرور سے رابطہ ممکن نہ ہو سکا۔</p>`;
    }
  }

  /* ------------------------------------------------------------------------
   * 5B. Scholarly Hybrid RAG, 3-Tier Living Memory, StagedProposals & Offline Sync
   * ------------------------------------------------------------------------ */
  const OFFLINE_QUEUE_KEY = "albahith_offline_proposal_queue";

  function readOfflineQueue() {
    try {
      return JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || "[]") || [];
    } catch (_) {
      return [];
    }
  }

  function writeOfflineQueue(arr) {
    try {
      localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(arr));
    } catch (_) {}
  }

  async function flushOfflineQueue() {
    const q = readOfflineQueue();
    if (!q.length || (typeof navigator !== "undefined" && navigator.onLine === false)) return;
    const remaining = [];
    for (const item of q) {
      try {
        const r = await origFetch(`${BASE_PATH}/api/v1/proposals`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(item),
        });
        if (!r.ok) remaining.push(item);
      } catch (_) {
        remaining.push(item);
      }
    }
    writeOfflineQueue(remaining);
  }
  window.addEventListener("online", () => {
    flushOfflineQueue();
  });

  function openResearchModal(initialTab) {
    const ov = document.getElementById("albahith-research-overlay");
    if (!ov) return;
    ov.hidden = false;
    switchResearchTab(initialTab || "rag");
  }

  function switchResearchTab(tabName) {
    for (const btn of document.querySelectorAll("#albahith-research-card .ab-rs-tab")) {
      btn.classList.toggle("is-active", btn.dataset.tab === tabName);
    }
    for (const pane of document.querySelectorAll("#albahith-research-card .ab-rs-pane")) {
      pane.hidden = pane.dataset.pane !== tabName;
    }
    if (tabName === "memory") refreshLivingMemoryPane();
    if (tabName === "proposals") refreshStagedProposalsPane();
  }

  async function runHybridRagQuery(qStr) {
    const out = document.getElementById("ab-rag-output");
    if (!out) return;
    const q = String(qStr || "").trim();
    if (!q) return;
    out.innerHTML = `<p style="color:var(--ab-muted);">مستند ذخیرے میں ہائبرڈ تلاش (BM25 + Dense + RRF + Reranker) جاری ہے...</p>`;
    try {
      const r = await origFetch(`${BASE_PATH}/api/v1/rag/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, top_k: 5 }),
      });
      const data = await r.json();
      if (data.abstained) {
        out.innerHTML = `<div class="ab-abstain-box" role="status"><strong>علمی احتیاط (Abstention Gate):</strong><br>${escapeHtml(data.answer_ur || "دستیاب مستند ذخیرے میں اس سوال کا واضح حوالہ موجود نہیں۔")}</div>`;
        return;
      }
      const cards = (data.citations || []).map((c) => `
        <div class="ab-lx-item">
          <div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;">
            <strong><bdi>[${escapeHtml(c.citation_id)}]</bdi> ${escapeHtml(c.book_ur || c.book_ar)} — حدیث/صفحہ: <bdi>${escapeHtml(c.number_or_page)}</bdi></strong>
            <span style="font-size:0.8rem;color:var(--ab-accent);">حکم: ${escapeHtml(c.grade_ur || c.grade_ar)} • مطابقت: <bdi>${Math.round((c.rerank_score || 0) * 100)}%</bdi></span>
          </div>
          <div class="sharh-ar-body" style="margin-block-start:4px;">${escapeHtml(c.canonical_snapshot || "")}</div>
          ${c.urdu_snapshot ? `<div class="ur-hadith-block">${escapeHtml(c.urdu_snapshot)}</div>` : ""}
        </div>
      `);
      out.innerHTML = cards.join("");
    } catch (_) {
      out.innerHTML = `<p style="color:var(--ab-muted);">تحقیقی انجن سے رابطہ ممکن نہ ہو سکا۔</p>`;
    }
  }

  async function refreshLivingMemoryPane() {
    const listEl = document.getElementById("ab-mem-list");
    if (!listEl) return;
    try {
      const r = await origFetch(`${BASE_PATH}/api/v1/memory`);
      const data = await r.json();
      const items = data.items || [];
      if (!items.length) {
        listEl.innerHTML = `<p style="color:var(--ab-muted);font-size:0.9rem;">ابھی کوئی تحقیقی ترجیح محفوظ نہیں۔</p>`;
        return;
      }
      const tierLbl = { 1: "درجہ ۱ (مستقل ترجیح)", 2: "درجہ ۲ (زیرِ تحقیق مع میعاد)", 3: "درجہ ۳ (سیشن کنٹیکسٹ)" };
      listEl.innerHTML = items.map((m) => `
        <div class="ab-mem-row">
          <div>
            <div style="font-size:0.78rem;color:var(--ab-accent);">${tierLbl[m.tier] || "درجہ ۱"} • <bdi>${escapeHtml(m.valid_from || "")}</bdi></div>
            <div><strong>${escapeHtml(m.fact_key)}:</strong> ${escapeHtml(m.fact_value)}</div>
          </div>
          <button type="button" class="ur-tx-btn ab-mem-del-btn" data-mid="${m.id}">حذف کریں</button>
        </div>
      `).join("");
      for (const b of listEl.querySelectorAll(".ab-mem-del-btn")) {
        b.addEventListener("click", async () => {
          await origFetch(`${BASE_PATH}/api/v1/memory/${b.dataset.mid}`, { method: "DELETE" });
          refreshLivingMemoryPane();
        });
      }
    } catch (_) {}
  }

  async function refreshStagedProposalsPane() {
    const listEl = document.getElementById("ab-prop-list");
    if (!listEl) return;
    await flushOfflineQueue();
    const offlinePending = readOfflineQueue();
    try {
      const r = await origFetch(`${BASE_PATH}/api/v1/proposals`);
      const data = await r.json();
      const items = data.items || [];
      const offlineBanner = offlinePending.length
        ? `<div class="ab-abstain-box" style="margin-block-end:10px;">آف لائن قطار میں <bdi>${offlinePending.length}</bdi> مسودات محفوظ ہیں (انٹرنیٹ بحال ہوتے ہی خودکار سنک ہوں گے)۔</div>`
        : "";
      if (!items.length) {
        listEl.innerHTML = offlineBanner + `<p style="color:var(--ab-muted);font-size:0.9rem;">اس وقت کوئی زیرِ التوا تجویز موجود نہیں۔</p>`;
        return;
      }
      listEl.innerHTML = offlineBanner + items.map((p) => `
        <div class="ab-staged-card" data-pid="${p.id}">
          <div style="display:flex;justify-content:space-between;font-size:0.82rem;">
            <strong>ہدف: <bdi>${escapeHtml(p.target_id)}</bdi> (${escapeHtml(p.target_type)})</strong>
            <span style="color:var(--ab-accent);">حالت: <bdi>${escapeHtml(p.status)}</bdi></span>
          </div>
          <div class="ab-staged-diff">${escapeHtml(p.proposed_text)}<div style="font-size:0.8rem;color:var(--ab-muted);margin-block-start:4px;"><bdi>${escapeHtml(p.diff_summary || "")}</bdi></div></div>
          <div class="ab-staged-risk">${escapeHtml(p.risk_summary || "")}</div>
          ${p.status === "pending" ? `
            <div class="ab-staged-actions">
              <button type="button" class="ur-tx-btn ab-prop-act" data-act="approve" data-pid="${p.id}" style="border-color:var(--ab-accent);color:var(--ab-accent);font-weight:600;">تجویز قبول کریں</button>
              <button type="button" class="ur-tx-btn ab-prop-edit" data-pid="${p.id}">ترمیم کریں</button>
              <button type="button" class="ur-tx-btn ab-prop-act" data-act="reject" data-pid="${p.id}">رد کریں</button>
            </div>
          ` : ""}
        </div>
      `).join("");
      for (const b of listEl.querySelectorAll(".ab-prop-act")) {
        b.addEventListener("click", async () => {
          await origFetch(`${BASE_PATH}/api/v1/proposals/${b.dataset.pid}/review`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: b.dataset.act }),
          });
          refreshStagedProposalsPane();
        });
      }
      for (const b of listEl.querySelectorAll(".ab-prop-edit")) {
        b.addEventListener("click", async () => {
          const card = b.closest(".ab-staged-card");
          const curTxt = card ? card.querySelector(".ab-staged-diff")?.childNodes[0]?.textContent || "" : "";
          const nextTxt = window.prompt("تجویز کردہ عبارت میں ترمیم کریں:", curTxt);
          if (nextTxt && nextTxt.trim()) {
            await origFetch(`${BASE_PATH}/api/v1/proposals/${b.dataset.pid}/review`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action: "approve", edited_text: nextTxt.trim() }),
            });
            refreshStagedProposalsPane();
          }
        });
      }
    } catch (_) {}
  }

  function maybeMountDevComponentInspector() {
    try {
      const qs = window.location.search || "";
      const hs = window.location.hash || "";
      if (!qs.includes("__inspector=1") && hs !== "#__inspector") return;
      if (document.getElementById("albahith-dev-inspector")) return;
      const wrap = document.createElement("div");
      wrap.id = "albahith-dev-inspector";
      wrap.innerHTML = `
        <div style="max-width:820px;margin-inline:auto;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-block-end:16px;">
            <h2 style="margin:0;color:var(--ab-accent);">الباحث الحديثي — Dev Component Inspector (<bdi>Zero-Prod-Impact</bdi>)</h2>
            <button type="button" class="ur-tx-btn" id="ab-close-inspector">✕ بند کریں</button>
          </div>
          <section class="ab-staged-card">
            <strong>۱۔ نستعلیق عمودی بلندی و عدمِ کٹائی ٹیسٹ (Nastaliq ک/گ Clipping Check — <bdi>line-height: 2.28</bdi>)</strong>
            <div class="ur-hadith-block">سیدنا عمر بن خطاب رضی اللہ عنہ سے روایت ہے کہ رسول اللہ ﷺ نے فرمایا: اعمال کا دارومدار نیتوں پر ہے، اور ہر شخص کے لیے وہی ہے جس کی اس نے نیت کی۔ کتاب و سنت کی روشنی میں گفتگو، پاکیزگی اور اخلاص۔</div>
          </section>
          <section class="ab-staged-card">
            <strong>۲۔ علمی احتیاط (Abstention Threshold <bdi>&lt; 0.22</bdi>)</strong>
            <div class="ab-abstain-box">دستیاب مستند ذخیرے میں اس سوال کا واضح حوالہ موجود نہیں۔</div>
          </section>
          <section class="ab-staged-card">
            <strong>۳۔ اسٹیجڈ ہیومن-ان-دی-لوپ کارڈ (<bdi>&lt;StagedProposalCard /&gt;</bdi>)</strong>
            <div class="ab-staged-diff">انما الاعمال بالنیات کا سلیس سلفی اردو ترجمہ <bdi>[+ مستند اضافہ]</bdi></div>
            <div class="ab-staged-risk">یہ تجویز زیرِ التوا (Pending) ہے؛ انسانی منظوری کے بغیر ڈیٹا بیس میں کوئی تبدیلی نہیں ہوگی۔</div>
            <div class="ab-staged-actions">
              <button type="button" class="ur-tx-btn">تجویز قبول کریں</button>
              <button type="button" class="ur-tx-btn">ترمیم کریں</button>
              <button type="button" class="ur-tx-btn">رد کریں</button>
            </div>
          </section>
        </div>
      `;
      document.body.appendChild(wrap);
      document.getElementById("ab-close-inspector").addEventListener("click", () => wrap.remove());
    } catch (_) {}
  }

  /* ------------------------------------------------------------------------
   * 6. Native Header Integration (`اردو | عربي | لغت | معاون | خط`) & Drawer Items
   * ------------------------------------------------------------------------ */
  function refreshHomeSearchIfNeeded() {
    if (!isHomePath(window.location.pathname)) return;
    const inp = document.querySelector("#search-input input, input[type='search']");
    if (inp && inp.value && inp.value.trim()) {
      const v = inp.value;
      inp.value = v + " ";
      inp.dispatchEvent(new Event("input", { bubbles: true }));
      setTimeout(() => {
        inp.value = v;
        inp.dispatchEvent(new Event("input", { bubbles: true }));
      }, 25);
    }
  }

  function setLanguage(nextLang) {
    if (nextLang !== "ur" && nextLang !== "ar") return;
    const changed = currentLang !== nextLang;
    currentLang = nextLang;
    persistLangCookie(currentLang);
    updateTopbarActiveState();
    localizeSubtree(document.body);
    if (currentLang === "ur") {
      applyEncyclopediaUrduEnrichment();
    }
    if (changed) {
      refreshHomeSearchIfNeeded();
    }
  }

  function updateTopbarActiveState() {
    const btnUr = document.getElementById("ab-btn-ur");
    const btnAr = document.getElementById("ab-btn-ar");
    if (btnUr) btnUr.classList.toggle("is-active", currentLang === "ur");
    if (btnAr) btnAr.classList.toggle("is-active", currentLang === "ar");
    const drwLang = document.getElementById("ab-drawer-lang-label");
    if (drwLang) {
      drwLang.textContent = currentLang === "ur" ? "زبان: اردو ⇄ عربي" : "اللغة: العربية ⇄ اردو";
    }
    const drwLex = document.getElementById("ab-drawer-lex-label");
    if (drwLex) {
      drwLex.textContent = currentLang === "ur" ? "معجم ریختہ و غریب الحدیث" : "معجم ريخته وغريب الحديث";
    }
    const drwRs = document.getElementById("ab-drawer-rs-label");
    if (drwRs) {
      drwRs.textContent = currentLang === "ur" ? "علمی معاون، یادداشت و مسودات" : "المعاون العلمي والذاكرة";
    }
    const drwFont = document.getElementById("ab-drawer-font-label");
    if (drwFont) {
      drwFont.textContent = currentLang === "ur" ? "اردو رسم الخط و حجم" : "الخط الأردي وحجمه";
    }
    const segUr = document.getElementById("ab-seg-ur");
    const segAr = document.getElementById("ab-seg-ar");
    if (segUr) segUr.classList.toggle("active", currentLang === "ur");
    if (segAr) segAr.classList.toggle("active", currentLang === "ar");
  }

  function syncHeaderPlacement() {
    const pageHdr = document.getElementById("page-header");
    const siteSlot = document.querySelector("header .ms-auto");
    if (pageHdr || siteSlot) {
      document.documentElement.setAttribute("data-sk-mounted", "1");
    }

    // Rewrite root-absolute `/assets/...` images & internal links when running under a subpath proxy
    if (BASE_PATH) {
      for (const img of document.querySelectorAll('img[src^="/assets/"]')) {
        const rawSrc = img.getAttribute("src");
        if (rawSrc && !rawSrc.startsWith(BASE_PATH + "/")) {
          img.setAttribute("src", BASE_PATH + rawSrc);
        }
      }
      for (const a of document.querySelectorAll('a[href^="/"]')) {
        const rawHref = a.getAttribute("href");
        if (rawHref && !rawHref.startsWith("//") && !rawHref.startsWith(BASE_PATH + "/") && rawHref !== BASE_PATH) {
          a.setAttribute("href", rawHref === "/" ? BASE_PATH + "/" : BASE_PATH + rawHref);
        }
      }
    }

    const bar = document.getElementById("albahith-topbar");
    if (!bar) return;

    // If on `/(site)/*`, mount inline inside `header .ms-auto` right next to the dark-mode toggle!
    if (siteSlot && !isHomePath(window.location.pathname)) {
      if (bar.parentElement !== siteSlot) {
        siteSlot.insertBefore(bar, siteSlot.firstChild);
      }
      bar.classList.remove("is-home-mode");
      bar.classList.add("is-site-mode");
    } else {
      if (bar.parentElement !== document.body) {
        document.body.appendChild(bar);
      }
      bar.classList.remove("is-site-mode");
      bar.classList.add("is-home-mode");
    }

    // Inject native monochrome Lucide rows inside Home `☰` drawer (`nav.svelte-1ga7kze ul.menu-card` under `القائمة`)
    const menuCards = document.querySelectorAll("nav.svelte-1ga7kze ul.menu-card");
    if (menuCards.length >= 2) {
      const qaimaList = menuCards[1];
      if (qaimaList && !qaimaList.querySelector("#ab-drawer-lex-btn")) {
        const firstLi = qaimaList.querySelector("li");
        const anchorAfterSettings = firstLi ? firstLi.nextSibling : qaimaList.firstChild;
        const sampleBtn = qaimaList.querySelector("button.menu-action");
        const svelteClass = sampleBtn
          ? Array.from(sampleBtn.classList).filter((c) => c.startsWith("svelte-")).join(" ")
          : "";
        const svgLang = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg>`;
        const svgBook = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"/></svg>`;
        const svgSpark = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v18"/><path d="M3 12h18"/><circle cx="12" cy="12" r="9"/></svg>`;
        const svgFont = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/><line x1="12" x2="12" y1="4" y2="20"/></svg>`;

        const liLang = document.createElement("li");
        if (firstLi) liLang.className = firstLi.className;
        liLang.innerHTML = `<button type="button" id="ab-drawer-lang-btn" class="menu-action ${svelteClass}"><span class="icon-wrap ${svelteClass}">${svgLang}</span> <span id="ab-drawer-lang-label" data-ur-localized="1"></span></button>`;

        const liLex = document.createElement("li");
        if (firstLi) liLex.className = firstLi.className;
        liLex.innerHTML = `<button type="button" id="ab-drawer-lex-btn" class="menu-action ${svelteClass}"><span class="icon-wrap ${svelteClass}">${svgBook}</span> <span id="ab-drawer-lex-label" data-ur-localized="1"></span></button>`;

        const liRs = document.createElement("li");
        if (firstLi) liRs.className = firstLi.className;
        liRs.innerHTML = `<button type="button" id="ab-drawer-rs-btn" class="menu-action ${svelteClass}"><span class="icon-wrap ${svelteClass}">${svgSpark}</span> <span id="ab-drawer-rs-label" data-ur-localized="1"></span></button>`;

        const liFont = document.createElement("li");
        if (firstLi) liFont.className = firstLi.className;
        liFont.innerHTML = `<button type="button" id="ab-drawer-font-btn" class="menu-action ${svelteClass}"><span class="icon-wrap ${svelteClass}">${svgFont}</span> <span id="ab-drawer-font-label" data-ur-localized="1"></span></button>`;

        qaimaList.insertBefore(liLang, anchorAfterSettings);
        qaimaList.insertBefore(liLex, anchorAfterSettings);
        qaimaList.insertBefore(liRs, anchorAfterSettings);
        qaimaList.insertBefore(liFont, anchorAfterSettings);

        liLang.querySelector("button").addEventListener("click", () => {
          setLanguage(currentLang === "ur" ? "ar" : "ur");
        });
        liLex.querySelector("button").addEventListener("click", () => {
          openLexiconModal("");
        });
        liRs.querySelector("button").addEventListener("click", () => {
          openResearchModal("rag");
        });
        liFont.querySelector("button").addEventListener("click", (ev) => {
          ev.stopPropagation();
          const pop = document.getElementById("albahith-font-popover");
          if (!pop) return;
          const rect = ev.currentTarget.getBoundingClientRect();
          pop.style.top = `${Math.min(window.innerHeight - 250, Math.max(42, Math.round(rect.bottom + 6)))}px`;
          pop.style.left = `${Math.max(12, Math.min(window.innerWidth - 280, Math.round(rect.left)))}px`;
          pop.hidden = !pop.hidden;
        });
        updateTopbarActiveState();
      }
    }

    // Also integrate Urdu/Arabic segmented switch inside `.settings-panel.svelte-9kge23` (`إعدادات` modal)
    const settingsPanel = document.querySelector(".settings-panel");
    if (settingsPanel && !settingsPanel.querySelector("#ab-settings-lang-card")) {
      const sampleCard = settingsPanel.querySelector(".setting-card");
      const sc = sampleCard
        ? Array.from(sampleCard.classList).filter((c) => c.startsWith("svelte-")).join(" ")
        : "";
      const card = document.createElement("section");
      card.id = "ab-settings-lang-card";
      card.className = `setting-card ${sc}`.trim();
      card.innerHTML = `
        <h3 class="${sc}" data-ur-localized="1">${currentLang === "ur" ? "زبان و ترجمہ" : "اللغة والترجمة"}</h3>
        <div class="segmented ${sc}" role="group">
          <button type="button" id="ab-seg-ur" class="${sc} ${currentLang === "ur" ? "active" : ""}" data-ur-localized="1">اردو + عربي</button>
          <button type="button" id="ab-seg-ar" class="${sc} ${currentLang === "ar" ? "active" : ""}" data-ur-localized="1">عربي فقط</button>
        </div>
      `;
      settingsPanel.insertBefore(card, settingsPanel.firstChild);
      card.querySelector("#ab-seg-ur").addEventListener("click", () => setLanguage("ur"));
      card.querySelector("#ab-seg-ar").addEventListener("click", () => setLanguage("ar"));
    }
  }

  function mountTopbarAndModals() {
    if (document.getElementById("albahith-topbar")) return;

    // 1. Compact Native Topbar (`اردو | عربي | لغت | معاون | خط`)
    const bar = document.createElement("div");
    bar.id = "albahith-topbar";
    bar.className = "is-home-mode";
    bar.setAttribute("role", "group");
    bar.setAttribute("aria-label", "تبديل اللغة والمعجم");
    bar.innerHTML = `
      <button type="button" id="ab-btn-ur" title="سلفی اردو ترجمہ و عنوانات">اردو</button>
      <button type="button" id="ab-btn-ar" title="النسخة العربية الأصلية">عربي</button>
      <span class="ab-sep"></span>
      <button type="button" id="ab-btn-lex" title="ریختہ و قاری اردو-عربی لغت (۲۸۳,۶۰۱ الفاظ)">لغت</button>
      <button type="button" id="ab-btn-rs" title="علمی معاون، ۳-درجاتی یادداشت اور مجوزہ ترامیم">معاون</button>
      <button type="button" id="ab-btn-font" title="اردو رسم الخط اور حجم">خط</button>
    `;
    document.body.appendChild(bar);

    // 2. Font Settings Popover (including self-hosted Noto Nastaliq Urdu Variable 400-700)
    const pop = document.createElement("div");
    pop.id = "albahith-font-popover";
    pop.hidden = true;
    const savedFont = localStorage.getItem(FONT_KEY) || "jameel";
    pop.innerHTML = `
      <div class="ab-pop-title">اردو ترجمہ رسم الخط و حجم</div>
      <button type="button" class="ab-font-opt ${savedFont === "jameel" ? "is-selected" : ""}" data-font="jameel">
        <span>جمیل نوری نستعلیق</span><span>نستعلیق</span>
      </button>
      <button type="button" class="ab-font-opt ${savedFont === "noto" ? "is-selected" : ""}" data-font="noto">
        <span>نوٹو نستعلیق اردو</span><span>ویری ایبل</span>
      </button>
      <button type="button" class="ab-font-opt ${savedFont === "mehr" ? "is-selected" : ""}" data-font="mehr">
        <span>مہر نستعلیق ویب</span><span>خطِ نستعلیق</span>
      </button>
      <button type="button" class="ab-font-opt ${savedFont === "sakkal" ? "is-selected" : ""}" data-font="sakkal">
        <span>سکل مجلہ بولڈ</span><span>نسخ واضح</span>
      </button>
      <button type="button" class="ab-font-opt ${savedFont === "plex" ? "is-selected" : ""}" data-font="plex">
        <span>آئی بی ایم پلیکس نسخ</span><span>جدید نسخ</span>
      </button>
      <div class="ab-scale-row">
        <span>حجمِ خط:</span>
        <div>
          <button type="button" class="ab-scale-btn" id="ab-scale-dec" aria-label="حجم کم کریں">−</button>
          <span id="ab-scale-val" style="display:inline-block;min-width:44px;text-align:center;">100%</span>
          <button type="button" class="ab-scale-btn" id="ab-scale-inc" aria-label="حجم بڑھائیں">+</button>
        </div>
      </div>
    `;
    document.body.appendChild(pop);

    // 3. Rekhta & Qari Lexicon Modal
    const lx = document.createElement("div");
    lx.id = "albahith-lexicon-overlay";
    lx.hidden = true;
    lx.innerHTML = `
      <div id="albahith-lexicon-card" role="dialog" aria-modal="true" aria-label="معجم ریختہ و غریب الحدیث">
        <header>
          <h3>ریختہ و قاری اردو-عربی لغت و غریب الحدیث (۲۸۳,۶۰۱ الفاظ)</h3>
          <button type="button" class="ab-lx-close" id="ab-lx-close" aria-label="بند کریں">✕</button>
        </header>
        <form class="ab-lx-searchbar" id="ab-lx-form">
          <input type="search" dir="auto" id="albahith-lexicon-input" placeholder="عربی یا اردو لفظ لکھیں (مثلاً: النيات، الإخلاص، الصبر)..." autocomplete="off" />
          <button type="submit">تلاش</button>
        </form>
        <div id="albahith-lexicon-body">
          <p style="text-align:center;color:var(--ab-muted);">کسی بھی حدیث کے لفظ پر ڈبل کلک کریں یا اوپر لفظ درج کر کے تلاش کریں۔</p>
        </div>
      </div>
    `;
    document.body.appendChild(lx);

    // 4. Scholarly Hybrid RAG, 3-Tier Living Memory & Staged Proposal Modal
    const rs = document.createElement("div");
    rs.id = "albahith-research-overlay";
    rs.hidden = true;
    rs.innerHTML = `
      <div id="albahith-research-card" role="dialog" aria-modal="true" aria-label="علمی معاون، یادداشت و مسودات">
        <header>
          <h3>علمی معاون — مستند حوالہ جاتی تحقیق، ۳-درجاتی یادداشت و مجوزہ مسودات</h3>
          <button type="button" class="ab-lx-close ab-rs-close" id="ab-rs-close" aria-label="بند کریں">✕</button>
        </header>
        <div class="ab-rs-tabs" role="tablist">
          <button type="button" class="ab-rs-tab is-active" data-tab="rag">تحقیقی معاون (Hybrid RAG)</button>
          <button type="button" class="ab-rs-tab" data-tab="memory">علمی یادداشت (3-Tier Memory)</button>
          <button type="button" class="ab-rs-tab" data-tab="proposals">مجوزہ ترامیم و نوٹس (HITL)</button>
        </div>
        <div class="ab-rs-body">
          <div class="ab-rs-pane" data-pane="rag">
            <form class="ab-lx-searchbar" id="ab-rag-form" style="padding-inline:0;padding-block-start:0;">
              <input type="search" dir="auto" id="ab-rag-input" placeholder="علمی سوال لکھیں (مثلاً: والدین کے ساتھ حسن سلوک، غصے پر قابو پانے کا حکم)..." autocomplete="off" />
              <button type="submit" class="ab-rs-btn">تحقیق</button>
            </form>
            <div id="ab-rag-output">
              <p style="color:var(--ab-muted);font-size:0.9rem;">ہر جواب مستند کتبِ حدیث سے BM25 + Dense Vector + RRF + Reranker کے ذریعے مع حوالہ پیش کیا جاتا ہے؛ حوالہ نہ ملنے پر قیاس آرائی سے اجتناب کیا جاتا ہے۔</p>
            </div>
          </div>
          <div class="ab-rs-pane" data-pane="memory" hidden>
            <form id="ab-mem-form" style="display:flex;flex-wrap:wrap;gap:6px;margin-block-end:12px;">
              <select id="ab-mem-tier" style="padding:6px;border-radius:6px;border:1px solid var(--ab-border);background:var(--ab-surface-muted);color:var(--ab-text);">
                <option value="1">درجہ ۱: مستقل علمی ترجیح</option>
                <option value="2">درجہ ۲: زیرِ تحقیق موضوع (مع میعاد)</option>
                <option value="3">درجہ ۳: سیشن کنٹیکسٹ</option>
              </select>
              <input type="text" dir="auto" id="ab-mem-key" placeholder="عنوان (مثلاً: موضوعِ تحقیق)" style="flex:1;min-width:120px;padding:6px 8px;border-radius:6px;border:1px solid var(--ab-border);background:var(--ab-surface-muted);color:var(--ab-text);" />
              <input type="text" dir="auto" id="ab-mem-val" placeholder="تفصیل (مثلاً: کتاب الصلاۃ — صحیح بخاری)" style="flex:2;min-width:160px;padding:6px 8px;border-radius:6px;border:1px solid var(--ab-border);background:var(--ab-surface-muted);color:var(--ab-text);" />
              <button type="submit" class="ur-tx-btn ab-rs-btn" style="border-color:var(--ab-accent);color:var(--ab-accent);font-weight:600;">محفوظ کریں</button>
            </form>
            <div id="ab-mem-list"></div>
          </div>
          <div class="ab-rs-pane" data-pane="proposals" hidden>
            <form id="ab-prop-form" style="display:flex;flex-direction:column;gap:6px;margin-block-end:12px;">
              <div style="display:flex;gap:6px;flex-wrap:wrap;">
                <select id="ab-prop-type" style="padding:6px;border-radius:6px;border:1px solid var(--ab-border);background:var(--ab-surface-muted);color:var(--ab-text);">
                  <option value="scholarly_note">علمی حاشیہ / نوٹ</option>
                  <option value="urdu_translation">سلفی اردو ترجمہ تجویز</option>
                </select>
                <input type="text" dir="auto" id="ab-prop-tid" placeholder="حدیث آئی ڈی یا حوالہ (مثلاً: bukhari-1)" style="flex:1;padding:6px 8px;border-radius:6px;border:1px solid var(--ab-border);background:var(--ab-surface-muted);color:var(--ab-text);" />
              </div>
              <textarea dir="auto" id="ab-prop-text" rows="2" placeholder="تجویز کردہ اردو ترجمہ یا علمی حاشیہ درج کریں (آف لائن ہونے پر بھی مقامی قطار میں محفوظ رہے گا)..." style="padding:6px 8px;border-radius:6px;border:1px solid var(--ab-border);background:var(--ab-surface-muted);color:var(--ab-text);font-family:var(--ur-ui-font);"></textarea>
              <button type="submit" class="ur-tx-btn ab-rs-btn" style="align-self:flex-start;border-color:var(--ab-accent);color:var(--ab-accent);font-weight:600;">بطورِ زیرِ التوا تجویز (Pending Proposal) شامل کریں</button>
            </form>
            <div id="ab-prop-list"></div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(rs);

    for (const tBtn of rs.querySelectorAll(".ab-rs-tab")) {
      tBtn.addEventListener("click", () => switchResearchTab(tBtn.dataset.tab));
    }
    document.getElementById("ab-rs-close").addEventListener("click", () => {
      rs.hidden = true;
    });
    rs.addEventListener("click", (e) => {
      if (e.target === rs) rs.hidden = true;
    });
    document.getElementById("ab-rag-form").addEventListener("submit", (e) => {
      e.preventDefault();
      runHybridRagQuery(document.getElementById("ab-rag-input").value);
    });
    document.getElementById("ab-mem-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const tier = parseInt(document.getElementById("ab-mem-tier").value || "1", 10);
      const fk = document.getElementById("ab-mem-key").value.trim();
      const fv = document.getElementById("ab-mem-val").value.trim();
      if (!fk || !fv) return;
      await origFetch(`${BASE_PATH}/api/v1/memory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tier, fact_key: fk, fact_value: fv, provenance: "user_explicit" }),
      });
      document.getElementById("ab-mem-key").value = "";
      document.getElementById("ab-mem-val").value = "";
      refreshLivingMemoryPane();
    });
    document.getElementById("ab-prop-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const target_type = document.getElementById("ab-prop-type").value;
      const target_id = document.getElementById("ab-prop-tid").value.trim() || "general-note";
      const proposed_text = document.getElementById("ab-prop-text").value.trim();
      if (!proposed_text) return;
      const payload = { target_type, target_id, original_text: "", proposed_text, provenance: "researcher_proposal" };
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        const q = readOfflineQueue();
        q.push(payload);
        writeOfflineQueue(q);
      } else {
        try {
          const r = await origFetch(`${BASE_PATH}/api/v1/proposals`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          if (!r.ok) throw new Error("queue");
        } catch (_) {
          const q = readOfflineQueue();
          q.push(payload);
          writeOfflineQueue(q);
        }
      }
      document.getElementById("ab-prop-text").value = "";
      refreshStagedProposalsPane();
    });
    document.getElementById("ab-btn-rs").addEventListener("click", () => {
      pop.hidden = true;
      openResearchModal("rag");
    });

    maybeMountDevComponentInspector();
    syncHeaderPlacement();
    updateTopbarActiveState();

    const updateScaleLabel = () => {
      const sc = parseFloat(localStorage.getItem(SCALE_KEY) || "1") || 1;
      const el = document.getElementById("ab-scale-val");
      if (el) el.textContent = `${Math.round(sc * 100)}%`;
    };
    updateScaleLabel();

    document.getElementById("ab-btn-ur").addEventListener("click", () => setLanguage("ur"));
    document.getElementById("ab-btn-ar").addEventListener("click", () => setLanguage("ar"));
    document.getElementById("ab-btn-lex").addEventListener("click", () => {
      pop.hidden = true;
      openLexiconModal("");
    });
    document.getElementById("ab-btn-font").addEventListener("click", (e) => {
      e.stopPropagation();
      const rect = e.currentTarget.getBoundingClientRect();
      pop.style.top = `${Math.min(window.innerHeight - 250, Math.max(42, Math.round(rect.bottom + 6)))}px`;
      pop.style.left = `${Math.max(10, Math.min(window.innerWidth - 268, Math.round(rect.left)))}px`;
      pop.hidden = !pop.hidden;
    });

    for (const opt of pop.querySelectorAll(".ab-font-opt")) {
      opt.addEventListener("click", () => {
        const fk = opt.dataset.font || "jameel";
        localStorage.setItem(FONT_KEY, fk);
        for (const o of pop.querySelectorAll(".ab-font-opt")) o.classList.toggle("is-selected", o === opt);
        applySavedTypography();
      });
    }

    document.getElementById("ab-scale-dec").addEventListener("click", () => {
      const cur = parseFloat(localStorage.getItem(SCALE_KEY) || "1") || 1;
      const nxt = Math.max(0.85, Math.round((cur - 0.05) * 100) / 100);
      localStorage.setItem(SCALE_KEY, String(nxt));
      applySavedTypography();
      updateScaleLabel();
    });

    document.getElementById("ab-scale-inc").addEventListener("click", () => {
      const cur = parseFloat(localStorage.getItem(SCALE_KEY) || "1") || 1;
      const nxt = Math.min(1.35, Math.round((cur + 0.05) * 100) / 100);
      localStorage.setItem(SCALE_KEY, String(nxt));
      applySavedTypography();
      updateScaleLabel();
    });

    document.getElementById("ab-lx-close").addEventListener("click", () => {
      lx.hidden = true;
    });
    lx.addEventListener("click", (e) => {
      if (e.target === lx) lx.hidden = true;
    });
    document.getElementById("ab-lx-form").addEventListener("submit", (e) => {
      e.preventDefault();
      runLexiconLookup(document.getElementById("albahith-lexicon-input").value);
    });

    document.addEventListener("click", (e) => {
      if (!pop.hidden && !pop.contains(e.target) && !(e.target && e.target.closest && e.target.closest("#ab-btn-font, #ab-drawer-font-btn"))) {
        pop.hidden = true;
      }
    });

    // Double-click any Arabic/Urdu word to inspect in Rekhta & Qari Lexicon
    document.addEventListener("dblclick", (e) => {
      if (e.target && e.target.closest && e.target.closest("#albahith-topbar, #albahith-font-popover, #albahith-lexicon-overlay, input, textarea, button")) {
        return;
      }
      const sel = ((window.getSelection && window.getSelection().toString()) || "").trim();
      const cleaned = sel.replace(/[^\u0600-\u06FF]/g, "");
      if (cleaned.length >= 2 && cleaned.length <= 28) {
        openLexiconModal(cleaned);
      }
    });
  }

  /* ------------------------------------------------------------------------
   * 7. Lifecycle & Debounced DOM Observer
   * ------------------------------------------------------------------------ */
  let mutScheduled = false;
  function onDomMutated() {
    if (mutScheduled) return;
    mutScheduled = true;
    requestAnimationFrame(() => {
      mutScheduled = false;
      syncHeaderPlacement();
      localizeSubtree(document.body);
      if (currentLang === "ur") {
        applyEncyclopediaUrduEnrichment();
      }
    });
  }

  /* ------------------------------------------------------------------------
   * 6B. Cooperative Home Search Failsafe (Zero-Failure Guarantee)
   *     Normally `DbNwGjsa.js` handles live search in 260ms (`lastNativeSearchTs`).
   *     If an exotic IME or iframe quirk ever suppresses Svelte's input binding,
   *     this cooperative handler transparently renders identical results + sharh.
   * ------------------------------------------------------------------------ */
  function installCooperativeSearchFailsafe() {
    let failsafeTimer = null;
    let activeReqSeq = 0;

    async function runFailsafeSearch(queryStr, pageNum, appendMode) {
      const seq = ++activeReqSeq;
      const isUr = currentLang === "ur";
      const url = `${BASE_PATH}/api/v1/home/search?q=${encodeURIComponent(queryStr)}&page=${pageNum}&per_page=15&auto_translate=${isUr ? "true" : "false"}`;
      try {
        const r = await origFetch(url, { headers: { "x-albahith-lang": currentLang } });
        if (!r.ok || seq !== activeReqSeq) return;
        const payload = await r.json();
        if (seq !== activeReqSeq) return;
        // Abort if native SvelteKit search already rendered
        if (document.querySelector("ul.search-results:not(#albahith-failsafe-ul) > li")) {
          const oldBox = document.getElementById("albahith-failsafe-results");
          if (oldBox) oldBox.remove();
          return;
        }
        const anchor = document.querySelector(".search-form") || document.querySelector("input.search-input")?.closest("div") || document.querySelector("main");
        if (!anchor || !anchor.parentNode) return;

        let container = document.getElementById("albahith-failsafe-results");
        if (!container) {
          container = document.createElement("div");
          container.id = "albahith-failsafe-results";
          container.dir = "rtl";
          container.style.cssText = "max-width:52rem;margin:1rem auto 2.5rem;padding:0 1rem;";
          anchor.insertAdjacentElement("afterend", container);
        }

        const total = Number(payload.count || 0);
        const items = Array.isArray(payload.data) ? payload.data : [];

        if (!appendMode) {
          container.innerHTML = `
            <div class="ab-fs-count" style="font-size:0.95rem;opacity:0.8;margin:0.5rem 0 1rem;">
              ${isUr ? `تعدادِ نتائج: ${toUrduDigits(String(total))}` : `عدد النتائج: ${total}`}
            </div>
            <ul id="albahith-failsafe-ul" class="search-results svelte-adnwyt" style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:1.15rem;"></ul>
            <div id="albahith-failsafe-more" style="text-align:center;margin-top:1.25rem;"></div>
          `;
        }

        const ul = container.querySelector("#albahith-failsafe-ul");
        for (const it of items) {
          const li = document.createElement("li");
          li.className = "svelte-adnwyt";
          li.style.cssText = "padding:1.1rem 1.25rem;border-radius:0.75rem;border:1px solid rgba(128,128,128,0.2);background:rgba(128,128,128,0.03);";
          const arHtml = it.text || escapeHtml(it.text_plain || "");
          const urHtml = isUr && (it.text_urdu || it.text_urdu_plain)
            ? `<span class="ur-hadith-block" dir="rtl">${it.text_urdu || escapeHtml(it.text_urdu_plain)}</span>`
            : "";
          const rawiLbl = isUr ? (it.rawy_ur || it.rawy || "") : (it.rawy || "");
          const mohLbl = isUr ? (it.muhaddith_ur || it.muhaddith || "") : (it.muhaddith || "");
          const srcLbl = isUr ? (it.source_ur || it.source || "") : (it.source || "");
          const numLbl = isUr ? (it.num_ur || it.num || "") : (it.num || "");
          const hukmAr = it.hukm ? `[${it.hukm}]` : "";
          const hukmUr = isUr && it.hukm_ur && it.hukm_ur !== it.hukm ? ` <span class="ur-hukm-inline">• ${escapeHtml(it.hukm_ur)}</span>` : "";
          const metaParts = [];
          if (rawiLbl) metaParts.push(`<span>${isUr ? "راوی:" : "الراوي:"} <strong>${escapeHtml(rawiLbl)}</strong></span>`);
          if (mohLbl) metaParts.push(`<span>${isUr ? "محدث:" : "المحدث:"} <strong>${escapeHtml(mohLbl)}</strong></span>`);
          if (srcLbl) metaParts.push(`<span>${isUr ? "ماخذ:" : "المصدر:"} <strong>${escapeHtml(srcLbl)}</strong></span>`);
          if (numLbl) metaParts.push(`<span>${isUr ? "صفحہ یا نمبر:" : "الصفحة أو الرقم:"} <strong>${escapeHtml(numLbl)}</strong></span>`);

          const sharhBtnHtml = it.sharh_id
            ? `<button type="button" class="ab-fs-sharh-btn" data-sid="${escapeHtml(String(it.sharh_id))}" style="margin-right:0.75rem;padding:0.2rem 0.65rem;border-radius:0.4rem;border:1px solid rgba(128,128,128,0.3);background:transparent;cursor:pointer;font-size:0.85rem;">${isUr ? "حدیث کی شرح" : "شرح الحديث"}</button>`
            : "";

          li.innerHTML = `
            <div class="hadith-body" style="font-family:'Kitab','SakkalMajallaBold',serif;font-size:1.3rem;line-height:2;">${arHtml}${urHtml}</div>
            <div class="h-info" style="margin-top:0.65rem;font-size:0.9rem;opacity:0.88;display:flex;flex-wrap:wrap;gap:0.65rem;align-items:center;">
              ${metaParts.join(" <span style='opacity:0.4'>|</span> ")}
              <span class="hukm ${it.grade_class === "bad" ? "text-red-600" : "text-emerald-700"}" style="font-weight:600;">${escapeHtml(hukmAr)}${hukmUr}</span>
              ${sharhBtnHtml}
            </div>
            <div class="ab-fs-sharh-box" hidden style="margin-top:0.75rem;padding:0.85rem;border-radius:0.5rem;background:rgba(128,128,128,0.06);"></div>
          `;
          const shBtn = li.querySelector(".ab-fs-sharh-btn");
          if (shBtn) {
            shBtn.addEventListener("click", async () => {
              const box = li.querySelector(".ab-fs-sharh-box");
              if (!box) return;
              if (!box.hidden && box.dataset.loaded === "1") {
                box.hidden = true;
                return;
              }
              box.hidden = false;
              if (box.dataset.loaded === "1") return;
              box.textContent = isUr ? "شرح لوڈ ہو رہی ہے..." : "جاري تحميل الشرح...";
              try {
                const sr = await origFetch(`${BASE_PATH}/api/v1/wire?action=sharh&id=${encodeURIComponent(shBtn.dataset.sid)}&_lang=${currentLang}`);
                const sj = await sr.json();
                box.innerHTML = (sj && sj.data) ? sj.data : (isUr ? "اس روایت کی شرح دستیاب نہیں۔" : "الشرح غير متوفر.");
                box.dataset.loaded = "1";
              } catch (_) {
                box.textContent = isUr ? "شرح لوڈ کرنے میں دشواری پیش آئی۔" : "تعذر تحميل الشرح.";
              }
            });
          }
          ul.appendChild(li);
        }

        const moreWrap = container.querySelector("#albahith-failsafe-more");
        if (moreWrap) {
          moreWrap.innerHTML = "";
          if (payload.has_more) {
            const mBtn = document.createElement("button");
            mBtn.type = "button";
            mBtn.textContent = isUr ? "مزید احادیث دکھائیں" : "عرض المزيد";
            mBtn.style.cssText = "padding:0.45rem 1.25rem;border-radius:0.5rem;border:1px solid rgba(128,128,128,0.35);background:transparent;cursor:pointer;";
            mBtn.addEventListener("click", () => runFailsafeSearch(queryStr, pageNum + 1, true));
            moreWrap.appendChild(mBtn);
          }
        }
      } catch (_) {}
    }

    function scheduleCheck(inputEl, delayMs) {
      clearTimeout(failsafeTimer);
      const q = (inputEl.value || "").trim();
      if (q.replace(/\s+/g, "").length < 2) {
        const oldBox = document.getElementById("albahith-failsafe-results");
        if (oldBox) oldBox.remove();
        return;
      }
      const strokeTs = Date.now();
      failsafeTimer = setTimeout(() => {
        if (lastNativeSearchTs >= strokeTs - 40) return;
        // Also try dispatching a bubbling native input event once in case Svelte missed IME composition
        if (!inputEl.__abDispatchedOnce || inputEl.__abLastVal !== q) {
          inputEl.__abDispatchedOnce = true;
          inputEl.__abLastVal = q;
          try {
            inputEl.dispatchEvent(new Event("input", { bubbles: true }));
          } catch (_) {}
        }
        setTimeout(() => {
          if (lastNativeSearchTs >= strokeTs - 40) return;
          if (document.querySelector("ul.search-results:not(#albahith-failsafe-ul) > li")) return;
          runFailsafeSearch(q, 1, false);
        }, 340);
      }, delayMs);
    }

    document.addEventListener("input", (e) => {
      const t = e.target;
      if (t && t.matches && t.matches("input.search-input") && e.isTrusted) {
        scheduleCheck(t, 520);
      }
    }, true);

    document.addEventListener("keydown", (e) => {
      const t = e.target;
      if (e.key === "Enter" && t && t.matches && t.matches("input.search-input")) {
        scheduleCheck(t, 160);
      }
    }, true);
  }

  function bootBridge() {
    mountTopbarAndModals();
    installCooperativeSearchFailsafe();
    syncHeaderPlacement();
    localizeSubtree(document.body);
    applyEncyclopediaUrduEnrichment();

    const obs = new MutationObserver(onDomMutated);
    obs.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootBridge, { once: true });
  } else {
    bootBridge();
  }
})();
