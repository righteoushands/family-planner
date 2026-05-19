/* Rule of Life Wizard — client behavior.
 * - Auto-saves every field/checkbox change to POST /frol-wizard
 * - Handles Lucy chat streaming + <frol-set> tags that fill form fields
 * - Dismisses the dashboard setup card via cookie
 * - Add/remove member rows on step 1
 */

(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function status(msg) {
    var el = document.getElementById("frol-save-status");
    if (el) el.textContent = msg;
  }

  function debounce(fn, ms) {
    var t = null;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function gatherFieldPayload(el) {
    var step = el.getAttribute("data-step");
    var key  = el.getAttribute("data-key");
    var list = el.getAttribute("data-list") || "";
    var idx  = el.getAttribute("data-idx");
    var multi = el.getAttribute("data-multi") === "1";
    var value;
    if (multi) {
      var siblings = $$('input[type="checkbox"][data-step="' + step + '"][data-key="' + key + '"][data-multi="1"]');
      value = siblings.filter(function (s) { return s.checked; }).map(function (s) { return s.value; });
    } else if (el.type === "checkbox") {
      value = el.checked ? "yes" : "no";
    } else {
      value = el.value;
    }
    return { step: step, key: key, list: list, idx: idx, value: value };
  }

  var saveField = debounce(function (payload) {
    status("Saving…");
    var form = $("#frol-form");
    var isV2 = form && form.getAttribute("data-version") === "2";
    var fd = new FormData();
    fd.append("action", isV2 ? "save_field_v2" : "save_field");
    fd.append(isV2 ? "section" : "step", payload.step);
    fd.append("field",  payload.key);
    if (payload.list) { fd.append("list", payload.list); }
    if (payload.idx !== null && payload.idx !== undefined && payload.idx !== "") {
      fd.append("idx", payload.idx);
    }
    if (Array.isArray(payload.value)) {
      payload.value.forEach(function (v) { fd.append("value[]", v); });
    } else {
      fd.append("value", payload.value);
    }
    var formMode = form && form.getAttribute("data-mode") || "";
    if (formMode) { fd.append("mode", formMode); }
    fetch("/frol-wizard", { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) { status(r.ok ? "Saved" : "Save failed"); })
      .catch(function () { status("Offline — will retry"); });
  }, 350);

  function bindAutoSave() {
    $$("[data-step][data-key]").forEach(function (el) {
      if (el.getAttribute("data-frol-bound") === "1") return;
      el.setAttribute("data-frol-bound", "1");
      var ev = (el.tagName === "SELECT" || el.type === "checkbox" || el.type === "color"
                || el.type === "date" || el.type === "time") ? "change" : "input";
      el.addEventListener(ev, function () { saveField(gatherFieldPayload(el)); });
    });
  }

  /* Step 8 — reveal next emergency contact row (max 5 visible). */
  window.frolRevealContact = function () {
    var rows = $$(".frol-contact-row");
    var nextIdx = -1;
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].style.display === "none") { nextIdx = i; break; }
    }
    if (nextIdx === -1) return;
    rows[nextIdx].style.display = "";
    var visible = rows.filter(function (r) { return r.style.display !== "none"; }).length;
    if (visible >= 5) {
      var btn = document.getElementById("frol-add-contact");
      if (btn) btn.style.display = "none";
    }
  };

  /* V2 shared activity builder — add a new row to the live builder.
   * Each row's inputs carry data-step/data-key/data-list="activities"
   * /data-idx, so the existing saveField pipeline handles persistence
   * (dict-of-dicts shape already supported server-side). */
  window.frolActivityAdd = function (step, slug) {
    var holder = document.getElementById("frol-activity-rows-" + step);
    if (!holder) return;
    var existing = holder.querySelectorAll(".frol-activity-row");
    var maxIdx = -1;
    existing.forEach(function (r) {
      var v = parseInt(r.getAttribute("data-idx"), 10);
      if (!isNaN(v) && v > maxIdx) maxIdx = v;
    });
    var idx = maxIdx + 1;
    var row = document.createElement("div");
    row.className = "frol-activity-row";
    row.setAttribute("data-idx", String(idx));
    row.style.cssText = "display:grid;grid-template-columns:1.2fr 0.8fr 1fr 0.7fr 0.7fr auto;" +
                        "gap:6px;margin-bottom:6px;align-items:center;";
    // Clone the first row's selects to inherit the member/when/duration options.
    var template = existing.length ? existing[0] : null;
    function pickSelect(name) {
      if (!template) return "<select></select>";
      var sel = template.querySelector('select[data-key="' + name + '"]');
      return sel ? sel.outerHTML : "<select></select>";
    }
    row.innerHTML =
      '<input type="text" placeholder="Activity name" data-step="' + step +
      '" data-key="name" data-list="activities" data-idx="' + idx + '" value="">' +
      pickSelect("leader").replace(/data-idx="\d+"/, 'data-idx="' + idx + '"') +
      pickSelect("when").replace(/data-idx="\d+"/, 'data-idx="' + idx + '"') +
      pickSelect("duration_min").replace(/data-idx="\d+"/, 'data-idx="' + idx + '"') +
      '<input type="text" placeholder="Credits" data-step="' + step +
      '" data-key="credits" data-list="activities" data-idx="' + idx + '" value="" style="width:100%;">' +
      '<button type="button" class="frol-btn ghost" style="padding:4px 10px;"' +
      ' onclick="frolActivityRemove(this,' + step + ',' + idx + ')">&times;</button>';
    holder.appendChild(row);
    bindAutoSave();
    // Persist the new (empty) row so server-side has an entry to update.
    var firstInput = row.querySelector('input[data-key="name"]');
    if (firstInput) saveField(gatherFieldPayload(firstInput));
  };

  window.frolActivityRemove = function (btn, step, idx) {
    var row = btn.closest(".frol-activity-row");
    if (!row) return;
    row.parentNode.removeChild(row);
    // Tell the server this row is gone.
    var fd = new FormData();
    fd.append("action", "save_field");
    fd.append("step",   step);
    fd.append("field",  "name");
    fd.append("list",   "activities");
    fd.append("idx",    String(idx));
    fd.append("value",  "__DELETE__");
    var formMode = ($("#frol-form") && $("#frol-form").getAttribute("data-mode")) || "";
    if (formMode) { fd.append("mode", formMode); }
    fetch("/frol-wizard", { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) { status(r.ok ? "Saved" : "Save failed"); });
  };

  /* ── V3 activity builder (Phase A) ───────────────────────────────────
   * The builder is rendered by render_frol_wizard._render_activity_builder.
   * Steps A→B→C→D reveal progressively as the user fills in earlier steps. */
  window.frolActivityStepReveal = function (form) {
    if (!form) return;
    var name = form.querySelector('input[name="name"]');
    var stepB = form.querySelector('[data-ab-step="B"]');
    if (name && stepB) {
      stepB.style.display = (name.value || "").trim() ? "" : "none";
    }
  };

  /* Step D reveal — gated per who_type branch. Called by the Step C
   * inputs whenever they change so D appears only after C is meaningfully
   * satisfied (family: time entered; individual: person picked;
   * mixed: at least one person checked). */
  function _frolMaybeRevealStepD(form) {
    if (!form) return;
    var stepD = form.querySelector('[data-ab-step="D"]');
    if (!stepD) return;
    var wt = (form.querySelector('input[name="who_type"]:checked') || {}).value || "";
    var ready = false;
    if (wt === "family") {
      var ft = form.querySelector('input[name="time"]');
      ready = !!(ft && (ft.value || "").trim());
    } else if (wt === "individual") {
      var sp = form.querySelector('select[name="who_single"]');
      ready = !!(sp && (sp.value || "").trim());
    } else if (wt === "mixed") {
      ready = form.querySelectorAll('input[name="who"]:checked').length > 0;
    }
    stepD.style.display = ready ? "" : "none";
  }

  window.frolActivityWhoType = function (form, wt) {
    if (!form) return;
    var stepC = form.querySelector('[data-ab-step="C"]');
    if (stepC) stepC.style.display = "";
    var branches = form.querySelectorAll('.frol-ab-branch');
    for (var i = 0; i < branches.length; i++) {
      branches[i].style.display = (branches[i].getAttribute('data-branch') === wt) ? "" : "none";
    }
    /* Wire Step C inputs in the active branch to re-check Step D readiness
     * on every change. Bind once (data-d-bound flag) so toggling who_type
     * back and forth doesn't pile up listeners. */
    var active = form.querySelector('.frol-ab-branch[data-branch="' + wt + '"]');
    if (active) {
      var inputs = active.querySelectorAll('input, select');
      for (var j = 0; j < inputs.length; j++) {
        var el = inputs[j];
        if (el.getAttribute('data-d-bound') === '1') continue;
        el.setAttribute('data-d-bound', '1');
        var ev = (el.tagName === 'SELECT' || el.type === 'checkbox' || el.type === 'time')
                  ? 'change' : 'input';
        el.addEventListener(ev, function () { _frolMaybeRevealStepD(form); });
      }
    }
    _frolMaybeRevealStepD(form);
  };

  window.frolActivitySinglePerson = function (form, name) {
    /* Individual branch — re-check Step D readiness when a person is picked. */
    if (!form) return;
    _frolMaybeRevealStepD(form);
  };

  window.frolActivityPeopleChange = function (form) {
    /* Mixed branch — rebuild per-person time/duration rows for everyone
     * currently checked in the people picker, then re-check Step D readiness. */
    if (!form) return;
    var holder = form.querySelector('[data-mixed-rows]');
    if (!holder) { _frolMaybeRevealStepD(form); return; }
    var checks = form.querySelectorAll('input[name="who"]:checked');
    var names  = Array.prototype.map.call(checks, function (c) { return c.value; });
    /* Preserve any already-typed values across re-renders. */
    var prev = {};
    holder.querySelectorAll('[data-mixed-person]').forEach(function (row) {
      var p = row.getAttribute('data-mixed-person');
      var t = row.querySelector('input[type="time"]');
      var d = row.querySelector('input[type="number"]');
      prev[p] = { time: t ? t.value : '', duration: d ? d.value : '' };
    });
    function escHtml(s) {
      return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
    holder.innerHTML = '';
    names.forEach(function (n) {
      var row = document.createElement('div');
      row.setAttribute('data-mixed-person', n);
      row.style.cssText = 'display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:6px;align-items:end;';
      var pv = prev[n] || { time: '', duration: '30' };
      var attr = escHtml(n);
      var disp = escHtml(n);
      var pvTime = escHtml(pv.time || '');
      var pvDur  = escHtml(pv.duration || '30');
      row.innerHTML =
        '<div style="font-size:12px;color:#374151;font-weight:600;align-self:center;">' + disp + '</div>' +
        '<div><label style="font-size:11px;color:#6b7280;">Time</label>' +
          '<input type="time" name="person_' + attr + '_time" value="' + pvTime +
          '" style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;"></div>' +
        '<div><label style="font-size:11px;color:#6b7280;">Duration (min)</label>' +
          '<input type="number" min="0" max="600" name="person_' + attr + '_duration_min" value="' + pvDur +
          '" style="width:100%;padding:6px;border:1px solid #d1d5db;border-radius:6px;"></div>';
      holder.appendChild(row);
    });
    _frolMaybeRevealStepD(form);
  };

  /* V2 — update generic section dots after async progress changes. */
  window.frolUpdateDots = function (current, total, completed) {
    var holder = document.querySelector(".frol-dots");
    if (!holder) return;
    var html = "";
    for (var i = 1; i <= total; i++) {
      var cls = "frol-dot";
      if (completed && completed.indexOf(i) !== -1) cls += " done";
      if (i === current) cls += " current";
      html += '<span class="' + cls + '" title="Section ' + i + '"></span>';
    }
    holder.innerHTML = html;
  };

  /* V2 — fill the Lucy hint slot for the current step. Server may push
   * hints in response to /frol-wizard-chat replies; UI just slots them in. */
  window.frolSetLucyHint = function (step, html) {
    var slot = document.getElementById("frol-lucy-hint-" + step);
    if (!slot) return;
    if (html && String(html).trim()) {
      slot.innerHTML = html;
      slot.style.display = "";
    } else {
      slot.style.display = "none";
      slot.innerHTML = "";
    }
  };

  /* Step 1 — add/remove members */
  window.frolAddMember = function () {
    var holder = document.getElementById("frol-members");
    if (!holder) return;
    var existing = holder.querySelectorAll("[data-mem-idx]");
    var i = 0;
    existing.forEach(function (n) {
      var v = parseInt(n.getAttribute("data-mem-idx"), 10);
      if (!isNaN(v) && v >= i) i = v + 1;
    });
    var div = document.createElement("div");
    div.className = "frol-member";
    div.setAttribute("data-mem-idx", i);
    div.innerHTML = ''
      + '<div class="frol-row">'
      + '  <div><label class="frol-fld">Name</label>'
      + '    <input class="frol-input" data-step="1" data-list="members" data-idx="' + i + '" data-key="name"></div>'
      + '  <div><label class="frol-fld">Role</label>'
      + '    <input class="frol-input" data-step="1" data-list="members" data-idx="' + i + '" data-key="role"></div>'
      + '</div>'
      + '<div class="frol-row">'
      + '  <div><label class="frol-fld">Birthday</label>'
      + '    <input class="frol-input" type="date" data-step="1" data-list="members" data-idx="' + i + '" data-key="birthday"></div>'
      + '  <div><label class="frol-fld">Color</label>'
      + '    <input class="frol-input" type="color" data-step="1" data-list="members" data-idx="' + i + '" data-key="color" value="#4a6fa5"></div>'
      + '  <div style="flex:0 0 auto;align-self:flex-end;">'
      + '    <button type="button" class="frol-rm" onclick="frolRemoveMember(' + i + ')">Remove</button></div>'
      + '</div>';
    holder.appendChild(div);
    bindAutoSave();
    /* Persist the new (empty) member row immediately so it survives a
       page reload even if the user doesn't type anything. */
    var formMode = ($("#frol-form") && $("#frol-form").getAttribute("data-mode")) || "";
    ["name", "role"].forEach(function (key) {
      var fd = new FormData();
      fd.append("action", "save_field");
      fd.append("step",   "1");
      fd.append("field",  key);
      fd.append("list",   "members");
      fd.append("idx",    String(i));
      fd.append("value",  "");
      if (formMode) { fd.append("mode", formMode); }
      fetch("/frol-wizard", { method: "POST", body: fd, credentials: "same-origin" });
    });
    status("Saved");
    setTimeout(function () { status(""); }, 1500);
  };

  window.frolRemoveMember = function (i) {
    var holder = document.getElementById("frol-members");
    if (!holder) return;
    var node = holder.querySelector('[data-mem-idx="' + i + '"]');
    if (node) node.remove();
    var fd = new FormData();
    fd.append("action", "remove_list_item");
    fd.append("step", "1"); fd.append("list", "members"); fd.append("idx", String(i));
    fetch("/frol-wizard", { method: "POST", body: fd, credentials: "same-origin" });
  };

  /* Step submit — wait briefly for any debounced field saves to flush,
     then POST the advance action via fetch and navigate on success.
     For step 1 we ALSO fire a one-shot seed_members POST first so the
     server atomically merges _settings_members() with any newly-typed
     entries before advancing. */
  function _seedMembersIfStep1(step, mode) {
    if (parseInt(step, 10) !== 1) return Promise.resolve();
    var fd = new FormData();
    fd.append("action", "seed_members");
    fd.append("step", "1");
    if (mode) fd.append("mode", String(mode));
    return fetch("/frol-wizard", { method: "POST", body: fd, credentials: "same-origin" })
      .catch(function () { /* non-fatal — fall through to advance */ });
  }

  window.frolAdvance = function (e, step, mode) {
    if (e && e.preventDefault) e.preventDefault();
    var btn = e && e.target ? (e.target.querySelector ? e.target.querySelector('button[type="submit"]') : null) : null;
    if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
    status("Saving…");
    setTimeout(function () {
      _seedMembersIfStep1(step, mode).then(function () {
      var form = $("#frol-form");
      var isV2 = form && form.getAttribute("data-version") === "2";
      var fd = new FormData();
      fd.append("action", isV2 ? "advance_v2" : "advance");
      fd.append(isV2 ? "section" : "step", String(step));
      if (mode) fd.append("mode", String(mode));
      fetch("/frol-wizard", { method: "POST", body: fd, credentials: "same-origin", redirect: "manual" })
        .then(function (r) {
          /* opaqueredirect (status 0 with redirect:manual) and 2xx are both success */
          var ok = r.ok || r.type === "opaqueredirect" || r.status === 0;
          if (!ok) {
            status("Save failed (" + r.status + ")");
            if (btn) { btn.disabled = false; btn.textContent = "Save & Continue"; }
            return;
          }
          status("Saved");
          var next = (parseInt(step, 10) || 0) + 1;
          var modeQs = mode ? ("&mode=" + encodeURIComponent(mode)) : "";
          window.location.href = "/frol-wizard?step=" + next + modeQs;
        })
        .catch(function () {
          status("Save failed — network");
          if (btn) { btn.disabled = false; btn.textContent = "Save & Continue"; }
        });
      });
    }, 400);
    return false;
  };

  /* Setup card dismissal — sets a 1-year cookie. */
  window.frolDismissCard = function () {
    document.cookie = "frol_card_dismissed=1; path=/; max-age=" + (60 * 60 * 24 * 365);
    var c = document.getElementById("frol-setup-card");
    if (c) c.style.display = "none";
  };

  /* Lucy chat — streams response, applies <frol-set> tags to form fields. */
  window.frolChatSend = function (e, step) {
    e.preventDefault();
    var input = document.getElementById("frol-chat-input");
    var log   = document.getElementById("frol-chat-log");
    var msg   = (input.value || "").trim();
    if (!msg || !log) return false;
    var meDiv = document.createElement("div"); meDiv.className = "me"; meDiv.textContent = msg;
    log.appendChild(meDiv); input.value = ""; log.scrollTop = log.scrollHeight;

    var luDiv = document.createElement("div"); luDiv.className = "lu"; luDiv.textContent = "…";
    log.appendChild(luDiv);

    var fd = new FormData();
    fd.append("message", msg);
    fd.append("step", String(step));

    fetch("/frol-wizard-chat", { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) { luDiv.textContent = "Lucy is unavailable right now."; return; }
        var reader = r.body.getReader(); var dec = new TextDecoder(); var acc = "";
        function pump() {
          return reader.read().then(function (chunk) {
            if (chunk.done) {
              var visible = stripFrolTags(acc, function (field, value) {
                applyChatFieldUpdate(field, value);
              });
              luDiv.textContent = visible || "…";
              log.scrollTop = log.scrollHeight;
              return;
            }
            acc += dec.decode(chunk.value, { stream: true });
            luDiv.textContent = stripFrolTags(acc, null);
            log.scrollTop = log.scrollHeight;
            return pump();
          });
        }
        return pump();
      })
      .catch(function () { luDiv.textContent = "Lucy is unavailable right now."; });
    return false;
  };

  function stripFrolTags(text, onMatch) {
    var re = /<frol-set\s+field="([^"]+)"\s+value="([^"]*)"\s*\/?>/g;
    var m;
    if (onMatch) {
      while ((m = re.exec(text)) !== null) { try { onMatch(m[1], m[2]); } catch (e) {} }
    }
    return text.replace(re, "").trim();
  }

  function applyChatFieldUpdate(field, value) {
    var step = ($("#frol-form") && $("#frol-form").getAttribute("data-step")) || "";
    var sel  = '[data-step="' + step + '"][data-key="' + field + '"]';
    var els  = $$(sel);
    if (!els.length) { return; }
    var first = els[0];
    if (first.type === "checkbox") {
      els.forEach(function (cb) {
        if (cb.value === value) { cb.checked = true; cb.dispatchEvent(new Event("change")); }
      });
    } else if (first.tagName === "SELECT") {
      first.value = value; first.dispatchEvent(new Event("change"));
    } else {
      first.value = value;
      first.dispatchEvent(new Event("input"));
      first.dispatchEvent(new Event("change"));
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindAutoSave);
  } else {
    bindAutoSave();
  }
})();

// ─── §12 Build Your Day — view toggles ────────────────────────────────
// Moved here from inline <script> in render_section_12 so they survive
// any future <script>-stripping in _section_chrome / in transit.
window.s12ShowView = function (v) {
  var l  = document.getElementById('s12-list');
  var g  = document.getElementById('s12-grid');
  var bl = document.getElementById('s12-btn-list');
  var bg = document.getElementById('s12-btn-grid');
  if (v === 'grid') {
    if (l) l.style.display = 'none';
    if (g) g.style.display = 'block';
    if (bl) { bl.style.background = '#fff';    bl.style.color = '#4a6fa5'; }
    if (bg) { bg.style.background = '#4a6fa5'; bg.style.color = '#fff';    }
  } else {
    if (l) l.style.display = 'block';
    if (g) g.style.display = 'none';
    if (bl) { bl.style.background = '#4a6fa5'; bl.style.color = '#fff';    }
    if (bg) { bg.style.background = '#fff';    bg.style.color = '#4a6fa5'; }
  }
};

// ─── Phase B — Persistent live grid preview ──────────────────────────
// Component HTML is rendered by render_frol_wizard._render_grid_preview.
// These handlers wire up:
//   - Variant tab clicks (ephemeral; no persistence)
//   - Person pill toggles (persisted via /frol-wizard save_field)
//   - Phase A form submits (intercept → fetch → refresh grid fragment)
//   - iOS Safari sticky-header fallback (UA-gated)
(function () {
  if (window.__frolGridBound) return;
  window.__frolGridBound = true;

  function gridContainer() { return document.getElementById('frol-grid-container'); }

  function refreshGrid() {
    var c = gridContainer();
    if (!c) return Promise.resolve();
    var sec = c.getAttribute('data-section') || '';
    var av  = c.getAttribute('data-active-variant') || 'weekday';
    var url = '/frol-grid-fragment?section=' + encodeURIComponent(sec) +
              '&active_variant=' + encodeURIComponent(av);
    return fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.text() : ''; })
      .then(function (html) {
        if (!html) return;
        var box = c.querySelector('.frol-grid-scroll');
        if (box) {
          box.innerHTML = html;
          applyIosStickyFallback(box);
        }
      })
      .catch(function () { /* swallow — grid is non-critical */ });
  }

  window.frolGridVariant = function (btn) {
    var c = gridContainer();
    if (!c || !btn) return;
    var v = btn.getAttribute('data-variant');
    c.setAttribute('data-active-variant', v);
    var tabs = c.querySelectorAll('.frol-grid-vtab');
    for (var i = 0; i < tabs.length; i++) {
      var on = (tabs[i].getAttribute('data-variant') === v);
      tabs[i].style.background = on ? '#4a6fa5' : '#fff';
      tabs[i].style.color      = on ? '#fff'    : '#33507e';
    }
    refreshGrid();
  };

  window.frolGridTogglePerson = function (btn) {
    var c = gridContainer();
    if (!c || !btn) return;
    var on = (btn.getAttribute('data-on') === '1');
    var newOn = !on;
    btn.setAttribute('data-on', newOn ? '1' : '0');
    btn.style.background = newOn ? '#4a6fa5' : '#fff';
    btn.style.color      = newOn ? '#fff'    : '#33507e';
    // Persist the new visible set to the section bucket via save_field.
    var section = c.getAttribute('data-section') || '0';
    var pills = c.querySelectorAll('.frol-grid-ppill');
    var visible = [];
    for (var i = 0; i < pills.length; i++) {
      if (pills[i].getAttribute('data-on') === '1') {
        visible.push(pills[i].getAttribute('data-person'));
      }
    }
    var form = document.getElementById('frol-form');
    var formMode = (form && form.getAttribute('data-mode')) || '';
    var isV2 = form && form.getAttribute('data-version') === '2';
    var fd = new FormData();
    fd.append('action', isV2 ? 'save_field_v2' : 'save_field');
    fd.append(isV2 ? 'section' : 'step', section);
    fd.append('field', 'grid_visible_persons');
    visible.forEach(function (p) { fd.append('value[]', p); });
    if (!visible.length) { fd.append('value', ''); }
    if (formMode) { fd.append('mode', formMode); }
    // Serialize: wait for persistence to commit before re-rendering,
    // otherwise a high-latency POST can race the page refetch and the
    // refreshed grid would reflect the stale stored visible-set.
    fetch('/frol-wizard', { method: 'POST', body: fd, credentials: 'same-origin' })
      .then(function () { refreshGridFull(); })
      .catch(function () { refreshGridFull(); });
  };

  function refreshGridFull() {
    var c = gridContainer();
    if (!c) return;
    var sec = c.getAttribute('data-section') || '';
    var av  = c.getAttribute('data-active-variant') || 'weekday';
    // Re-request the section page and pluck out a fresh #frol-grid-container.
    var pageUrl = window.location.pathname + window.location.search;
    fetch(pageUrl, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.text() : ''; })
      .then(function (html) {
        if (!html) { refreshGrid(); return; }
        var tmp = document.createElement('div');
        tmp.innerHTML = html;
        var fresh = tmp.querySelector('#frol-grid-container');
        if (!fresh) { refreshGrid(); return; }
        // Preserve the user's current active variant choice across the swap.
        fresh.setAttribute('data-active-variant', av);
        c.parentNode.replaceChild(fresh, c);
        var box = document.querySelector('#frol-grid-container .frol-grid-scroll');
        if (box) { applyIosStickyFallback(box); }
        // After replacement, re-sync variant tab visuals + table contents
        // to the preserved active variant.
        var nc = gridContainer();
        if (nc) {
          var tabs = nc.querySelectorAll('.frol-grid-vtab');
          for (var i = 0; i < tabs.length; i++) {
            var on = (tabs[i].getAttribute('data-variant') === av);
            tabs[i].style.background = on ? '#4a6fa5' : '#fff';
            tabs[i].style.color      = on ? '#fff'    : '#33507e';
          }
        }
        refreshGrid();
      })
      .catch(function () { refreshGrid(); });
  }

  // Intercept Phase A CRUD form submits when a grid is on the page,
  // so add/edit/delete refreshes the grid in place rather than
  // triggering a full navigation back to the section.
  var CRUD_PATHS = ['/frol-add-activity', '/frol-edit-activity', '/frol-delete-activity'];
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (!form || form.tagName !== 'FORM') return;
    if (!gridContainer()) return;
    var act = (form.getAttribute('action') || '').split('?')[0];
    if (CRUD_PATHS.indexOf(act) < 0) return;
    e.preventDefault();
    var fd = new FormData(form);
    status('Saving…');
    fetch(act, { method: 'POST', body: fd, credentials: 'same-origin', redirect: 'manual' })
      .then(function (r) {
        // 302 (redirect manual → opaqueredirect/status 0) and 2xx are
        // both server-side success. Anything else surfaces a status
        // message so failures don't silently masquerade as success.
        var ok = r.ok || r.type === 'opaqueredirect' || r.status === 0 ||
                 (r.status >= 200 && r.status < 400);
        if (!ok) {
          status('Save failed (' + r.status + ')');
          return;
        }
        status('Saved');
        setTimeout(function () { status(''); }, 1500);
        refreshGridFull();
      })
      .catch(function () {
        status('Save failed — network');
      });
  }, true);

  // iOS Safari sticky-header fallback. Modern iOS handles position:sticky
  // natively, but older iOS Safari (≤12) loses the sticky on cells inside
  // a scrollable <table>. We add a UA-gated handler that re-applies
  // transform offsets to thead + first-column cells on scroll. Desktop
  // browsers use pure CSS.
  function isIosSafari() {
    var ua = navigator.userAgent || '';
    var isIos = /iP(hone|od|ad)/.test(ua);
    var isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS/.test(ua);
    return isIos && isSafari;
  }

  function applyIosStickyFallback(scrollBox) {
    if (!isIosSafari() || !scrollBox) return;
    if (scrollBox.__frolStickyBound) return;
    scrollBox.__frolStickyBound = true;
    var thead = scrollBox.querySelector('thead');
    var firstColCells = scrollBox.querySelectorAll('tbody td.frol-grid-time');
    var corner = scrollBox.querySelector('.frol-grid-corner');
    function paint() {
      var sx = scrollBox.scrollLeft;
      var sy = scrollBox.scrollTop;
      if (thead) {
        var ths = thead.querySelectorAll('th');
        for (var i = 0; i < ths.length; i++) {
          ths[i].style.transform = 'translateY(' + sy + 'px)';
        }
      }
      for (var j = 0; j < firstColCells.length; j++) {
        firstColCells[j].style.transform = 'translateX(' + sx + 'px)';
      }
      if (corner) {
        corner.style.transform = 'translate(' + sx + 'px,' + sy + 'px)';
        corner.style.zIndex = '4';
      }
    }
    scrollBox.addEventListener('scroll', paint, { passive: true });
    paint();
  }

  // Apply the fallback once on load if the grid is already on the page.
  function initFallback() {
    var box = document.querySelector('#frol-grid-container .frol-grid-scroll');
    if (box) applyIosStickyFallback(box);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFallback);
  } else {
    initFallback();
  }
})();

window.s12TogglePerson = function (btn) {
  var p = btn.getAttribute('data-person');
  var hidden = btn.getAttribute('data-hidden') === '1';
  var all = document.querySelectorAll('.s12-col');
  for (var i = 0; i < all.length; i++) {
    if (all[i].getAttribute('data-person') === p) {
      all[i].style.display = hidden ? '' : 'none';
    }
  }
  if (hidden) {
    btn.setAttribute('data-hidden', '0');
    btn.style.background = '#4a6fa5';
    btn.style.color      = '#fff';
  } else {
    btn.setAttribute('data-hidden', '1');
    btn.style.background = '#fff';
    btn.style.color      = '#4a6fa5';
  }
};
