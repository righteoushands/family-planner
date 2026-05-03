"""
father_gregory.py — Shared helper for the Father Gregory AI grading prompt.

Wraps the Anthropic Claude Opus 4.5 vision call used to give student work
rich, age-aware structured feedback (the same persona used by Lauren's
/assignment-analyzer flow).

Public surface:
    build_prompt(child_hint, subject_hint, lesson_hint, description) -> str
    analyze_image(image_bytes, mime, child_hint, subject_hint,
                  lesson_hint, description) -> dict
    letter_to_pct(letter) -> float | None

The prompt body is copied verbatim from the inline prompt in
app.py /assignment-analyze (lines 2269-2341). Two definitions exist
intentionally for now — DRY-up of app.py is a deferred follow-up.
"""
from __future__ import annotations
import base64 as _b64
import json as _json
import re as _re
import urllib.request as _ur


# ── Image shrinking (duplicated from app.py:_shrink_image_for_anthropic) ────
# Kept local to avoid an import cycle with app.py.
def _shrink_image_for_anthropic(raw_bytes: bytes, mime: str):
    """Anthropic enforces a 5 MB cap on the BASE64 representation of each
    image (~3.7 MB raw). iPhone JPEGs routinely exceed that. This shrinks
    the image (resizing + JPEG re-encoding with progressively lower quality)
    until it fits, returning (bytes, mime). Falls back to the original bytes
    if Pillow isn't available — caller will get a clearer error from the API.
    """
    _CAP_RAW = 3 * 1024 * 1024
    if len(raw_bytes) <= _CAP_RAW:
        return raw_bytes, mime
    try:
        from PIL import Image
        import io
    except Exception:
        return raw_bytes, mime
    try:
        im = Image.open(io.BytesIO(raw_bytes))
        try:
            from PIL import ImageOps
            im = ImageOps.exif_transpose(im)
        except Exception:
            pass
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        long_edge = max(im.size)
        for max_dim, qual in [(2200, 88), (1800, 85), (1400, 82),
                              (1100, 78), (900, 75)]:
            if long_edge > max_dim:
                ratio = max_dim / float(long_edge)
                new_w = int(im.size[0] * ratio)
                new_h = int(im.size[1] * ratio)
                im2 = im.resize((new_w, new_h), Image.LANCZOS)
            else:
                im2 = im
            buf = io.BytesIO()
            im2.save(buf, format="JPEG", quality=qual, optimize=True)
            data = buf.getvalue()
            if len(data) <= _CAP_RAW:
                return data, "image/jpeg"
        return data, "image/jpeg"
    except Exception:
        return raw_bytes, mime


# ── Prompt body (verbatim from app.py:2269-2341) ────────────────────────────
_BASE_PROMPT = (
    "You are FATHER GREGORY — the academic director and headmaster of the McAdams "
    "family homeschool. You are a wise, warm scholar in the tradition of Benedictine "
    "and Jesuit education, formed by the classical Trivium (Grammar, Logic, Rhetoric) "
    "and Charlotte Mason's living-books philosophy. Lauren is the mom and primary "
    "teacher. You are reviewing a piece of student work she has uploaded.\n"
    "\n"
    "== THE McADAMS BOYS ==\n"
    "JP — 14, 9th-grade equivalent. Most advanced. Ready for formal logic, "
    "advanced composition, rhetoric, dialectic-level argument. Hold him to substance, "
    "structure, citations, and clarity of thesis. Push him.\n"
    "Joseph — 12, 7th-grade equivalent. Logic stage. Ready for structured argument, "
    "cause-and-effect, mastery of grammar. Encourage neat work, complete sentences, "
    "and one clear next step at a time.\n"
    "Michael — 5, kindergarten / early Grammar stage. Wonder years. Praise effort, "
    "neat letters, and oral narration. Suggestions must be tiny and concrete "
    "(\"trace the o all the way around\"). Never overwhelm; one or two gentle nudges.\n"
    "James — 13 months. Not in school yet. Skip feedback if the work is his.\n"
    "\n"
    "== HOW TO REVIEW ==\n"
    "If the upload contains the student's actual WORK (handwritten answers, an essay, "
    "a math sheet with solutions, a drawing, a worksheet with their writing on it), "
    "give Father Gregory's feedback. If it is only the assignment instructions with no "
    "student work yet, set gregory_feedback to a brief one-sentence note that the work "
    "hasn't been done yet, and leave strengths/growth_edges empty.\n"
    "Always tailor depth and vocabulary to the named/guessed child's age. For JP use "
    "scholarly directness; for Joseph use clear and warm coaching; for Michael use "
    "tender, celebratory praise plus one tiny next step.\n"
    "Be specific: cite what you actually see (\"your second paragraph opens with a "
    "strong topic sentence — 'Greek myths gave us…'\"). Avoid generic praise.\n"
    "Growth edges should be LEADING — not the answer, but a question or nudge that "
    "guides the student to discover the improvement themselves.\n"
    "\n"
    "Return ONE JSON object — no markdown, no commentary, just raw JSON — with these "
    "exact keys:\n"
    '  "title": short descriptive title of the assignment (string)\n'
    '  "subject": best-guess from: Math, Latin, Greek, Religion, History, Science, '
    "Reading, Writing, Grammar, Literature, Art, Music, Logic, PE, Other (string)\n"
    '  "child_guess": JP / Joseph / Michael, or empty string if unclear (string)\n'
    '  "assignment_type": e.g. worksheet, reading, test, quiz, project, practice, '
    "essay, copywork, oral recitation, problem set, other (string)\n"
    '  "estimated_minutes": realistic time-on-task for that child (integer)\n'
    '  "due_date_hint": any due-date language inferable ("today", "Friday", a date, '
    "or empty string) (string)\n"
    '  "instructions_summary": 1-3 sentences in plain English summarizing what the '
    "child needs to do (string)\n"
    '  "sub_items": list of individual sub-tasks if multi-part (up to 30 strings); '
    "empty list otherwise (array of strings)\n"
    '  "materials_needed": list of supplies; empty list if none obvious (array of strings)\n'
    '  "notes_for_mom": anything Mom should know — pitfalls, prep needed, context — '
    "or empty string (string)\n"
    '  "work_present": true if the upload shows the student has actually done work '
    "on the assignment; false if it is only the assignment prompt/instructions (boolean)\n"
    '  "gregory_feedback": Father Gregory speaking in first person to the child by '
    "name, 2-5 sentences, age-appropriate, warm and specific. Empty string if no work "
    "is present yet. (string)\n"
    '  "strengths": 1-4 short bullet phrases naming specific things the child did '
    "well — must reference what you actually see in the work. Empty list if no work. "
    "(array of strings)\n"
    '  "growth_edges": 1-3 short LEADING suggestions for improvement, age-appropriate '
    "in tone and difficulty. Phrase as a gentle nudge or question, not a correction "
    "(\"What if you tried…\", \"Could you find one place where…\"). Empty list if no "
    "work or if the work is essentially perfect for the child's level. "
    "(array of strings)\n"
    '  "suggested_grade": Father Gregory\'s suggested letter grade for the work as it '
    "stands, age-normed for the child (A+, A, A-, B+, B, B-, C+, C, C-, D, F). For "
    "Michael (5) prefer encouragement marks instead of letters: \"✦ Excellent\", "
    "\"✓ Good work\", \"↻ Try again\". Empty string if no work is present. (string)\n"
    '  "grade_rationale": 1-3 sentences in Father Gregory\'s voice explaining WHY he '
    "gave that grade — what it reflects about completeness, accuracy, effort, and "
    "craftsmanship for the child's age. No rubric is set up yet, so use sound "
    "headmaster judgement. Empty string if no work. (string)\n"
)


def build_prompt(child_hint: str = "",
                 subject_hint: str = "",
                 lesson_hint: str = "",
                 description: str = "") -> str:
    """Build the full Father Gregory prompt with optional per-request hints."""
    out = _BASE_PROMPT
    if child_hint:
        out += f"\nMom hinted this is for: {child_hint}.\n"
    if subject_hint:
        out += f"Mom hinted the subject is: {subject_hint}.\n"
    if lesson_hint:
        out += f"Mom hinted the specific lesson is: {lesson_hint}.\n"
    if description:
        out += (
            "\nMom provided this description of what was assigned — "
            "use it as authoritative context for what the student was "
            "asked to do, and judge the work against it:\n"
            f"\"\"\"\n{description[:4000]}\n\"\"\"\n"
        )
    return out


# ── Letter → percent (standard 13-point scale) ──────────────────────────────
_LETTER_PCT = {
    "A+": 98.0, "A": 95.0, "A-": 92.0,
    "B+": 87.0, "B": 85.0, "B-": 82.0,
    "C+": 77.0, "C": 75.0, "C-": 72.0,
    "D+": 67.0, "D": 65.0, "D-": 62.0,
    "F":  50.0,
}


def letter_to_pct(letter: str):
    """Map a Father Gregory letter grade to a 0-100 percent for grades.json.
    Returns None for unmappable strings (e.g. Michael's '✦ Excellent')."""
    if not isinstance(letter, str):
        return None
    return _LETTER_PCT.get(letter.strip().upper().replace(" ", ""))


# ── Anthropic vision call ───────────────────────────────────────────────────
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-opus-4-5"
_TIMEOUT = 60


def _get_api_key() -> str:
    """Read the Anthropic key from app settings (matches app.py:2258-2262)."""
    try:
        from render_settings import load_app_settings
        s = load_app_settings()
        key = (s.get("family_constraints", {}).get("anthropic_api_key", "")
               or s.get("anthropic_api_key", ""))
        return (key or "").strip()
    except Exception:
        return ""


def analyze_image(image_bytes: bytes,
                  mime: str,
                  child_hint: str = "",
                  subject_hint: str = "",
                  lesson_hint: str = "",
                  description: str = "") -> dict:
    """Send one image to Father Gregory for structured feedback.

    Returns:
        {"ok": bool, "error": str, "parsed": {...16 keys...}}
        On success `parsed` carries Father Gregory's full structured output.
        On failure `parsed` is {} and `error` describes what went wrong.
    """
    if not image_bytes:
        return {"ok": False, "error": "no_image", "parsed": {}}

    api_key = _get_api_key()
    if not api_key:
        return {"ok": False, "error": "no_api_key", "parsed": {}}

    # Normalise MIME, then shrink for the 5 MB base64 cap.
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"
    if mime == "image/heic":
        mime = "image/jpeg"
    api_bytes, api_mime = _shrink_image_for_anthropic(image_bytes, mime)

    prompt = build_prompt(child_hint=child_hint,
                          subject_hint=subject_hint,
                          lesson_hint=lesson_hint,
                          description=description)

    payload = {
        "model": _MODEL,
        "max_tokens": 1500,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64",
                            "media_type": api_mime,
                            "data": _b64.b64encode(api_bytes).decode("ascii")}},
                {"type": "text", "text": prompt},
            ],
        }],
    }

    try:
        req = _ur.Request(
            _ANTHROPIC_URL,
            data=_json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with _ur.urlopen(req, timeout=_TIMEOUT) as r:
            resp = _json.loads(r.read().decode())
        ai_text = resp.get("content", [{}])[0].get("text", "").strip()
    except _ur.HTTPError as he:
        try:
            body = he.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        return {"ok": False,
                "error": f"HTTP {he.code}: {body[:600]}",
                "parsed": {}}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300], "parsed": {}}

    # Strip ```json fences if present
    txt = ai_text
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json"):
            txt = txt[4:].lstrip()
    parsed = {}
    try:
        parsed = _json.loads(txt)
    except Exception:
        m = _re.search(r"\{[\s\S]*\}", ai_text)
        if m:
            try:
                parsed = _json.loads(m.group(0))
            except Exception as je:
                return {"ok": False,
                        "error": f"could not parse AI JSON: {je}",
                        "parsed": {}}
        else:
            return {"ok": False,
                    "error": "AI response was not JSON",
                    "parsed": {}}

    if not isinstance(parsed, dict):
        return {"ok": False, "error": "AI returned non-object JSON",
                "parsed": {}}

    return {"ok": True, "error": "", "parsed": parsed}
