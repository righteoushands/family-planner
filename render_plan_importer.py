"""
render_plan_importer.py — Plan Import Tool

Paste any free-form plan from an external AI, get it parsed into calendar
events and tasks, review/edit each item, then apply with one click.
"""
import json
import uuid
from datetime import date, timedelta
from html import escape

FAMILY_MEMBERS = ["Lauren", "John", "JP", "Joseph", "Michael", "James"]


def _load_upcoming_events(days: int = 30) -> list:
    try:
        with open("data/events.json") as f:
            data = json.load(f)
        events = data.get("data", [])
    except Exception:
        events = []
    today = date.today()
    cutoff = today + timedelta(days=days)
    upcoming = []
    for ev in events:
        if ev.get("archived"):
            continue
        try:
            d = date.fromisoformat(ev.get("start_date", ""))
            if today <= d <= cutoff:
                upcoming.append(ev)
        except Exception:
            pass
    return sorted(upcoming, key=lambda e: e.get("start_date", ""))


def _format_events_summary(events: list) -> str:
    if not events:
        return "No upcoming events in the next 30 days."
    lines = []
    for ev in events:
        who = ", ".join(ev.get("assigned_to", []))
        t = ev.get("start_time", "")
        e = ev.get("end_time", "")
        time_str = f" {t}" if t else ""
        if e:
            time_str += f"–{e}"
        lines.append(f"- {ev.get('start_date')} {ev.get('title','')}{time_str} [{who}]")
    return "\n".join(lines)


def build_analysis_system_prompt(iso_today: str, label_today: str, events_summary: str) -> str:
    return f"""You are a careful planning assistant for the McAdams Catholic homeschooling family.

TODAY IS: {label_today} ({iso_today})

== FAMILY MEMBERS ==
- Lauren (Mom) — manages the household and homeschool; default assignee for unspecified adult tasks
- John (Dad) — works; sometimes from home
- JP — 14 years old, 9th grade; handles significant academic and household tasks
- Joseph — 12 years old, 7th grade; capable but needs more support than JP
- Michael — 5 years old, kindergarten; very simple tasks only (e.g. "put away toys")
- James — 13 months old, toddler; CANNOT be assigned tasks

== PARSING RULES ==
1. Resolve ALL relative dates ("tomorrow", "next Tuesday", "this weekend", "in two weeks") using TODAY = {iso_today}
2. Separate CALENDAR EVENTS (time-bound) from TASKS (action items with deadlines)
3. If an item has both an event and preparatory tasks, split them
4. Assign to the most specific person context implies; use Lauren for unspecified adult items
5. COMMITMENT TEST — before creating a task, ask: did the person who wrote this text indicate they will actually do this, or is this something they might do, could do, or would benefit from doing? Only emit a task if the answer is "will do." Route everything else to suggestions[].
6. AI-GENERATED IDEAS — if the source text was itself an AI response (brainstorming, recommendations, "consider doing X", "you might want to"), treat every action item in it as a suggestion, not a task. Do not create tasks from AI suggestions unless the user's own words show they agreed to do it.
7. For tasks with natural sub-steps, list as subtasks (max 5)
8. Set confidence: "high" = certain; "medium" = best inference; "low" = critical info missing
9. Items with missing critical info (date or person unknown) MUST appear in "questions" too
10. NEVER set end_time earlier than time on the same date — if you can't compute a sensible end, leave end_time empty
11. NEVER mix data from two different source lines into one event — each distinct trip / flight / train / appointment is its own event
12. NO DATE = NO TASK — if you cannot determine a due date from the source text, do NOT emit the item as a task. Put it in questions[] instead with field: "due_date" and a note explaining what information is needed to schedule it. A task without a due date is not a task — it is an unresolved question.

== TRAVEL & MULTI-DAY RULES ==
A. Multi-day visits ("X visiting May 15–17", "guest stays 5/15 to 5/17"):
   → ONE event with date = first day, end_date = last day, time = "" and end_time = "" (treat as all-day span). Title like "Sarah Ori visiting".
B. Flights — create ONE event per flight segment. Title format: "Flight [airline] [#] — [arrives|departs] [airport]".
   • Arrival flight ("arrives DCA 12:20 PM on 5/15"): time = arrival time, end_time empty.
   • Departure flight ("departs DCA 6:50 PM on 5/15"): time = departure time, end_time empty.
   • If the visitor is being picked up/dropped off, ALSO create a related task ("Pick up Sarah Ori at DCA — Southwest 3702") assigned to the most likely driver (Lauren by default), due_date = same day.
C. Trains/buses with both depart and arrive times ("Amtrak 95 departs ALX 2:56 PM arrives FBG 3:42 PM on 5/15"):
   → ONE event. time = depart time, end_time = arrive time. Title like "Amtrak 95 — ALX → FBG". Notes: include train name and full depart/arrive details.
D. If a visitor's arrival logistics include both a flight AND a connecting train on the same day, those are TWO separate events plus optional pickup tasks — never merge them.
E. Date ranges with en-dash (–), em-dash (—), or hyphen (-) between two dates ALWAYS mean a span; resolve both endpoints.

== EXISTING CALENDAR (next 30 days — scan for conflicts) ==
{events_summary}

== WARNINGS TO FLAG ==
- Date/time conflicts (same person, overlapping or same time slot)
- Days that look overloaded (many events + tasks on same day for same person)
- Deadlines that are already past today
- Events that likely need a time but have none (doctor, dentist, activity)
- Items that seem age-inappropriate for the assigned person

== SUGGESTIONS TO OFFER ==
Suggestions are for ideas, recommendations, and things the family might benefit from doing but has NOT committed to. Route here instead of tasks[] when the source text is AI-generated brainstorming or recommendations, when the action is conditional such as "if you have time", "consider", or "might want to", when the user's words show interest but not commitment, or when no due date is determinable and the item has no urgency signal.

Specific suggestion types to look for: shifting tasks to balance load across days, adding prep reminders before appointments, breaking multi-week projects into milestone tasks, and ideas surfaced from AI brainstorming that Lauren hasn't committed to.

== ROUTING & PLACEMENT ==
Some lines in a pasted plan don't represent new events or tasks — they're info that belongs on an existing record. Examples:
- "Bring snacks for soccer practice on Tuesday" → a NOTE on the existing Tuesday soccer event
- "JP wants the Lego Bionicle set for his birthday" → APPEND to JP's profile gift_ideas
- "The Smiths can't have peanuts" → UPDATE the Smith family's food_allergies in friends.json
- "Restocked pantry: flour, sugar, baking soda" → APPEND to meal_inventory.json pantry
- "Pray for Aunt Mary's surgery on May 12" → CREATE in prayer/intentions.json
- "Remember to thank the Joneses for the casserole" → CREATE in thankyou_reminders.json

Emit these as "placements" — separate from events and tasks. Each placement targets ONE field on ONE existing (or new) record.

Available destinations (use these exact strings — do not invent others):
- events.json — info to attach to an existing calendar event
- profiles/jp.json, profiles/joseph.json, profiles/michael.json, profiles/james.json — child profile data
- profiles/mom.json, profiles/john.json — adult profile data
- friends.json — info about a friend family
- meal_inventory.json — pantry / fridge / freezer / use_soon updates
- prayer/intentions.json — a new prayer intention
- thankyou_reminders.json — a thank-you reminder to send

Each placement carries: id, destination, action ("UPDATE" / "APPEND" / "CREATE"), match_hint (free text to find the right record — event title+date, family name, etc.), field (the specific field name like "notes", "gift_ideas", "food_allergies", "pantry"), value (the actual content), confidence, and reason (one short line explaining why this routing was chosen).

If one record needs multiple field updates, emit each as a SEPARATE placement entry — never combine fields into one placement. If a line doesn't fit any of the destinations above, leave it as a regular task or event instead — do not invent a destination.

== OUTPUT FORMAT ==
Respond with ONLY valid JSON inside ```json ... ``` code fences. No other text outside the fences.
CRITICAL JSON RULES:
- Do NOT put literal line breaks inside string values — use \\n if needed
- Do NOT use trailing commas after the last item in an array or object
- All string values must be on one line or use \\n escapes
- Use only standard ASCII quotes ("), never curly/smart quotes

{{
  "events": [
    {{
      "id": "e1",
      "title": "Dentist — Michael",
      "date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD",
      "time": "10:00 AM",
      "end_time": "11:00 AM",
      "who": ["Lauren", "Michael"],
      "notes": "Bring insurance card",
      "recurrence": "none",
      "confidence": "high"
    }}
  ],
  "tasks": [
    {{
      "id": "t1",
      "person": "JP",
      "text": "Write history essay introduction",
      "due_date": "YYYY-MM-DD",
      "source": "committed",   // committed means the user stated they will do this — never emit a task with source "suggested"
      "subtasks": ["Research topic", "Create outline", "Write opening paragraph"],
      "notes": "",
      "confidence": "high"
    }}
  ],
  "questions": [
    {{
      "id": "q1",
      "text": "What time is the dentist appointment — morning or afternoon?",
      "related_to": "e1",
      "field": "time"
    }}
  ],
  "warnings": [
    {{
      "text": "JP already has a scheduled activity on that date — verify no conflict.",
      "severity": "high",
      "related_to": "e2"
    }}
  ],
  "suggestions": [
    {{
      "text": "Consider moving the grocery run to Monday to prepare for Tuesday's dinner.",
      "related_to": null
    }}
  ],
  "placements": [
    {{
      "id": "p1",
      "destination": "events.json",
      "action": "UPDATE",
      "match_hint": "Sea Cadets Drill — May 3",
      "field": "notes",
      "value": "Bring water bottle and Class B uniform",
      "confidence": "high",
      "reason": "Detail belongs on the existing event, not as a new event"
    }},
    {{
      "id": "p2",
      "destination": "profiles/jp.json",
      "action": "APPEND",
      "match_hint": "JP",
      "field": "gift_ideas",
      "value": "Lego Bionicle set",
      "confidence": "high",
      "reason": "Birthday gift idea belongs on JP's profile"
    }}
  ]
}}"""


# ── Companion detection & consultation ────────────────────────────────────────

_COMPANION_KEYWORDS = {
    "gregory": {
        "words": [
            "school","lesson","lessons","curriculum","homework","essay","study","class","subject",
            "assignment","academic","history","math","reading","science","latin","writing","spelling",
            "phonics","catechism","literature","geography","schedule school","teach","textbook",
            "co-op","co op","learning","workbook","chapter",
        ],
        "label": "Fr. Gregory",
        "role": "Headmaster · School",
        "color": "#1e3566",
        "emoji": "📚",
        "prompt_intro": (
            "You are being consulted during a plan import. Lauren has pasted a plan from an "
            "external AI and you are reviewing the school-related portions. Give your perspective "
            "as the academic director: are the school tasks realistic, well-sequenced, and "
            "appropriate for each child? Flag anything concerning. Be concise and direct."
        ),
    },
    "lorenzo": {
        "words": [
            "meal","dinner","lunch","breakfast","cook","cooking","recipe","grocery","groceries",
            "food","menu","restaurant","kitchen","bake","baking","snack","prep","crockpot",
            "slow cooker","instant pot","leftovers","pantry","shop","shopping","ingredients",
        ],
        "label": "Lorenzo",
        "role": "Personal Chef",
        "color": "#8b3a1a",
        "emoji": "🍽️",
        "prompt_intro": (
            "You are being consulted during a plan import. Lauren has pasted a plan from an "
            "external AI and you are reviewing the meal and food-related portions. Give your "
            "perspective as the family chef: are the meals planned wisely, is the timing "
            "realistic, any suggestions for simplifying or improving the week's menu? "
            "Be practical and specific."
        ),
    },
    "coach": {
        "words": [
            "exercise","sport","sports","soccer","baseball","basketball","run","running","bike",
            "biking","walk","hike","gym","pe","physical education","outdoor","park","swim",
            "swimming","practice","game","tournament","yoga","workout","movement","fitness",
            "strength","stretching","kickball","tee ball","active",
        ],
        "label": "Coach",
        "role": "Fitness",
        "color": "#1a6e3e",
        "emoji": "💪",
        "prompt_intro": (
            "You are being consulted during a plan import. Lauren has pasted a plan from an "
            "external AI and you are reviewing the physical activity and fitness portions. "
            "Give your perspective as the family fitness coach: is there enough movement? "
            "Are activities age-appropriate? Any concerns or suggestions? Be energetic and direct."
        ),
    },
    "monica": {
        "words": [
            "doctor","dentist","appointment","sick","health","vaccine","vaccination","milestone",
            "development","pediatric","checkup","check-up","fever","medicine","therapy","speech",
            "vision","hearing","well visit","well-child","growth","nap","sleep","potty","feeding",
            "weight","allergy","allergist","pediatrician","james","michael",
        ],
        "label": "Dr. Monica",
        "role": "Health & Development",
        "color": "#8b3a5c",
        "emoji": "🌸",
        "prompt_intro": (
            "You are being consulted during a plan import. Lauren has pasted a plan from an "
            "external AI and you are reviewing the child health, development, and medical portions. "
            "Give your perspective as the family's child development and pediatric health expert: "
            "anything concerning, any follow-ups to recommend, any developmental context to add? "
            "Be warm and reassuring but thorough."
        ),
    },
    "lucy": {
        "words": [],  # Lucy is always relevant as the integrator
        "label": "Lucy",
        "role": "Family Companion",
        "color": "#5b3a8a",
        "emoji": "✨",
        "prompt_intro": (
            "You are being consulted during a plan import. Lauren has pasted a plan from an "
            "external AI and wants your overall perspective. Look at the plan holistically: "
            "Does it feel balanced? Is there rest built in? Does it honor the family's faith "
            "life and rhythms? What would make this week feel more like a gift than a grind? "
            "Be warm, honest, and practical."
        ),
    },
}


def detect_relevant_companions(parsed_data: dict) -> list:
    """Return list of companion keys that are relevant to this parsed plan."""
    # Gather all text from events and tasks
    all_text = []
    for ev in parsed_data.get("events", []):
        all_text.append(ev.get("title", "").lower())
        all_text.append(ev.get("notes", "").lower())
    for t in parsed_data.get("tasks", []):
        all_text.append(t.get("text", "").lower())
        all_text.append(t.get("notes", "").lower())
        for s in t.get("subtasks", []):
            all_text.append(s.lower())
    corpus = " ".join(all_text)

    relevant = []
    for key, cfg in _COMPANION_KEYWORDS.items():
        if key == "lucy":
            continue  # Lucy is added at the end always
        if any(w in corpus for w in cfg["words"]):
            relevant.append(key)

    # Lucy is always available as the integrator
    relevant.append("lucy")
    return relevant


def build_consult_system_prompt(companion_key: str, parsed_data: dict,
                                 iso: str, weekday: str, date_label: str) -> str:
    """Build a full system prompt for a companion consulting on the imported plan."""
    cfg = _COMPANION_KEYWORDS.get(companion_key, {})
    intro = cfg.get("prompt_intro", "")

    # Get companion's own system prompt
    try:
        if companion_key == "lucy":
            from render_lucy import build_lucy_context
            base_ctx = build_lucy_context(iso, weekday, date_label)
        elif companion_key == "lorenzo":
            from render_lorenzo import build_lorenzo_context
            base_ctx = build_lorenzo_context(iso, weekday, date_label)
        elif companion_key == "gregory":
            from render_gregory import build_gregory_context
            base_ctx = build_gregory_context(iso, weekday, date_label)
        elif companion_key == "coach":
            from render_coach import build_coach_context
            base_ctx = build_coach_context(iso, weekday, date_label)
        elif companion_key == "monica":
            from render_monica import build_monica_context
            base_ctx = build_monica_context(iso, weekday, date_label)
        else:
            base_ctx = ""
    except Exception:
        base_ctx = ""

    # Build compact plan summary
    plan_lines = []
    events = parsed_data.get("events", [])
    if events:
        plan_lines.append("CALENDAR EVENTS IN THE PLAN:")
        for ev in events:
            who = ", ".join(ev.get("who", []))
            t = ev.get("time", "")
            plan_lines.append(f"  - {ev.get('date','')} {ev.get('title','')} {t} [{who}]")
            if ev.get("notes"):
                plan_lines.append(f"    Notes: {ev['notes']}")

    tasks = parsed_data.get("tasks", [])
    if tasks:
        plan_lines.append("TASKS IN THE PLAN:")
        for t in tasks:
            subs = t.get("subtasks", [])
            plan_lines.append(f"  - [{t.get('person','')}] {t.get('text','')} (due {t.get('due_date','')})")
            for s in subs:
                plan_lines.append(f"      • {s}")

    warnings = parsed_data.get("warnings", [])
    if warnings:
        plan_lines.append("FLAGGED WARNINGS:")
        for w in warnings:
            plan_lines.append(f"  ⚠ {w.get('text','')}")

    plan_summary = "\n".join(plan_lines) if plan_lines else "No events or tasks parsed yet."

    return f"""{base_ctx}

== PLAN IMPORT CONSULTATION ==
{intro}

Here is what was parsed from Lauren's imported plan:

{plan_summary}

Lauren may ask you general questions or request specific advice about this plan.
Keep responses concise and actionable — she is in the middle of reviewing the plan.
Do NOT try to apply or write anything to the system — just advise."""


_COMPANION_COLORS = {
    "lucy":    "#5b3a8a",
    "lorenzo": "#8b3a1a",
    "gregory": "#1e3566",
    "coach":   "#1a6e3e",
    "monica":  "#8b3a5c",
}

_COMPANION_DISPLAY = {
    "lucy":    ("✨", "Lucy"),
    "lorenzo": ("🍽️", "Lorenzo"),
    "gregory": ("📚", "Father Gregory"),
    "coach":   ("💪", "Coach"),
    "monica":  ("🌸", "Dr. Monica"),
}


def build_roundtable_prompt(
    companion_keys: list,
    plan_data: dict,
    question: str,
    iso: str,
    weekday: str,
    date_label: str,
) -> str:
    """Single-call prompt that makes all companions respond then Lucy synthesizes."""

    # Build plan summary
    plan_lines = []
    events = plan_data.get("events", [])
    if events:
        plan_lines.append("CALENDAR EVENTS:")
        for ev in events:
            who = ", ".join(ev.get("who", []))
            t   = ev.get("time", "")
            plan_lines.append(f"  - {ev.get('date','')} {ev.get('title','')} {t} [{who}]")
    tasks = plan_data.get("tasks", [])
    if tasks:
        plan_lines.append("TASKS:")
        for t in tasks:
            subs = t.get("subtasks", [])
            plan_lines.append(f"  - [{t.get('person','')}] {t.get('text','')} (due {t.get('due_date','')})")
            for s in subs:
                plan_lines.append(f"      • {s}")
    warnings = plan_data.get("warnings", [])
    if warnings:
        plan_lines.append("FLAGS/WARNINGS:")
        for w in warnings:
            plan_lines.append(f"  ⚠ {w.get('text','')}")
    plan_summary = "\n".join(plan_lines) if plan_lines else "No events or tasks in plan yet."

    # Describe present companions
    present = [k for k in companion_keys if k in _COMPANION_DISPLAY]
    if "lucy" not in present:
        present.append("lucy")  # always moderates

    companion_descriptions = {
        "lucy":    "Lucy — warm Catholic companion and family integrator; cares about faith rhythms, rest, emotional balance, and the big picture",
        "lorenzo": "Lorenzo — personal chef; focused on meals, grocery reality, kitchen prep time, and feeding the family well",
        "gregory": "Father Gregory — homeschool headmaster; focused on academics, child-appropriate learning, lesson sequencing, and formation",
        "coach":   "Coach — fitness and movement guide; focused on physical activity, outdoor time, age-appropriate exercise, and energy levels",
        "monica":  "Dr. Monica — child development and pediatric health expert; focused on James and Michael's developmental needs, health appointments, and age-appropriate expectations",
    }
    companions_text = "\n".join(
        f"- {companion_descriptions[k]}"
        for k in present if k in companion_descriptions
    )

    # Non-Lucy companions speak first, then Lucy synthesizes
    speakers = [k for k in present if k != "lucy"]
    speaker_lines = "\n".join(
        f"**{_COMPANION_DISPLAY[k][1]}:** [2–4 sentences from {_COMPANION_DISPLAY[k][1]}'s specific perspective on this question and plan]"
        for k in speakers
    )

    return f"""You are facilitating a private roundtable among the McAdams family's AI companions.
Today is {weekday}, {date_label} ({iso}).

THE FAMILY: Lauren (Mom, homeschools), John (Dad, works), JP (14), Joseph (12), Michael (5), James (13 months).

COMPANIONS PRESENT:
{companions_text}

THE IMPORTED PLAN:
{plan_summary}

LAUREN'S QUESTION / SITUATION:
\"{question}\"

YOUR TASK:
Write the roundtable discussion as if each companion is speaking in turn, then Lucy gives a final synthesis.
Be concrete and specific to THIS plan and THIS question. Each companion should speak from their expertise.
Keep each voice brief (2–4 sentences). Lucy's synthesis should be 4–6 sentences and give a clear, actionable recommendation.

FORMAT (use exactly this structure — bold names, colon, then response):

{speaker_lines}

**Lucy's Synthesis:** [Warm, decisive, practical wrap-up that weaves all perspectives into one clear recommendation for Lauren. What should she actually DO?]

Do not add any other text outside this format. Do not use headers or section breaks beyond the companion names."""


def render_plan_import_page() -> str:
    today = date.today()
    iso   = today.isoformat()
    label = today.strftime("%A, %B %d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Plan Import &middot; McAdams Family</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --ink:#2c2825;--ink-soft:rgba(44,40,37,.7);--ink-faint:rgba(44,40,37,.4);
  --parchment:#fdf8f0;--cream:#f7f1e6;--gold:#b8860b;--gold-light:#d4a843;
  --border:rgba(44,40,37,.12);--border-light:rgba(44,40,37,.07);
  --green:#1a6e3e;--amber:#d97706;--red:#b91c1c;--navy:#1e3566;--purple:#5b3a8a;
}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:var(--parchment);color:var(--ink);min-height:100vh;padding-bottom:80px;}}
.pi-header{{background:var(--navy);color:#fff;padding:14px 16px 12px;
            display:flex;align-items:center;gap:10px;}}
.pi-header a{{color:rgba(255,255,255,0.7);text-decoration:none;font-size:0.8em;}}
.pi-header h1{{font-size:1em;font-weight:700;flex:1;}}
.pi-body{{max-width:680px;margin:0 auto;padding:16px;}}
.pi-card{{background:#fff;border:1px solid var(--border);border-radius:14px;
          padding:16px;margin-bottom:14px;}}
.pi-label{{font-size:0.72em;font-weight:700;letter-spacing:.06em;
           color:var(--ink-faint);text-transform:uppercase;margin-bottom:8px;}}
textarea.pi-paste{{width:100%;min-height:180px;border:1.5px solid var(--border);
  border-radius:10px;padding:12px;font-family:inherit;font-size:0.88em;
  line-height:1.55;color:var(--ink);background:var(--cream);resize:vertical;}}
textarea.pi-paste:focus{{outline:none;border-color:var(--navy);}}
.pi-btn{{display:inline-flex;align-items:center;gap:7px;padding:11px 22px;
         border:none;border-radius:24px;font-family:inherit;font-weight:700;
         font-size:0.88em;cursor:pointer;transition:opacity .15s;}}
.pi-btn:disabled{{opacity:.5;cursor:not-allowed;}}
.pi-btn-primary{{background:var(--navy);color:#fff;}}
.pi-btn-apply{{background:var(--green);color:#fff;font-size:0.95em;padding:13px 28px;}}
.pi-btn-sm{{padding:5px 12px;font-size:0.75em;border-radius:14px;font-weight:600;}}
.pi-btn-remove{{background:rgba(185,28,28,.08);color:var(--red);border:1px solid rgba(185,28,28,.18);}}
.pi-btn-edit{{background:rgba(30,53,102,.08);color:var(--navy);border:1px solid rgba(30,53,102,.15);}}
.task-decide-row{{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;}}
.pi-btn-add{{background:rgba(22,163,74,.10);color:var(--green);border:1px solid rgba(22,163,74,.25);}}
.pi-btn-skip{{background:rgba(82,82,91,.10);color:var(--ink-faint);border:1px solid rgba(82,82,91,.20);}}
.pi-btn-defer{{background:rgba(245,158,11,.12);color:var(--amber);border:1px solid rgba(245,158,11,.30);}}
.section-header{{display:flex;align-items:center;gap:8px;margin-bottom:12px;}}
.section-icon{{font-size:1.2em;}}
.section-title{{font-size:0.9em;font-weight:700;color:var(--ink);}}
.section-count{{background:var(--navy);color:#fff;border-radius:10px;
                padding:2px 8px;font-size:0.72em;font-weight:700;}}
.section-count.green{{background:var(--green);}}
.section-count.amber{{background:var(--amber);}}
.section-count.red{{background:var(--red);}}
.section-count.blue{{background:var(--navy);}}
.placement-row{{border:1px solid rgba(30,53,102,.18);border-radius:10px;margin-bottom:8px;overflow:hidden;background:rgba(30,53,102,.03);}}
.placement-main{{display:flex;align-items:center;gap:10px;padding:10px 12px;cursor:pointer;
                 background:rgba(30,53,102,.06);transition:background .1s;}}
.placement-main:hover{{background:rgba(30,53,102,.10);}}
.action-badge{{display:inline-block;font-size:0.66em;font-weight:700;letter-spacing:.04em;
               padding:2px 7px;border-radius:6px;text-transform:uppercase;flex-shrink:0;}}
.action-badge.update{{background:rgba(30,53,102,.12);color:var(--navy);}}
.action-badge.append{{background:rgba(26,110,62,.12);color:var(--green);}}
.action-badge.create{{background:rgba(91,58,138,.12);color:var(--purple);}}
.placement-dest{{font-size:0.72em;color:var(--ink-soft);margin-top:2px;}}
.placement-reason{{font-size:0.78em;color:var(--ink-soft);font-style:italic;
                   margin-top:6px;line-height:1.45;}}
.placement-meta-row{{display:flex;flex-wrap:wrap;gap:6px 12px;font-size:0.74em;
                     color:var(--ink-soft);margin-bottom:8px;}}
.placement-meta-row strong{{color:var(--ink);font-weight:700;}}
textarea.placement-value{{width:100%;min-height:64px;border:1px solid var(--border);
  border-radius:7px;padding:7px 10px;font-family:inherit;font-size:0.84em;
  color:var(--ink);background:#fafafa;resize:vertical;line-height:1.5;}}
textarea.placement-value:focus{{outline:none;border-color:var(--navy);}}
.item-row{{border:1px solid var(--border);border-radius:10px;margin-bottom:8px;overflow:hidden;}}
.item-main{{display:flex;align-items:center;gap:10px;padding:10px 12px;cursor:pointer;
            background:var(--cream);transition:background .1s;}}
.item-main:hover{{background:#efe9de;}}
.item-cb{{width:18px;height:18px;accent-color:var(--green);cursor:pointer;flex-shrink:0;}}
.item-info{{flex:1;min-width:0;}}
.item-title{{font-size:0.88em;font-weight:600;color:var(--ink);}}
.item-meta{{font-size:0.72em;color:var(--ink-soft);margin-top:2px;}}
.item-conf{{font-size:0.68em;padding:2px 7px;border-radius:8px;font-weight:700;
            flex-shrink:0;}}
.conf-high{{background:rgba(26,110,62,.12);color:var(--green);}}
.conf-medium{{background:rgba(217,119,6,.12);color:var(--amber);}}
.conf-low{{background:rgba(185,28,28,.12);color:var(--red);}}
.item-edit{{border-top:1px solid var(--border);padding:12px;background:#fff;display:none;}}
.item-edit.open{{display:block;}}
.edit-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px;}}
.edit-field{{display:flex;flex-direction:column;gap:3px;}}
.edit-field label{{font-size:0.68em;font-weight:700;color:var(--ink-faint);
                   text-transform:uppercase;letter-spacing:.04em;}}
.edit-field input,.edit-field select,.edit-field textarea{{
  border:1px solid var(--border);border-radius:7px;padding:6px 9px;
  font-family:inherit;font-size:0.82em;color:var(--ink);background:#fafafa;}}
.edit-field input:focus,.edit-field select:focus,.edit-field textarea:focus{{
  outline:none;border-color:var(--navy);}}
.subtask-list{{margin-top:6px;}}
.subtask-item{{display:flex;align-items:center;gap:6px;margin-bottom:4px;}}
.subtask-item input{{flex:1;border:1px solid var(--border);border-radius:6px;
                     padding:4px 8px;font-size:0.8em;font-family:inherit;}}
.subtask-del{{background:none;border:none;color:var(--red);cursor:pointer;font-size:1em;}}
.q-item{{background:#fffbf0;border:1px solid rgba(217,119,6,.25);border-radius:10px;
          padding:12px;margin-bottom:8px;}}
.q-text{{font-size:0.85em;font-weight:600;color:var(--ink);margin-bottom:6px;}}
.q-input{{width:100%;border:1px solid var(--border);border-radius:7px;padding:7px 10px;
           font-family:inherit;font-size:0.84em;color:var(--ink);background:#fff;}}
.q-input:focus{{outline:none;border-color:var(--amber);}}
.warn-item{{display:flex;gap:10px;padding:10px 12px;border-radius:9px;margin-bottom:6px;
             background:rgba(185,28,28,.05);border:1px solid rgba(185,28,28,.15);}}
.warn-item.medium{{background:rgba(217,119,6,.06);border-color:rgba(217,119,6,.2);}}
.warn-item.low{{background:rgba(44,40,37,.04);border-color:var(--border);}}
.warn-icon{{font-size:1em;flex-shrink:0;}}
.warn-text{{font-size:0.82em;color:var(--ink);line-height:1.45;}}
.sug-item{{display:flex;gap:10px;padding:10px 12px;border-radius:9px;margin-bottom:6px;
            background:rgba(91,58,138,.05);border:1px solid rgba(91,58,138,.15);}}
.sug-text{{font-size:0.82em;color:var(--ink);line-height:1.45;}}
.spinner{{display:inline-block;width:16px;height:16px;border:2px solid rgba(255,255,255,.3);
          border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.phase{{display:none;}}
.phase.active{{display:block;}}
#phase-thinking{{text-align:center;padding:48px 24px;}}
.thinking-label{{font-size:0.85em;color:var(--ink-soft);margin-top:16px;}}
.thinking-spinner{{width:40px;height:40px;border:3px solid var(--border);
                   border-top-color:var(--navy);border-radius:50%;
                   animation:spin .9s linear infinite;margin:0 auto;}}
.apply-bar{{position:sticky;bottom:0;background:var(--parchment);
            border-top:1px solid var(--border);padding:12px 16px;
            display:flex;align-items:center;justify-content:space-between;}}
.apply-summary{{font-size:0.82em;color:var(--ink-soft);}}
.apply-summary strong{{color:var(--ink);}}
.badge{{display:inline-block;background:var(--gold-light);color:#fff;
        border-radius:12px;padding:2px 9px;font-size:0.7em;font-weight:700;
        margin-left:4px;vertical-align:middle;}}
.success-card{{text-align:center;padding:40px 20px;}}
.success-icon{{font-size:3em;margin-bottom:12px;}}
.success-title{{font-size:1.2em;font-weight:700;color:var(--green);margin-bottom:8px;}}
.success-body{{font-size:0.88em;color:var(--ink-soft);line-height:1.6;}}
/* Receipt phase ────────────────────────────────────────────────────────── */
.receipt-card{{background:#fff;border:1px solid var(--border);border-radius:14px;
               margin:0 16px 24px;padding:18px 16px 14px;}}
.receipt-banner{{display:flex;align-items:center;gap:10px;margin-bottom:18px;
                 padding-bottom:14px;border-bottom:1px solid var(--border);}}
.receipt-icon{{font-size:1.6em;}}
.receipt-title{{font-size:1.05em;font-weight:700;color:var(--green);}}
.receipt-summary{{font-size:0.78em;color:var(--ink-soft);margin-top:2px;}}
.receipt-section{{margin-bottom:14px;}}
.receipt-section:last-child{{margin-bottom:0;}}
.receipt-section-head{{display:flex;align-items:center;gap:8px;margin-bottom:8px;
                       font-size:0.84em;font-weight:700;color:var(--ink);}}
.receipt-section-count{{background:var(--ink-faint);color:#fff;border-radius:10px;
                        padding:2px 8px;font-size:0.7em;font-weight:700;}}
.receipt-row{{display:flex;align-items:flex-start;gap:10px;padding:10px 12px;
              border:1px solid var(--border);border-radius:9px;
              background:var(--cream);margin-bottom:6px;}}
.receipt-row.undone{{opacity:.55;background:#f3efe5;}}
.receipt-row-info{{flex:1;min-width:0;}}
.receipt-row-label{{font-size:0.74em;font-weight:700;color:var(--ink-soft);
                    text-transform:uppercase;letter-spacing:.04em;}}
.receipt-row-title{{font-size:0.88em;font-weight:600;color:var(--ink);
                    margin-top:2px;word-wrap:break-word;}}
.receipt-row-preview{{font-size:0.78em;color:var(--ink-soft);margin-top:3px;
                      line-height:1.4;word-wrap:break-word;}}
.receipt-row-meta{{font-size:0.72em;color:var(--ink-faint);margin-top:3px;}}
.receipt-undo-btn{{background:rgba(185,28,28,.08);color:var(--red);
                   border:1px solid rgba(185,28,28,.2);
                   border-radius:14px;padding:5px 12px;font-size:0.74em;
                   font-weight:700;cursor:pointer;flex-shrink:0;
                   font-family:inherit;}}
.receipt-undo-btn:hover{{background:rgba(185,28,28,.14);}}
.receipt-undo-btn:disabled{{opacity:.4;cursor:not-allowed;}}
.receipt-undo-status{{font-size:0.74em;color:var(--ink-faint);
                      font-style:italic;flex-shrink:0;align-self:center;}}
.receipt-empty{{font-size:0.78em;color:var(--ink-faint);font-style:italic;
                padding:8px 0;}}
.person-tag{{display:inline-block;padding:1px 7px;border-radius:8px;
             font-size:0.7em;font-weight:700;margin-right:3px;
             background:rgba(30,53,102,.1);color:var(--navy);}}
/* Companion consultation panel */
.consult-card{{background:#fff;border:1px solid var(--border);border-radius:14px;
               margin:0 16px 80px;overflow:hidden;}}
.consult-header{{padding:12px 16px 8px;}}
.consult-title{{font-size:0.82em;font-weight:700;color:var(--ink);margin-bottom:6px;}}
.consult-subtitle{{font-size:0.72em;color:var(--ink-faint);line-height:1.4;}}
.companion-row{{display:flex;gap:7px;flex-wrap:wrap;padding:0 16px 12px;}}
/* Council */
.council-section{{margin:0 16px 12px;padding:11px 13px;background:linear-gradient(135deg,#f9f4ff 0%,#f4f0fb 100%);border:1px solid #d9cef0;border-radius:10px;}}
.council-title{{font-size:0.75em;font-weight:700;color:#5b3a8a;margin-bottom:6px;letter-spacing:.04em;text-transform:uppercase;}}
.council-presets{{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:8px;}}
.council-preset{{font-size:0.72em;padding:4px 10px;border:1px solid #c8b8e8;background:#fff;border-radius:14px;cursor:pointer;color:#5b3a8a;font-family:inherit;transition:background .12s;white-space:nowrap;}}
.council-preset:hover{{background:#ede5ff;}}
.council-preset.selected{{background:#5b3a8a;color:#fff;border-color:#5b3a8a;}}
.council-input-row{{display:flex;gap:6px;}}
.council-input{{flex:1;padding:7px 10px;font-size:0.78em;border:1px solid #c8b8e8;border-radius:8px;font-family:inherit;background:#fff;color:var(--ink);outline:none;}}
.council-input:focus{{border-color:#5b3a8a;box-shadow:0 0 0 2px #5b3a8a30;}}
.council-btn{{padding:7px 14px;background:#5b3a8a;border:none;border-radius:8px;color:#fff;font-size:0.78em;font-weight:700;font-family:inherit;cursor:pointer;white-space:nowrap;}}
.council-btn:hover{{background:#4a2e72;}}
.council-btn:disabled{{opacity:.5;cursor:not-allowed;}}
.council-response{{margin-top:10px;display:none;}}
.council-thread{{font-size:0.82em;line-height:1.55;color:var(--ink);}}
.council-voice{{margin-bottom:10px;padding:9px 12px;border-radius:8px;background:#fff;border-left:3px solid #ccc;}}
.council-voice-name{{font-weight:700;font-size:0.9em;margin-bottom:3px;}}
.council-voice-text{{color:var(--ink-sub);}}
.council-synthesis{{margin-bottom:10px;padding:10px 13px;border-radius:8px;background:#f0e8ff;border-left:3px solid #5b3a8a;}}
.council-synthesis .council-voice-name{{color:#5b3a8a;}}
.council-thinking{{font-size:0.8em;color:var(--ink-faint);font-style:italic;padding:6px 0;}}
.council-error{{font-size:0.8em;color:#c0392b;padding:6px 0;}}
/* Companion suggestions strip (extracted actionable items below a chat reply) */
.companion-suggestions{{margin:6px 0 14px 14px;padding:8px 10px 10px;
                        border-left:3px solid #5b3a8a;background:#fafaff;
                        border-radius:0 8px 8px 0;}}
.companion-suggestions-header{{font-size:0.74em;font-weight:700;color:var(--ink);
                                margin-bottom:6px;letter-spacing:.02em;
                                display:flex;align-items:center;gap:6px;}}
.companion-suggestions .item-row{{margin:5px 0;}}
.companion-suggestions .item-title{{font-size:0.86em;}}
.companion-btn{{display:flex;align-items:center;gap:6px;padding:7px 13px;
                border:none;border-radius:20px;font-family:inherit;font-size:0.78em;
                font-weight:700;cursor:pointer;color:#fff;transition:opacity .15s;
                white-space:nowrap;}}
.companion-btn:hover{{opacity:.88;}}
.companion-btn.active{{box-shadow:0 0 0 3px rgba(255,255,255,.6),0 0 0 5px currentColor;}}
.consult-chat-area{{border-top:1px solid var(--border);}}
.consult-chat-header{{display:flex;align-items:center;gap:10px;padding:10px 14px 8px;}}
.consult-chat-name{{font-size:0.85em;font-weight:700;flex:1;}}
.consult-chat-close{{background:none;border:none;cursor:pointer;font-size:1.1em;
                     color:var(--ink-faint);padding:4px;}}
.consult-messages{{padding:10px 14px;max-height:280px;overflow-y:auto;
                   display:flex;flex-direction:column;gap:8px;}}
.cmsg-user{{background:var(--navy);color:#fff;padding:8px 12px;border-radius:14px 14px 4px 14px;
             font-size:0.84em;line-height:1.5;max-width:80%;align-self:flex-end;}}
.cmsg-ai{{background:var(--cream);padding:8px 12px;border-radius:4px 14px 14px 14px;
           font-size:0.84em;line-height:1.6;max-width:90%;align-self:flex-start;white-space:pre-wrap;}}
.cmsg-thinking{{font-size:0.78em;color:var(--ink-faint);align-self:flex-start;
                 font-style:italic;padding:4px 0;}}
.consult-input-row{{display:flex;gap:8px;padding:8px 14px 12px;border-top:1px solid var(--border);}}
.consult-input{{flex:1;border:1px solid var(--border);border-radius:20px;
                padding:8px 14px;font-family:inherit;font-size:0.84em;
                color:var(--ink);background:var(--cream);}}
.consult-input:focus{{outline:none;border-color:var(--navy);}}
.consult-send{{background:var(--navy);color:#fff;border:none;border-radius:20px;
               padding:8px 16px;font-family:inherit;font-size:0.82em;font-weight:700;cursor:pointer;}}
</style>
</head>
<body>
<div class="pi-header">
  <a href="/">&#8592; Home</a>
  <h1>&#128203; Plan Importer</h1>
  <a href="/plan-import-history" style="margin-left:auto;font-size:0.82em;">&#128190; Saved analyses</a>
</div>

<!-- Phase 1: Paste -->
<div id="phase-paste" class="phase active">
<div class="pi-body">
  <div class="pi-card">
    <div class="pi-label">Paste your plan</div>
    <p style="font-size:0.82em;color:var(--ink-soft);margin-bottom:10px;line-height:1.5;">
      Copy any plan you made with an external AI — ChatGPT, Claude, Gemini, etc. It can be a
      full weekly schedule, a project plan, a list of tasks, or anything in between. The more
      detail you include, the better the results.
    </p>
    <textarea class="pi-paste" id="plan-text"
      placeholder="Paste your plan here, or attach an image below...&#10;&#10;For example:&#10;• Monday: dentist for Michael at 2pm, Lauren driving&#10;• JP needs to finish his history essay by Friday&#10;• Family picnic Saturday at Riverside Park&#10;• Joseph: read chapters 5–8 of The Hobbit this week"></textarea>

    <!-- Image upload (file picker, drag-drop, paste) -->
    <div id="img-drop" style="margin-top:10px;padding:14px;border:1.5px dashed #cbd5e1;
         border-radius:10px;background:#fafaf7;text-align:center;cursor:pointer;
         transition:background 0.15s,border-color 0.15s;">
      <div style="font-size:0.82em;color:var(--ink-soft);">
        &#128247; <strong>Add an image</strong> &mdash; tap to choose, drag &amp; drop, or paste a screenshot
      </div>
      <div style="font-size:0.72em;color:var(--ink-faint);margin-top:4px;">
        (handwritten notes, calendar screenshots, itineraries, etc.)
      </div>
      <input type="file" id="plan-image-input" accept="image/*" style="display:none;">
    </div>
    <div id="img-preview-wrap" style="display:none;margin-top:10px;padding:10px;
         background:#f0fdf4;border-radius:10px;border:1.5px solid #86efac;">
      <div style="display:flex;align-items:flex-start;gap:10px;">
        <img id="img-preview" alt="Attached image" style="max-width:120px;max-height:120px;
             border-radius:6px;border:1px solid #cbd5e1;object-fit:cover;">
        <div style="flex:1;font-size:0.8em;color:#166534;">
          <div style="font-weight:600;" id="img-preview-name">image attached</div>
          <div style="font-size:0.78em;color:var(--ink-soft);margin-top:2px;" id="img-preview-size"></div>
          <button type="button" onclick="clearPlanImage()" class="pi-btn pi-btn-sm"
                  style="margin-top:6px;background:#fee2e2;color:#991b1b;border:none;
                         padding:4px 10px;font-size:0.78em;border-radius:6px;cursor:pointer;">
            &#10005; Remove image
          </button>
        </div>
      </div>
    </div>

    <div style="margin-top:10px;display:flex;align-items:center;gap:10px;">
      <button class="pi-btn pi-btn-primary" id="analyze-btn" onclick="analyzePlan()">
        &#128269; Analyze Plan
      </button>
      <span style="font-size:0.75em;color:var(--ink-faint);">
        Claude will parse events, tasks, and flag any questions.
      </span>
    </div>
    <div id="paste-error" style="margin-top:8px;font-size:0.8em;color:var(--red);display:none;"></div>
  </div>

  <div style="font-size:0.72em;color:var(--ink-faint);padding:4px 4px;line-height:1.5;">
    &#128274; This tool only writes to your calendar and task lists when you click Apply.
    Everything is shown for your review and approval first. You can edit any item before applying.
  </div>
</div>
</div>

<!-- Phase 2: Thinking -->
<div id="phase-thinking" class="phase">
  <div class="thinking-spinner"></div>
  <div class="thinking-label" id="thinking-label">Analyzing your plan&hellip;</div>
</div>

<!-- Phase 3: Results -->
<div id="phase-results" class="phase">
<div class="pi-body">

  <!-- Restore banner (shown when session auto-restored) -->
  <div id="restore-banner" style="display:none;background:#f0fdf4;border:1px solid #86efac;
       border-radius:10px;padding:10px 14px;margin-bottom:10px;font-size:0.8em;
       color:#166534;align-items:center;gap:8px;flex-wrap:wrap;">
    <span>&#x1F7E2;</span>
    <span>Your previous plan was restored. Selections are intact — continue where you left off.</span>
    <button id="save-to-server-btn" onclick="saveSessionToServer()" style="margin-left:auto;background:#166534;
            color:#fff;border:none;border-radius:6px;padding:5px 10px;cursor:pointer;font-size:0.85em;font-weight:600;">
      &#128190; Save to server
    </button>
    <a href="/plan-import-history" style="color:#166534;text-decoration:underline;">Saved analyses</a>
    <button onclick="this.parentElement.style.display='none'" style="background:none;
            border:none;cursor:pointer;color:#166534;font-size:1.1em;line-height:1;">&#10005;</button>
  </div>

  <!-- Project label strip -->
  <div style="display:flex;align-items:center;gap:10px;padding:10px 14px;
       background:#fdf8f0;border-radius:10px;border:1.5px solid #e2e8f0;margin-bottom:10px;">
    <span style="font-size:0.8em;color:var(--ink-soft);white-space:nowrap;font-weight:600;">
      &#127991; Project label
    </span>
    <input type="text" id="project-label-input"
           placeholder="e.g. Soccer Season, Week 14, Spring Planning&hellip;"
           maxlength="60"
           style="flex:1;padding:7px 10px;border:1.5px solid #dbeafe;border-radius:8px;
                  font-family:inherit;font-size:0.82em;background:white;outline:none;">
    <span style="font-size:0.72em;color:var(--ink-faint);white-space:nowrap;">
      Stamps every item
    </span>
  </div>

  <!-- Questions -->
  <div id="section-questions" style="display:none;">
    <div class="pi-card">
      <div class="section-header">
        <span class="section-icon">&#10067;</span>
        <span class="section-title">Questions — needs clarification</span>
        <span class="section-count amber" id="q-count">0</span>
      </div>
      <p style="font-size:0.78em;color:var(--ink-soft);margin-bottom:12px;">
        Answer these to improve accuracy before applying, or leave blank to skip those items.
      </p>
      <div id="questions-list"></div>
      <button class="pi-btn pi-btn-primary" style="margin-top:4px;font-size:0.8em;padding:8px 18px;"
              onclick="reanalyzeWithAnswers()">
        &#8635; Re-analyze with my answers
      </button>
    </div>
  </div>

  <!-- Warnings & Suggestions -->
  <div id="section-warnings" style="display:none;">
    <div class="pi-card">
      <div class="section-header">
        <span class="section-icon">&#9888;&#65039;</span>
        <span class="section-title">Warnings &amp; Suggestions</span>
        <span class="section-count amber" id="ws-count">0</span>
      </div>
      <div id="warnings-list"></div>
      <div id="suggestions-list"></div>
    </div>
  </div>

  <!-- Placements (info to file onto existing records) -->
  <div id="section-placements" style="display:none;">
    <div class="pi-card">
      <div class="section-header">
        <span class="section-icon">&#128204;</span>
        <span class="section-title">Placements &mdash; info for existing records</span>
        <span class="section-count blue" id="placements-count">0</span>
      </div>
      <p style="font-size:0.78em;color:var(--ink-soft);margin-bottom:12px;">
        These pieces of info will be filed onto existing records (event notes, profiles, friends,
        pantry, etc.) instead of becoming new tasks or events.
      </p>
      <div id="placements-list"></div>
    </div>
  </div>

  <!-- Calendar Events -->
  <div id="section-events" style="display:none;">
    <div class="pi-card">
      <div class="section-header">
        <span class="section-icon">&#128197;</span>
        <span class="section-title">Calendar Events</span>
        <span class="section-count green" id="ev-count">0</span>
      </div>
      <div id="events-list"></div>
    </div>
  </div>

  <!-- Tasks -->
  <div id="section-tasks" style="display:none;">
    <div class="pi-card">
      <div class="section-header">
        <span class="section-icon">&#9989;</span>
        <span class="section-title">Tasks</span>
        <span class="section-count green" id="task-count">0</span>
      </div>
      <div id="tasks-list"></div>

      <!-- Inline add-task form (hidden until triggered) -->
      <div id="add-task-form" style="display:none;margin-top:12px;padding:14px;
           background:#f0f9f4;border-radius:10px;border:1.5px dashed #6ee7b7;">
        <div class="edit-grid">
          <div class="edit-field" style="grid-column:1/-1;">
            <label>Task description</label>
            <input type="text" id="new-task-text" placeholder="What needs to be done?">
          </div>
          <div class="edit-field">
            <label>Assigned to</label>
            <select id="new-task-person">
              <option>Lauren</option><option>John</option><option>JP</option>
              <option>Joseph</option><option>Michael</option><option>James</option>
            </select>
          </div>
          <div class="edit-field">
            <label>Due date</label>
            <input type="date" id="new-task-date">
          </div>
          <div class="edit-field" style="grid-column:1/-1;">
            <label>Notes <span style="font-weight:400;color:var(--ink-faint);">(optional)</span></label>
            <input type="text" id="new-task-notes" placeholder="">
          </div>
        </div>
        <div style="margin-top:10px;display:flex;gap:8px;justify-content:flex-end;">
          <button class="pi-btn pi-btn-sm" onclick="cancelAddTask()">Cancel</button>
          <button class="pi-btn pi-btn-sm pi-btn-primary" onclick="submitManualTask()">&#9989; Add Task</button>
        </div>
      </div>

      <div style="margin-top:10px;text-align:center;">
        <button id="show-add-task-btn" class="pi-btn pi-btn-sm pi-btn-edit"
                onclick="showAddTaskForm(null)"
                style="font-size:0.78em;">
          &#43; Add task manually
        </button>
      </div>
    </div>
  </div>

  <!-- No results fallback -->
  <div id="section-empty" style="display:none;">
    <div class="pi-card" style="text-align:center;padding:32px;">
      <div style="font-size:2em;margin-bottom:10px;">&#129300;</div>
      <div style="font-weight:700;margin-bottom:6px;">Nothing to parse</div>
      <div style="font-size:0.82em;color:var(--ink-soft);">
        The plan didn't contain any recognizable calendar events or tasks.
        Try including dates, times, and action items.
      </div>
      <button class="pi-btn pi-btn-primary" style="margin-top:16px;font-size:0.82em;"
              onclick="resetToPaste()">&#8592; Try again</button>
    </div>
  </div>

</div>

<!-- Companion Consultation Panel -->
<div id="consult-panel" style="display:none;margin-bottom:4px;">
  <div class="consult-card">
    <div class="consult-header">
      <div class="consult-title">&#129504; Get Expert Input</div>
      <div class="consult-subtitle">
        Ask all companions together for a group recommendation, or tap one for a 1-on-1 chat.
      </div>
    </div>

    <!-- Group Council -->
    <div class="council-section">
      <div class="council-title">&#x1F4AC; Group Council</div>
      <div class="council-presets" id="council-presets">
        <button class="council-preset" onclick="selectPreset(this,'Low capacity day \u2014 what should we simplify or cut?')">&#x1F33F; Low capacity day</button>
        <button class="council-preset" onclick="selectPreset(this,'We feel overwhelmed. What are the top things to drop or defer?')">&#x1F4A8; Overwhelmed</button>
        <button class="council-preset" onclick="selectPreset(this,'Quick check \u2014 anything missing or that we might regret skipping?')">&#x2705; Quick review</button>
        <button class="council-preset" onclick="selectPreset(this,'How does this plan fit our Catholic family rhythms and faith life?')">&#x271D;&#xFE0F; Faith check</button>
      </div>
      <div class="council-input-row">
        <input class="council-input" id="council-input" type="text"
               placeholder="Or describe your situation\u2026" />
        <button class="council-btn" id="council-btn" onclick="conveneCouncil()">Convene &#x2728;</button>
      </div>
      <div class="council-response" id="council-response">
        <div class="council-thread" id="council-thread"></div>
      </div>
    </div>

    <div class="companion-row" id="companion-row"></div>
    <div class="consult-chat-area" id="consult-chat-area" style="display:none;">
      <div class="consult-chat-header">
        <span id="consult-chat-emoji" style="font-size:1.3em;"></span>
        <span class="consult-chat-name" id="consult-chat-name"></span>
        <button class="consult-chat-close" onclick="closeConsultChat()" title="Close">&#10005;</button>
      </div>
      <div class="consult-messages" id="consult-messages"></div>
      <div class="consult-input-row">
        <input class="consult-input" id="consult-input" placeholder="Ask this companion\u2026"
               onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();consultSend();}}">
        <button class="consult-send" id="consult-send-btn" onclick="consultSend()">Send</button>
      </div>
    </div>
  </div>
</div>

<!-- Apply bar -->
<div class="apply-bar" id="apply-bar" style="display:none;">
  <div>
    <button class="pi-btn" style="background:var(--ink-faint);color:#fff;font-size:0.78em;padding:8px 16px;"
            onclick="resetToPaste()">&#8592; Start over</button>
  </div>
  <div style="text-align:right;">
    <div class="apply-summary" id="apply-summary"></div>
    <button class="pi-btn pi-btn-apply" style="margin-top:6px;" id="apply-btn" onclick="applyPlan()">
      &#9989; Apply Selected Items
    </button>
  </div>
</div>
</div>

<!-- Phase 4: Success -->
<div id="phase-success" class="phase">
<div class="pi-body">
  <div class="pi-card success-card">
    <div class="success-icon">&#127881;</div>
    <div class="success-title">Plan Applied</div>
    <div class="success-body" id="success-body"></div>
    <div style="display:flex;gap:10px;justify-content:center;margin-top:20px;flex-wrap:wrap;">
      <a href="/calendar" class="pi-btn pi-btn-primary" style="text-decoration:none;">
        &#128197; View Calendar
      </a>
      <a href="/today" class="pi-btn" style="background:var(--green);color:#fff;text-decoration:none;">
        &#9989; View Today
      </a>
      <button class="pi-btn" style="background:var(--ink-faint);color:#fff;"
              onclick="resetToPaste()">&#128203; Import Another</button>
    </div>
  </div>
</div>
</div>

<!-- Phase 4b: Receipt (added alongside phase-success — see Task #15) -->
<div id="phase-receipt" class="phase">
<div class="pi-body">
  <div class="receipt-card">
    <div class="receipt-banner">
      <div class="receipt-icon">&#127881;</div>
      <div>
        <div class="receipt-title">Plan Applied</div>
        <div class="receipt-summary" id="receipt-summary"></div>
      </div>
    </div>
    <div class="receipt-section" id="receipt-events-section">
      <div class="receipt-section-head">
        <span>&#128197; Events Added</span>
        <span class="receipt-section-count" id="receipt-events-count">0</span>
      </div>
      <div id="receipt-events-body"></div>
    </div>
    <div class="receipt-section" id="receipt-tasks-section">
      <div class="receipt-section-head">
        <span>&#9989; Tasks Added</span>
        <span class="receipt-section-count" id="receipt-tasks-count">0</span>
      </div>
      <div id="receipt-tasks-body"></div>
    </div>
    <div class="receipt-section" id="receipt-placements-section">
      <div class="receipt-section-head">
        <span>&#128221; Placements Filed</span>
        <span class="receipt-section-count" id="receipt-placements-count">0</span>
      </div>
      <div id="receipt-placements-body"></div>
    </div>
  </div>
  <div style="display:flex;gap:10px;justify-content:center;margin:0 16px 24px;flex-wrap:wrap;">
    <a href="/calendar" class="pi-btn pi-btn-primary" style="text-decoration:none;">
      &#128197; View Calendar
    </a>
    <a href="/today" class="pi-btn" style="background:var(--green);color:#fff;text-decoration:none;">
      &#9989; View Today
    </a>
    <button class="pi-btn" style="background:var(--ink-faint);color:#fff;"
            onclick="resetToPaste()">&#128203; Import Another</button>
  </div>
</div>
</div>

<script>
const TODAY_ISO = {json.dumps(iso)};
const TODAY_LABEL = {json.dumps(label)};
const FAMILY = {json.dumps(FAMILY_MEMBERS)};
</script>
<script src="/static/js/plan_importer_core.js"></script>
<script src="/static/js/plan_importer_consult.js"></script>
</body>
</html>"""
