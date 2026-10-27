# Liftlog — notes for Claude Code

Workout tracker, built as a data-engineering practice project.
Live: GitHub Pages from `main` (root). Installable as a PWA (Android/Chrome).

## How to work here
- Terse. Short answers, no praise, no filler. Say plainly when unsure.
- Incremental changes; show short diffs/pseudocode, not essays.
- Ask before anything destructive to the data model; otherwise just do it, commit, push.

## Hard rules
- **The repo is public. Never commit personal data** (`liftlog-import.json`, exports, notes exports, `CLAUDE.local.md`). `.gitignore` covers the usual names.
- **Personal facts stay out of this file.** Training history, note-taking quirks, data-specific cleanup dates and open items about someone's records go in `CLAUDE.local.md` (gitignored, loaded by Claude Code locally).
- **App ships empty.** No seed data in `index.html`.
- **Bump `VERSION` in `sw.js` on every change to `index.html`** (`liftlog-vN` → `vN+1`), or installed phones keep the old cache.
- Single self-contained `index.html`: no build step, no framework, vanilla JS. External loads: Google Fonts only.
- Data lives in `localStorage` only. Never break old saved data: add fields with defaults (`db.x = db.x || …`), don't rename keys.
- All UI must work at 360 px wide, dark and light presets, Greek text.

## Deploy
Commit + push to `main` → Pages redeploys (~1 min). That is the whole deploy.
To verify UI: `pip install playwright && playwright install chromium`, load `file://…/index.html` at 360×780, seed `localStorage["liftlog.v1"]` with made-up data, screenshot, check `pageerror`.

## Files
| File | Purpose |
|---|---|
| `index.html` | the whole app (HTML + CSS + JS) |
| `sw.js` | offline cache, network-first for app files |
| `manifest.webmanifest`, `icon-*.png` | PWA install |
| `tools/xiaomi_to_liftlog.py` | ETL pass 1: Xiaomi Notes `.md` export → canonical text |
| `tools/cleanup.js` | ETL pass 2: manual cleanup rules, uses the app's own parser from `index.html`; data-specific dates come in as arguments |

Build an import file: `python3 tools/xiaomi_to_liftlog.py <notes_dir> /tmp/s1.json && node tools/cleanup.js /tmp/s1.json liftlog-import.json [ohp_barbell_from]` (output stays out of git).

## Data model (`localStorage`)
- `liftlog.v1` = `{workouts, weights, height, aliases, exercises, exOverrides, wY}`
  - workout `{id, date:"YYYY-MM-DD", title, raw, notes, original}`. **`raw` is the source of truth**; everything else (sets, muscles, records) is derived on every render by `parseBody` + `resolve`. Never store derived data.
  - weight `{id, t:"YYYY-MM-DDTHH:MM", kg}`; `height` cm; `wY` manual y-axis `{min,max}`.
  - `aliases` `{normalizedName: exerciseId}` (user mappings), `exercises` user-created, `exOverrides` edits to built-ins.
- `liftlog.settings.v3` = colors, font, `split` (muscle order preset id), `custom` presets, `tabs` shown.
- `liftlog.draft` = Log tab draft.
- Export/Import JSON = `liftlog.v1` content; import merges by id, skips existing.

## Text grammar (canonical, what `parseBody` reads)
```
Exercise name [modifiers]          # line without sets = exercise header
10x60  3x6x100  10x0  8x-10        # RxW, SxRxW; 0 = bodyweight; negative = assisted
10xΚλειστα                         # word instead of kg = variant (qualitative, first-class)
4x30+6x20                          # + links parts into one set (called superset in the UI; same exercise)
10x20 10x40 | 3x6x100              # | : sets before it on that line are warm-ups
... Fail on last  PR  δύσκολα       # words after a set = note on that set; /fail|αποτυχ/ marks failed
"Gym Leg Oct 5"                    # header line → new workout (date, year inferred)
```
Stats rules: warm-ups count nowhere; a failed group drops its last set from records; linked parts add no extra sets; muscle sets = sets × weight (1, ½, ¼).

## Exercise resolution
`norm()`: strip accents, lowercase, ς→σ, map Greek/Latin look-alikes (ΒP, Αbs). `resolve()`: exact alias → strip modifiers (`splitMods`: MODLIST words, STOP words, `ez`/`db` suffix, numbers and `(…)` ignored) → exact base → fuzzy (Levenshtein ≤1–2, same first letter). Modifiers (EZ, Machine, Good machine, Rope, V bar, Dumbbell, Barbell, Interior/Exterior, Small grip, …) become tags and split Records per exercise+modifier set.
Built-in catalog: `EX` (36 exercises, Greek + English aliases); `TAGS` = expected tags per exercise; Dumbbell/Barbell allowed everywhere. Muscle groups: 13 (`MUSCLES`, incl. forearms, abductors).

## Tabs
History (workouts, ✕ per exercise) · Muscles (weighted sets 7d/28d/8w, grouped by split preset, Core always last) · Records (heaviest, heaviest 5+ reps; remap / new exercise / ✕ delete everywhere) · Weight (7D/30D/90D/All, 7-day rolling mean, healthy BMI band from height, manual y-axis) · Log (text + notes, autosaved draft, live preview, map unknown names) · Settings (gear: colors/hex, Default dark/light, font, tabs shown, muscle order presets incl. MegaLeg + custom, Exercises editor, Import/Export, delete all).
MegaLeg preset = Push: glute drive, bench, OHP, tricep · Pull: deadlift, pull-up, row, bicep · Leg: squat, abductors, Ραχαίοι, Γάμπες, abs.

## Open items
- "Τρικεφαλα σχοινί"-style names don't map until "τρικεφαλα" is added as an alias.
