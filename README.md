# Liftlog

Workout log you write as text: `Squat` / `10x20 3x6x100 Fail on last`.
Runs fully in the browser; each person's data stays in their own phone's storage.

## Put it online (GitHub Pages)
1. github.com → **New repository** → name `liftlog` → Public → Create.
2. **Add file → Upload files** → drop all files from this folder → Commit.
3. **Settings → Pages** → Source: *Deploy from a branch*, Branch: `main`, folder `/ (root)` → Save.
4. After ~1 min it's live at `https://<your-username>.github.io/liftlog/`.

## Install on Android
Open the link in Chrome → ⋮ → **Install app** (or *Add to Home screen*).

## Your history
Settings (gear) → **Import .json** → pick `liftlog-import.json` (keep that file out of this repo; the repo is public).

## Updating
Edit `index.html`, then bump `VERSION` in `sw.js` (e.g. `liftlog-v2`) so installed copies refresh.
