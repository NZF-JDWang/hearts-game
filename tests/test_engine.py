"""Hearts engine tests — rules, scoring, trick resolution."""

import pytest
from hearts.cards import Card, Rank, Suit, Hand
from hearts import engine as eng


# ---------------------------------------------------------------------------
# Card / Hand basics
# ---------------------------------------------------------------------------

def test_deck_has_52_unique_cards():
    deck = list(eng.Deck.full().cards)
    assert len(deck) == 52
    assert len(set(deck)) == 52


def test_deck_deal_4_ways():
    import random
    deck = eng.Deck.full()
    deck.shuffle(random.Random(1))
    hands = deck.deal(4)
    assert all(len(h) == 13 for h in hands)
    union = [c for h in hands for c in h]
    assert len(set(union)) == 52


def test_hand_sort():
    h = Hand([Card(rank=Rank.ACE, suit=Suit.HEARTS),
              Card(rank=Rank.TWO, suit=Suit.CLUBS),
              Card(rank=Rank.KING, suit=Suit.SPADES)])
    sorted_cards = h.sorted_cards()
    assert sorted_cards[0].rank is Rank.TWO
    assert sorted_cards[-1].rank is Rank.ACE


def test_card_str():
    c = Card(rank=Rank.QUEEN, suit=Suit.HEARTS)
    assert str(c) == "Q♥"


def test_card_is_heart_and_qs():
    assert Card(rank=Rank.FIVE, suit=Suit.HEARTS).is_heart
    assert not Card(rank=Rank.FIVE, suit=Suit.SPADES).is_heart
    assert Card(rank=Rank.QUEEN, suit=Suit.SPADES).is_queen_of_spades
    assert not Card(rank=Rank.KING, suit=Suit.SPADES).is_queen_of_spades


# ---------------------------------------------------------------------------
# Pass direction cycling
# ---------------------------------------------------------------------------

def test_pass_cycle_left_right_across_none():
    assert eng.PassDirection.cycle(1) is eng.PassDirection.LEFT
    assert eng.PassDirection.cycle(2) is eng.PassDirection.RIGHT
    assert eng.PassDirection.cycle(3) is eng.PassDirection.ACROSS
    assert eng.PassDirection.cycle(4) is eng.PassDirection.NONE
    assert eng.PassDirection.cycle(5) is eng.PassDirection.LEFT


# ---------------------------------------------------------------------------
# Trick winner
# ---------------------------------------------------------------------------

def test_trick_winner_highest_of_led_suit():
    trick = eng.Trick()
    trick.add(0, Card(rank=Rank.FIVE, suit=Suit.SPADES))
    trick.add(1, Card(rank=Rank.KING, suit=Suit.SPADES))
    trick.add(2, Card(rank=Rank.SEVEN, suit=Suit.HEARTS))
    trick.add(3, Card(rank=Rank.TEN, suit=Suit.SPADES))
    assert eng.trick_winner(trick) == 1


def test_trick_winner_ignores_off_suit():
    trick = eng.Trick()
    trick.add(0, Card(rank=Rank.ACE, suit=Suit.HEARTS))
    trick.add(1, Card(rank=Rank.TWO, suit=Suit.HEARTS))
    trick.add(2, Card(rank=Rank.THREE, suit=Suit.HEARTS))
    trick.add(3, Card(rank=Rank.KING, suit=Suit.SPADES))
    assert eng.trick_winner(trick) == 0  # A♥ is highest of led suit


def test_trick_winner_empty_raises():
    trick = eng.Trick()
    with pytest.raises(AssertionError):
        eng.trick_winner(trick)


# ---------------------------------------------------------------------------
# Score trick
# ---------------------------------------------------------------------------

def test_score_trick_all_hearts():
    trick = eng.Trick()
    trick.add(0, Card(rank=Rank.FIVE, suit=Suit.HEARTS))
    trick.add(1, Card(rank=Rank.SEVEN, suit=Suit.HEARTS))
    trick.add(2, Card(rank=Rank.THREE, suit=Suit.HEARTS))
    trick.add(3, Card(rank=Rank.NINE, suit=Suit.HEARTS))
    assert eng.score_trick(trick) == 4


def test_score_trick_with_qs():
    trick = eng.Trick()
    trick.add(0, Card(rank=Rank.ACE, suit=Suit.HEARTS))
    trick.add(1, Card(rank=Rank.QUEEN, suit=Suit.SPADES))
    trick.add(2, Card(rank=Rank.FIVE, suit=Suit.CLUBS))
    trick.add(3, Card(rank=Rank.TWO, suit=Suit.DIAMONDS))
    assert eng.score_trick(trick) == 14  # 1 + 13


def test_score_trick_zero():
    trick = eng.Trick()
    trick.add(0, Card(rank=Rank.TWO, suit=Suit.CLUBS))
    trick.add(1, Card(rank=Rank.FIVE, suit=Suit.CLUBS))
    trick.add(2, Card(rank=Rank.SEVEN, suit=Suit.CLUBS))
    trick.add(3, Card(rank=Rank.KING, suit=Suit.CLUBS))
    assert eng.score_trick(trick) == 0


# ---------------------------------------------------------------------------
# score_game — shoot the moon
# ---------------------------------------------------------------------------

def test_score_game_no_moon():
    assert eng.score_game([5, 7, 3, 11]) == [5, 7, 3, 11]


def test_score_game_moon_player_0():
    assert eng.score_game([26, 0, 0, 0]) == [0, 26, 26, 26]


def test_score_game_moon_player_2():
    assert eng.score_game([0, 0, 26, 0]) == [26, 26, 0, 26]


def test_score_game_moon_handles_partial():
    """If someone has 26 points, shoot-the-moon applies. Other players' scores
    from the same round are wiped and replaced with 26."""
    assert eng.score_game([26, 5, 5, 5]) == [0, 26, 26, 26]


# ---------------------------------------------------------------------------
# Pass: validation
# ---------------------------------------------------------------------------

def test_pass_must_be_three_cards():
    state = eng.new_game(seed=1)
    h = state.hands[0].cards
    with pytest.raises(eng.IllegalMoveError):
        state.pass_cards(0, [h[0], h[1]])


def test_pass_cards_not_in_hand_raises():
    state = eng.new_game(seed=1)
    h = state.hands[0].cards
    h1 = state.hands[1].cards
    bad = [h[0], h[1], h1[0]]
    with pytest.raises(eng.IllegalMoveError):
        state.pass_cards(0, bad)


def test_pass_resolves_when_all_submit():
    state = eng.new_game(seed=1)
    for p in range(4):
        picks = [c for c in state.hands[p].cards[:3]]
        state.pass_cards(p, picks)
    assert state.phase is eng.Phase.PLAYING
    total = sum(len(h) for h in state.hands)
    assert total == 52


def test_pass_none_round_skips_phase():
    state = eng.new_game(seed=1)
    state.round_number = 4
    state.start_round()
    assert state.pass_direction is eng.PassDirection.NONE
    assert state.phase is eng.Phase.PLAYING


def test_pass_after_passing_raises():
    state = eng.new_game(seed=1)
    for p in range(4):
        state.pass_cards(p, state.hands[p].cards[:3])
    # Now phase is PLAYING; passing again should raise.
    with pytest.raises(eng.IllegalMoveError):
        state.pass_cards(0, state.hands[0].cards[:3])


def test_pass_in_none_round_raises():
    state = eng.new_game(seed=1)
    state.round_number = 4
    state.start_round()
    assert state.pass_direction is eng.PassDirection.NONE
    with pytest.raises(eng.IllegalMoveError):
        state.pass_cards(0, state.hands[0].cards[:3])


# ---------------------------------------------------------------------------
# Pass: card movement
# ---------------------------------------------------------------------------

def test_pass_left_moves_to_left_neighbor():
    """Round 1: pass LEFT — player 0's cards go to player 1."""
    from hearts import ai
    state = eng.new_game(seed=1)
    # Capture player 0's hand before pass.
    pre0 = list(state.hands[0].cards)
    # Capture player 1's hand.
    pre1 = list(state.hands[1].cards)
    # Player 0 passes 3 cards.
    picked = pre0[:3]
    state.pass_cards(0, picked)
    # Player 1 has not passed yet, so the pass hasn't resolved.
    # Resolve by having everyone pass.
    for p in range(1, 4):
        state.pass_cards(p, state.hands[p].cards[:3])
    # Player 0's original 3 cards are now in player 1's hand.
    for c in picked:
        assert c in state.hands[1].cards
    # Player 0's hand is now their original 10 + 3 from player 3.
    # But player 0 should not still have any of the picked cards.
    for c in picked:
        assert c not in state.hands[0].cards


# ---------------------------------------------------------------------------
# Legal plays — first trick
# ---------------------------------------------------------------------------

def test_legal_plays_first_trick_must_lead_2c():
    state = eng.new_game(seed=1)
    # Submit pass for all 4 players to enter PLAYING phase.
    for p in range(4):
        state.pass_cards(p, state.hands[p].cards[:3])
    assert state.phase is eng.Phase.PLAYING
    leader = state.current_player_idx
    legal = eng.legal_plays(state, leader)
    assert Card(rank=Rank.TWO, suit=Suit.CLUBS) in legal
    assert all(c.rank is Rank.TWO and c.suit is Suit.CLUBS for c in legal)


def test_legal_plays_first_trick_void_clubs_allows_points():
    """First trick, void of clubs: any card in hand is legal."""
    state = eng.new_game(seed=1)
    for p in range(4):
        state.pass_cards(p, state.hands[p].cards[:3])
    leader = state.current_player_idx
    state.play_card(leader, Card(rank=Rank.TWO, suit=Suit.CLUBS))
    # Find a player with no clubs and check.
    for p in range(4):
        if not state.hands[p].of_suit(Suit.CLUBS):
            legal = eng.legal_plays(state, p)
            # Should be all cards in hand (since void of clubs).
            assert set(legal) == set(state.hands[p].cards)
            return
    # If all players have at least one club, this test is moot.
    pytest.skip("no player was void of clubs in this seed")


# ---------------------------------------------------------------------------
# Legal plays — following
# ---------------------------------------------------------------------------

def test_legal_plays_suit_follow():
    state = eng.new_game(seed=1)
    for p in range(4):
        state.pass_cards(p, state.hands[p].cards[:3])
    from hearts import ai
    # Play through round 1 fully to get past first trick.
    while len(state.trick_history) == 0:
        cur = state.current_player_idx
        legal = eng.legal_plays(state, cur)
        assert legal, f"empty legal at player {cur}"
        card = ai.choose_play(state, cur, "balanced")
        assert card in legal
        state.play_card(cur, card)
    # Now we are mid-round. If a player leads, the next player follows suit.
    # Find a player with cards of multiple suits and have them lead.
    lead = state.current_player_idx
    if state.hands[lead].of_suit(Suit.SPADES):
        low = min(state.hands[lead].of_suit(Suit.SPADES),
                  key=lambda c: c.rank.value)
        state.play_card(lead, low)
        # Next player: if they have spades, must follow.
        cur2 = state.current_player_idx
        held = state.hands[cur2].of_suit(Suit.SPADES)
        legal = eng.legal_plays(state, cur2)
        if held:
            assert all(c.suit is Suit.SPADES for c in legal)


def test_legal_plays_hearts_locked_when_not_broken():
    state = eng.new_game(seed=1)
    for p in range(4):
        state.pass_cards(p, state.hands[p].cards[:3])
    from hearts import ai
    # Play through round 1 fully.
    while len(state.trick_history) == 0:
        cur = state.current_player_idx
        legal = eng.legal_plays(state, cur)
        card = ai.choose_play(state, cur, "balanced")
        state.play_card(cur, card)
    # If hearts_broken already, skip.
    if state.hearts_broken:
        pytest.skip("hearts already broken in this seed")
    # Find the next leader.
    lead = state.current_player_idx
    # If the lead has any non-point non-heart cards, leading must be one of them.
    safe = [c for c in state.hands[lead].cards
            if not c.is_heart and not c.is_queen_of_spades]
    legal = eng.legal_plays(state, lead)
    if safe:
        assert all(not c.is_heart and not c.is_queen_of_spades for c in legal)
    else:
        # If no safe leads, hearts/Q♠ are legal.
        assert set(legal) == set(state.hands[lead].cards)


# ---------------------------------------------------------------------------
# play_card illegal moves
# ---------------------------------------------------------------------------

def test_play_wrong_player_raises():
    state = eng.new_game(seed=1)
    leader = state.current_player_idx
    wrong = (leader + 1) % 4
    card = state.hands[wrong].cards[0]
    with pytest.raises(eng.IllegalMoveError):
        state.play_card(wrong, card)


def test_play_card_not_in_hand_raises():
    state = eng.new_game(seed=1)
    leader = state.current_player_idx
    fake = Card(rank=Rank.TWO, suit=Suit.HEARTS)
    if fake not in state.hands[leader].cards:
        with pytest.raises(eng.IllegalMoveError):
            state.play_card(leader, fake)


def test_play_illegal_suit_raises():
    """If you hold the led suit, you must follow it."""
    state = eng.new_game(seed=1)
    leader = state.current_player_idx
    state.play_card(leader, Card(rank=Rank.TWO, suit=Suit.CLUBS))
    # Find a player with at least one club and an off-suit card.
    for p in range(4):
        clubs = state.hands[p].of_suit(Suit.CLUBS)
        off = [c for c in state.hands[p].cards if c.suit is not Suit.CLUBS]
        if clubs and off:
            with pytest.raises(eng.IllegalMoveError):
                state.play_card(p, off[0])
            return
    pytest.skip("no player with both clubs and off-suit")


# ---------------------------------------------------------------------------
# Hearts broken
# ---------------------------------------------------------------------------

def test_hearts_broken_after_heart_played_to_non_heart_trick():
    state = eng.new_game(seed=1)
    from hearts import ai
    # Force one round.
    while len(state.trick_history) == 0:
        cur = state.current_player_idx
        legal = eng.legal_plays(state, cur)
        card = ai.choose_play(state, cur, "balanced")
        state.play_card(cur, card)
    # Check hearts_broken reflects whether any heart has been played.
    any_heart = any(c.is_heart
                    for t in state.trick_history
                    for _, c in t.plays)
    assert state.hearts_broken == any_heart


# ---------------------------------------------------------------------------
# End of round / game over
# ---------------------------------------------------------------------------

def test_round_number_increments_after_round_end():
    state = eng.new_game(seed=1)
    assert state.round_number == 1
    for h in state.hands:
        h.cards = []
    state._end_round()
    assert state.round_number == 2


def test_game_over_at_100_points():
    state = eng.new_game(seed=1)
    # Drive game to a state where a player reaches 100. Easier: force
    # total_scores and empty hands to trigger end-of-round logic.
    state.total_scores = [99, 50, 50, 50]
    for h in state.hands:
        h.cards = []
    state._end_round()
    # After end, game should be over because the new totals include
    # the round's scores. If round scores were 0, totals stay 99/50/50/50 —
    # so the next round starts. We need to force a 1-point round to push
    # someone over 100.
    # Manually set phase and end it again.
    state.total_scores[0] = 100
    state.phase = eng.Phase.PLAYING
    for h in state.hands:
        h.cards = []
    state._end_round()
    assert state.phase is eng.Phase.GAME_OVER
    assert state.winner() is not None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_legal_plays_empty_when_pass_phase():
    """legal_plays in passing phase returns the full hand."""
    state = eng.new_game(seed=1)
    assert state.phase is eng.Phase.PASSING
    for p in range(4):
        legal = eng.legal_plays(state, p)
        assert set(legal) == set(state.hands[p].cards)


def test_legal_plays_when_only_hearts_can_lead():
    """Player with only hearts + Q♠ can lead any of them."""
    # Construct a minimal test: a hand with only hearts + Q♠, leading.
    test_hand = [Card(rank=Rank.ACE, suit=Suit.HEARTS),
                 Card(rank=Rank.KING, suit=Suit.HEARTS),
                 Card(rank=Rank.QUEEN, suit=Suit.SPADES)]
    gs = eng.GameState(num_players=2)
    gs.hands = [Hand(test_hand), Hand([])]
    gs.phase = eng.Phase.PLAYING
    gs.hearts_broken = False
    gs.trick = eng.Trick()
    gs.trick_history = [eng.Trick()]  # mark as past first trick
    legal = eng.legal_plays(gs, 0)
    # All three are legal leads because no safe leads exist.
    assert set(legal) == set(test_hand)
