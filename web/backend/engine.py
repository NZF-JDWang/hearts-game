"""
Hearts card game engine — pure Python, no UI dependencies.

Rules implemented:
  - 4 players, standard 52-card deck
  - 2 of Clubs leads first trick
  - Must follow suit; play any card if void
  - Hearts cannot be led until broken (or only hearts remain)
  - Queen of Spades = 13 points, each Heart = 1 point
  - Shooting the Moon: take all 26 → 0 for you, +26 for everyone else
  - Card passing: Left, Right, Across, Hold (rotates each round)
  - Game ends when any player reaches 100 points
"""

import random
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Set

# ── Constants ──────────────────────────────────────────────────────────

SUITS = ("♣", "♦", "♠", "♥")
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")
RANK_VALUES = {r: i for i, r in enumerate(RANKS)}

CLUBS, DIAMONDS, SPADES, HEARTS = SUITS
QUEEN_OF_SPADES = (SPADES, "Q")
TWO_OF_CLUBS = (CLUBS, "2")
POINTS_TO_END = 100


class PassDirection(IntEnum):
    LEFT = 0
    RIGHT = 1
    ACROSS = 2
    HOLD = 3


PASS_NAMES = {PassDirection.LEFT: "Left", PassDirection.RIGHT: "Right",
              PassDirection.ACROSS: "Across", PassDirection.HOLD: "Hold"}


# ── Card helpers ───────────────────────────────────────────────────────

@dataclass(frozen=True, order=True)
class Card:
    suit: str
    rank: str

    @property
    def value(self) -> int:
        return RANK_VALUES[self.rank]

    @property
    def points(self) -> int:
        if self == Card(*QUEEN_OF_SPADES):
            return 13
        if self.suit == HEARTS:
            return 1
        return 0

    def __repr__(self):
        return f"{self.rank}{self.suit}"

    def __str__(self):
        return f"{self.rank}{self.suit}"

    @classmethod
    def from_str(cls, s: str) -> "Card":
        """Parse from 'Q♠' or '10♥' style string."""
        if s[:2] == "10":
            return cls(suit=s[2], rank="10")
        return cls(suit=s[1], rank=s[0])


def make_deck() -> List[Card]:
    return [Card(s, r) for s in SUITS for r in RANKS]


def card_sort_key(card: Card) -> Tuple[int, int]:
    return (SUITS.index(card.suit), RANK_VALUES[card.rank])


# ── Game phases ────────────────────────────────────────────────────────

class Phase(IntEnum):
    PASSING = 0
    PLAYING = 1
    TRICK_END = 2
    ROUND_END = 3
    GAME_OVER = 4


# ── Game state ─────────────────────────────────────────────────────────

@dataclass
class TrickCard:
    player: int
    card: Card


@dataclass
class GameState:
    hands: List[List[Card]] = field(default_factory=list)
    current_trick: List[TrickCard] = field(default_factory=list)
    trick_leader: int = 0
    current_player: int = 0
    scores: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    round_scores: List[int] = field(default_factory=lambda: [0, 0, 0, 0])
    hearts_broken: bool = False
    phase: Phase = Phase.PASSING
    pass_direction: PassDirection = PassDirection.LEFT
    round_number: int = 0
    trick_number: int = 0
    passed_cards: Dict[int, List[Card]] = field(default_factory=dict)
    tricks_won: List[List[Card]] = field(default_factory=lambda: [[], [], [], []])

    @property
    def is_hold_round(self) -> bool:
        return self.pass_direction == PassDirection.HOLD

    def to_dict(self) -> dict:
        return {
            "hands": [[str(c) for c in h] for h in self.hands],
            "current_trick": [{"player": tc.player, "card": str(tc.card)} for tc in self.current_trick],
            "trick_leader": self.trick_leader,
            "current_player": self.current_player,
            "scores": self.scores,
            "round_scores": self.round_scores,
            "hearts_broken": self.hearts_broken,
            "phase": int(self.phase),
            "pass_direction": int(self.pass_direction),
            "pass_direction_name": PASS_NAMES[self.pass_direction],
            "round_number": self.round_number,
            "trick_number": self.trick_number,
            "passed_cards": {str(k): [str(c) for c in v] for k, v in self.passed_cards.items()},
            "tricks_won": [[str(c) for c in tw] for tw in self.tricks_won],
        }


class HeartsEngine:
    """Full Hearts game logic — stateless transformations on GameState."""

    def new_game(self) -> GameState:
        state = GameState()
        self._deal(state)
        state.phase = Phase.PASSING if not state.is_hold_round else Phase.PLAYING
        if state.is_hold_round:
            self._set_first_player(state)
        return state

    def _deal(self, state: GameState) -> None:
        deck = make_deck()
        random.shuffle(deck)
        state.hands = [sorted(deck[i::4], key=card_sort_key) for i in range(4)]

    def _set_first_player(self, state: GameState) -> None:
        for i, hand in enumerate(state.hands):
            if Card(*TWO_OF_CLUBS) in hand:
                state.current_player = i
                state.trick_leader = i
                return

    # ── Passing ─────────────────────────────────────────────────────

    def pass_cards(self, state: GameState, player: int, cards: List[Card]) -> bool:
        if state.phase != Phase.PASSING:
            return False
        hand = state.hands[player]
        for c in cards:
            if c not in hand:
                return False
        if len(cards) != 3:
            return False
        state.passed_cards[player] = cards
        if len(state.passed_cards) == 4:
            self._execute_pass(state)
            state.phase = Phase.PLAYING
            self._set_first_player(state)
        return True

    def _execute_pass(self, state: GameState) -> None:
        direction = state.pass_direction
        received: Dict[int, List[Card]] = {i: [] for i in range(4)}

        for player, cards in state.passed_cards.items():
            for c in cards:
                state.hands[player].remove(c)
            if direction == PassDirection.LEFT:
                target = (player + 1) % 4
            elif direction == PassDirection.RIGHT:
                target = (player - 1) % 4
            elif direction == PassDirection.ACROSS:
                target = (player + 2) % 4
            else:
                target = player
            received[target].extend(cards)

        for target, cards in received.items():
            state.hands[target].extend(cards)
            state.hands[target].sort(key=card_sort_key)

        state.passed_cards = {}

    # ── Playing ─────────────────────────────────────────────────────

    def valid_plays(self, state: GameState, player: int) -> List[Card]:
        hand = state.hands[player]
        if not hand:
            return []

        # First trick of round: must lead 2♣
        if state.trick_number == 0 and not state.current_trick:
            two_clubs = Card(*TWO_OF_CLUBS)
            if two_clubs in hand:
                return [two_clubs]

        # Must follow suit if leading suit exists
        if state.current_trick:
            lead_suit = state.current_trick[0].card.suit
            follow = [c for c in hand if c.suit == lead_suit]
            if follow:
                return follow
            # Void — can play anything with restrictions on first trick
            if state.trick_number == 0:
                # Can't play points on first trick (unless only points remain)
                non_points = [c for c in hand if c.points == 0]
                if non_points:
                    return non_points
            return list(hand)

        # Leading
        if not state.hearts_broken:
            non_hearts = [c for c in hand if c.suit != HEARTS]
            if non_hearts:
                return non_hearts
        return list(hand)

    def play_card(self, state: GameState, player: int, card: Card) -> bool:
        if state.phase != Phase.PLAYING:
            return False
        if player != state.current_player:
            return False
        if card not in self.valid_plays(state, player):
            return False

        state.hands[player].remove(card)
        state.current_trick.append(TrickCard(player=player, card=card))

        if card.suit == HEARTS:
            state.hearts_broken = True

        if len(state.current_trick) == 4:
            state.phase = Phase.TRICK_END
        else:
            state.current_player = (player + 1) % 4
        return True

    def resolve_trick(self, state: GameState) -> int:
        """Resolve completed trick, return winner index."""
        if state.phase != Phase.TRICK_END:
            return -1
        lead_suit = state.current_trick[0].card.suit
        winner = max(
            (tc for tc in state.current_trick if tc.card.suit == lead_suit),
            key=lambda tc: tc.card.value
        )
        trick_cards = [tc.card for tc in state.current_trick]
        points = sum(c.points for c in trick_cards)
        state.round_scores[winner.player] += points
        state.tricks_won[winner.player].extend(trick_cards)

        state.trick_leader = winner.player
        state.current_player = winner.player
        state.current_trick = []
        state.trick_number += 1

        if state.trick_number == 13:
            self._resolve_round(state)
        else:
            state.phase = Phase.PLAYING
        return winner.player

    def _resolve_round(self, state: GameState) -> None:
        # Shooting the moon
        for i in range(4):
            if state.round_scores[i] == 26:
                state.round_scores = [26, 26, 26, 26]
                state.round_scores[i] = 0
                break

        state.scores = [s + r for s, r in zip(state.scores, state.round_scores)]
        state.round_scores = [0, 0, 0, 0]
        state.tricks_won = [[], [], [], []]

        if any(s >= POINTS_TO_END for s in state.scores):
            state.phase = Phase.GAME_OVER
        else:
            state.phase = Phase.ROUND_END

    def next_round(self, state: GameState) -> None:
        if state.phase != Phase.ROUND_END:
            return
        state.round_number += 1
        state.pass_direction = PassDirection(state.round_number % 4)
        state.hearts_broken = False
        state.trick_number = 0
        state.current_trick = []
        self._deal(state)
        state.passed_cards = {}
        if state.is_hold_round:
            state.phase = Phase.PLAYING
            self._set_first_player(state)
        else:
            state.phase = Phase.PASSING