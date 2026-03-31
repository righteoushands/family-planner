"""
render_ai_planner.py — AI scheduling assistant.

Three modes:
  Ask      — free-form question about today's schedule
  Review   — one-click full-day conflict/gap review
  Generate — build a proposed schedule from constraints

Context sent to Claude every time:
  - Today's family grid (time × person)
  - Each child's school blocks and chores
  - Calendar events for the day
  - Family constraints from settings
  - Current daily plan items

API: POST /plan-ai-suggest → streams Claude response as plain text
"""
from datetime import date
from html import escape


# ── Context packet ────────────────────────────────────────────────────────────
def build_context_packet(iso: str, weekday: str, date_label: str) -> str:
    """
    Build a rich plain-text context string to send as Claude's system prompt.
    """
    lines = [
        f"You are a helpful scheduling assistant for a homeschooling family.",
        f"Today is {weekday}, {date_label} ({iso}).",
        "",
        "== FAMILY MEMBERS ==",
    ]

    # Children with ages
    try:
        from daily_schedule_engine import CHILDREN
        from render_daily_bar import get_child_age
        for child in CHILDREN:
            age = get_child_age(child)
            age_str = f"{age['years']} years old" if age else "age unknown"
            lines.append(f"- {child}: {age_str}")
        lines.append("- Mom: the planner and primary supervisor")
        lines.append("- James: baby/toddler, needs supervision at all times")
    except Exception:
        lines.append("- Family members: JP, Joseph, Michael, James (baby), Mom")

    lines += ["", "== FAMILY CONSTRAINTS =="]

    # Constraints from settings
    try:
        from render_settings import load_app_settings
        settings = load_app_settings()
        constraints = settings.get("family_constraints", {})

        supervision    = constraints.get("supervision_rules", "")
        james_schedule = constraints.get("james_schedule", "")
        school_durations = constraints.get("school_durations", "")
        meal_prep      = constraints.get("meal_prep", "")
        independence   = constraints.get("independence_notes", "")
        mom_supervision = constraints.get("mom_supervision_subjects", "")
        other          = constraints.get("other_notes", "")

        if supervision:
            lines.append(f"Supervision rules: {supervision}")
        if james_schedule:
            lines.append(f"James care schedule: {james_schedule}")
        if school_durations:
            lines.append(f"School duration per child: {school_durations}")
        if meal_prep:
            lines.append(f"Meal prep notes: {meal_prep}")
        if independence:
            lines.append(f"Independent work capacity: {independence}")
        if mom_supervision:
            lines.append(f"Subjects needing Mom directly: {mom_supervision}")
        if other:
            lines.append(f"Other notes: {other}")
        if not any([supervision, james_schedule, school_durations, meal_prep,
                    independence, mom_supervision, other]):
            lines.append("(No constraints entered yet — go to Settings → Family to add them)")
    except Exception:
        lines.append("(Could not load constraints)")

    lines += ["", "== TODAY'S CALENDAR EVENTS =="]
    try:
        from render_calendar import load_calendar_cache, events_for_date, load_subscribed_calendars
        cache = load_calendar_cache()
        all_events = cache.get("events", [])
        today_events = events_for_date(all_events, iso)
        if today_events:
            for ev in today_events:
                t = ev.get("start", "")[-5:] if "T" in ev.get("start", "") else "all day"
                lines.append(f"- {ev.get('title','?')} at {t}")
        else:
            lines.append("No calendar events today.")
    except Exception:
        lines.append("(Calendar not available)")

    lines += ["", "== TODAY'S FAMILY SCHEDULE GRID =="]
    try:
        from data_helpers import load_family_schedule
        from render_schedule_support import generate_half_hour_times, _slot_minutes
        schedule  = load_family_schedule()
        times     = schedule.get("times", []) or generate_half_hour_times()
        day_slots = schedule.get("days", {}).get(weekday, {})
        populated = [(t, day_slots.get(t, "")) for t in times if day_slots.get(t, "")]
        if populated:
            for t, activity in populated:
                lines.append(f"  {t}: {activity}")
        else:
            lines.append("(No schedule grid entries for today)")
    except Exception:
        lines.append("(Schedule grid not available)")

    lines += ["", "== EACH CHILD'S DAY =="]
    try:
        from daily_schedule_engine import CHILDREN, build_schedule_payload
        from render_schedule_support import _slot_minutes
        for child in CHILDREN:
            payload = build_schedule_payload(child, weekday, date_label, iso)
            school_blocks = payload.get("school_blocks", [])
            chore_items   = payload.get("chore_items", [])
            lines.append(f"\n{child}:")
            if school_blocks:
                subjects = [b.get("subject","?") for b in school_blocks]
                lines.append(f"  School subjects today: {', '.join(subjects)}")
            else:
                lines.append("  No school scheduled")
            if chore_items:
                chores = [c.get("text","?") for c in chore_items[:4]]
                lines.append(f"  Chores: {', '.join(chores)}")
    except Exception:
        lines.append("(Could not load child schedules)")

    lines += ["", "== CURRENT DAILY PLAN =="]
    try:
        from render_daily_plan import load_daily_plan
        plan  = load_daily_plan(iso)
        items = plan.get("items", [])
        if items:
            for item in items:
                t    = item.get("time", "—")
                text = item.get("text", "")
                done = "✓" if item.get("done") else " "
                lines.append(f"  [{done}] {t}: {text}")
        else:
            lines.append("(No plan items yet)")
    except Exception:
        lines.append("(Could not load daily plan)")

    lines += [
        "",
        "== YOUR ROLE ==",
        "Help Mom plan the day effectively. Be specific and practical.",
        "When suggesting schedule changes, reference actual time slots.",
        "When covering James, name a specific sibling and explain why they're available.",
        "Keep responses concise — bullet points preferred over long paragraphs.",
        "If the schedule has real conflicts or coverage gaps, flag them clearly.",
    ]

    return "\n".join(lines)


# ── AI panel UI ───────────────────────────────────────────────────────────────
def render_ai_panel(iso: str) -> str:
    """
    Floating corner button (bottom-right) that expands into a full panel.
    Three tabs: Ask / Review / Generate. Reasoning panel on the right.
    Uses position:fixed so it floats over any page scroll position.
    """
    return f"""
    <!-- AI floating button -->
    <div id="ai-float" style="position:fixed;bottom:24px;right:24px;z-index:900;">

        <!-- Collapsed: just the button -->
        <div id="ai-bubble-btn"
             onclick="aiToggle()"
             style="width:52px;height:52px;border-radius:50%;background:#8b5a3c;
                    color:white;font-size:1.3em;display:flex;align-items:center;
                    justify-content:center;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,0.22);
                    transition:transform 0.2s;user-select:none;"
             title="AI scheduling assistant"
             onmouseover="this.style.transform='scale(1.08)'"
             onmouseout="this.style.transform='scale(1)'">
            ✨
        </div>

        <!-- Expanded panel -->
        <div id="ai-panel"
             style="display:none;position:fixed;bottom:86px;right:24px;
                    width:680px;max-width:calc(100vw - 32px);
                    background:white;border:1px solid #e4dbd2;border-radius:16px;
                    box-shadow:0 8px 40px rgba(0,0,0,0.18);overflow:hidden;
                    z-index:900;">

            <!-- Panel header -->
            <div style="display:flex;align-items:center;justify-content:space-between;
                        padding:12px 16px;background:#faf8f5;border-bottom:1px solid #f0ebe4;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <span style="font-size:1em;">✨</span>
                    <strong style="font-size:0.88em;color:#2c2c2c;">AI Scheduling Assistant</strong>
                </div>
                <div style="display:flex;align-items:center;gap:10px;">
                    <span id="ai-status" style="font-size:0.75em;color:#aaa;"></span>
                    <button onclick="aiToggle()"
                            style="background:none;border:none;cursor:pointer;font-size:1.1em;
                                   color:#aaa;padding:2px 6px;border-radius:4px;font-family:inherit;">
                        ✕
                    </button>
                </div>
            </div>

            <!-- Tab strip -->
            <div style="display:flex;border-bottom:1px solid #f0ebe4;background:#faf8f5;">
                <button onclick="aiTab('ask')" id="ai-tab-ask"
                        style="padding:8px 16px;font-size:0.82em;font-weight:600;border:none;
                               background:none;cursor:pointer;font-family:inherit;
                               color:#8b5a3c;border-bottom:2px solid #8b5a3c;margin-bottom:-1px;">
                    💬 Ask
                </button>
                <button onclick="aiTab('review')" id="ai-tab-review"
                        style="padding:8px 16px;font-size:0.82em;font-weight:600;border:none;
                               background:none;cursor:pointer;font-family:inherit;
                               color:#888;border-bottom:2px solid transparent;margin-bottom:-1px;">
                    🔍 Review
                </button>
                <button onclick="aiTab('generate')" id="ai-tab-generate"
                        style="padding:8px 16px;font-size:0.82em;font-weight:600;border:none;
                               background:none;cursor:pointer;font-family:inherit;
                               color:#888;border-bottom:2px solid transparent;margin-bottom:-1px;">
                    ✨ Generate
                </button>
            </div>

            <!-- Two-column body -->
            <div style="display:grid;grid-template-columns:1fr 220px;height:380px;">

                <!-- Left: tab content -->
                <div style="padding:14px 16px;overflow-y:auto;border-right:1px solid #f0ebe4;">

                    <!-- Ask -->
                    <div id="ai-pane-ask">
                        <div id="ai-history"
                             style="max-height:220px;overflow-y:auto;margin-bottom:10px;
                                    display:flex;flex-direction:column;gap:6px;"></div>
                        <div style="display:flex;gap:6px;">
                            <input type="text" id="ai-question"
                                   placeholder="Who watches James at 2pm? JP gap at 10am?"
                                   style="flex:1;margin-bottom:0;font-size:0.85em;padding:7px 10px;"
                                   onkeydown="if(event.key==='Enter')aiAsk()">
                            <button onclick="aiAsk()"
                                    style="padding:7px 12px;font-size:0.82em;white-space:nowrap;">Ask →</button>
                        </div>
                        <div style="margin-top:6px;display:flex;gap:5px;flex-wrap:wrap;">
                            <button onclick="aiQuick('Who can watch James right now?')"
                                    class="ghost" style="padding:2px 8px;font-size:0.72em;">James coverage</button>
                            <button onclick="aiQuick('Does this schedule make sense? Flag any problems.')"
                                    class="ghost" style="padding:2px 8px;font-size:0.72em;">Quick review</button>
                            <button onclick="aiQuick('Who has a gap right now and what should they do?')"
                                    class="ghost" style="padding:2px 8px;font-size:0.72em;">Fill gaps</button>
                        </div>
                    </div>

                    <!-- Review -->
                    <div id="ai-pane-review" style="display:none;">
                        <p style="font-size:0.85em;color:#555;margin-bottom:10px;">
                            Claude reads today's full schedule and flags conflicts, coverage gaps, and overloads.
                        </p>
                        <button onclick="aiReview()" style="font-size:0.85em;padding:7px 16px;">
                            🔍 Review today's schedule
                        </button>
                        <div id="ai-review-response"
                             style="margin-top:12px;font-size:0.85em;line-height:1.6;
                                    white-space:pre-wrap;color:#333;"></div>
                    </div>

                    <!-- Generate -->
                    <div id="ai-pane-generate" style="display:none;">
                        <p style="font-size:0.85em;color:#555;margin-bottom:8px;">
                            Describe today's special constraints, then Claude proposes a full schedule.
                        </p>
                        <textarea id="ai-gen-notes" rows="3"
                                  placeholder="e.g. I have an appointment 2–3pm. Michael has a test."
                                  style="font-size:0.82em;margin-bottom:8px;resize:vertical;width:100%;"></textarea>
                        <button onclick="aiGenerate()" style="font-size:0.85em;padding:7px 16px;">
                            ✨ Generate schedule
                        </button>
                        <div id="ai-gen-response"
                             style="margin-top:12px;font-size:0.85em;line-height:1.6;
                                    white-space:pre-wrap;color:#333;"></div>
                    </div>

                </div>

                <!-- Right: reasoning panel -->
                <div style="padding:12px 14px;background:#fdfaf7;overflow-y:auto;">
                    <div style="font-size:0.68em;font-weight:700;text-transform:uppercase;
                                letter-spacing:0.08em;color:#bbb;margin-bottom:6px;">Context used</div>
                    <div id="ai-reasoning"
                         style="font-size:0.75em;color:#999;line-height:1.5;">
                        <span style="color:#ccc;">Ask a question to see reasoning here.</span>
                    </div>
                    <div style="margin-top:12px;border-top:1px solid #f0ebe4;padding-top:10px;">
                        <div style="font-size:0.68em;color:#bbb;line-height:1.4;margin-bottom:4px;">
                            Reads: schedule grid · child plans · calendar · your constraints
                        </div>
                        <a href="/settings#s-constraints"
                           style="font-size:0.72em;color:#8b5a3c;">Edit constraints →</a>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <script>
    var _aiIso = '{escape(iso)}';
    var _aiOpen = false;

    function aiToggle() {{
        _aiOpen = !_aiOpen;
        document.getElementById('ai-panel').style.display = _aiOpen ? '' : 'none';
        if (_aiOpen) {{
            setTimeout(function() {{
                var q = document.getElementById('ai-question');
                if (q) q.focus();
            }}, 100);
        }}
    }}

    /* Close on Escape */
    document.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape' && _aiOpen) aiToggle();
    }});

    function aiTab(tab) {{
        ['ask','review','generate'].forEach(function(t) {{
            document.getElementById('ai-pane-'+t).style.display = (t===tab) ? '' : 'none';
            var btn = document.getElementById('ai-tab-'+t);
            btn.style.color = (t===tab) ? '#8b5a3c' : '#888';
            btn.style.borderBottomColor = (t===tab) ? '#8b5a3c' : 'transparent';
        }});
    }}

    function aiQuick(q) {{
        document.getElementById('ai-question').value = q;
        aiAsk();
    }}

    function aiSetStatus(msg) {{
        var el = document.getElementById('ai-status');
        if (el) el.textContent = msg;
    }}

    function aiSetReasoning(text) {{
        var el = document.getElementById('ai-reasoning');
        if (el) el.innerHTML = '<span style="color:#888;">' + text.replace(/\n/g,'<br>') + '</span>';
    }}

    function _aiBubble(role, text) {{
        var hist = document.getElementById('ai-history');
        if (!hist) return null;
        var div = document.createElement('div');
        div.style.textAlign = role === 'user' ? 'right' : 'left';
        var bubble = document.createElement('span');
        bubble.style.cssText = role === 'user'
            ? 'display:inline-block;background:#8b5a3c;color:white;padding:5px 10px;border-radius:10px 10px 2px 10px;font-size:0.83em;max-width:88%;text-align:left;'
            : 'display:inline-block;background:#f0ebe4;color:#333;padding:5px 10px;border-radius:10px 10px 10px 2px;font-size:0.83em;max-width:88%;text-align:left;white-space:pre-wrap;';
        bubble.textContent = text;
        div.appendChild(bubble);
        hist.appendChild(div);
        hist.scrollTop = hist.scrollHeight;
        return bubble;
    }}

    function aiAsk() {{
        var q = document.getElementById('ai-question').value.trim();
        if (!q) return;
        document.getElementById('ai-question').value = '';
        _aiBubble('user', q);
        var rb = _aiBubble('assistant', '…');
        aiSetStatus('Thinking…');
        aiSetReasoning('Reading schedule, constraints, and calendar…');
        fetch('/plan-ai-suggest', {{
            method:'POST',
            headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
            body:'iso='+encodeURIComponent(_aiIso)+'&mode=ask&question='+encodeURIComponent(q)
        }}).then(function(r) {{
            if (!r.ok) {{ if(rb) rb.textContent='Error — check API key in Settings.'; aiSetStatus(''); return; }}
            return _aiStream(r, function(t) {{
                if(rb) rb.textContent=t;
                var h=document.getElementById('ai-history');
                if(h) h.scrollTop=h.scrollHeight;
            }}, function() {{
                aiSetStatus('');
                aiSetReasoning('Used: family schedule · child assignments · calendar events · family constraints');
            }});
        }}).catch(function(e) {{ if(rb) rb.textContent='Network error: '+e.message; aiSetStatus(''); }});
    }}

    function aiReview() {{
        var el=document.getElementById('ai-review-response');
        el.textContent='…'; aiSetStatus('Reviewing…');
        aiSetReasoning('Scanning for coverage gaps, conflicts, overloads…');
        fetch('/plan-ai-suggest', {{
            method:'POST',
            headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
            body:'iso='+encodeURIComponent(_aiIso)+'&mode=review'
        }}).then(function(r) {{
            if (!r.ok) {{ el.textContent='Error — check API key in Settings.'; aiSetStatus(''); return; }}
            return _aiStream(r, function(t){{el.textContent=t;}},
                function(){{ aiSetStatus(''); aiSetReasoning('Checked: all time slots · supervision · child loads · calendar'); }});
        }}).catch(function(e){{ el.textContent='Network error: '+e.message; aiSetStatus(''); }});
    }}

    function aiGenerate() {{
        var notes=document.getElementById('ai-gen-notes').value.trim();
        var el=document.getElementById('ai-gen-response');
        el.textContent='…'; aiSetStatus('Generating…');
        aiSetReasoning('Building schedule from constraints + commitments…');
        fetch('/plan-ai-suggest', {{
            method:'POST',
            headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
            body:'iso='+encodeURIComponent(_aiIso)+'&mode=generate&question='+encodeURIComponent(notes)
        }}).then(function(r) {{
            if (!r.ok) {{ el.textContent='Error — check API key in Settings.'; aiSetStatus(''); return; }}
            return _aiStream(r, function(t){{el.textContent=t;}},
                function(){{ aiSetStatus(''); aiSetReasoning('Generated from: ages · school blocks · chores · calendar · constraints'); }});
        }}).catch(function(e){{ el.textContent='Network error: '+e.message; aiSetStatus(''); }});
    }}

    function _aiStream(response, onChunk, onDone) {{
        var reader=response.body.getReader(), decoder=new TextDecoder(), full='';
        function read() {{
            return reader.read().then(function(res) {{
                if (res.done) {{ onDone(full); return; }}
                full += decoder.decode(res.value, {{stream:true}});
                onChunk(full);
                return read();
            }});
        }}
        return read();
    }}
    </script>"""
