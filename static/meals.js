/* Meal Planner — client-side logic
   Data injected by server via <script id="meal-data" type="application/json">
*/

(function () {
  "use strict";

  var data = {};
  try {
    var el = document.getElementById("meal-data");
    if (el) data = JSON.parse(el.textContent);
  } catch (e) {}

  var _mealWeek    = data.week || "";
  var _groceryGaps = data.grocery_gaps || [];
  var _prepNotes   = data.prep_notes || {};
  var _apiKey      = "";
  var _mealChanges = {};
  var _mealTimer   = null;
  var _wakeLock    = null;
  var _micRecog    = null;
  var _micActive   = false;
  var _swapSource  = null;

  var DAYS_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
  var ALL_SLOTS  = ["breakfast","lunch","dinner","snacks","dad_lunch","boys_help"];

  /* ── Wake Lock ── */
  function requestWakeLock() {
    if (navigator.wakeLock) {
      navigator.wakeLock.request("screen").then(function (wl) {
        _wakeLock = wl;
      }).catch(function () {});
    }
  }
  function releaseWakeLock() {
    if (_wakeLock) { _wakeLock.release().catch(function(){}); _wakeLock = null; }
  }
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") requestWakeLock();
    else releaseWakeLock();
  });
  requestWakeLock();

  /* ── API key ── */
  try {
    fetch("/api-key").then(function (r) { return r.json(); }).then(function (d) {
      if (d.key) _apiKey = d.key;
    });
  } catch (e) {}

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

  /* ── Cell changed (auto-save) ── */
  window.cellChanged = function (ta) {
    var day  = ta.dataset.day;
    var slot = ta.dataset.slot;
    if (!_mealChanges[day]) _mealChanges[day] = {};
    _mealChanges[day][slot] = ta.value;
    clearTimeout(_mealTimer);
    _mealTimer = setTimeout(autoSavePlan, 900);
    var el = document.getElementById("grid-status");
    if (el) el.textContent = "Unsaved changes...";
  };

  function autoSavePlan() { savePlan(); }

  window.addEventListener("beforeunload", function () {
    if (Object.keys(_mealChanges).length) savePlan();
  });

  /* ── Save plan ── */
  window.savePlan = function () {
    var cells = document.querySelectorAll("#meal-grid textarea");
    var days  = {};
    cells.forEach(function (ta) {
      var d = ta.dataset.day, s = ta.dataset.slot;
      if (!days[d]) days[d] = {};
      days[d][s] = ta.value;
    });
    fetch("/meal-save-plan", {
      method:  "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body:    "week=" + encodeURIComponent(_mealWeek) + "&days=" + encodeURIComponent(JSON.stringify(days))
    }).then(function () {
      _mealChanges = {};
      var el = document.getElementById("grid-status");
      if (el) { el.textContent = "Saved \u2713"; setTimeout(function () { el.textContent = ""; }, 1800); }
    });
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

  /* ── Generate meal plan via AI ── */
  window.generatePlan = function () {
    saveInventory();
    var st = document.getElementById("ai-status");
    if (st) st.textContent = "\u2728 Generating your meal plan\u2026 (this takes 15\u201330 seconds)";
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
    fetch("/meal-generate", {
      method:  "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body:    "week=" + encodeURIComponent(_mealWeek) + "&inventory=" + encodeURIComponent(JSON.stringify(inv))
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.error) { if (st) st.textContent = "Error: " + d.error; return; }
        if (st) st.textContent = "\u2713 Plan generated! Review and edit below.";
        _groceryGaps = d.grocery_gaps || [];
        _prepNotes   = d.prep_notes  || {};
        var days = d.days || {};
        Object.keys(days).forEach(function (day) {
          Object.keys(days[day]).forEach(function (slot) {
            var ta = document.querySelector(
              "#meal-grid textarea[data-day='" + day + "'][data-slot='" + slot + "']"
            );
            if (ta) ta.value = days[day][slot];
          });
        });
        savePlan();
      })
      .catch(function () {
        if (st) st.textContent = "Generation failed. Check API key in Settings.";
      });
  };

  /* ── View modals ── */
  window.viewGrocery = function () {
    var html = "<h3 style='margin-bottom:14px;'>Grocery list</h3>";
    if (!_groceryGaps.length) {
      html += "<p style='color:#888;'>Generate a meal plan first to see the grocery list.</p>";
    } else {
      html += "<p style='font-size:0.85em;color:#888;margin-bottom:12px;'>Items not in your inventory that are needed:</p>";
      html += "<ul style='padding-left:20px;'>";
      _groceryGaps.forEach(function (item) {
        html += "<li style='padding:4px 0;font-size:0.9em;'>" + item + "</li>";
      });
      html += "</ul>";
    }
    document.getElementById("modal-body").innerHTML = html;
    document.getElementById("modal-overlay").style.display = "block";
  };

  window.viewPrepSchedule = function () {
    var DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
    var html = "<h3 style='margin-bottom:14px;'>Daily prep schedule</h3>";
    DAYS.forEach(function (day) {
      var note = _prepNotes[day] || "";
      if (note) {
        html += "<div style='padding:8px 0;border-bottom:1px solid #f0ebe4;'>";
        html += "<div style='font-weight:700;font-size:0.85em;color:#1a3870;margin-bottom:3px;'>" + day + "</div>";
        html += "<div style='font-size:0.85em;'>" + note + "</div></div>";
      }
    });
    if (html === "<h3 style='margin-bottom:14px;'>Daily prep schedule</h3>") {
      html += "<p style='color:#888;'>Generate a meal plan first to see the prep schedule.</p>";
    }
    document.getElementById("modal-body").innerHTML = html;
    document.getElementById("modal-overlay").style.display = "block";
  };

  /* ── Print ── */
  window.printFridge = function () {
    savePlan();
    setTimeout(function () {
      window.open("/meal-print?week=" + encodeURIComponent(_mealWeek), "_blank");
    }, 500);
  };

  /* ── Day Swap ── */
  function _updateSwapUI() {
    DAYS_ORDER.forEach(function (day) {
      var btn = document.getElementById("swap-btn-" + day);
      if (!btn) return;
      if (!_swapSource) {
        btn.innerHTML = "&#8644;";
        btn.style.opacity   = "0.5";
        btn.style.background = "transparent";
        btn.title = "Swap " + day + " with another day";
      } else if (_swapSource === day) {
        btn.textContent = "✕";
        btn.style.opacity   = "1";
        btn.style.background = "rgba(192,57,43,0.7)";
        btn.style.color      = "white";
        btn.title = "Cancel swap";
      } else {
        btn.textContent = "↔";
        btn.style.opacity   = "1";
        btn.style.background = "rgba(45,80,22,0.7)";
        btn.style.color      = "white";
        btn.title = "Swap " + _swapSource + " ↔ " + day;
      }
    });
  }

  window.activateSwap = function (day) {
    if (_swapSource === day) {
      _swapSource = null;
      _updateSwapUI();
      return;
    }
    if (_swapSource) {
      var src = _swapSource;
      _swapSource = null;
      _updateSwapUI();
      _doSwap(src, day);
      return;
    }
    _swapSource = day;
    _updateSwapUI();
  };

  function _doSwap(dayA, dayB) {
    ALL_SLOTS.forEach(function (slot) {
      var taA = document.querySelector(
        "#meal-grid textarea[data-day='" + dayA + "'][data-slot='" + slot + "']");
      var taB = document.querySelector(
        "#meal-grid textarea[data-day='" + dayB + "'][data-slot='" + slot + "']");
      if (!taA || !taB) return;
      var tmp = taA.value;
      taA.value = taB.value;
      taB.value = tmp;
      if (!_mealChanges[dayA]) _mealChanges[dayA] = {};
      if (!_mealChanges[dayB]) _mealChanges[dayB] = {};
      _mealChanges[dayA][slot] = taA.value;
      _mealChanges[dayB][slot] = taB.value;
    });
    var st = document.getElementById("grid-status");
    if (st) st.textContent = dayA + " \u2194 " + dayB + " swapped \u2014 saving\u2026";
    savePlan();
  }

  /* ── AI Edit Chat ── */
  function _collectCurrentPlan() {
    var days = {};
    document.querySelectorAll("#meal-grid textarea").forEach(function (ta) {
      var d = ta.dataset.day, s = ta.dataset.slot;
      if (d && s) {
        if (!days[d]) days[d] = {};
        days[d][s] = ta.value;
      }
    });
    return days;
  }

  window.sendMealChat = function () {
    var inp = document.getElementById("meal-chat-input");
    var st  = document.getElementById("meal-chat-status");
    if (!inp) return;
    var msg = inp.value.trim();
    if (!msg) return;

    var days = _collectCurrentPlan();
    var constraints = "";
    var cEl = document.getElementById("meal-constraints");
    if (cEl) constraints = cEl.value;

    if (st) { st.style.color = "var(--gold)"; st.textContent = "\u2728 Thinking\u2026 (may take 15\u201330s)"; }
    inp.disabled = true;

    fetch("/meal-edit", {
      method:  "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body:    "week=" + encodeURIComponent(_mealWeek) +
               "&message=" + encodeURIComponent(msg) +
               "&days=" + encodeURIComponent(JSON.stringify(days)) +
               "&constraints=" + encodeURIComponent(constraints)
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        inp.disabled = false;
        if (d.error) {
          if (st) { st.style.color = "#c0392b"; st.textContent = "Error: " + d.error; }
          return;
        }
        var updated = d.days || {};
        Object.keys(updated).forEach(function (day) {
          Object.keys(updated[day]).forEach(function (slot) {
            var ta = document.querySelector(
              "#meal-grid textarea[data-day='" + day + "'][data-slot='" + slot + "']");
            if (ta) ta.value = updated[day][slot];
          });
        });
        if (d.prep_notes)   _prepNotes   = d.prep_notes;
        if (d.grocery_gaps) _groceryGaps = d.grocery_gaps;
        inp.value = "";
        if (st) {
          st.style.color = "#27ae60";
          st.textContent = d.summary || "Plan updated \u2713";
          setTimeout(function () { st.textContent = ""; }, 5000);
        }
        savePlan();
      })
      .catch(function () {
        inp.disabled = false;
        if (st) { st.style.color = "#c0392b"; st.textContent = "Edit failed \u2014 try again."; }
      });
  };

  /* ── Constraints ── */
  var _constraintsTimer = null;
  window.constraintsChanged = function () {
    clearTimeout(_constraintsTimer);
    _constraintsTimer = setTimeout(saveConstraints, 2000);
  };

  window.saveConstraints = function () {
    var el = document.getElementById("meal-constraints");
    if (!el) return;
    fetch("/meal-save-constraints", {
      method:  "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body:    "week=" + encodeURIComponent(_mealWeek) +
               "&constraints=" + encodeURIComponent(el.value)
    }).then(function () {
      var st = document.getElementById("constraints-status");
      if (st) { st.textContent = "Saved \u2713"; setTimeout(function () { st.textContent = ""; }, 2000); }
    });
  };

  /* ── Init ── */
  document.addEventListener("DOMContentLoaded", function () {
    _updateSwapUI();
    var inp = document.getElementById("meal-chat-input");
    if (inp) {
      inp.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          sendMealChat();
        }
      });
    }
    // Populate constraints field from server data
    var cEl = document.getElementById("meal-constraints");
    if (cEl && !cEl.value && data.constraints) {
      cEl.value = data.constraints;
    }
  });

})();
