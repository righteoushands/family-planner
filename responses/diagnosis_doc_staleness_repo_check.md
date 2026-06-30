# DIAGNOSIS — are your local doc copies stale vs. the repo?

Repo is a git repo. **Only 2 of the 5 files live in the repo. The other 3 are not in the repo at all** — they live outside it, you maintain them yourself, so "has Replit touched them?" is moot for those three.

---

## 1. TRACKER_Known_Issues.txt — ❌ NOT FOUND IN REPO
`find . -name TRACKER_Known_Issues.txt` returned nothing. This file does not exist anywhere in the repo (including subfolders). It is yours, outside the repo — nothing here can have changed it.

## 2. 6_11_SF_Known_Issues_Notes.txt — ❌ NOT FOUND IN REPO
Not present anywhere in the repo. Same conclusion: lives outside the repo, maintained by you.

## 3. TRACKER_UX_Meal_Wizard.txt — ❌ NOT FOUND IN REPO
Not present anywhere in the repo. Lives outside the repo, maintained by you.

> **Diff request:** A unified diff between `TRACKER_Known_Issues.txt` and `6_11_SF_Known_Issues_Notes.txt` was requested *only if both exist in the repo*. **Neither exists in the repo**, so no diff can be produced here. If you want them compared, paste both copies and I'll diff them.

---

## 4. PROJECT_STATE.md — ✅ IN REPO
- **Path:** `./PROJECT_STATE.md`
- **Filesystem last-modified:** `Jun 30 03:07` (size 50,429 bytes)
  - `-rw-r--r-- 1 runner runner 50429 Jun 30 03:07 PROJECT_STATE.md`
- **Tracked in git:** yes
- **Last commit touching it:** `2026-06-30 03:08:06 +0000 — Update project state to reflect meal wizard completion`
- **Content fingerprint (header):** `Generated 2026-06-30.` (line 3: "…sessions for a fast orientation. Generated 2026-06-30.")
- This is the Phase-G snapshot I regenerated on June 30. If your pasted copy says anything other than **Generated 2026-06-30**, yours is stale.

## 5. claud.md — ✅ IN REPO
- **Path:** `./claud.md`
- **Filesystem last-modified:** `Jun 28 11:52` (size 14,725 bytes)
  - `-rw-r--r-- 1 runner runner 14725 Jun 28 11:52 claud.md`
- **Tracked in git:** yes
- **Last commit touching it:** `2026-06-28 16:17:25 +0000 — Add functionality to confirm and remove meals within the meal wizard`
- **Content fingerprint:** No "Last updated" header line. Its dated marker is the **DOC CORRECTION LOG → "June 28 2026"** entry at the end (Rule 3 corrected to elif, AI-call model line, `_repair_and_parse_json` scope). If your pasted copy lacks that June 28 2026 correction log, yours is stale.

---

## Summary table

| # | File | In repo? | Path | FS mtime | Last commit (date — msg) | Fingerprint |
|---|------|----------|------|----------|--------------------------|-------------|
| 1 | TRACKER_Known_Issues.txt | ❌ No | — | — | — | (outside repo) |
| 2 | 6_11_SF_Known_Issues_Notes.txt | ❌ No | — | — | — | (outside repo) |
| 3 | TRACKER_UX_Meal_Wizard.txt | ❌ No | — | — | — | (outside repo) |
| 4 | PROJECT_STATE.md | ✅ Yes | ./PROJECT_STATE.md | Jun 30 03:07 | 2026-06-30 03:08:06 — Update project state to reflect meal wizard completion | Generated 2026-06-30 |
| 5 | claud.md | ✅ Yes | ./claud.md | Jun 28 11:52 | 2026-06-28 16:17:25 — Add functionality to confirm and remove meals within the meal wizard | DOC CORRECTION LOG: June 28 2026 |

## Bottom line
- **The three TRACKER / Known-Issues files are not in the repo** — they are entirely yours; Replit has never created, edited, or version-controlled them. Whatever copy you hold is the only copy.
- **PROJECT_STATE.md and claud.md are in the repo and git-tracked.** PROJECT_STATE.md is current as of **2026-06-30** (Phase G); claud.md is current as of **2026-06-28**. Compare your pasted copies' fingerprints against those dates to know if yours are stale.

*No changes were made — diagnosis only.*
