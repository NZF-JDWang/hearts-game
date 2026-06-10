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
        id="vamp_countess",
        name="Countess Mara",
        personality="aggressive",
        avatar_file="avatar_01.png",
        tagline="Take what you want.",
        bio=(
            "An immortal aristocrat from a fallen house. She treats Hearts "
            "like a court intrigue — every Q♠ is a hostage."
        ),
    ),
    Character(
        id="mad_hatter",
        name="Thaddeus Brass",
        personality="balanced",
        avatar_file="avatar_02.png",
        tagline="Calibrate, then commit.",
        bio=(
            "Steampunk inventor who runs every hand through a small brass "
            "differential engine. Never over-extends, never under-estimates."
        ),
    ),
    Character(
        id="jazz_singer",
        name="Lina Holloway",
        personality="conservative",
        avatar_file="avatar_03.png",
        tagline="A whisper wins a room.",
        bio=(
            "A 1920s cabaret singer who learned patience between sets. "
            "Holds the line, lets the others over-play, picks up the mess."
        ),
    ),
    Character(
        id="hacker",
        name="Zero",
        personality="aggressive",
        avatar_file="avatar_04.png",
        tagline="Already inside the trick.",
        bio=(
            "Grey-hat pentester who treats Hearts as a stack to be popped. "
            "Will burn a hand to read yours."
        ),
    ),
    Character(
        id="samurai",
        name="Reza Hayashi",
        personality="balanced",
        avatar_file="avatar_05.png",
        tagline="One cut, no more.",
        bio=(
            "A ronin of the cherry-blossom school. Waits for the moment the "
            "trick is hers, then takes it cleanly."
        ),
    ),
    Character(
        id="disco_queen",
        name="Vee Stardust",
        personality="aggressive",
        avatar_file="avatar_06.png",
        tagline="Every hand is a comeback.",
        bio=(
            "Mirror-ball survivor of the disco wars. Sling-shot heart cards "
            "across the table like sequins. Pure spectacle."
        ),
    ),
    Character(
        id="mystic",
        name="Wren of the Hollow",
        personality="conservative",
        avatar_file="avatar_07.png",
        tagline="The forest is patient.",
        bio=(
            "A hedge-witch who keeps a candle-lit ledger of every card she "
            "has ever seen played. Slow, careful, and you never notice her."
        ),
    ),
    Character(
        id="pirate",
        name="Captain Saul",
        personality="aggressive",
        avatar_file="avatar_08.png",
        tagline="Booty first, heart last.",
        bio=(
            "Privateer turned cardsharp. Reads the wind (and the lead suit) "
            "and goes straight for the chest."
        ),
    ),
    Character(
        id="mad_scientist",
        name="Dr. Indy Vex",
        personality="balanced",
        avatar_file="avatar_09.png",
        tagline="Hypothesis: you can't.",
        bio=(
            "Abolished from three academies for unethical shuffling. Plays a "
            "near-optimal game, occasionally stops to take notes on you."
        ),
    ),
    Character(
        id="grandmaster",
        name="Aurelia Voss",
        personality="conservative",
        avatar_file="avatar_10.png",
        tagline="The board remembers.",
        bio=(
            "Three-time under-21 world finalist. Treats Hearts as a "
            "long-game and only deviates from the book with cause."
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
