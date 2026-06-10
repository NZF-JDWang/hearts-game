"""AI opponents. Three personalities: aggressive, balanced, conservative.

Public API:
  choose_pass(state, player, personality) -> list[Card] (3 cards)
  choose_play(state, player, personality) -> Card
"""

from __future__ import annotations

from typing import List

from .cards import Card, Rank, Suit
from .engine import GameState, legal_plays, _card_points


def choose_pass(state: GameState, player: int, personality: str) -> List[Card]:
    hand = list(state.hands[player].cards)
    if personality == "aggressive":
        # Dump high cards; try to unload Q♠ and A/K hearts/spades.
        return _pick_pass_aggressive(hand)
    if personality == "balanced":
        return _pick_pass_balanced(hand)
    # conservative
    return _pick_pass_conservative(hand)


def _pick_pass_aggressive(hand: List[Card]) -> List[Card]:
    """Aggressive: dump the Q♠ first, then high hearts, then high off-suit."""
    sorted_cards = sorted(hand, key=lambda c: -_danger_score(c))
    return sorted_cards[:3]


def _pick_pass_balanced(hand: List[Card]) -> List[Card]:
    """Balanced: dump A/K of spades and clubs, keep hearts low."""
    sorted_cards = sorted(hand, key=lambda c: -_danger_score(c) * 0.7)
    return sorted_cards[:3]


def _pick_pass_conservative(hand: List[Card]) -> List[Card]:
    """Conservative: dump high off-suit; try to keep clubs/diamonds control."""
    hearts = [c for c in hand if c.is_heart]
    others = [c for c in hand if not c.is_heart]
    others.sort(key=lambda c: -_danger_score(c))
    picks: List[Card] = []
    # First two: highest off-suit.
    picks.extend(others[:2])
    # Third: lowest heart (unload the small heart to a void target).
    if hearts:
        picks.append(min(hearts, key=lambda c: c.rank.value))
    else:
        picks.append(others[2])
    return picks[:3]


def _danger_score(card: Card) -> float:
    """Higher = more dangerous to keep."""
    if card.is_queen_of_spades:
        return 100.0
    if card.is_heart:
        # A♥/K♥/Q♥/J♥ are big trouble.
        return 20.0 + card.rank.value
    if card.suit is Suit.SPADES:
        return 10.0 + card.rank.value
    if card.suit is Suit.CLUBS:
        return 8.0 + card.rank.value
    return 5.0 + card.rank.value * 0.2


def choose_play(state: GameState, player: int, personality: str) -> Card:
    legal = legal_plays(state, player)
    if not legal:
        # Defensive: fall back to a hand card. Engine should never do this.
        return min(state.hands[player].cards,
                   key=lambda c: (_card_points(c), c.rank.value))
    if len(legal) == 1:
        return legal[0]
    if state.trick.lead_suit is None:
        return _choose_lead(state, player, personality, legal)
    return _choose_follow(state, player, personality, legal)


def _choose_lead(state: GameState, player: int, personality: str,
                 legal: List[Card]) -> Card:
    if not legal:
        # Defensive: engine should never return an empty legal list, but
        # don't crash. Return the safest card in hand.
        return min(state.hands[player].cards, key=lambda c: _danger_score(c))
    hand = list(state.hands[player].cards)
    is_first_trick = len(state.trick_history) == 0
    if is_first_trick:
        # Must lead 2♣.
        return next(c for c in legal if c.rank is Rank.TWO and c.suit is Suit.CLUBS)
    if personality == "aggressive":
        # Lead the most damaging card: Q♠ if held, else high heart, else high off-suit.
        if any(c.is_queen_of_spades for c in legal):
            return next(c for c in legal if c.is_queen_of_spades)
        if any(c.is_heart for c in legal):
            return max([c for c in legal if c.is_heart], key=lambda c: c.rank.value)
        return max(legal, key=lambda c: c.rank.value)
    if personality == "balanced":
        # Lead a moderately high off-suit, prefer a suit we have several of.
        suit_counts = {s: sum(1 for c in hand if c.suit is s) for s in Suit}
        legal_sorted = sorted(
            legal,
            key=lambda c: (-(suit_counts[c.suit] - 1), -c.rank.value),
        )
        # Avoid leading singleton hearts (suit count = 1) at the top of the list.
        for c in legal_sorted:
            if c.is_heart and suit_counts[c.suit] == 1:
                continue
            return c
        return legal_sorted[0]
    # conservative
    # Lead low from a long suit. Avoid leading hearts unless broken or only-hearts.
    if not legal:
        # Defensive: the engine guarantees at least one legal card. If somehow
        # we got an empty list, fall through to the leader-2♣ rule below.
        pass
    if state.hearts_broken:
        non_hearts = [c for c in legal if not c.is_heart]
        if non_hearts:
            non_hearts.sort(key=lambda c: c.rank.value)
            return non_hearts[0]
    if any(not c.is_heart for c in legal):
        safe = [c for c in legal if not c.is_heart]
        safe.sort(key=lambda c: c.rank.value)
        return safe[0]
    if legal:
        return min(legal, key=lambda c: c.rank.value)
    # Hard fallback: pick anything in hand. Should never happen.
    return min(state.hands[player].cards, key=lambda c: _danger_score(c))


def _choose_follow(state: GameState, player: int, personality: str,
                   legal: List[Card]) -> Card:
    trick = state.trick
    led = trick.lead_suit
    # Find current highest in trick of led suit.
    if led is not None:
        led_in_trick = [c for _, c in trick.plays if c.suit is led]
        if led_in_trick:
            highest = max(led_in_trick, key=lambda c: c.rank.value)
        else:
            highest = None
    else:
        highest = None
    if personality == "aggressive":
        # Try to take the trick with the highest card that beats current.
        if highest is not None:
            beating = [c for c in legal if c.suit is led and c.rank.value > highest.rank.value]
            if beating:
                return min(beating, key=lambda c: c.rank.value)
        # Can't beat it: dump the most dangerous card.
        return max(legal, key=lambda c: _danger_score(c))
    if personality == "balanced":
        # Avoid taking the trick if we don't have to.
        if highest is not None:
            beating = [c for c in legal if c.suit is led and c.rank.value > highest.rank.value]
            if not beating:
                # All losers. Dump the highest one (we have to play one).
                return max(legal, key=lambda c: c.rank.value)
            # Try to win cheap.
            return min(beating, key=lambda c: c.rank.value)
        # Void in led suit. Slough highest-point card.
        return max(legal, key=lambda c: _card_points(c))
    # conservative
    if highest is not None:
        beating = [c for c in legal if c.suit is led and c.rank.value > highest.rank.value]
        if beating:
            # Win as cheaply as possible.
            return min(beating, key=lambda c: c.rank.value)
        # Dump the safest (lowest point, then lowest rank) losing card.
        return min(legal, key=lambda c: (_card_points(c), c.rank.value))
    # Void: dump the most expensive card we can.
    return max(legal, key=lambda c: (_card_points(c), _danger_score(c)))
