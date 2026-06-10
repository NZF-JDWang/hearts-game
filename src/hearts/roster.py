"""The 10 named AI opponents and per-game selection logic.

Each new (non-rematch) game randomly draws 3 characters from ROSTER to fill
the three AI seats. Each character has a permanent avatar (in assets/avatars/),
a personality that maps to hearts.ai.choose_play's strategy, a short tagline
shown in the roster UI, and a 1-2 sentence bio shown on hover.

Public API:
  ROSTER              : tuple of all 10 Character records (immutable).
  PERSONALITIES       : alias for the three allowed personality strings.
  pick_ai_three(seed) : deterministic 3-of-10 draw, personality coverage.
  draw_ai_three()     : non-deterministic version, uses module random.

Constraints enforced by pick_ai_three:
  - 3 distinct characters.
  - At least one aggressive, one balanced, one conservative (replacement
    policy: if a personality is missing from a uniform 3-sample, swap one
    slot for the lowest-indexed character of the missing personality).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

PERSONALITIES: Tuple[str, ...] = ("aggressive", "balanced", "conservative")

@dataclass(frozen=True)
class Character:
    """One named AI opponent with a permanent visual + flavor."""

    id: str
    name: str
    personality: str
    avatar_file: str
    tagline: str
    bio: str

    def __post_init__(self) -> None:
        if self.personality not in PERSONALITIES:
            raise ValueError(
                f"character {self.id!r} has invalid personality "
                f"{self.personality!r} (must be one of {PERSONALITIES})"
            )
        if not self.avatar_file.startswith("avatar_"):
            raise ValueError(
                f"character {self.id!r} avatar_file must start with 'avatar_'"
            )
        if not self.tagline or len(self.tagline) > 40:
            raise ValueError(
                f"character {self.id!r} tagline must be 1..40 chars"
            )


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------

ROSTER: Tuple[Character, ...] = (
    Character(
        id="marco",
        name="Marco",
        personality="aggressive",
        avatar_file="avatar_01.png",
        tagline="I play to win.",
        bio=(
            "Competitive card player from Milan. Never passes up a chance "
            "to take the lead and force the table to react."
        ),
    ),
    Character(
        id="priya",
        name="Priya",
        personality="balanced",
        avatar_file="avatar_02.png",
        tagline="Read the table, then decide.",
        bio=(
            "Data analyst from Toronto who approaches every hand like a "
            "puzzle. Adapts strategy based on what others have shown."
        ),
    ),
    Character(
        id="tomoko",
        name="Tomoko",
        personality="conservative",
        avatar_file="avatar_03.png",
        tagline="Patience pays off.",
        bio=(
            "Retired accountant from Osaka. Keeps a mental ledger of every "
            "card played and rarely takes unnecessary risks."
        ),
    ),
    Character(
        id="jesus",
        name="Jesús",
        personality="aggressive",
        avatar_file="avatar_04.png",
        tagline="No mercy at the table.",
        bio=(
            "Amateur poker champion from Seville who brings the same "
            "relentless energy to Hearts. Leads hard, folds never."
        ),
    ),
    Character(
        id="anna",
        name="Anna",
        personality="balanced",
        avatar_file="avatar_05.png",
        tagline="Steady and sharp.",
        bio=(
            "Medical resident from Stockholm. Long shifts taught her to "
            "stay calm under pressure and pick her moments carefully."
        ),
    ),
    Character(
        id="kwame",
        name="Kwame",
        personality="aggressive",
        avatar_file="avatar_06.png",
        tagline="Control the game early.",
        bio=(
            "High school maths teacher from Accra. Treats every hand as "
            "a probability problem — and plays to tilt the odds."
        ),
    ),
    Character(
        id="sarah",
        name="Sarah",
        personality="conservative",
        avatar_file="avatar_07.png",
        tagline="Let them make mistakes.",
        bio=(
            "Librarian from Dublin who learned Hearts at family gatherings. "
            "Quiet, observant, and content to let others overextend."
        ),
    ),
    Character(
        id="dmitri",
        name="Dmitri",
        personality="aggressive",
        avatar_file="avatar_08.png",
        tagline="Push until they fold.",
        bio=(
            "Former chess hustler from Saint Petersburg who switched to "
            "Hearts for faster games. Plays with cold, calculated pressure."
        ),
    ),
    Character(
        id="lin",
        name="Lin",
        personality="balanced",
        avatar_file="avatar_09.png",
        tagline="Adapt or lose.",
        bio=(
            "Engineering student from Shanghai who treats every round as "
            "an optimisation problem. Switches gears mid-hand as needed."
        ),
    ),
    Character(
        id="ben",
        name="Ben",
        personality="conservative",
        avatar_file="avatar_10.png",
        tagline="Slow and steady.",
        bio=(
            "Retired postal worker from Christchurch. Learned Hearts in "
            "the break room — plays tight, trims losses, waits for openings."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def _by_personality(personality: str) -> List[Character]:
    return [c for c in ROSTER if c.personality == personality]

def pick_ai_three(seed: Optional[int] = None) -> List[Character]:
    """Return 3 distinct characters with at least one of each personality.

    `seed` for determinism in tests; `None` uses a fresh RNG.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    # Uniform sample of 3, then ensure coverage.
    picks = rng.sample(ROSTER, 3)
    covered = {c.personality for c in picks}
    for needed in PERSONALITIES:
        if needed in covered:
            continue
        # Replace the first pick whose personality is most common in `picks`
        # (so we don't lose diversity we've already got). If there's a tie,
        # take the first.
        from collections import Counter
        counts = Counter(c.personality for c in picks)
        victim_idx = next(
            i for i, c in enumerate(picks)
            if counts[c.personality] > 1 or c.personality not in covered
        )
        replacement_pool = _by_personality(needed)
        # Avoid the same character if one is already in picks.
        picks_set = set(id(c) for c in picks)
        replacement = next(
            (c for c in replacement_pool if id(c) not in picks_set),
            replacement_pool[0],
        )
        picks[victim_idx] = replacement
        covered.add(needed)
    return list(picks)


# Module-level random for the non-deterministic path. `random.Random()` is
# safe to instantiate at import; it seeds from os.urandom.
_DEFAULT_RNG = random.Random()


def draw_ai_three() -> List[Character]:
    """Non-deterministic 3-of-10 draw using a per-process RNG."""
    return pick_ai_three(seed=_DEFAULT_RNG.randint(0, 2**31 - 1))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_by_id(char_id: str) -> Character:
    """Lookup by `id`. Raises KeyError if not found."""
    for c in ROSTER:
        if c.id == char_id:
            return c
    raise KeyError(f"no character with id={char_id!r}")

def avatar_path(char: Character, assets_root: Path) -> Path:
    """Resolve a character's avatar_file against the avatars directory."""
    return assets_root / "avatars" / char.avatar_file