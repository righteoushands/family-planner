# claud.md — Rule 10 Addendum inserted (structural, not procedural isolation)

## What I did
Inserted your addendum into `claud.md` **directly below the existing Rule 10
text** (Rule 10 is at lines 58–62; the addendum is now lines 63–74, labeled
`10a.` in the file's existing numbered-rule style, immediately before Rule 11).
Text is verbatim to your wording, kept ASCII-clean (no backslashes, no nested
quotes) so it doesn't itself trip Rules 1/2.

## Where it landed
```
10.   test fixtures must never write to live data: ... restore from backup ...
10a.  RULE 10 ADDENDUM — ISOLATION MUST BE STRUCTURAL, NOT PROCEDURAL. Any
      verify_*.py harness ... import its isolation guard ... as the literal
      first import ... must raise (not warn) ... snapshot-and-restore-after is
      not equivalent to never touching live data. ... extend the existing
      isolation module's pattern ... rather than a new one-off mechanism.
11.   double-escaping HTML entities: ...
```

## Compliance check — the three existing harnesses already satisfy the rule
I verified the ordering the addendum now mandates. In all three,
`mw_test_isolation` is imported **before** `config`, `data_helpers`, and every
`render_*` module, and `assert_isolated()` runs before the first write:

| harness | isolation import | precedes app modules? | `assert_isolated()` before first write? |
|---|---|---|---|
| `verify_meal_wizard_step4.py` | line 29 | yes (config 31, data_helpers 32, render 34) | yes (55, render-only) |
| `verify_meal_wizard_step4_lock.py` | line 47 | yes (config 49, data_helpers 50, render_meals 52) | yes (94 → first write 135) |
| `verify_meal_wizard_step4_writeloop.py` | line 41 | yes (config 43, data_helpers 44) | yes (110 → server 111) |

And `assert_isolated()` **raises** (not warns) if any sink still resolves to a
live path — matching the addendum's "must raise" requirement.

## One honest note on "literal first import"
A handful of pure-stdlib imports (`os`, `sys`, `traceback`, plus `sys.path`
setup) necessarily precede `mw_test_isolation`, because you need them to locate
and import the isolation module from `data/` in the first place. None of them
bind or read a live data path, so they don't defeat the guarantee. The operative
criterion — the one your addendum's own clause spells out — is *"before
data_helpers, config, or any render_*.py module,"* and that is satisfied. If you'd
prefer the stricter literal reading enforced mechanically, I can add a tiny
self-check in `mw_test_isolation` that inspects already-imported modules at import
time and raises if `config`/`data_helpers`/`render_*` were imported first — say
the word.

## Scope
Only `claud.md` changed. No code, no harness edits (they were already compliant).
