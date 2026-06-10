"""Smoke tests: full game plays to completion across many seeds."""
import pytest
from hearts import engine as eng, ai


def test_full_game_completes():
    state = eng.new_game(seed=1)
    while state.phase is not eng.Phase.GAME_OVER:
        # If still in passing phase, just skip (pass NONE is set in round 4 only).
        if state.phase is eng.Phase.PASSING:
            for p in range(state.num_players):
                picks = ai.choose_pass(state, p, "balanced")
                state.pass_cards(p, picks)
            continue
        legal = eng.legal_plays(state, state.current_player_idx)
        card = ai.choose_play(state, state.current_player_idx, "balanced")
        assert card in legal
        state.play_card(state.current_player_idx, card)
    assert state.winner() is not None
    # Total points across all players is 26 per round * num_rounds.
    total = sum(state.total_scores)
    assert total % 26 == 0


@pytest.mark.parametrize("seed", [1, 7, 42, 100, 999])
@pytest.mark.parametrize("personality", ["aggressive", "balanced", "conservative"])
def test_full_game_completes_all_personalities(seed, personality):
    state = eng.new_game(seed=seed)
    while state.phase is not eng.Phase.GAME_OVER:
        if state.phase is eng.Phase.PASSING:
            for p in range(state.num_players):
                picks = ai.choose_pass(state, p, personality)
                state.pass_cards(p, picks)
            continue
        card = ai.choose_play(state, state.current_player_idx, personality)
        state.play_card(state.current_player_idx, card)
    assert state.winner() is not None


def test_pass_cycling():
    state = eng.new_game(seed=1)
    assert state.pass_direction is eng.PassDirection.LEFT
    state.round_number += 1
    state.start_round()  # round 2
    assert state.pass_direction is eng.PassDirection.RIGHT
    state.round_number += 1
    state.start_round()  # round 3
    assert state.pass_direction is eng.PassDirection.ACROSS
    state.round_number += 1
    state.start_round()  # round 4
    assert state.pass_direction is eng.PassDirection.NONE
