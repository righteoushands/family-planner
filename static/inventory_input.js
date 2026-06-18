/* Inventory Input — shared client-side logic
   Extracted from static/meals.js so both the Meal Planner page and the
   Meal Wizard can reuse the dictate / parse / save inventory flow.

   Exposes window.toggleMic, window.parseInventory, window.saveInventory
   exactly as before, so existing inline handlers keep working.

   Required DOM element IDs on the host page:
     mic-btn, inv-paste-raw, inv-parse-status,
     inv-fridge, inv-freezer, inv-pantry, inv-use-soon, inv-status
*/

(function () {
  "use strict";

  var _wakeLock  = null;
  var _micRecog  = null;
  var _micActive = false;

  /* ── Wake Lock (duplicated from meals.js — shared helper, kept private here) ── */
  function requestWakeLock() {
    if (navigator.wakeLock) {
      navigator.wakeLock.request("screen").then(function (wl) {
        _wakeLock = wl;
      }).catch(function () {});
    }
  }

  /* ── Mic / Speech Recognition ── */
  window.toggleMic = function () {
    var btn = document.getElementById("mic-btn");
    var ta  = document.getElementById("inv-paste-raw");
    if (!btn || !ta) return;

    if (_micActive) {
      if (_micRecog) _micRecog.stop();
      return;
    }

    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      alert("Speech recognition is not supported in this browser. Try Chrome or Safari on iOS.");
      return;
    }

    _micRecog = new SR();
    _micRecog.continuous     = true;
    _micRecog.interimResults = true;
    _micRecog.lang           = "en-US";

    var committed = ta.value;

    _micRecog.onstart = function () {
      _micActive = true;
      btn.textContent = "\u23F9 Stop";
      btn.style.background = "#c0392b";
      requestWakeLock();
    };

    _micRecog.onresult = function (e) {
      var interim = "";
      for (var i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          committed += e.results[i][0].transcript;
        } else {
          interim = e.results[i][0].transcript;
        }
      }
      ta.value = committed + interim;
    };

    _micRecog.onend = function () {
      _micActive = false;
      btn.textContent = "\uD83C\uDF04 Dictate";
      btn.style.background = "#1c3d6e";
      ta.value = committed;
    };

    _micRecog.onerror = function (e) {
      _micActive = false;
      btn.textContent = "\uD83C\uDF04 Dictate";
      btn.style.background = "#1c3d6e";
      var st = document.getElementById("inv-parse-status");
      if (st) st.textContent = "Mic error: " + e.error;
    };

    _micRecog.start();
  };

  /* ── Parse Inventory ── */
  window.parseInventory = function () {
    var raw = document.getElementById("inv-paste-raw");
    var st  = document.getElementById("inv-parse-status");
    if (!raw) return;

    var text = raw.value.trim();
    if (!text) {
      if (st) {
        st.style.color = "#c0392b";
        st.textContent = "Nothing to parse — type or dictate your inventory first.";
        setTimeout(function () { st.textContent = ""; st.style.color = "#27ae60"; }, 3000);
      }
      return;
    }

    /* Step 1 — tag section keywords with unambiguous markers */
    text = text
      .replace(/\b(in\s+(the\s+|my\s+))?(fridge|refrigerator)\b[\s:,]*/gi, "\n__FRIDGE__\n")
      .replace(/\b(in\s+(the\s+|my\s+))?freezer\b[\s:,]*/gi,               "\n__FREEZER__\n")
      .replace(/\bfrozen\b[\s:,]*/gi,                                        "\n__FREEZER__\n")
      .replace(/\b(in\s+(the\s+|my\s+))?(pantry|cabinet|cupboard|shelf|shelves|dry\s+goods)\b[\s:,]*/gi, "\n__PANTRY__\n")
      .replace(/\b(use\s+soon|need\s+to\s+use(\s+(soon|up))?|going\s+bad)\b[\s:,]*/gi, "\n__SOON__\n")
      .replace(/\b(expir\w+|wilting)\b/gi,                                   "\n__SOON__\n$1");

    /* Step 2 — split on "I have", periods, semicolons */
    text = text
      .replace(/\.\s*I\s+(also\s+)?(have|got)\s+/gi, "\n")
      .replace(/\bI\s+(also\s+)?(have|got)\s+/gi,   "\n")
      .replace(/[.;]\s+/g,                            "\n");

    /* Step 3 — parse lines into buckets */
    var chunks = { fridge: [], freezer: [], pantry: [], use_soon: [] };
    var current = "pantry";

    text.split("\n").forEach(function (line) {
      var l = line.replace(/^[\s,;:]+/, "").replace(/[\s,;:]+$/, "");
      if (!l) return;

      if (l === "__FRIDGE__")  { current = "fridge";   return; }
      if (l === "__FREEZER__") { current = "freezer";  return; }
      if (l === "__PANTRY__")  { current = "pantry";   return; }
      if (l === "__SOON__")    { current = "use_soon"; return; }

      /* split comma-separated items within the line */
      l.split(",").forEach(function (item) {
        var it = item.replace(/^[\s,;:]+/, "").replace(/[\s,;:]+$/, "");
        it = it.replace(/^(and|also|plus|some|any|a|an)\s+/i, "");
        it = it.replace(/^(I\s+)?(also\s+)?(have|got)\s+/i, "");
        it = it.trim();
        if (it && it.length > 1) chunks[current].push(it);
      });
    });

    var filled = 0;
    var elF = document.getElementById("inv-fridge");
    var elZ = document.getElementById("inv-freezer");
    var elP = document.getElementById("inv-pantry");
    var elS = document.getElementById("inv-use-soon");

    if (elF && chunks.fridge.length)   { elF.value = chunks.fridge.join("\n");   filled++; }
    if (elZ && chunks.freezer.length)  { elZ.value = chunks.freezer.join("\n");  filled++; }
    if (elP && chunks.pantry.length)   { elP.value = chunks.pantry.join("\n");   filled++; }
    if (elS && chunks.use_soon.length) { elS.value = chunks.use_soon.join(", "); filled++; }

    if (st) {
      if (filled) {
        var total = chunks.fridge.length + chunks.freezer.length +
                    chunks.pantry.length + chunks.use_soon.length;
        st.style.color = "#27ae60";
        st.textContent = total + " item" + (total === 1 ? "" : "s") + " parsed \u2713 \u2014 review and save.";
      } else {
        st.style.color = "#c0392b";
        st.textContent = "Couldn\u2019t parse \u2014 try: \"In the fridge I have eggs. Freezer: ground beef. Pantry: rice.\"";
      }
      setTimeout(function () { st.textContent = ""; st.style.color = "#27ae60"; }, 5000);
    }
  };

  /* ── Save inventory ── */
  window.saveInventory = function () {
    var elF = document.getElementById("inv-fridge");
    var elZ = document.getElementById("inv-freezer");
    var elP = document.getElementById("inv-pantry");
    var elS = document.getElementById("inv-use-soon");
    var inv = {
      fridge:   elF ? elF.value : "",
      freezer:  elZ ? elZ.value : "",
      pantry:   elP ? elP.value : "",
      use_soon: elS ? elS.value : ""
    };
    fetch("/meal-save-inventory", {
      method:  "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body:    "data=" + encodeURIComponent(JSON.stringify(inv))
    }).then(function () {
      var el = document.getElementById("inv-status");
      if (el) { el.textContent = "Inventory saved \u2713"; setTimeout(function () { el.textContent = ""; }, 2000); }
    });
  };

  /* ── Save inventory (wizard) — same payload, posts to the wizard route ── */
  window.saveInventoryWizard = function () {
    var elF = document.getElementById("inv-fridge");
    var elZ = document.getElementById("inv-freezer");
    var elP = document.getElementById("inv-pantry");
    var elS = document.getElementById("inv-use-soon");
    var inv = {
      fridge:   elF ? elF.value : "",
      freezer:  elZ ? elZ.value : "",
      pantry:   elP ? elP.value : "",
      use_soon: elS ? elS.value : ""
    };
    fetch("/meal-wizard-step2-save", {
      method:  "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body:    "data=" + encodeURIComponent(JSON.stringify(inv))
    }).then(function (r) {
      var el = document.getElementById("inv-status");
      if (r && r.ok) {
        if (el) { el.textContent = "Saved \u2713"; }
        window.location.href = "/meal-wizard-step3";
      } else {
        if (el) { el.textContent = "Could not save. Please try again."; }
      }
    }).catch(function () {
      var el = document.getElementById("inv-status");
      if (el) { el.textContent = "Could not save. Please try again."; }
    });
  };

  /* ── Clear inventory (client-side only — no server call, no stored data) ── */
  window.clearInventory = function () {
    var ids = ["inv-paste-raw", "inv-fridge", "inv-freezer", "inv-pantry", "inv-use-soon"];
    ids.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.value = "";
    });
    var st = document.getElementById("inv-status");
    if (st) {
      st.style.color = "#27ae60";
      st.textContent = "Cleared \u2014 type or dictate, then Save";
      setTimeout(function () { st.textContent = ""; }, 3000);
    }
  };

})();
