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
    var fd = new FormData();
    fd.append("action", "save_field");
    fd.append("step",   payload.step);
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
    var formMode = ($("#frol-form") && $("#frol-form").getAttribute("data-mode")) || "";
    if (formMode) { fd.append("mode", formMode); }
    fetch("/frol-wizard", { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) { status(r.ok ? "Saved" : "Save failed"); })
      .catch(function () { status("Offline — will retry"); });
  }, 350);

  function bindAutoSave() {
    $$("[data-step][data-key]").forEach(function (el) {
      var ev = (el.tagName === "SELECT" || el.type === "checkbox" || el.type === "color"
                || el.type === "date" || el.type === "time") ? "change" : "input";
      el.addEventListener(ev, function () { saveField(gatherFieldPayload(el)); });
    });
  }

  /* Step 1 — add/remove members */
  window.frolAddMember = function () {
    var holder = document.getElementById("frol-members");
    if (!holder) return;
    var i = holder.children.length;
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

  /* Step submit — POSTs the advance action; server bumps current_step. */
  window.frolAdvance = function (e, step, mode) {
    /* allow normal form POST so the page reloads onto the next step */
    return true;
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
