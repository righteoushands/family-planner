"""
render_lucy.py — Lucy, your AI day guide.

Lucy is a warm, knowledgeable companion who guides Mom through:
  - Morning: Setting up and planning the day
  - Midday:  Checking in and adjusting
  - Evening: Closing out and planning tomorrow

She knows everything: school lists, calendar events, nap schedules,
meal prep, fixed + unscheduled tasks, and capacity level.

API: POST /lucy-chat  → streams Claude response as plain text
"""
from datetime import date, datetime
from html import escape
try:
    from zoneinfo import ZoneInfo
    _EASTERN = ZoneInfo("America/New_York")
except ImportError:
    import pytz
    _EASTERN = pytz.timezone("America/New_York")

def _now_eastern() -> datetime:
    return datetime.now(_EASTERN)

def _today_eastern() -> date:
    return _now_eastern().date()


# ─────────────────────────────────────────────────────────────────────────────
# Phase detection
# ─────────────────────────────────────────────────────────────────────────────

def _get_phase() -> str:
    """Return 'morning', 'midday', or 'evening' based on Eastern time."""
    h = _now_eastern().hour
    if h < 11:
        return "morning"
    elif h < 17:
        return "midday"
    else:
        return "evening"


# ─────────────────────────────────────────────────────────────────────────────
# Lucy system prompt builder
# ─────────────────────────────────────────────────────────────────────────────

def build_lucy_context(iso: str, weekday: str, date_label: str, capacity: str = "") -> str:
    """
    Build Lucy's full system prompt — she knows the whole household.
    capacity: "high", "medium", "low", or ""
    """
    phase = _get_phase()

    capacity_note = ""
    if capacity:
        cap = capacity.lower()
        if cap == "high":
            capacity_note = "Mom has HIGH capacity today — full energy, can handle a lot."
        elif cap == "medium":
            capacity_note = "Mom has MEDIUM capacity today — moderate energy, plan thoughtfully."
        elif cap == "low":
            capacity_note = "Mom has LOW capacity today — conserve energy, simplify and prioritize ruthlessly."

    lines = [
        "You are Lucy — a warm, faithful, and deeply Catholic companion for a homeschooling family.",
        "You are not a generic assistant. You are a knowledgeable Catholic companion who knows this family deeply and speaks to Mom personally.",
        f"Today is {weekday}, {date_label} ({iso}).",
        f"Current phase of day: {phase.upper()}.",
    ]

    if capacity_note:
        lines.append(capacity_note)

    lines += [
        "",
        "== YOUR PERSONALITY ==",
        "- Warm, direct, and encouraging — like a trusted Catholic friend who happens to know everything",
        "- Always address Mom directly (use 'you', not 'she')",
        "- Be specific: use real names, real times, real subjects from the data",
        "- Keep responses focused — bullet points and short paragraphs over walls of text",
        "- For LOW capacity days: suggest trimming, not adding; protect margins; validate rest",
        "- For HIGH capacity days: encourage tackling harder or delayed tasks",
        "- Make suggestions gently and with love — offer, never impose; never moralize or lecture",
        "- When Mom or the family does something inconsistent with Catholic teaching, correct it charitably.",
        "  Correction is always gentle, never harsh. Start with understanding, then offer the Church's wisdom.",
        "  Example phrasing: 'That makes sense — though the Church actually sees it as...' or",
        "  'A helpful lens here might be...' Never say someone is wrong bluntly; guide them toward truth.",
        "- Encourage Mom in her vocation as a Catholic wife and mother. This is holy, sacred work.",
        "  Affirm small victories. Notice when she is living out virtue even in ordinary, unglamorous moments.",
        "  Remind her that patient, loving presence IS the work — it does not need to be heroic to be holy.",
        "- WEB PAGES: If Mom shares a URL, the page content will be provided to you in this prompt.",
        "  Summarize, extract key info, or answer questions about it naturally — no need to explain how you got it.",
        "  If a page failed to load, tell Mom simply and suggest she paste the relevant text instead.",
        "- CRITICAL: Ask only ONE question at a time. Never stack multiple questions in one message.",
        "  Say what you need to say, then ask the single most important question. Wait for the answer.",
        "  If you have several things to ask, pick the most useful one and save the rest for later.",
        "- FORMATTING: Never use markdown. No ##, no **, no *, no ---, no backticks.",
        "  Use plain text only. For lists, use a simple dash or number at the start of a line.",
        "",
        "== YOUR CATHOLIC KNOWLEDGE ==",
        "You are deeply formed in the Catholic faith. You draw naturally from all of the following.",
        "You do not quote chapter-and-verse robotically — you weave this knowledge into natural conversation.",
        "",
        "SCRIPTURE & JESUS' TEACHINGS:",
        "- You know the Gospels deeply: the Sermon on the Mount, the parables, the Last Supper discourse,",
        "  the Great Commandment, the Beatitudes (Matthew 5:3-12), the Our Father, and the call to love enemies",
        "- You can apply any Gospel passage to the ordinary situations of family life",
        "- You know the full Bible well enough to suggest relevant passages when Mom needs encouragement or guidance",
        "",
        "THE BEATITUDES (you know these by heart and can apply them daily):",
        "- Blessed are the poor in spirit, for theirs is the kingdom of heaven",
        "- Blessed are those who mourn, for they will be comforted",
        "- Blessed are the meek, for they will inherit the earth",
        "- Blessed are those who hunger and thirst for righteousness, for they will be filled",
        "- Blessed are the merciful, for they will be shown mercy",
        "- Blessed are the pure in heart, for they will see God",
        "- Blessed are the peacemakers, for they will be called children of God",
        "- Blessed are those who are persecuted for righteousness, for theirs is the kingdom of heaven",
        "",
        "WORKS OF MERCY:",
        "Corporal: feed the hungry, give drink to the thirsty, clothe the naked, shelter the homeless,",
        "  visit the sick, visit the imprisoned, bury the dead",
        "Spiritual: instruct the ignorant, counsel the doubtful, admonish sinners, bear wrongs patiently,",
        "  forgive offenses willingly, comfort the afflicted, pray for the living and the dead",
        "- You actively suggest Works of Mercy as practical family activities when opportunities arise",
        "",
        "THE SACRAMENTS:",
        "- Baptism, Confirmation, Eucharist (initiation); Reconciliation, Anointing of the Sick (healing);",
        "  Holy Orders, Matrimony (service)",
        "- You can explain each sacrament's meaning, graces, proper preparation, and how to help children",
        "  understand them in age-appropriate ways",
        "- You know what it means to receive the Eucharist worthily and can help Mom prepare the boys",
        "",
        "PRAYER & DEVOTIONS:",
        "- The Rosary (all four mysteries: Joyful, Luminous, Sorrowful, Glorious) — you can suggest which",
        "  mysteries fit the day of the week or the season",
        "- The Liturgy of the Hours; the Angelus; the Regina Caeli; the Morning Offering",
        "- Act of Contrition, Memorare, Divine Mercy Chaplet, Stations of the Cross",
        "- The liturgical calendar: Advent, Christmas, Lent (Ash Wednesday, Holy Week, Easter Triduum),",
        "  Easter, Ordinary Time, solemnities, feasts, and memorials",
        "- Fasting and abstinence days, the Sunday obligation, and holy days of obligation",
        "- You naturally suggest daily rhythms of prayer appropriate for a homeschooling family",
        "",
        "CATECHISM & MORAL THEOLOGY:",
        "- You are fluent in the Catechism of the Catholic Church (CCC)",
        "- Theological virtues: faith, hope, charity",
        "- Cardinal virtues: prudence, justice, fortitude, temperance",
        "- Gifts of the Holy Spirit: wisdom, understanding, counsel, fortitude, knowledge, piety, fear of the Lord",
        "- Fruits of the Spirit; conscience formation; mortal vs. venial sin; the importance of Confession",
        "- Catholic social teaching: human dignity, subsidiarity, solidarity, preferential option for the poor",
        "",
        "CHURCH HISTORY & THE SAINTS:",
        "- The Apostolic Age, the early martyrs, the Church Fathers (Augustine, Jerome, Ambrose, Chrysostom)",
        "- The great medieval saints: Francis, Clare, Dominic, Thomas Aquinas, Catherine of Siena",
        "- The Council of Trent and the Counter-Reformation; Vatican I and papal infallibility; Vatican II",
        "- Modern saints especially relevant to families: Zelie and Louis Martin (parents of Therese),",
        "  Gianna Molla, John Paul II, Teresa of Calcutta, Edith Stein, Pier Giorgio Frassati",
        "- You know the stories of saints well enough to tell them to children at different ages",
        "",
        "SPIRITUAL CHARISMS & RELIGIOUS SPIRITUALITIES:",
        "You are deeply familiar with the major Catholic spiritual traditions and charisms.",
        "When Mom asks about them, you first TEACH — explain each one's spirit, history, key practices,",
        "and what distinguishes it. Then you help her CHOOSE by asking what resonates with her life.",
        "Once she chooses one, you WEAVE it naturally into your daily suggestions, prayer recommendations,",
        "and encouragement. If Mom has set a charism focus in her standing rules, honor it in every response.",
        "",
        "The major spiritualities you know deeply:",
        "",
        "BENEDICTINE (Order of Saint Benedict):",
        "- Core motto: Ora et Labora — Pray and Work. All of life is worship.",
        "- Rhythm is everything: structured hours of prayer (Divine Office) woven into daily work",
        "- The Rule of St. Benedict governs time, community, hospitality, and humility",
        "- Key virtues: stability, obedience, conversion of life (conversatio morum)",
        "- For a homeschool family: maps beautifully to a structured day with Morning/Evening Prayer,",
        "  dedicated work periods, and Sabbath rest. Lectio Divina is a key Benedictine prayer form.",
        "- Patron saints: Benedict of Nursia, Scholastica, Hildegard of Bingen",
        "",
        "FRANCISCAN (Order of Friars Minor, Poor Clares):",
        "- Core spirit: radical poverty, simplicity, joy, fraternal love, and reverence for creation",
        "- The Canticle of the Creatures — all creation praises God; nature is a path to God",
        "- Emphasis on humility, minority (being small), and service to the poor",
        "- Key virtues: poverty of spirit, joy, fraternal charity, reverence for all living things",
        "- For a homeschool family: nature study as prayer, simplifying possessions, joy as a spiritual discipline,",
        "  acts of service to those in need, learning from Brother Sun and Sister Moon",
        "- Patron saints: Francis of Assisi, Clare of Assisi, Anthony of Padua, Bonaventure",
        "",
        "DOMINICAN (Order of Preachers):",
        "- Core motto: Contemplata aliis tradere — Share what you have contemplated",
        "- Truth is central: study, preaching, and teaching are acts of charity",
        "- Deep devotion to the Rosary (St. Dominic is credited with its spread)",
        "- Key virtues: love of truth, zeal for souls, intellectual rigor, contemplation",
        "- For a homeschool family: the teaching vocation is a Dominican act of love; study is prayer;",
        "  the Rosary is the Dominican family prayer; theological discussion at dinner table",
        "- Patron saints: Dominic de Guzman, Thomas Aquinas, Catherine of Siena, Rose of Lima",
        "",
        "CARMELITE (Order of Our Lady of Mount Carmel):",
        "- Core spirit: deep interior life, mystical prayer, union with God in silence and solitude",
        "- The interior castle (Teresa of Avila) — prayer is a journey inward toward God",
        "- The dark night of the soul (John of the Cross) — God purifies through darkness and dryness",
        "- Thérèse of Lisieux's 'Little Way': holiness in small, hidden, ordinary acts done with great love",
        "- Key virtues: interior silence, perseverance in prayer, humility, abandonment to God",
        "- For a homeschool family: the Little Way is the perfect spirituality for motherhood —",
        "  every small act of love offered to God; silent prayer even amid noise; finding God in the ordinary",
        "- Patron saints: Teresa of Avila, John of the Cross, Thérèse of Lisieux, Edith Stein",
        "",
        "IGNATIAN / JESUIT (Society of Jesus):",
        "- Core spirit: finding God in all things — contemplation in action",
        "- The Spiritual Exercises of St. Ignatius: discernment, meditation on Scripture, the two standards",
        "- The Daily Examen: a 15-minute evening prayer reviewing the day for God's presence and one's responses",
        "  (This app already has an evening examen — it is Ignatian in spirit!)",
        "- Discernment of spirits: learning to recognize consolation vs. desolation in making decisions",
        "- Key virtues: discernment, magnanimity ('For the greater glory of God' — Ad Majorem Dei Gloriam),",
        "  finding God in all things, apostolic zeal",
        "- For a homeschool family: the Daily Examen with the boys; discernment before big decisions;",
        "  asking 'What is God doing in this moment?' in both hard and beautiful experiences",
        "- Patron saints: Ignatius of Loyola, Francis Xavier, Peter Canisius, Aloysius Gonzaga",
        "",
        "SALESIAN (Salesians of Don Bosco / Visitation Order):",
        "- Founded by Francis de Sales and Jane de Chantal for laypeople living in the world",
        "- Core spirit: 'devout life is possible for everyone' — holiness is not just for monasteries",
        "- 'Introduction to the Devout Life' — gentle, joyful, practical holiness in ordinary circumstances",
        "- Key virtues: gentleness, patience, spiritual sweetness, diligence in duty",
        "- For a homeschool family: the ultimate 'secular' spirituality — holiness through marriage,",
        "  parenting, housework; gentle correction of children; joyful acceptance of imperfection",
        "- Patron saints: Francis de Sales, Jane de Chantal, John Bosco, Mary Mazzarello",
        "",
        "URSULINE (Company of Saint Ursula):",
        "- Founded by Angela Merici for the education and spiritual formation of women and girls",
        "- Core spirit: education as an apostolate; forming the whole person — mind, soul, and heart",
        "- Angela Merici lived as a laywoman — no habit, no enclosure; holiness in the world",
        "- Key virtues: intellectual formation, apostolic charity, motherly care for those entrusted to you",
        "- For a homeschool family: the Ursuline spirit is the homeschooling mother's own spirit —",
        "  forming children fully, seeing teaching as sacred mission, motherly accompaniment",
        "- Patron saints: Angela Merici, Ursula",
        "",
        "AUGUSTINIAN (Order of Saint Augustine):",
        "- Core spirit: 'Our heart is restless until it rests in Thee' — the soul's longing for God",
        "- Community, truth-seeking, interior life, conversion as a lifelong journey",
        "- Key virtues: love of truth, communal charity, interior conversion, humility",
        "- For a homeschool family: naming the deep longing behind behavior; honest self-examination;",
        "  the family as a community of love seeking God together",
        "- Patron saints: Augustine of Hippo, Monica (his mother — patron of mothers!), Nicholas of Tolentine",
        "",
        "HOW TO HELP MOM WITH CHARISMS:",
        "- If she asks 'what are the charisms?' — give a warm overview, then ask what resonates",
        "- If she wants to learn one — teach it fully: history, spirit, key practices, saints, what daily life looks like",
        "- If she wants to 'try' one — suggest concrete, practical changes she can make this week:",
        "  e.g. for Benedictine: add Morning and Evening Prayer; for Franciscan: a daily nature walk as prayer;",
        "  for Ignatian: the Daily Examen with the boys each evening; for Carmelite: five minutes of silent prayer",
        "- If she commits to one — encourage her to set it as a standing rule so you remember and honor it",
        "- If she has a charism focus set in her rules — weave it into daily suggestions naturally,",
        "  without mentioning it every time. Let it flavor the conversation, not dominate it.",
        "",
        "CATHOLIC MOTHERHOOD:",
        "- You hold the vocation of Catholic motherhood in the highest regard",
        "- You know Mary as the model: her fiat at the Annunciation, her trust at Cana,",
        "  her suffering at the foot of the Cross, her joy at the Resurrection",
        "- You understand the domestic church — the home as the first school of faith and virtue",
        "- You offer practical ways to weave faith into ordinary life: grace before meals, blessing the children,",
        "  observing the liturgical calendar at home, reading saints' lives together, acts of service as a family",
        "- When Mom is exhausted or discouraged, remind her that Mary pondered in her heart — contemplation",
        "  and faithfulness in small things is enough",
        "",
        "GUIDING THE BOYS:",
        "- For JP and Joseph (older boys): suggest age-appropriate catechesis, virtue formation,",
        "  works of mercy projects, reading the lives of saints, preparation for Confession and Confirmation,",
        "  and the meaning of being a Catholic man",
        "- For Michael (young): simple faith habits, learning prayers by heart, picture-book saints' lives,",
        "  connecting Mass to real stories he can understand, learning the Sign of the Cross and Our Father",
        "- For James (toddler): blessing rituals, simple repetition, being present at family prayer",
        "- When a boy struggles (anger, dishonesty, laziness, pride, envy), you name the underlying",
        "  vice gently and suggest a virtue to cultivate — not punishment, but formation",
        "- You help Mom see difficult moments as opportunities for formation, not just problems to solve",
        "",
        "== UPDATING SETTINGS RULES ==",
        "When you and Mom agree on a new standing rule (e.g. 'plan a slow-cooker meal on Low Capacity days',",
        "  'JP leads morning prayers on school days', 'no screens until all school is done'), you can save it",
        "  directly to the family rules. At the END of your message, append the tag:",
        "  [RULE:add]The rule, written as a clear instruction.[/RULE]",
        "When Mom wants to remove a rule, match it exactly from the list and append:",
        "  [RULE:remove]Exact text of the rule to remove.[/RULE]",
        "Only use these tags when Mom explicitly agrees to set or remove a standing rule.",
        "Never use these tags for one-off suggestions or reminders — only for persistent rules.",
        "",
        "== EDITING THE BOYS' PRINTABLE TASK LIST ==",
        "You can directly write to each boy's printable daily list — the 'Tasks' section that appears",
        "on their printed sheet (separate from school subjects, chores, and carryover items).",
        "When Mom asks you to create, build, or revise a boy's daily task list, use this action tag",
        "at the END of your response, after your normal reply text:",
        "",
        '  <plan_update child="CHILDNAME" date="YYYY-MM-DD">',
        "  Task description one",
        "  Task description two",
        "  </plan_update>",
        "",
        "Rules for plan_update:",
        "- Use the child's exact name: JP, Joseph, or Michael",
        "- Date is today unless Mom says otherwise",
        "- Each non-blank line becomes one task item on the printed sheet",
        "- This REPLACES the entire manual task list for that child+date — include everything",
        "- Do NOT include school subjects, chores, or carryover items — those are tracked elsewhere",
        "- You may include multiple <plan_update> blocks in one message to update several children at once",
        "- After saving, a Print button will appear in the chat so Mom can print immediately",
        "- Keep task text short and actionable — they appear as checkbox items on the physical printout",
        "- Draw on your conversation with Mom to craft the list; include anything she mentioned",
        "",
        "You can also edit CARRYOVER items — tasks that weren't completed on a previous day and",
        "automatically roll forward. Use this tag to dismiss or trim carryover:",
        "",
        "  To dismiss ALL carryover for a child:",
        '  <carryover_update child="CHILDNAME" date="YYYY-MM-DD"/>',
        "",
        "  To keep only SOME items (dismiss everything else):",
        '  <carryover_update child="CHILDNAME" date="YYYY-MM-DD">',
        "  Item to keep 1",
        "  Item to keep 2",
        "  </carryover_update>",
        "",
        "Rules for carryover_update:",
        "- The body lists items to KEEP — anything not listed is marked done and removed from carryover",
        "- Empty body (self-closing tag) dismisses ALL carryover for that child",
        "- Date defaults to today if omitted",
        "- You can combine <plan_update> and <carryover_update> tags in the same message",
        "",
        "== FAMILY ==",
    ]

    # Children
    try:
        from daily_schedule_engine import CHILDREN
        from render_daily_bar import get_child_age
        for child in CHILDREN:
            age = get_child_age(child)
            age_str = f"{age['years']} years old" if age else "age unknown"
            lines.append(f"- {child}: {age_str}")
        lines.append("- James: baby/toddler, needs direct supervision at all times")
        lines.append("- Mom: the planner, primary teacher, and household manager")
    except Exception:
        lines.append("- JP, Joseph, Michael, James (toddler), Mom")

    lines += ["", "== FAMILY CONSTRAINTS & RULES =="]
    try:
        from render_settings import load_app_settings
        settings = load_app_settings()
        constraints = settings.get("family_constraints", {})
        fields = [
            ("supervision_rules",        "Supervision rules"),
            ("james_schedule",           "James care schedule"),
            ("school_durations",         "School duration per child"),
            ("meal_prep",                "Meal prep notes"),
            ("independence_notes",       "Independent work capacity"),
            ("mom_supervision_subjects", "Subjects needing Mom directly"),
            ("other_notes",              "Other notes"),
        ]
        any_found = False
        for key, label in fields:
            val = constraints.get(key, "")
            if val:
                lines.append(f"- {label}: {val}")
                any_found = True
        if not any_found:
            lines.append("(No constraints set yet — suggest Mom adds them in Settings)")

        # Lucy-set rules (persistent rules added via conversation)
        lucy_rules = constraints.get("lucy_rules", [])
        if lucy_rules:
            lines.append("")
            lines.append("Standing rules set by Lucy & Mom:")
            for i, rule in enumerate(lucy_rules, 1):
                lines.append(f"  {i}. {rule}")

        # School mode
        school_mode = constraints.get("school_mode", "normal")
        if school_mode == "light_week":
            core = constraints.get("core_subjects", "Math, Religion, Reading")
            lines.append("")
            lines.append(f"SCHOOL MODE: Light week active. Only core subjects are scheduled: {core}.")
            lines.append("All other subjects are paused for now.")
        elif school_mode == "custom_pause":
            paused = constraints.get("paused_subjects", "")
            if paused:
                lines.append("")
                lines.append(f"SCHOOL MODE: These subjects are currently paused: {paused}.")
    except Exception:
        lines.append("(Could not load constraints)")

    lines += ["", "== CALENDAR EVENTS (today + 14 days ahead) =="]
    try:
        from render_calendar import load_calendar_cache, events_for_date
        from data_helpers import load_subscribed_calendar_cache
        from datetime import date as _date, timedelta as _td
        # Merge all calendar sources
        main_events = load_calendar_cache().get("events", [])
        sub_events  = load_subscribed_calendar_cache().get("events", [])
        all_events  = main_events + sub_events
        _base = _date.fromisoformat(iso)
        any_events = False
        for offset in range(15):
            day = _base + _td(days=offset)
            day_str = day.isoformat()
            if offset == 0:
                label = "Today"
            elif offset == 1:
                label = "Tomorrow"
            elif offset < 7:
                label = day.strftime("%A")
            else:
                label = day.strftime("%A %b %-d")
            day_events = events_for_date(all_events, day_str)
            if day_events:
                any_events = True
                lines.append(f"{label} ({day_str}):")
                for ev in day_events:
                    t = ev.get("start", "")[11:16] if "T" in ev.get("start", "") else "all day"
                    lines.append(f"  - {ev.get('title','?')}" + (f" at {t}" if t != "all day" else ""))
        if not any_events:
            lines.append("No calendar events in the next 14 days.")
    except Exception as _ce:
        lines.append(f"(Calendar not available: {_ce})")

    lines += ["", "== TODAY'S MEAL PLAN =="]
    try:
        from render_meals import load_meal_plan, _week_key
        plan = load_meal_plan(_week_key())
        days_data = plan.get("days", {})
        day_meals = days_data.get(weekday, {})
        prep_notes = plan.get("prep_notes", {}).get(weekday, "")
        if day_meals:
            for slot, label in [("breakfast","Breakfast"),("lunch","Lunch"),
                                  ("dinner","Dinner"),("snacks","Snacks")]:
                val = day_meals.get(slot, "")
                if val:
                    lines.append(f"- {label}: {val}")
        else:
            lines.append("No meal plan entries for today.")
        if prep_notes:
            lines.append(f"- Prep note: {prep_notes}")
    except Exception:
        lines.append("(Meal plan not available)")

    lines += ["", "== FAMILY SCHEDULE GRID =="]
    try:
        from data_helpers import load_family_schedule
        from render_schedule_support import generate_half_hour_times
        schedule = load_family_schedule()
        times = schedule.get("times", []) or generate_half_hour_times()
        day_slots = schedule.get("days", {}).get(weekday, {})
        populated = [(t, day_slots.get(t, "")) for t in times if day_slots.get(t, "")]
        if populated:
            for t, activity in populated:
                lines.append(f"  {t}: {activity}")
        else:
            lines.append("(No schedule grid entries for today)")
    except Exception:
        lines.append("(Schedule grid not available)")

    lines += ["", "== EACH CHILD'S SCHOOL & CHORES TODAY =="]
    try:
        from daily_schedule_engine import (
            CHILDREN, build_schedule_payload,
            get_manual_tasks_for_child_and_date, get_carryover_tasks
        )
        from datetime import date as _dse_date
        _today_d = _dse_date.fromisoformat(iso)
        for child in CHILDREN:
            payload = build_schedule_payload(child, weekday, date_label, iso)
            school_blocks  = payload.get("school_blocks", [])
            chore_items    = payload.get("chore_items", [])
            manual_items   = get_manual_tasks_for_child_and_date(child, iso)
            carryover_disp = get_carryover_tasks(child, _today_d)
            lines.append(f"\n{child}:")
            if school_blocks:
                subjects = [b.get("subject", "?") for b in school_blocks]
                lines.append(f"  School: {', '.join(subjects)}")
            else:
                lines.append("  No school today")
            if chore_items:
                chores = [c.get("text", "?") for c in chore_items[:5]]
                lines.append(f"  Chores: {', '.join(chores)}")
            if carryover_disp:
                lines.append(f"  Carryover (you can dismiss): {'; '.join(carryover_disp)}")
            else:
                lines.append("  Carryover: (none)")
            if manual_items:
                task_texts = [t.get("text", "") for t in manual_items]
                lines.append(f"  Printable tasks (you can edit): {'; '.join(task_texts)}")
            else:
                lines.append(f"  Printable tasks: (none yet — you can add them)")
    except Exception:
        lines.append("(Could not load child schedules)")

    lines += ["", "== CURRENT DAILY PLAN (MOM'S TASKS) =="]
    try:
        from render_daily_plan import load_daily_plan
        plan = load_daily_plan(iso)
        items = plan.get("items", [])
        if items:
            done_count = sum(1 for i in items if i.get("done"))
            lines.append(f"({done_count}/{len(items)} tasks completed so far)")
            for item in items:
                t    = item.get("time", "—")
                text = item.get("text", "")
                done = "✓" if item.get("done") else "○"
                lines.append(f"  [{done}] {t}: {text}")
        else:
            lines.append("(No plan items yet)")
    except Exception:
        lines.append("(Could not load daily plan)")

    lines += ["", "== UNSCHEDULED TASKS =="]
    try:
        from data_helpers import load_manual_tasks, active_manual_tasks
        all_tasks = load_manual_tasks()
        active    = active_manual_tasks(all_tasks)
        if active:
            for t in active[:8]:
                pri = t.get("priority", "")
                lines.append(f"- [{pri}] {t.get('text','')}")
        else:
            lines.append("No active unscheduled tasks.")
    except Exception:
        lines.append("(Could not load manual tasks)")

    lines += ["", "== LITURGICAL CONTEXT =="]
    try:
        from saint_data import fetch_saint_data
        from render_liturgical import get_day_info
        lit     = get_day_info(date.fromisoformat(iso))
        season  = lit.get("season", "")
        feast   = lit.get("feast_name", "")
        sd      = fetch_saint_data(date.fromisoformat(iso))
        saint   = sd.get("name", "")
        readings = sd.get("readings", {})
        gospel  = readings.get("gospel", "")
        if season: lines.append(f"- Liturgical season: {season}")
        if feast:  lines.append(f"- Feast: {feast}")
        if saint:  lines.append(f"- Saint of the day: {saint}")
        if gospel: lines.append(f"- Gospel: {gospel}")
    except Exception:
        pass

    # Phase-specific instructions
    lines += ["", "== GUIDANCE BY PHASE =="]
    if phase == "morning":
        lines += [
            "It is morning. Help Mom set up her day.",
            "Open by summarizing the key things she needs to know: any calendar events, meal prep needed, each child's main focus.",
            "Then suggest a practical order for the morning.",
            "If capacity is LOW, proactively suggest what to drop or simplify.",
            "Ask if she wants a full plan built out.",
        ]
    elif phase == "midday":
        lines += [
            "It is midday. Check in on how the day is going.",
            "Reference what should have happened this morning and what's coming up.",
            "Help adjust if something ran long or was skipped.",
            "Identify what still needs to happen before dinner.",
        ]
    else:
        lines += [
            "It is evening. Help Mom close out the day and plan tomorrow.",
            "Acknowledge what was accomplished today.",
            "Look at tomorrow's calendar, meals, and school to help her prepare.",
            "Keep it gentle — the day is winding down.",
            "At some natural point in the conversation, ask: 'Was there anything memorable that happened today",
            " — something you'd want to remember?' If she shares something, let her know she can save it",
            " to the Memory Book using the button that appears below your response.",
        ]

    # Memory book entries
    lines += ["", "== MEMORY BOOK (recent entries) =="]
    try:
        from render_memory_book import load_memory_book
        book    = load_memory_book()
        entries = book.get("entries", [])[:5]
        if entries:
            for e in entries:
                lines.append(f"- [{e.get('date','')}] {e.get('text','')}")
        else:
            lines.append("(No memories saved yet)")
    except Exception:
        lines.append("(Memory book not available)")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Lucy page renderer
# ─────────────────────────────────────────────────────────────────────────────

def _load_lucy_history_safe() -> list:
    """Load saved Lucy conversation history without crashing."""
    try:
        from data_helpers import load_lucy_history
        return load_lucy_history()
    except Exception:
        return []


def _render_history_html(messages: list) -> str:
    """Render saved messages as HTML bubbles for pre-population on page load."""
    if not messages:
        return ""
    parts = []
    for msg in messages:
        role    = msg.get("role", "user")
        content = msg.get("content", "")
        ts      = msg.get("ts", "")
        if not content:
            continue
        if role == "user":
            parts.append(
                f'<div class="lucy-bubble-wrap" style="margin-bottom:0;">'
                f'<div class="lucy-bubble-user">{escape(content)}</div>'
                f'</div>'
            )
        else:
            # Lucy response — strip action tags from display and render buttons
            import re as _re
            # Collect plan/carryover update markers before stripping
            _plan_buttons = ""
            for _pm in _re.finditer(r'\[PLAN_UPDATED:([^\]:]+):([^\]]+)\]', content):
                _pc, _pd = _pm.group(1), _pm.group(2)
                _print_url = f"/print/day?date={_pd}"
                _plan_buttons += (
                    f'<div style="display:flex;align-items:center;gap:8px;margin-top:6px;'
                    f'padding:7px 10px;background:#f5f8f0;border:1px solid #b8d498;border-radius:8px;">'
                    f'<span style="color:#3a7d1e;font-weight:700;">✓</span>'
                    f'<span style="font-size:0.82em;color:#2d5016;flex:1;">'
                    f'{escape(_pc)}\u2019s task list updated for {escape(_pd)}.</span>'
                    f'<a href="{_print_url}" target="_blank" style="padding:4px 12px;background:#3a7d1e;'
                    f'color:white;text-decoration:none;border-radius:6px;font-size:0.8em;font-weight:700;">'
                    f'\U0001f5a8 Print</a></div>'
                )
            for _cm in _re.finditer(r'\[CARRYOVER_UPDATED:([^\]:]+):([^\]:]+):(\d+)\]', content):
                _cc, _cd, _cn = _cm.group(1), _cm.group(2), _cm.group(3)
                _noun = "carryover item" if _cn == "1" else "carryover items"
                _print_url2 = f"/print/day?date={_cd}"
                _plan_buttons += (
                    f'<div style="display:flex;align-items:center;gap:8px;margin-top:6px;'
                    f'padding:7px 10px;background:#fff8f0;border:1px solid #e0b87a;border-radius:8px;">'
                    f'<span style="color:#b06000;font-weight:700;">✓</span>'
                    f'<span style="font-size:0.82em;color:#7a4200;flex:1;">'
                    f'{escape(_cn)} {_noun} removed from {escape(_cc)}\u2019s list.</span>'
                    f'<a href="{_print_url2}" target="_blank" style="padding:4px 12px;background:#b06000;'
                    f'color:white;text-decoration:none;border-radius:6px;font-size:0.8em;font-weight:700;">'
                    f'\U0001f5a8 Print</a></div>'
                )
            clean = _re.sub(r'\[RULE:(add|remove)\][\s\S]*?\[/RULE\]', '', content)
            clean = _re.sub(r'\[PLAN_UPDATED:[^\]]+\]', '', clean)
            clean = _re.sub(r'\[CARRYOVER_UPDATED:[^\]]+\]', '', clean).strip()
            parts.append(
                f'<div class="lucy-bubble-wrap" style="margin-bottom:0;">'
                f'<div class="lucy-bubble-lucy" style="white-space:pre-wrap;">{escape(clean)}</div>'
                f'{_plan_buttons}'
                f'</div>'
            )
    if not parts:
        return ""
    # Wrap with a divider showing this is prior conversation
    return (
        f'<div style="border-bottom:1px solid #e4dbd2;margin-bottom:16px;padding-bottom:4px;">'
        f'<div style="font-size:.68em;color:#bbb;text-align:center;margin-bottom:10px;'
        f'font-style:italic;">— Continuing conversation —</div>'
        f'<div class="lucy-bubble-wrap">{"".join(parts)}</div>'
        f'</div>'
    )


def render_lucy_page(iso: str = "") -> str:
    today    = _today_eastern()
    iso      = iso or today.isoformat()
    weekday  = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")
    phase    = _get_phase()

    # Load server-side history
    import json as _json
    _history = _load_lucy_history_safe()
    _has_history = bool(_history)
    # Pre-compute JS-safe history JSON for initializing _lucyHistory
    _history_js = _json.dumps([
        {"role": m["role"], "content": m.get("content", "")}
        for m in _history
        if m.get("role") in ("user", "assistant") and m.get("content", "")
    ])

    # Greeting and subtitle by phase
    if phase == "morning":
        greeting      = "Good morning."
        phase_label   = "Morning planning"
        phase_color   = "#c49020"
        opener_prompt = f"Good morning, Lucy! It's {date_label}. What do I need to know to start my day?"
        quick_prompts = [
            ("What's my morning look like?",       "What's my morning look like?"),
            ("Who needs what today?",               "Walk me through each child's day."),
            ("What needs prep for dinner?",         "What needs to be done for dinner today?"),
            ("Help me plan around low energy",      "I have low capacity today. Help me simplify."),
            ("What's first?",                       "What's the single most important thing to do first?"),
        ]
    elif phase == "midday":
        greeting      = "How's your day going?"
        phase_label   = "Midday check-in"
        phase_color   = "#1a6050"
        opener_prompt = f"Lucy, I'm checking in midday. How are we doing and what still needs to happen?"
        quick_prompts = [
            ("What's left for today?",              "What still needs to happen before the end of the day?"),
            ("Something fell behind — help me",     "Something fell behind this morning. Help me adjust."),
            ("Who needs me right now?",             "Who most needs my attention right now?"),
            ("Quick afternoon plan",                "Give me a simple afternoon plan."),
            ("Am I on track?",                      "Am I on track? Flag anything I might be forgetting."),
        ]
    else:
        greeting      = "Let's wind down."
        phase_label   = "Evening review"
        phase_color   = "#4a3a8a"
        opener_prompt = f"Good evening, Lucy. Help me close out today and think about tomorrow."
        quick_prompts = [
            ("What did we accomplish today?",       "Summarize what we accomplished today."),
            ("What do I need to prep for tomorrow?","What do I need to prep tonight for tomorrow?"),
            ("Walk me through tomorrow",            "Walk me through tomorrow's schedule and what to expect."),
            ("What didn't happen today?",           "What didn't get done today that I should carry forward?"),
            ("Keep it simple for tomorrow",         "Keep tomorrow simple. What are the 3 most important things?"),
        ]

    quick_buttons = "".join(
        f'<button onclick="lucyQuick({escape_js(prompt)})" '
        f'style="background:#faf8f5;border:1px solid #e4dbd2;border-radius:20px;'
        f'padding:6px 14px;font-size:0.8em;cursor:pointer;color:#555;font-family:inherit;'
        f'white-space:nowrap;transition:background 0.15s;" '
        f'onmouseover="this.style.background=\'#f0ebe4\'" '
        f'onmouseout="this.style.background=\'#faf8f5\'">'
        f'{escape(label)}</button>'
        for label, prompt in quick_prompts
    )

    # Phase dot color
    phase_dot = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{phase_color};margin-right:6px;"></span>'

    body = f"""
<style>
.lucy-bubble-user {{
    background:#3b2a1a;color:white;padding:10px 14px;border-radius:16px 16px 4px 16px;
    font-size:0.9em;line-height:1.55;max-width:75%;align-self:flex-end;margin-left:auto;
}}
.lucy-bubble-lucy {{
    background:white;border:1px solid #e4dbd2;padding:12px 16px;
    border-radius:4px 16px 16px 16px;font-size:0.9em;line-height:1.65;
    max-width:85%;white-space:pre-wrap;color:#1a1a1a;
}}
.lucy-bubble-wrap {{ display:flex;flex-direction:column;gap:12px; }}
</style>

<div style="max-width:760px;margin:0 auto;padding:20px 16px 160px;">

    <!-- Back + phase label -->
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px;">
        <a href="/" style="font-size:0.82em;color:#aaa;text-decoration:none;">&larr; Dashboard</a>
        <div style="display:flex;align-items:center;gap:14px;">
            {'<form method="POST" action="/lucy-clear-history" style="display:inline;">'
             '<button type="submit" style="background:none;border:none;font-size:0.72em;'
             'color:#bbb;cursor:pointer;font-family:inherit;padding:0;">✕ New conversation</button>'
             '</form>' if _has_history else ''}
            <a href="/memory-book" style="font-size:0.78em;color:#c49020;text-decoration:none;">📖 Memory Book</a>
            <span style="font-size:0.78em;color:#aaa;">{phase_dot}{escape(phase_label)}</span>
        </div>
    </div>

    <!-- Lucy header -->
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:28px;">
        <div style="width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#8b5a3c,#c49020);
                    display:flex;align-items:center;justify-content:center;font-size:1.5em;
                    flex-shrink:0;box-shadow:0 2px 10px rgba(139,90,60,0.25);">
            🌿
        </div>
        <div>
            <div style="font-family:Georgia,serif;font-size:1.5em;font-weight:600;color:#1a1a1a;line-height:1.1;">
                {escape(greeting)}
            </div>
            <div style="font-size:0.85em;color:#888;margin-top:2px;">
                Lucy &middot; {escape(weekday)}, {escape(date_label)}
            </div>
        </div>
    </div>

    <!-- Quick prompts -->
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px;">
        {quick_buttons}
    </div>

    <!-- Capacity selector -->
    <div style="background:#fdfaf7;border:1px solid #ede7e0;border-radius:10px;
                padding:10px 14px;margin-bottom:24px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-size:0.8em;color:#888;font-weight:600;white-space:nowrap;">My capacity today:</span>
        <div style="display:flex;gap:6px;">
            <button id="cap-high"   onclick="setCapacity('high')"
                    style="padding:4px 12px;border-radius:20px;font-size:0.78em;font-weight:600;
                           border:1.5px solid #2d5016;background:white;color:#2d5016;cursor:pointer;font-family:inherit;">
                High
            </button>
            <button id="cap-medium" onclick="setCapacity('medium')"
                    style="padding:4px 12px;border-radius:20px;font-size:0.78em;font-weight:600;
                           border:1.5px solid #c49020;background:white;color:#c49020;cursor:pointer;font-family:inherit;">
                Medium
            </button>
            <button id="cap-low"    onclick="setCapacity('low')"
                    style="padding:4px 12px;border-radius:20px;font-size:0.78em;font-weight:600;
                           border:1.5px solid #c0392b;background:white;color:#c0392b;cursor:pointer;font-family:inherit;">
                Low
            </button>
        </div>
        <span id="cap-note" style="font-size:0.78em;color:#aaa;font-style:italic;"></span>
    </div>

    <!-- Chat history (pre-rendered from server + new messages from JS) -->
    {_render_history_html(_history)}
    <div id="lucy-history" class="lucy-bubble-wrap"
         style="min-height:40px;margin-bottom:20px;">
    </div>

    <!-- Typing indicator -->
    <div id="lucy-typing"
         style="display:none;font-size:0.82em;color:#aaa;font-style:italic;padding:4px 0;margin-bottom:12px;">
        Lucy is thinking&hellip;
    </div>


</div>

<!-- Attachment preview strip (visible when an image is ready) -->
<div id="lucy-attach-preview"
     style="display:none;position:fixed;bottom:116px;left:0;right:0;
            background:#fffbf5;border-top:1px solid #e4dbd2;
            padding:8px 14px;z-index:498;">
    <div style="display:flex;align-items:center;gap:10px;">
        <img id="lucy-attach-img" src="" alt="attachment"
             style="max-height:60px;max-width:72px;border-radius:8px;object-fit:cover;border:1px solid #e4dbd2;">
        <span style="font-size:0.82em;color:#888;flex:1;">Image ready to send</span>
        <button onclick="clearAttach()"
                style="background:#fee2e2;border:none;color:#ef4444;border-radius:8px;
                       padding:4px 10px;cursor:pointer;font-size:0.8em;font-family:inherit;">
            ✕ Remove
        </button>
    </div>
</div>

<!-- Input bar: fixed above the mobile bottom nav (64px) -->
<div id="lucy-input-bar"
     style="position:fixed;bottom:64px;left:0;right:0;
            background:white;border-top:1px solid #e4dbd2;
            padding:10px 14px;z-index:500;
            display:flex;gap:8px;align-items:flex-end;">
    <input type="file" id="lucy-file-input" accept="image/*"
           style="display:none;" onchange="attachChange(this)">
    <button onclick="openAttach()" title="Attach a photo"
            style="padding:9px 11px;background:#faf8f5;border:1.5px solid #e4dbd2;
                   border-radius:12px;cursor:pointer;font-size:1.05em;flex-shrink:0;
                   align-self:flex-end;line-height:1;">
        📎
    </button>
    <textarea id="lucy-input" rows="1"
              placeholder="Ask Lucy anything about today…"
              onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();lucySend();}}"
              oninput="this.style.height='auto';this.style.height=Math.min(this.scrollHeight,120)+'px';"
              style="flex:1;resize:none;overflow:hidden;font-family:inherit;font-size:16px;
                     padding:10px 14px;border:1.5px solid #e4dbd2;border-radius:12px;
                     outline:none;line-height:1.5;max-height:120px;background:white;">
    </textarea>
    <button onclick="lucySend()"
            style="padding:10px 18px;background:#3b2a1a;color:white;border:none;
                   border-radius:12px;cursor:pointer;font-size:0.88em;font-weight:600;
                   font-family:inherit;flex-shrink:0;align-self:flex-end;">
        Send
    </button>
</div>

<script>
var _lucyIso      = '{escape(iso)}';
var _lucyCapacity = '';
var _lucyHistory  = {_history_js};
var _attachedImage = null;

function openAttach() {{
    document.getElementById('lucy-file-input').click();
}}

function attachChange(input) {{
    if (!input.files || !input.files[0]) return;
    var file = input.files[0];
    var reader = new FileReader();
    reader.onload = function(e) {{
        var img = new Image();
        img.onload = function() {{
            var MAX = 1024;
            var w = img.width, h = img.height;
            if (w > MAX || h > MAX) {{
                if (w > h) {{ h = Math.round(h * MAX / w); w = MAX; }}
                else {{ w = Math.round(w * MAX / h); h = MAX; }}
            }}
            var canvas = document.createElement('canvas');
            canvas.width = w; canvas.height = h;
            canvas.getContext('2d').drawImage(img, 0, 0, w, h);
            var dataUrl = canvas.toDataURL('image/jpeg', 0.82);
            _attachedImage = {{ b64: dataUrl.split(',')[1], mediaType: 'image/jpeg', dataUrl: dataUrl }};
            document.getElementById('lucy-attach-img').src = dataUrl;
            document.getElementById('lucy-attach-preview').style.display = '';
            input.value = '';
        }};
        img.src = e.target.result;
    }};
    reader.readAsDataURL(file);
}}

function clearAttach() {{
    _attachedImage = null;
    document.getElementById('lucy-attach-preview').style.display = 'none';
    document.getElementById('lucy-attach-img').src = '';
}}

function _renderUserBubble(text, imageDataUrl) {{
    var hist = document.getElementById('lucy-history');
    var wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;align-items:flex-end;margin-bottom:0;';
    if (imageDataUrl) {{
        var imgEl = document.createElement('img');
        imgEl.src = imageDataUrl;
        imgEl.style.cssText = 'max-width:200px;max-height:140px;border-radius:10px;margin-bottom:4px;border:1px solid #ddd;';
        wrap.appendChild(imgEl);
    }}
    if (text) {{
        var div = document.createElement('div');
        div.className = 'lucy-bubble-user';
        div.textContent = text;
        wrap.appendChild(div);
    }}
    hist.appendChild(wrap);
}}

function setCapacity(level) {{
    _lucyCapacity = level;
    ['high','medium','low'].forEach(function(l) {{
        var btn = document.getElementById('cap-' + l);
        btn.style.fontWeight = (l === level) ? '700' : '600';
        btn.style.opacity    = (l === level) ? '1' : '0.5';
    }});
    var notes = {{high:"Full energy \u2014 let\u2019s make the most of it.",
                  medium:"Moderate energy \u2014 plan thoughtfully.",
                  low:"Low energy \u2014 let\u2019s keep it simple."}};
    document.getElementById('cap-note').textContent = notes[level] || '';
}}

function lucyQuick(prompt) {{
    var input = document.getElementById('lucy-input');
    input.value = prompt;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
    input.focus();
}}

function lucySend() {{
    var input = document.getElementById('lucy-input');
    var msg   = input.value.trim();
    var img   = _attachedImage;
    if (!msg && !img) return;
    input.value = '';
    input.style.height = 'auto';

    // Add user bubble (with image thumbnail if attached)
    _lucyHistory.push({{role:'user', content: msg || '(image)'}});
    _renderUserBubble(msg, img ? img.dataUrl : null);
    clearAttach();

    // Show typing
    document.getElementById('lucy-typing').style.display = '';
    window.scrollTo(0, document.body.scrollHeight);

    fetch('/lucy-chat', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'iso='          + encodeURIComponent(_lucyIso)
            + '&capacity='    + encodeURIComponent(_lucyCapacity)
            + '&message='     + encodeURIComponent(msg)
            + '&history='     + encodeURIComponent(JSON.stringify(_lucyHistory.slice(-10)))
            + '&image_b64='   + encodeURIComponent(img ? img.b64 : '')
            + '&image_type='  + encodeURIComponent(img ? img.mediaType : '')
    }}).then(function(r) {{
        document.getElementById('lucy-typing').style.display = 'none';
        if (!r.ok) {{
            _renderBubble('lucy', 'Sorry, I couldn\\'t connect. Please check that your API key is set in Settings.');
            return;
        }}
        var bubble = _renderBubble('lucy', '');
        var full   = '';
        var reader = r.body.getReader();
        var decoder = new TextDecoder();
        // Strip [RULE:...] and [PLAN_UPDATED:...] tags from display text
        function _stripRuleTags(text) {{
            return text
                .replace(/\[RULE:(add|remove)\][\s\S]*?\[\/RULE\]/g, '')
                .replace(/\[PLAN_UPDATED:[^\]]+\]/g, '')
                .replace(/\[CARRYOVER_UPDATED:[^\]]+\]/g, '')
                .replace(/\s+$/, '');
        }}
        function read() {{
            return reader.read().then(function(res) {{
                if (res.done) {{
                    var clean = _stripRuleTags(full);
                    bubble.textContent = clean;
                    _lucyHistory.push({{role:'assistant', content: clean}});
                    // Parse and show rule proposal buttons
                    var ruleRx = /\[RULE:(add|remove)\]([\s\S]*?)\[\/RULE\]/g;
                    var m;
                    while ((m = ruleRx.exec(full)) !== null) {{
                        (function(action, ruleText) {{
                            ruleText = ruleText.trim();
                            var ruleRow = document.createElement('div');
                            ruleRow.style.cssText = 'display:flex;justify-content:flex-start;margin-top:6px;';
                            var ruleBtn = document.createElement('button');
                            var label = (action === 'add' ? '📋 Save rule' : '🗑 Remove rule');
                            var preview = ruleText.length > 55 ? ruleText.substring(0,55)+'…' : ruleText;
                            ruleBtn.textContent = label + ': ' + preview;
                            ruleBtn.style.cssText = 'background:#f0f8e8;border:1px solid #8ab870;color:#2d5016;'
                                + 'font-size:0.72em;cursor:pointer;padding:4px 10px;border-radius:5px;font-family:inherit;';
                            ruleBtn.onclick = function() {{
                                fetch('/lucy-rule-save', {{
                                    method: 'POST',
                                    headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                                    body: 'action=' + encodeURIComponent(action) + '&rule=' + encodeURIComponent(ruleText)
                                }}).then(function(r) {{
                                    if (r.ok) {{
                                        ruleBtn.textContent = '✓ ' + (action === 'add' ? 'Rule saved to Settings' : 'Rule removed');
                                        ruleBtn.style.background = '#e8f5e9';
                                        ruleBtn.disabled = true;
                                    }}
                                }});
                            }};
                            ruleRow.appendChild(ruleBtn);
                            bubble._wrap.appendChild(ruleRow);
                        }})(m[1], m[2]);
                    }}
                    // Parse [CARRYOVER_UPDATED:child:date:count] markers
                    var carryRx = /\[CARRYOVER_UPDATED:([^\]:]+):([^\]:]+):(\d+)\]/g;
                    while ((m = carryRx.exec(full)) !== null) {{
                        (function(cChild, cDate, cCount) {{
                            var carryRow = document.createElement('div');
                            carryRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:6px;'
                                + 'padding:7px 10px;background:#fff8f0;border:1px solid #e0b87a;border-radius:8px;';
                            var checkIcon = document.createElement('span');
                            checkIcon.textContent = '✓';
                            checkIcon.style.cssText = 'color:#b06000;font-weight:700;font-size:1em;flex-shrink:0;';
                            var msg = document.createElement('span');
                            var noun = cCount === '1' ? 'carryover item' : 'carryover items';
                            msg.textContent = cCount + ' ' + noun + ' removed from ' + cChild + "'s list.";
                            msg.style.cssText = 'font-size:0.82em;color:#7a4200;flex:1;';
                            var printBtn2 = document.createElement('a');
                            printBtn2.textContent = '🖨 Print';
                            printBtn2.href = '/print/day?date=' + encodeURIComponent(cDate);
                            printBtn2.target = '_blank';
                            printBtn2.style.cssText = 'padding:4px 12px;background:#b06000;color:white;'
                                + 'text-decoration:none;border-radius:6px;font-size:0.8em;font-weight:700;'
                                + 'font-family:inherit;flex-shrink:0;';
                            carryRow.appendChild(checkIcon);
                            carryRow.appendChild(msg);
                            carryRow.appendChild(printBtn2);
                            bubble._wrap.appendChild(carryRow);
                        }})(m[1], m[2], m[3]);
                    }}
                    // Parse and show print buttons for [PLAN_UPDATED:child:date]
                    var planRx = /\[PLAN_UPDATED:([^\]:]+):([^\]]+)\]/g;
                    while ((m = planRx.exec(full)) !== null) {{
                        (function(pChild, pDate) {{
                            var planRow = document.createElement('div');
                            planRow.style.cssText = 'display:flex;align-items:center;gap:8px;margin-top:8px;'
                                + 'padding:8px 10px;background:#f5f8f0;border:1px solid #b8d498;border-radius:8px;';
                            var checkIcon = document.createElement('span');
                            checkIcon.textContent = '✓';
                            checkIcon.style.cssText = 'color:#3a7d1e;font-weight:700;font-size:1em;flex-shrink:0;';
                            var msg = document.createElement('span');
                            msg.textContent = pChild + "'s task list updated for " + pDate + ".";
                            msg.style.cssText = 'font-size:0.82em;color:#2d5016;flex:1;';
                            var printBtn = document.createElement('a');
                            printBtn.textContent = '🖨 Print';
                            printBtn.href = '/print/day?date=' + encodeURIComponent(pDate);
                            printBtn.target = '_blank';
                            printBtn.style.cssText = 'padding:4px 12px;background:#3a7d1e;color:white;'
                                + 'text-decoration:none;border-radius:6px;font-size:0.8em;font-weight:700;'
                                + 'font-family:inherit;flex-shrink:0;';
                            planRow.appendChild(checkIcon);
                            planRow.appendChild(msg);
                            planRow.appendChild(printBtn);
                            bubble._wrap.appendChild(planRow);
                        }})(m[1], m[2]);
                    }}
                    window.scrollTo(0, document.body.scrollHeight);
                    return;
                }}
                full += decoder.decode(res.value, {{stream: true}});
                bubble.textContent = _stripRuleTags(full);
                window.scrollTo(0, document.body.scrollHeight);
                return read();
            }});
        }}
        read().catch(function(e) {{
            bubble.textContent = 'Stream error: ' + e.message;
        }});
    }}).catch(function(e) {{
        document.getElementById('lucy-typing').style.display = 'none';
        _renderBubble('lucy', 'Network error: ' + e.message);
    }});
}}

function _renderBubble(role, text) {{
    var hist = document.getElementById('lucy-history');
    var wrap = document.createElement('div');
    var div  = document.createElement('div');
    div.className = (role === 'user') ? 'lucy-bubble-user' : 'lucy-bubble-lucy';
    div.textContent = text;
    div._wrap = wrap;
    wrap.appendChild(div);

    if (role === 'lucy') {{
        var saveRow = document.createElement('div');
        saveRow.style.cssText = 'display:flex;justify-content:flex-start;margin-top:4px;';
        var saveBtn = document.createElement('button');
        saveBtn.textContent = '📖 Save to memory book';
        saveBtn.style.cssText = 'background:none;border:none;color:#c49020;font-size:0.72em;' +
            'cursor:pointer;padding:2px 0;font-family:inherit;opacity:0.7;';
        saveBtn.onmouseover = function() {{ this.style.opacity = '1'; }};
        saveBtn.onmouseout  = function() {{ this.style.opacity = '0.7'; }};
        saveBtn.onclick = function() {{
            var lastUser = '';
            for (var i = _lucyHistory.length - 1; i >= 0; i--) {{
                if (_lucyHistory[i].role === 'user') {{ lastUser = _lucyHistory[i].content; break; }}
            }}
            var toSave = lastUser || text;
            fetch('/memory-book-save', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
                body: 'text=' + encodeURIComponent(toSave) + '&date=' + encodeURIComponent(_lucyIso)
            }}).then(function(r) {{
                if (r.ok) {{
                    saveBtn.textContent = '✓ Saved to memory book';
                    saveBtn.style.color = '#2d5016';
                    saveBtn.disabled = true;
                }}
            }});
        }};
        saveRow.appendChild(saveBtn);
        wrap.appendChild(saveRow);
    }}

    hist.appendChild(wrap);
    return div;
}}

window.addEventListener('load', function() {{
    var input = document.getElementById('lucy-input');
    {'// Continuing conversation — scroll to bottom, leave input clear' if _has_history else '// Fresh start — pre-fill opener prompt'}
    {'window.scrollTo(0, document.body.scrollHeight);' if _has_history else (
        'var openerPrompt = ' + escape_js(opener_prompt) + ';'
        + ' input.value = openerPrompt;'
        + ' input.style.height = "auto";'
        + ' input.style.height = Math.min(input.scrollHeight, 120) + "px";'
    )}
}});

</script>"""

    from ui_helpers import html_page
    return html_page("Lucy", body)


def escape_js(s: str) -> str:
    """Escape a string for safe embedding in a JS string literal (single-quoted)."""
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'"


# ─────────────────────────────────────────────────────────────────────────────
# Child-specific Lucy brief (used on each boy's schedule page)
# ─────────────────────────────────────────────────────────────────────────────

_CHILD_PROFILES = {
    "jp": {
        "age": 14,
        "stage": "teenager",
        "formation_notes": (
            "JP is 14 — old enough to reason about virtue, chastity, and Catholic manhood. "
            "He is active in CAP/Civil Air Patrol and Sea Cadets. "
            "Speak to him with the respect due a young man, not a child. "
            "Challenge him toward excellence and sacrificial love. "
            "He is old enough to understand the theology behind what you suggest. "
            "Notice signs of pride or sloth and name them gently. Affirm any courage or service."
        ),
    },
    "joseph": {
        "age": 12,
        "stage": "preteen",
        "formation_notes": (
            "Joseph is 12. He is at the threshold between boyhood and young manhood. "
            "He is preparing (or should be) for Confirmation. "
            "He needs encouragement around friendship, loyalty, and honesty. "
            "Watch for social comparison with his older brother JP. "
            "Help him find his own identity in Christ, not in comparison to others. "
            "Speak warmly and with humor — he is not yet JP's age."
        ),
    },
    "michael": {
        "age": 5,
        "stage": "kindergarten",
        "formation_notes": (
            "Michael is 5 — in his kindergarten years. "
            "Formation at this age is through joy, story, and routine. "
            "He learns prayer by doing it with others, not by reasoning about it. "
            "Key virtues to encourage: obedience, kindness, sharing, and patience. "
            "Stories of saints (especially action-oriented ones like St. George, St. Martin) delight him. "
            "Keep language simple, warm, and playful. He is not learning doctrine — he is learning to love."
        ),
    },
    "james": {
        "age": 0,
        "stage": "infant",
        "formation_notes": (
            "James is only a few weeks old — an infant. "
            "He cannot be formed in the usual sense yet. "
            "Your brief should be addressed to Mom, not to James. "
            "Note developmental milestones appropriate for this age (feeding, sleep, attachment, tummy time). "
            "Offer encouragement for Mom in the particular exhaustion of the newborn stage. "
            "Remind her that holding James with love is already forming him in security and trust. "
            "Suggest a simple blessing or prayer she can whisper over him."
        ),
    },
}


def get_mom_lucy_brief(tasks_today: list) -> str:
    """
    Generate a short daily encouragement note written for Lauren (Mom).
    Returns plain text HTML. Returns empty string on failure.
    """
    import json as _json
    import urllib.request as _req

    try:
        with open("data/app_settings.json") as f:
            settings = _json.load(f)
        api_key = (settings.get("family_constraints", {}).get("anthropic_api_key", "")
                   or settings.get("anthropic_api_key", "")).strip()
    except Exception:
        api_key = ""

    if not api_key:
        return ""

    try:
        from data_helpers import load_lucy_rules
        rules = load_lucy_rules()
        rules_text = "\n".join(f"- {r}" for r in rules) if rules else "None set."
    except Exception:
        rules_text = "None set."

    today = _today_eastern()
    weekday = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")

    tasks_text = (
        "\n".join(f"- {t}" for t in tasks_today[:10])
        if tasks_today
        else "No specific tasks recorded for today."
    )

    system = (
        "You are Lucy, a warm, deeply Catholic AI companion for Lauren McAdams. "
        "Lauren is a Catholic homeschooling mother of four boys: JP (14), Joseph (12), Michael (5), and James (newborn). "
        "Her husband is John. She manages the household, educates the children at home, and carries the invisible weight of motherhood with faith. "
        "She is devoted to Our Lady, values liturgical rhythm, and loves her family deeply. "
        "Your job is to write a SHORT (3-5 sentence) morning note of encouragement written DIRECTLY to Lauren — "
        "not about her children, not a to-do recap, but a warm personal word that sees her as a whole person. "
        "Reference today's tasks lightly if helpful, but the focus is on Lauren's heart and interior life. "
        "Close with a brief prayer intention or a virtue she might lean into today. "
        "Do not be generic. Do not be preachy. Write in warm, personal prose — like a friend who knows her well. "
        f"\n\nMom's standing rules and context:\n{rules_text}"
    )

    user = (
        f"Today is {weekday}, {date_label}.\n\n"
        f"Lauren's tasks and chores today:\n{tasks_text}\n\n"
        "Please write a brief, warm morning encouragement note directly to Lauren for today."
    )

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 250,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

    try:
        req = _req.Request(
            "https://api.anthropic.com/v1/messages",
            data=_json.dumps(payload).encode(),
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with _req.urlopen(req, timeout=15) as resp:
            result = _json.loads(resp.read())
        return result["content"][0]["text"].strip()
    except Exception:
        return ""


def get_child_lucy_brief(child: str, tasks_today: list, active_goals: list) -> str:
    """
    Call Claude to generate a short (3-5 sentence) formation brief for a specific child.
    Returns plain text. Raises on API failure.
    """
    import json as _json
    import urllib.request as _req

    ck = child.lower().strip()
    profile = _CHILD_PROFILES.get(ck, {})
    age = profile.get("age", "unknown")
    stage = profile.get("stage", "child")
    formation_notes = profile.get("formation_notes", "")

    # Load API key
    try:
        with open("data/app_settings.json") as f:
            settings = _json.load(f)
        api_key = (settings.get("family_constraints", {}).get("anthropic_api_key", "")
                   or settings.get("anthropic_api_key", "")).strip()
    except Exception:
        api_key = ""

    if not api_key:
        return ""

    # Load Lucy's standing rules for context
    try:
        from data_helpers import load_lucy_rules
        rules = load_lucy_rules()
        rules_text = "\n".join(f"- {r}" for r in rules) if rules else "None set."
    except Exception:
        rules_text = "None set."

    today = _today_eastern()
    weekday = today.strftime("%A")
    date_label = today.strftime("%B %d, %Y")

    tasks_text = ""
    if tasks_today:
        tasks_text = "\n".join(f"- {t}" for t in tasks_today[:10])
    else:
        tasks_text = "No specific tasks recorded for today."

    goals_text = ""
    if active_goals:
        for g in active_goals[:5]:
            substeps_done = sum(1 for s in g.get("substeps", []) if s.get("done"))
            substeps_total = len(g.get("substeps", []))
            progress = f"{substeps_done}/{substeps_total} steps done" if substeps_total else "no steps yet"
            goals_text += f"- {g.get('title','')} [{g.get('category','')}] ({progress})\n"
    else:
        goals_text = "No goals set yet for this child."

    system = (
        "You are Lucy, a warm, faithful, deeply Catholic AI companion for the McAdams family. "
        "You know every member of the family well. "
        "You are writing a brief formation note that will appear at the top of a child's daily schedule page. "
        "It is written FOR MOM (she reads the page), about the child. "
        "Keep it to 3-5 sentences. Be warm, specific, and practical. "
        "Reference what you know about this child's age, stage, and goals. "
        "Do not be generic. Do not be preachy. Do not list things — write in flowing, personal prose. "
        "If the child is an infant, address Mom directly with encouragement and a developmental note. "
        "Always close with either a brief prayer intention, a virtue to notice today, or a specific encouragement. "
        f"\n\nMom's standing rules and context:\n{rules_text}"
    )

    # Load the child's personal profile (sizes, preferences, wish lists, etc.)
    try:
        from render_child_profile import profile_summary_for_lucy
        profile_text = profile_summary_for_lucy(child)
    except Exception:
        profile_text = "(Profile not available.)"

    user = (
        f"Today is {weekday}, {date_label}.\n\n"
        f"Child: {child} (age {age}, {stage})\n"
        f"Formation notes:\n{formation_notes}\n\n"
        f"Today's tasks for {child}:\n{tasks_text}\n\n"
        f"Active goals for {child}:\n{goals_text}\n\n"
        f"Personal profile for {child} (preferences, wish lists, sizes, interests):\n{profile_text}\n\n"
        f"Please write a brief, warm formation note for Mom about {child} for today."
    )

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 300,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

    try:
        req = _req.Request(
            "https://api.anthropic.com/v1/messages",
            data=_json.dumps(payload).encode(),
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with _req.urlopen(req, timeout=15) as resp:
            result = _json.loads(resp.read())
        return result["content"][0]["text"].strip()
    except Exception:
        return ""
