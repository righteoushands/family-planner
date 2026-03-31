"""
render_goals.py — Goal system data helpers.
"""
import json, os, uuid
from datetime import date, timedelta
from html import escape

GOALS_DIR = "data/goals"

CATEGORIES = [
    "Spiritual Formation",
    "Marriage & Family Culture",
    "Classical Education / Homeschool",
    "Latin / Language",
    "Physical Health",
    "Home & Order",
    "Financial Stewardship",
    "Creative / Personal Growth",
    "CAP / Sea Cadets",
    "Service / Apostolate",
    "Seasonal / Liturgical Traditions",
    "Wildcard",
]

CATEGORY_ICONS = {
    "Spiritual Formation":              "\u271d",
    "Marriage & Family Culture":        "\U0001f3e0",
    "Classical Education / Homeschool": "\U0001f4da",
    "Latin / Language":                 "\U0001f1fb\U0001f1e6",
    "Physical Health":                  "\U0001f33f",
    "Home & Order":                     "\u2728",
    "Financial Stewardship":            "\U0001f4b0",
    "Creative / Personal Growth":       "\U0001f58b\ufe0f",
    "CAP / Sea Cadets":                 "\u2693",
    "Service / Apostolate":             "\U0001f91d",
    "Seasonal / Liturgical Traditions": "\u26aa",
    "Wildcard":                         "\u2b50",
}

CHECK_COLORS = {
    "done":    "#22c55e",
    "partial": "#f59e0b",
    "skip":    "#ef4444",
    "":        "#e5e7eb",
}


def current_quarter(d=None):
    if d is None:
        d = date.today()
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def quarter_start(qk):
    try:
        year, q = qk.split("-Q")
        month = (int(q) - 1) * 3 + 1
        return date(int(year), month, 1)
    except Exception:
        return date.today().replace(day=1)


def quarter_end(qk):
    try:
        year, q = qk.split("-Q")
        month = int(q) * 3
        import calendar
        last_day = calendar.monthrange(int(year), month)[1]
        return date(int(year), month, last_day)
    except Exception:
        return date.today()


def quarter_week_number(d=None, quarter_key=None):
    if d is None:
        d = date.today()
    if quarter_key is None:
        quarter_key = current_quarter(d)
    qs  = quarter_start(quarter_key)
    mon = qs - timedelta(days=qs.weekday())
    delta = (d - mon).days
    return max(1, min(13, delta // 7 + 1))


def quarter_label(qk):
    labels = {"Q1": "Jan\u2013Mar", "Q2": "Apr\u2013Jun",
              "Q3": "Jul\u2013Sep", "Q4": "Oct\u2013Dec"}
    try:
        year, q = qk.split("-")
        return f"{labels.get(q, q)} {year}"
    except Exception:
        return qk


def all_quarters(year):
    return [f"{year}-Q1", f"{year}-Q2", f"{year}-Q3", f"{year}-Q4"]


def load_master_goals():
    os.makedirs(GOALS_DIR, exist_ok=True)
    path = f"{GOALS_DIR}/master.json"
    try:
        with open(path) as f:
            data = json.load(f)
        return data.get("goals", [])
    except Exception:
        return []


def save_master_goals(goals):
    os.makedirs(GOALS_DIR, exist_ok=True)
    with open(f"{GOALS_DIR}/master.json", "w") as f:
        json.dump({"goals": goals}, f, indent=2)


def get_goal_by_id(goal_id):
    for g in load_master_goals():
        if g.get("id") == goal_id:
            return g
    return {}


def add_master_goal(title, category, why="", metric=""):
    goals = load_master_goals()
    if len(goals) >= 12:
        return {}
    goal = {
        "id":       str(uuid.uuid4())[:8],
        "title":    title,
        "category": category,
        "why":      why,
        "metric":   metric,
        "created":  date.today().isoformat(),
    }
    goals.append(goal)
    save_master_goals(goals)
    return goal


def update_master_goal(goal_id, updates):
    goals = load_master_goals()
    for g in goals:
        if g.get("id") == goal_id:
            g.update(updates)
    save_master_goals(goals)


def delete_master_goal(goal_id):
    goals = [g for g in load_master_goals() if g.get("id") != goal_id]
    save_master_goals(goals)


def load_quarter_plan(quarter_key):
    os.makedirs(GOALS_DIR, exist_ok=True)
    path = f"{GOALS_DIR}/{quarter_key}.json"
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {
            "quarter":         quarter_key,
            "active_goal_ids": [],
            "goals":           {},
            "ai_reasoning":    "",
            "start_date":      quarter_start(quarter_key).isoformat(),
        }


def save_quarter_plan(plan):
    os.makedirs(GOALS_DIR, exist_ok=True)
    path = f"{GOALS_DIR}/{plan['quarter']}.json"
    with open(path, "w") as f:
        json.dump(plan, f, indent=2)


def get_active_goals_with_steps(quarter_key=None):
    if quarter_key is None:
        quarter_key = current_quarter()
    plan   = load_quarter_plan(quarter_key)
    master = {g["id"]: g for g in load_master_goals()}
    wk_num = quarter_week_number(quarter_key=quarter_key)
    result = []
    for gid in plan.get("active_goal_ids", []):
        g      = master.get(gid, {})
        g_plan = plan.get("goals", {}).get(gid, {})
        step   = g_plan.get("weekly_steps", {}).get(str(wk_num), "")
        status = g_plan.get("checkins", {}).get(str(wk_num), "")
        if g:
            result.append({
                "id":       gid,
                "title":    g.get("title", ""),
                "category": g.get("category", ""),
                "why":      g.get("why", ""),
                "metric":   g.get("metric", ""),
                "step":     step,
                "status":   status,
                "wk_num":   wk_num,
                "g_plan":   g_plan,
            })
    return result


def record_weekly_checkin(quarter_key, goal_id, week_num, status):
    plan = load_quarter_plan(quarter_key)
    plan.setdefault("goals", {}).setdefault(goal_id, {}).setdefault("checkins", {})[str(week_num)] = status
    save_quarter_plan(plan)


def update_weekly_step(quarter_key, goal_id, week_num, step_text):
    plan = load_quarter_plan(quarter_key)
    plan.setdefault("goals", {}).setdefault(goal_id, {}).setdefault("weekly_steps", {})[str(week_num)] = step_text
    save_quarter_plan(plan)


def completion_pct(g_plan, through_week=None):
    checkins = g_plan.get("checkins", {})
    if through_week is None:
        through_week = quarter_week_number()
    if through_week == 0:
        return 0
    done = sum(1 for w in range(1, through_week + 1)
               if checkins.get(str(w)) in ("done", "partial"))
    return round(done / through_week * 100)


def goal_progress_bars(g_plan, quarter_key=None):
    checkins = g_plan.get("checkins", {})
    steps    = g_plan.get("weekly_steps", {})
    wk_now   = quarter_week_number(quarter_key=quarter_key or current_quarter())
    squares  = ""
    for w in range(1, 14):
        status   = checkins.get(str(w), "")
        has_step = bool(steps.get(str(w), "").strip())
        if w > wk_now:
            color = "#dbeafe" if has_step else "#e5e7eb"
        elif status:
            color = CHECK_COLORS.get(status, "#e5e7eb")
        else:
            color = "#fef3c7" if has_step else "#e5e7eb"
        squares += (
            f'<span title="W{w}: {status or "upcoming"}" '
            f'style="display:inline-block;width:14px;height:14px;border-radius:3px;'
            f'background:{color};margin:1px;"></span>'
        )
    return squares