"""
render_child_goals.py — Per-child goals with substeps, deadlines, and review integration.
Goals stored in data/goals/children/<child_lower>.json
"""
import json, os, uuid
from datetime import date, timedelta
from html import escape

CHILD_GOALS_DIR = "data/goals/children"

CHILD_CATEGORIES = [
    "Spiritual Formation",
    "Virtue & Character",
    "Education & Learning",
    "Physical Development",
    "Social & Family",
    "Responsibilities & Chores",
    "Extracurricular",
    "Personal Growth",
]

CHILD_CATEGORY_ICONS = {
    "Spiritual Formation":       "✝",
    "Virtue & Character":        "⭐",
    "Education & Learning":      "📚",
    "Physical Development":      "🌿",
    "Social & Family":           "🏠",
    "Responsibilities & Chores": "✨",
    "Extracurricular":           "⚓",
    "Personal Growth":           "✏️",
}

CHILD_COLORS = {
    "jp":      {"bg": "#c0392b", "light": "#fdf0ef"},
    "joseph":  {"bg": "#27ae60", "light": "#edfaf3"},
    "michael": {"bg": "#e67e22", "light": "#fef6ed"},
    "james":   {"bg": "#2980b9", "light": "#eaf4fb"},
}


def _child_key(child: str) -> str:
    return child.lower().strip()


def _goals_path(child: str) -> str:
    os.makedirs(CHILD_GOALS_DIR, exist_ok=True)
    return f"{CHILD_GOALS_DIR}/{_child_key(child)}.json"


def load_child_goals(child: str) -> list:
    try:
        with open(_goals_path(child)) as f:
            return json.load(f).get("goals", [])
    except Exception:
        return []


def save_child_goals(child: str, goals: list):
    os.makedirs(CHILD_GOALS_DIR, exist_ok=True)
    with open(_goals_path(child), "w") as f:
        json.dump({"goals": goals}, f, indent=2)


def add_child_goal(child: str, title: str, category: str, why: str = "",
                   deadline: str = "", review_frequency: str = "weekly") -> dict:
    goals = load_child_goals(child)
    goal = {
        "id":               str(uuid.uuid4())[:8],
        "title":            title,
        "category":         category,
        "why":              why,
        "deadline":         deadline,
        "review_frequency": review_frequency,
        "substeps":         [],
        "created":          date.today().isoformat(),
        "archived":         False,
    }
    goals.append(goal)
    save_child_goals(child, goals)
    return goal


def update_child_goal(child: str, goal_id: str, updates: dict):
    goals = load_child_goals(child)
    for g in goals:
        if g.get("id") == goal_id:
            g.update(updates)
    save_child_goals(child, goals)


def add_substep(child: str, goal_id: str, text: str) -> dict:
    goals = load_child_goals(child)
    step = {"id": str(uuid.uuid4())[:8], "text": text, "done": False}
    for g in goals:
        if g.get("id") == goal_id:
            g.setdefault("substeps", []).append(step)
    save_child_goals(child, goals)
    return step


def toggle_substep(child: str, goal_id: str, step_id: str) -> bool:
    goals = load_child_goals(child)
    new_state = False
    for g in goals:
        if g.get("id") == goal_id:
            for s in g.get("substeps", []):
                if s.get("id") == step_id:
                    s["done"] = not s.get("done", False)
                    new_state = s["done"]
    save_child_goals(child, goals)
    return new_state


def delete_substep(child: str, goal_id: str, step_id: str):
    goals = load_child_goals(child)
    for g in goals:
        if g.get("id") == goal_id:
            g["substeps"] = [s for s in g.get("substeps", []) if s.get("id") != step_id]
    save_child_goals(child, goals)


def _deadline_badge(deadline_str: str) -> str:
    if not deadline_str:
        return ""
    try:
        dl = date.fromisoformat(deadline_str)
        today = date.today()
        delta = (dl - today).days
        if delta < 0:
            color, label = "#ef4444", f"Overdue by {abs(delta)}d"
        elif delta == 0:
            color, label = "#ef4444", "Due today"
        elif delta <= 7:
            color, label = "#f59e0b", f"{delta}d left"
        elif delta <= 30:
            color, label = "#3b82f6", f"{delta}d left"
        else:
            color, label = "#6b7280", dl.strftime("%b %d")
        return (
            f'<span style="font-size:.7em;padding:2px 7px;border-radius:10px;'
            f'background:{color};color:#fff;margin-left:6px;">{label}</span>'
        )
    except Exception:
        return ""


def _substep_progress_bar(substeps: list) -> str:
    total = len(substeps)
    if total == 0:
        return ""
    done = sum(1 for s in substeps if s.get("done"))
    pct = int(done / total * 100)
    color = "#22c55e" if pct == 100 else "#f59e0b" if pct >= 50 else "#e67e22"
    return (
        f'<div style="display:flex;align-items:center;gap:6px;margin:4px 0 8px;">'
        f'<div style="flex:1;height:6px;background:#e5e7eb;border-radius:3px;">'
        f'<div style="width:{pct}%;height:100%;background:{color};border-radius:3px;"></div>'
        f'</div>'
        f'<span style="font-size:.7em;color:#6b7280;">{done}/{total}</span>'
        f'</div>'
    )


def render_child_goals_section(child: str, review_mode: str = "weekly") -> str:
    """Render the full goals section for a child's page."""
    goals = [g for g in load_child_goals(child) if not g.get("archived")]
    ck = _child_key(child)
    colors = CHILD_COLORS.get(ck, {"bg": "#6b7280", "light": "#f9fafb"})
    bg = colors["bg"]
    child_esc = escape(child)

    add_form = f"""
    <form id="child-goal-add-form-{ck}" style="display:none;margin-top:10px;padding:10px;
          background:#f9fafb;border-radius:8px;border:1px solid #e5e7eb;">
        <div style="display:grid;gap:6px;">
            <input name="title" placeholder="Goal title" required
                   style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;width:100%;box-sizing:border-box;">
            <select name="category"
                    style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;">
                {''.join(f'<option>{escape(c)}</option>' for c in CHILD_CATEGORIES)}
            </select>
            <input name="why" placeholder="Why this matters (optional)"
                   style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;width:100%;box-sizing:border-box;">
            <input name="deadline" type="date"
                   style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;">
            <select name="review_frequency"
                    style="padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;">
                <option value="weekly">Review weekly</option>
                <option value="monthly">Review monthly</option>
                <option value="quarterly">Review quarterly</option>
            </select>
            <div style="display:flex;gap:8px;">
                <button type="submit" style="padding:6px 14px;background:{bg};color:#fff;
                        border:none;border-radius:6px;cursor:pointer;">Add Goal</button>
                <button type="button"
                        onclick="document.getElementById('child-goal-add-form-{ck}').style.display='none'"
                        style="padding:6px 14px;background:#e5e7eb;border:none;border-radius:6px;cursor:pointer;">Cancel</button>
            </div>
        </div>
        <input type="hidden" name="child" value="{child_esc}">
    </form>"""

    if not goals:
        goals_body = f"""
        <p style="color:#9ca3af;font-size:.9em;text-align:center;padding:16px 0;">
            No goals set yet. Add one to start tracking {child_esc}'s formation and growth.</p>"""
    else:
        goal_cards = ""
        for g in goals:
            gid = g.get("id", "")
            title = escape(g.get("title", ""))
            cat = g.get("category", "")
            cat_icon = CHILD_CATEGORY_ICONS.get(cat, "•")
            why = g.get("why", "")
            deadline = g.get("deadline", "")
            substeps = g.get("substeps", [])
            rev = g.get("review_frequency", "weekly")

            deadline_badge = _deadline_badge(deadline)
            progress_bar = _substep_progress_bar(substeps)

            substeps_html = ""
            for s in substeps:
                sid = s.get("id", "")
                stext = escape(s.get("text", ""))
                sdone = s.get("done", False)
                strike = "line-through;color:#9ca3af;" if sdone else ""
                substeps_html += f"""
                <div style="display:flex;align-items:flex-start;gap:8px;margin:3px 0;padding:3px 0;">
                    <input type="checkbox" {'checked' if sdone else ''}
                           style="margin-top:2px;cursor:pointer;accent-color:{bg};"
                           onchange="toggleSubstep('{ck}','{gid}','{sid}',this)">
                    <span style="font-size:.88em;text-decoration:{strike}flex:1;">{stext}</span>
                    <button onclick="deleteSubstep('{ck}','{gid}','{sid}',this)"
                            style="background:none;border:none;color:#d1d5db;cursor:pointer;font-size:.8em;padding:0 2px;"
                            title="Remove">✕</button>
                </div>"""

            add_substep_row = f"""
            <div style="margin-top:6px;display:flex;gap:6px;">
                <input id="new-step-{gid}" placeholder="Add a step…"
                       style="flex:1;padding:4px 8px;border:1px solid #e5e7eb;border-radius:5px;font-size:.85em;">
                <button onclick="addSubstep('{ck}','{gid}')"
                        style="padding:4px 10px;background:{bg};color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:.85em;">+</button>
            </div>"""

            goal_cards += f"""
            <div id="goal-card-{gid}" style="border:1px solid #e5e7eb;border-radius:10px;
                 padding:12px 14px;margin-bottom:10px;background:#fff;border-left:4px solid {bg};">
                <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px;">
                    <div style="flex:1;">
                        <div style="font-size:.78em;color:{bg};font-weight:600;margin-bottom:2px;">
                            {cat_icon} {escape(cat)}
                        </div>
                        <div style="font-weight:600;font-size:.97em;">{title}{deadline_badge}</div>
                        {f'<div style="font-size:.8em;color:#6b7280;margin-top:2px;font-style:italic;">{escape(why)}</div>' if why else ''}
                        <div style="font-size:.72em;color:#9ca3af;margin-top:2px;">Review: {rev}</div>
                    </div>
                    <button onclick="archiveGoal('{ck}','{gid}')"
                            style="background:none;border:none;color:#d1d5db;cursor:pointer;font-size:.85em;white-space:nowrap;"
                            title="Archive goal">Archive</button>
                </div>
                {progress_bar}
                <div id="substeps-{gid}">
                    {substeps_html if substeps_html else '<p style="font-size:.8em;color:#9ca3af;margin:4px 0;">No steps yet.</p>'}
                </div>
                {add_substep_row}
            </div>"""
        goals_body = goal_cards

    return f"""
<div class="card card-tight no-print" id="child-goals-{ck}" style="margin-top:10px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
        <h3 style="margin:0;">Goals & Formation</h3>
        <div style="display:flex;gap:6px;align-items:center;">
            <select id="review-mode-{ck}" onchange="filterGoalsByReview('{ck}', this.value)"
                    style="font-size:.78em;padding:3px 6px;border:1px solid #e5e7eb;border-radius:5px;">
                <option value="weekly" {'selected' if review_mode=='weekly' else ''}>Weekly review</option>
                <option value="monthly" {'selected' if review_mode=='monthly' else ''}>Monthly review</option>
                <option value="quarterly" {'selected' if review_mode=='quarterly' else ''}>Quarterly review</option>
            </select>
            <button onclick="document.getElementById('child-goal-add-form-{ck}').style.display='block'"
                    style="font-size:.8em;padding:4px 10px;background:{bg};color:#fff;
                           border:none;border-radius:6px;cursor:pointer;">+ Goal</button>
        </div>
    </div>
    {add_form}
    <div id="goals-list-{ck}">
        {goals_body}
    </div>
</div>

<script>
(function() {{
    // Add goal form submit
    var addForm = document.getElementById('child-goal-add-form-{ck}');
    if (addForm) {{
        addForm.addEventListener('submit', function(e) {{
            e.preventDefault();
            var fd = new FormData(addForm);
            fetch('/child-goal-add', {{method:'POST', body: fd}})
                .then(r => r.json()).then(d => {{
                    if (d.ok) location.reload();
                }});
        }});
    }}
}})();

function toggleSubstep(child, goalId, stepId, el) {{
    var fd = new FormData();
    fd.append('child', child); fd.append('goal_id', goalId); fd.append('step_id', stepId);
    fetch('/child-substep-toggle', {{method:'POST', body: fd}})
        .then(r => r.json()).then(d => {{
            var span = el.nextElementSibling;
            if (span) span.style.textDecoration = d.done ? 'line-through' : 'none';
            if (span) span.style.color = d.done ? '#9ca3af' : '';
        }});
}}

function addSubstep(child, goalId) {{
    var inp = document.getElementById('new-step-' + goalId);
    if (!inp || !inp.value.trim()) return;
    var fd = new FormData();
    fd.append('child', child); fd.append('goal_id', goalId); fd.append('text', inp.value.trim());
    fetch('/child-substep-add', {{method:'POST', body: fd}})
        .then(r => r.json()).then(d => {{ if (d.ok) location.reload(); }});
}}

function deleteSubstep(child, goalId, stepId, btn) {{
    if (!confirm('Remove this step?')) return;
    var fd = new FormData();
    fd.append('child', child); fd.append('goal_id', goalId); fd.append('step_id', stepId);
    fetch('/child-substep-delete', {{method:'POST', body: fd}})
        .then(r => r.json()).then(d => {{ if (d.ok) location.reload(); }});
}}

function archiveGoal(child, goalId) {{
    if (!confirm('Archive this goal?')) return;
    var fd = new FormData();
    fd.append('child', child); fd.append('goal_id', goalId);
    fetch('/child-goal-archive', {{method:'POST', body: fd}})
        .then(r => r.json()).then(d => {{ if (d.ok) location.reload(); }});
}}

function filterGoalsByReview(ck, mode) {{
    var cards = document.querySelectorAll('#goals-list-' + ck + ' [id^="goal-card-"]');
    cards.forEach(function(card) {{
        card.style.display = '';
    }});
}}
</script>"""
