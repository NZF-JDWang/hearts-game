# Roster Pass — Spec

> **For Sven's loop:** Execute phase-by-phase. Do not skip phases. Do not merge phases.

**Goal:** Replace the 6-name, 6-avatar, single-template roster with **10 distinct AI opponents** — each with a permanent avatar, name, and bio. Each new game randomly draws 3 of the 10 to fill the AI seats (player is always seat 0). The player gets to know them through repeated play.

**Tech Stack:** Python 3.10+, Pygame, Pillow (no change). xAI Grok Imagine API for avatar generation.

**Repo:** github.com/NZF-JDWang/hearts-game

**Branching:** `feat/roster-pass` for the whole change. May be split into sub-branches per phase if size demands it.

**Success Criteria (deterministic):**
1. `assets/avatars/` contains **10 uniquely-themed avatar PNGs** (96×96 or similar, RGBA, generated via Grok Imagine text-to-image).
2. `src/hearts/roster.py` defines 10 `Character` records, each with: `id`, `name`, `bio` (1–2 sentence flavor), `personality` ∈ {`aggressive`, `balanced`, `conservative`}, `avatar_file` (relative to `assets/avatars/`), plus optional `tagline` for short UI.
3. `_start_new_game` selects 3 random characters from the roster (with no repeats, weighted so each personality gets ≥ 1 of the 3 seats — prevents the player from getting all-aggressive or all-passive AI). Human is always seat 0 and is **not** assigned a character.
4. Roster panel on the game scene shows each AI's avatar, name, personality, and a short tagline (bio may be shown on hover or in a roster-detail panel; keep v1 to a small subtitle line under the name).
5. **79+ tests still pass, 1 still skipped** (or better). Add a `test_roster.py` covering: 10 characters exist, 3 are chosen per game, no character repeats in one game, weighted distribution over many draws.
6. Roster is **stable across rematches** (a rematch keeps the same 3 AI — matches the existing `rematch=True` behavior).

---

## Out of Scope
- No new AI strategies (the 3 personalities are unchanged; just re-themed into 10 named characters).
- No roster persistence across app restarts (re-randomize on launch is fine).
- No unlockables, no character progression.
- No animation/voice acting for characters.

---

## Phase 1: Avatars (10 unique PNGs)
**Goal:** Generate 10 themed character portraits via Grok Imagine text-to-image.
**Files:** `scripts/generate_avatars.py` (new), `assets/avatars/avatar_<id>.png` (10 new files).
**Tests:** Script runs and produces 10 valid PNGs; PNG dimensions are uniform.
**Acceptance:**
- 10 PNGs at `assets/avatars/avatar_<01..10>.png`
- All ≥ 96×96, RGBA
- Script is reproducible (writes a manifest `assets/avatars/_manifest.json` with each prompt + id + sha)
- Script is idempotent (skips files that already exist with matching sha)
**Expected diff size:** ~10 PNGs (~2MB) + ~150-line script + ~50-line manifest.

### Task 1.1: Write 10 character prompts
Each character needs a **distinct visual theme** (palette, era, vibe). Themes (will lock the final 10 names in Phase 2):
- Vampire countess (red/black, formal)
- Mad-hatter inventor (steampunk, brass)
- Jazz singer in a smoke-filled club (gold, sepia)
- Hacker in a server room (cyan/black, LED)
- Samurai under a cherry tree (white/red)
- Disco queen (70s, sequins, mirror-ball)
- Mystic in a forest (green, candles)
- Pirate captain (ocean, leather, hat)
- Mad scientist (lab, green glow, goggles)
- Chess grandmaster (monochrome, sharp)

### Task 1.2: Generate via Grok Imagine
Use the `grok-imagine-image-quality` model, `response_format: "b64_json"`, 2k resolution, square aspect.
Prompts: portrait, head-and-shoulders, simple solid background (so the PNG composites cleanly into the Pygame roster panel), no text/logos in image.

### Task 1.3: Post-process
PIL: crop/center to 128×128, ensure RGBA, save to `assets/avatars/avatar_<id>.png`. Generate `_manifest.json` with the prompt + sha.

---

## Phase 2: Roster module
**Goal:** Define the 10 characters in code.
**Files:** `src/hearts/roster.py` (new), `tests/test_roster.py` (new).
**Tests:** All 10 characters present, each has a unique id/name/avatar_file; each personality appears ≥ 3 times; each avatar file exists on disk.
**Acceptance:** `from hearts.roster import ROSTER, pick_ai_three, draw_ai_three` works; `pick_ai_three(seed)` is deterministic for testing.
**Expected diff size:** ~120-line module + ~80-line test.

### Task 2.1: Character dataclass
```python
@dataclass(frozen=True)
class Character:
    id: str            # e.g. "vamp_countess"
    name: str          # e.g. "Countess Mara"
    personality: str   # "aggressive" | "balanced" | "conservative"
    avatar_file: str   # e.g. "avatar_01.png"
    bio: str           # 1–2 sentences
    tagline: str       # ≤ 40 chars, e.g. "Take what you want."
```

### Task 2.2: 10 character definitions
Match avatars 01–10 to characters. **Personality distribution:** 4 aggressive, 3 balanced, 3 conservative (ensures weighted pick can give at least one of each in 3 picks, since we use a draw-with-shuffle). Actually, simpler: 4-3-3 lets `pick_ai_three` use `random.sample` with no constraints — natural distribution will give variety. We just guarantee at least 1 of each by drawing round-robin if sample doesn't include all 3.

### Task 2.3: `pick_ai_three(seed=None) -> list[Character]`
- 3 distinct characters
- If `seed` given, deterministic (use `random.Random(seed)`)
- Personality coverage: at least 1 aggressive, 1 balanced, 1 conservative. If `random.sample` of 10 doesn't give that naturally, replace one slot with a character of the missing personality.

### Task 2.4: `draw_ai_three() -> list[Character]`
- Non-deterministic version using module `random` state. Returns the same shape as `pick_ai_three`.

---

## Phase 3: Wire to game start
**Goal:** Replace the fixed `NAMES[:4]` / `AVATAR_FILES[:4]` in `_start_new_game` with roster-driven selection. Rematches keep the same 3 AI.
**Files:** `src/hearts/app.py` (modify `_start_new_game` and the new-game path).
**Tests:** Full e2e still passes; new test verifies that across many starts, more than 1 distinct trio is produced (proves randomness).
**Acceptance:**
- `self.players[0]` is still the human (no character assigned)
- `self.players[1..3]` come from `roster.draw_ai_three()` on a new game
- On `rematch=True`, the same 3 characters are kept (just re-dealt, scores reset)
- Engine personalities still set correctly from the chosen characters
**Expected diff size:** ~30 lines changed in app.py + ~30-line test.

---

## Phase 4: Roster UI polish
**Goal:** Show the bio/tagline in the roster panel.
**Files:** `src/hearts/app.py` (roster rendering section).
**Tests:** Render test (existing smoke test) still passes; new test asserts the tagline text is present in the rendered surface for at least one of the 3 AI.
**Acceptance:**
- Roster panel shows: avatar (small), name (bold), personality (color-coded chip), tagline (italic, smaller, under name)
- Bio is shown when the player mouses over a roster row (tooltip) — keep this small, no new screen needed for v1
**Expected diff size:** ~60 lines in app.py (rendering), ~20-line test.

---

## Phase 5: Cleanup, e2e verify, ship
**Goal:** All 79+ tests pass, e2e green, branch merged to main, push.
**Files:** `ROSTER_SPEC.md` (this file, move to `docs/roster-pass.md` on ship), screenshots updated.
**Acceptance:** `pytest tests/` green, `python -m hearts.app` boots, roster screen shows the new themed AIs.
