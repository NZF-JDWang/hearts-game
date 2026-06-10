"""Tests for the 10-character roster and per-game selection."""

from collections import Counter
from pathlib import Path

import pytest

from hearts import roster
from hearts.roster import (
    PERSONALITIES,
    ROSTER,
    Character,
    avatar_path,
    draw_ai_three,
    find_by_id,
    pick_ai_three,
)

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "avatars"


# ---------------------------------------------------------------------------
# Roster structure
# ---------------------------------------------------------------------------

def test_roster_has_ten_characters():
    assert len(ROSTER) == 10


def test_roster_ids_are_unique():
    ids = [c.id for c in ROSTER]
    assert len(set(ids)) == 10, f"duplicate ids: {[i for i in ids if ids.count(i) > 1]}"


def test_roster_names_are_unique():
    names = [c.name for c in ROSTER]
    assert len(set(names)) == 10


def test_roster_avatar_files_are_unique():
    files = [c.avatar_file for c in ROSTER]
    assert len(set(files)) == 10


def test_roster_personalities_are_valid():
    for c in ROSTER:
        assert c.personality in PERSONALITIES, f"{c.id} has bad personality {c.personality}"


def test_roster_personalities_distribution_4_3_3():
    # Aggressive should be 4, balanced 3, conservative 3 so a 3-sample
    # can plausibly cover all three.
    counts = Counter(c.personality for c in ROSTER)
    assert counts == {"aggressive": 4, "balanced": 3, "conservative": 3}, counts


def test_roster_avatar_files_exist():
    for c in ROSTER:
        path = ASSETS / c.avatar_file
        assert path.is_file(), f"avatar for {c.id} ({c.avatar_file}) missing on disk"


def test_roster_avatar_files_are_128_png():
    # Quick structural check: 128x128 RGBA PNGs.
    from PIL import Image
    for c in ROSTER:
        im = Image.open(ASSETS / c.avatar_file)
        assert im.size == (128, 128), f"{c.avatar_file} is {im.size}, want 128x128"
        assert im.mode == "RGBA", f"{c.avatar_file} mode is {im.mode}, want RGBA"


def test_roster_bios_are_meaningful():
    for c in ROSTER:
        assert 20 <= len(c.bio) <= 400, f"{c.id} bio length {len(c.bio)} out of range"
        assert c.bio.endswith((".", "!", "?")), f"{c.id} bio doesn't end with punctuation"


def test_roster_taglines_are_short():
    for c in ROSTER:
        assert 1 <= len(c.tagline) <= 40, f"{c.id} tagline length {len(c.tagline)} out of range"


# ---------------------------------------------------------------------------
# Character dataclass validation
# ---------------------------------------------------------------------------

def test_character_rejects_bad_personality():
    with pytest.raises(ValueError, match="invalid personality"):
        Character(
            id="bad", name="X", personality="wild", avatar_file="avatar_01.png",
            tagline="x", bio="x",
        )


def test_character_rejects_bad_avatar_prefix():
    with pytest.raises(ValueError, match="must start with"):
        Character(
            id="bad", name="X", personality="aggressive", avatar_file="weird.png",
            tagline="x", bio="x",
        )


def test_character_rejects_long_tagline():
    with pytest.raises(ValueError, match="1\\.\\.40"):
        Character(
            id="bad", name="X", personality="aggressive", avatar_file="avatar_01.png",
            tagline="x" * 41, bio="x",
        )


# ---------------------------------------------------------------------------
# pick_ai_three
# ---------------------------------------------------------------------------

def test_pick_returns_three_distinct_characters():
    picks = pick_ai_three(seed=42)
    assert len(picks) == 3
    assert len(set(id(c) for c in picks)) == 3


def test_pick_is_deterministic_with_seed():
    a = pick_ai_three(seed=123)
    b = pick_ai_three(seed=123)
    assert [c.id for c in a] == [c.id for c in b]


def test_pick_changes_with_seed():
    seen = set()
    for seed in range(50):
        picks = pick_ai_three(seed=seed)
        seen.add(tuple(c.id for c in picks))
    assert len(seen) > 1, "pick_ai_three is constant across seeds (bug?)"


def test_pick_covers_all_three_personalities():
    # Across many draws, every draw must have at least one of each
    # personality, by construction.
    missing = []
    for seed in range(200):
        picks = pick_ai_three(seed=seed)
        ps = {c.personality for c in picks}
        for needed in PERSONALITIES:
            if needed not in ps:
                missing.append((seed, needed, [c.id for c in picks]))
                break
    assert not missing, f"some seeds missed a personality: {missing[:5]}"


def test_pick_results_only_draw_from_roster():
    valid_ids = {c.id for c in ROSTER}
    for seed in range(100):
        picks = pick_ai_three(seed=seed)
        for c in picks:
            assert c.id in valid_ids


def test_draw_ai_three_returns_three():
    picks = draw_ai_three()
    assert len(picks) == 3
    assert len(set(c.id for c in picks)) == 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_find_by_id_found():
    c = find_by_id("marco")
    assert c.name == "Marco"


def test_find_by_id_missing_raises():
    with pytest.raises(KeyError, match="no character with id"):
        find_by_id("not_a_real_id")


def test_avatar_path_resolves_under_assets():
    p = avatar_path(ROSTER[0], Path("/tmp/fake_assets"))
    assert p == Path("/tmp/fake_assets/avatars/avatar_01.png")
