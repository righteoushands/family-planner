---
name: Liturgical colors in style attributes
description: season_color/feast_color are user-editable and must be allowlisted before going into inline style attributes (XSS).
---

# Liturgical colors are user-editable → allowlist before inlining into style

`get_day_info(d)` returns `season_color` and `feast_color`. These can originate
from **user-editable custom overrides** (the `/liturgical/edit` flow,
`load_liturgical_custom`), not just hardcoded tables.

**Rule:** never interpolate these (or any color field) raw into an inline
`style="..."` attribute. `escape()` does NOT neutralize CSS/attribute-breakout
payloads. Pass them through a strict allowlist first: hex (`#RGB/#RRGGBB/#RRGGBBAA`)
or a vetted set of named colors, else fall back to a safe default.

**Why:** a crafted custom color value containing a quote can break out of the
style attribute and inject script (stored XSS). Caught in architect review of the
Meal Wizard Step 1 "Week at a Glance" page; fixed there with `_wg_safe_color`.

**How to apply:** any new render code that surfaces `season_color`/`feast_color`
(or other data-sourced colors) must sanitize first. NOTE: `render_liturgical.py`
itself still interpolates `feast_color`/vestment colors raw in places — same
latent issue; sanitize if you touch those code paths.
