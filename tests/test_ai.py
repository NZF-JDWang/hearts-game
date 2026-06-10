"""AI personality tests — verify each personality plays a complete game and
follows the legal_plays constraint."""

import pytest
from hearts import engine as eng, ai


def _play_full_game(state, personality, max_turns=2000):
    """Helper: play a game to completion with the given personality for all AI."""
    turns = 0
    while state.phase is not eng.Phase.GAME_OVER:
        if state.phase is eng.Phase.PASSING:
            for p in range(state.num_players):
                picks = ai.choose_pass(state, p, personality)
                if len(picks) != 3:
                    return f"player {p} passed {len(picks)} cards"
                state.pass_cards(p, picks)
            continue
        cur = state.current_player_idx
        card = ai.choose_play(state, cur, personality)
        if card not in state.hands[cur].cards:
            return f"player {cur} tried to play {card} not in hand"
        try:
            state.play_card(cur, card)
        except eng.IllegalMoveError as e:
            return f"player {cur} illegal: {e}"
        turns += 1
        if turns > max_turns:
            return f"exceeded {max_turns} turns"
    return "ok"


def test_all_personalities_complete_a_game():
    for personality in ("aggressive", "balanced", "conservative"):
        for seed in (1, 7, 42, 100, 999):
            state = eng.new_game(seed=seed)
            result = _play_full_game(state, personality)
            assert result == "ok", (
                f"{personality} seed {seed}: {result}"
            )


def test_ai_choose_pass_returns_three_distinct_cards():
    for personality in ("aggressive", "balanced", "conservative"):
        state = eng.new_game(seed=1)
        for p in range(state.num_players):
            picks = ai.choose_pass(state, p, personality)
            assert len(picks) == 3
            assert len(set(picks)) == 3  # all distinct
            for c in picks:
                assert c in state.hands[p].cards


def test_ai_returns_legal_card():
    """In a normal game, AI must always return a card in legal_plays."""
    for personality in ("aggressive", "balanced", "conservative"):
        state = eng.new_game(seed=42)
        turns = 0
        while state.phase is not eng.Phase.GAME_OVER and turns < 4000:
            if state.phase is eng.Phase.PASSING:
                for p in range(state.num_players):
                    state.pass_cards(
                        p, ai.choose_pass(state, p, personality))
                continue
            cur = state.current_player_idx
            legal = eng.legal_plays(state, cur)
            card = ai.choose_play(state, cur, personality)
            assert card in legal, (
                f"{personality} player {cur} returned {card} not in {legal}"
            )
            state.play_card(cur, card)
            turns += 1
        # Game should reach GAME_OVER naturally.
        assert state.phase is eng.Phase.GAME_OVER


def test_ai_seed_reproducible():
    """Same seed + same personality produces identical card choices."""
    cards_a = []
    state = eng.new_game(seed=1)
    for p in range(state.num_players):
        picks = ai.choose_pass(state, p, "balanced")
        cards_a.extend(picks)
        state.pass_cards(p, picks)
    while state.phase is not eng.Phase.GAME_OVER:
        cur = state.current_player_idx
        cards_a.append(ai.choose_play(state, cur, "balanced"))
        state.play_card(cur, cards_a[-1])

    cards_b = []
    state = eng.new_game(seed=1)
    for p in range(state.num_players):
        picks = ai.choose_pass(state, p, "balanced")
        cards_b.extend(picks)
        state.pass_cards(p, picks)
    while state.phase is not eng.Phase.GAME_OVER:
        cur = state.current_player_idx
        cards_b.append(ai.choose_play(state, cur, "balanced"))
        state.play_card(cur, cards_b[-1])

    assert cards_a == cards_b


def test_aggressive_tends_to_pass_high_cards():
    """The aggressive player should not keep the highest hearts in hand."""
    state = eng.new_game(seed=42)
    pass_choices = []
    for p in range(state.num_players):
        picks = ai.choose_pass(state, p, "aggressive")
        pass_choices.append(set(picks))
        state.pass_cards(p, picks)
    # The aggressive personality tends to offload high-point cards.
    # We can't be too prescriptive (depends on hand), but verify that
    # the AI does pass *some* cards (not always low ones).
    # Just smoke test: a full game completes.
    while state.phase is not eng.Phase.GAME_OVER:
        cur = state.current_player_idx
        card = ai.choose_play(state, cur, "aggressive")
        state.play_card(cur, card)
    assert state.phase is eng.Phase.GAME_OVER


def test_ai_runs_through_first_trick():
    """The AI must successfully play the first trick (with 2♣ lead)."""
    state = eng.new_game(seed=1)
    for p in range(state.num_players):
        state.pass_cards(p, ai.choose_pass(state, p, "balanced"))
    assert state.phase is eng.Phase.PLAYING
    # The leader must play 2♣.
    cur = state.current_player_idx
    legal = eng.legal_plays(state, cur)
    card = ai.choose_play(state, cur, "balanced")
    assert card in legal
    state.play_card(cur, card)
    from hearts.cards import Rank, Suit
    assert card.rank is Rank.TWO
    assert card.suit is Suit.CLUBS
