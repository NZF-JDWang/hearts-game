"""
Hearts AI — three personalities, pure Python, no UI dependencies.

Personalities:
  - cautious: avoids taking points, plays high cards when safe
  - aggressive: tries to dump points early, targets leader
  - random: plays randomly from valid options
"""

import random
from typing import List, Optional
from engine import Card, GameState, HeartsEngine, SUITS, HEARTS, SPADES, QUEEN_OF_SPADES


AI_NAMES_POOL = [
    "Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Hank",
    "Ivy", "Jack", "Kate", "Leo", "Mia", "Nick", "Olive", "Pete",
    "Quinn", "Rose", "Sam", "Tina", "Uma", "Vic", "Wendy", "Xander",
    "Yara", "Zoe", "Arlo", "Bea", "Cleo", "Dax",
]


def pick_ai_names(count: int = 3) -> List[str]:
    return random.sample(AI_NAMES_POOL, count)


class BaseAI:
    """Base class for AI players."""

    def choose_pass_cards(self, hand: List[Card]) -> List[Card]:
        raise NotImplementedError

    def choose_play(self, engine: HeartsEngine, state: GameState, player: int) -> Card:
        raise NotImplementedError


class CautiousAI(BaseAI):
    """Avoids taking points. Passes high spades and hearts first."""

    def choose_pass_cards(self, hand: List[Card]) -> List[Card]:
        sorted_hand = sorted(hand, key=lambda c: _pass_danger(c), reverse=True)
        return sorted_hand[:3]

    def choose_play(self, engine: HeartsEngine, state: GameState, player: int) -> Card:
        valid = engine.valid_plays(state, player)
        if len(valid) == 1:
            return valid[0]

        # Try to play lowest point card
        safe = [c for c in valid if c.points == 0]
        if safe:
            # If following suit, try to play under the current trick winner
            if state.current_trick:
                lead_suit = state.current_trick[0].card.suit
                if valid[0].suit == lead_suit:
                    winning_val = max(
                        tc.card.value for tc in state.current_trick if tc.card.suit == lead_suit
                    )
                    under = [c for c in safe if c.value < winning_val]
                    if under:
                        return max(under, key=lambda c: c.value)
            return min(safe, key=lambda c: c.value)

        # Must take points — take as few as possible
        return min(valid, key=lambda c: c.points + c.value * 0.01)


class AggressiveAI(BaseAI):
    """Dumps points early and tries to target leader."""

    def choose_pass_cards(self, hand: List[Card]) -> List[Card]:
        queen = Card(*QUEEN_OF_SPADES)
        sorted_hand = sorted(hand, key=lambda c: _pass_danger(c), reverse=True)
        return sorted_hand[:3]

    def choose_play(self, engine: HeartsEngine, state: GameState, player: int) -> Card:
        valid = engine.valid_plays(state, player)
        if len(valid) == 1:
            return valid[0]

        # If we can dump the queen, do it
        queen = Card(*QUEEN_OF_SPADES)
        if queen in valid and not state.current_trick:
            # Don't lead with queen unless we have to
            non_queen = [c for c in valid if c != queen]
            if non_queen:
                return max(non_queen, key=lambda c: c.value)

        # If void, dump highest point card
        if state.current_trick:
            lead_suit = state.current_trick[0].card.suit
            following = [c for c in valid if c.suit == lead_suit]
            if not following:
                # Void! Dump dangerous cards
                points_cards = sorted(valid, key=lambda c: (c.points, c.value), reverse=True)
                return points_cards[0]

        return min(valid, key=lambda c: c.value)


class RandomAI(BaseAI):
    """Plays randomly from valid options."""

    def choose_pass_cards(self, hand: List[Card]) -> List[Card]:
        return random.sample(hand, 3)

    def choose_play(self, engine: HeartsEngine, state: GameState, player: int) -> Card:
        valid = engine.valid_plays(state, player)
        return random.choice(valid)


AI_CLASSES = {
    "cautious": CautiousAI,
    "aggressive": AggressiveAI,
    "random": RandomAI,
}

DEFAULT_AI = "cautious"


def _pass_danger(card: Card) -> float:
    """Higher = more dangerous to keep. Used to pick pass cards."""
    if card == Card(*QUEEN_OF_SPADES):
        return 100
    if card.suit == SPADES and card.rank in ("A", "K"):
        return 50 + card.value
    if card.suit == HEARTS:
        return 20 + card.value
    return card.value
# Map roster personality strings to AI classes
AI_CLASS_MAP = {
    "aggressive": AggressiveAI,
    "balanced": CautiousAI,     # balanced plays like cautious (mid-risk)
    "conservative": CautiousAI, # conservative plays very safe
    "random": RandomAI,
}
