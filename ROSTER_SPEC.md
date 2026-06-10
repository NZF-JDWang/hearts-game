# Roster Specification

## Overview

The Hearts game features 10 named AI opponents. Each new game randomly selects 3
distinct opponents, ensuring at least one aggressive, one balanced, and one
conservative personality. Rematches keep the same 3 opponents.

## Characters

| # | Name     | Personality   | Tagline                    | Bio                                          |
|---|----------|---------------|----------------------------|----------------------------------------------|
| 1 | Marco    | aggressive    | I play to win.             | Competitive card player from Milan.          |
| 2 | Priya    | balanced      | Read the table, then decide.| Data analyst from Toronto.                  |
| 3 | Tomoko   | conservative  | Patience pays off.         | Retired accountant from Osaka.               |
| 4 | Jesús    | aggressive    | No mercy at the table.     | Amateur poker champion from Seville.         |
| 5 | Anna     | balanced      | Steady and sharp.          | Medical resident from Stockholm.             |
| 6 | Kwame    | aggressive    | Control the game early.    | Maths teacher from Accra.                    |
| 7 | Sarah    | conservative  | Let them make mistakes.    | Librarian from Dublin.                       |
| 8 | Dmitri   | aggressive    | Push until they fold.      | Former chess hustler from Saint Petersburg.  |
| 9 | Lin      | balanced      | Adapt or lose.             | Engineering student from Shanghai.           |
| 10| Ben      | conservative  | Slow and steady.           | Retired postal worker from Christchurch.     |

## Personality Distribution

- **Aggressive (4):** Marco, Jesús, Kwame, Dmitri
- **Balanced (3):** Priya, Anna, Lin
- **Conservative (3):** Tomoko, Sarah, Ben

## Avatars

Each character has a permanent 128×128 PNG portrait in `assets/avatars/`.
Avatars are realistic human head-and-shoulders portraits with plain grey
backgrounds, generated via Grok Imagine (`grok-imagine-image-quality`).

## Selection Logic

- `draw_ai_three()` — random 3-of-10 with personality coverage guarantee.
- `pick_ai_three(seed)` — deterministic version for testing.
- Rematch preserves the same 3 characters from the previous game.

## Files

- `src/hearts/roster.py` — Character dataclass, ROSTER tuple, draw/pick functions.
- `tests/test_roster.py` — 22 tests covering roster invariants.
- `scripts/generate_avatars.py` — Idempotent avatar generator (--force to regenerate).
- `assets/avatars/` — 10 portrait PNGs + `_manifest.json`.