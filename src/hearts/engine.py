"""Hearts game engine: deal, pass, trick play, scoring, game end.

Public API:
  new_game(seed=...) -> GameState
  legal_plays(state, player) -> list[Card]
  play_card(state, player, card) -> None
  pass_cards(state, player, cards) -> None
  submit_pass(state) -> None  # for human when all 4 picks are in
  trick_winner(trick) -> int  # seat index
  score_trick(trick) -> int
  score_game(scores) -> list[int]  # apply shoot-the-moon
  trick_plays(trick) -> list[(player, card)]
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .cards import Card, Deck, Hand, Rank, Suit


class PassDirection(Enum):
    LEFT = "left"
    RIGHT = "right"
    ACROSS = "across"
    NONE = "none"

    @classmethod
    def cycle(cls, round_number: int) -> "PassDirection":
        # Round 1: LEFT, 2: RIGHT, 3: ACROSS, 4: NONE, 5: LEFT, ...
        order = [cls.LEFT, cls.RIGHT, cls.ACROSS, cls.NONE]
        return order[(round_number - 1) % 4]


class IllegalMoveError(Exception):
    pass


class Phase(Enum):
    PASSING = "passing"
    PLAYING = "playing"
    GAME_OVER = "game_over"


# Lookup: card points. Hearts = 1, Q♠ = 13, everything else = 0.
def _card_points(card: Card) -> int:
    if card.is_queen_of_spades:
        return 13
    if card.is_heart:
        return 1
    return 0


_CARD_POINTS: Dict[Tuple[int, int], int] = {
    (c.rank.value, c.suit.value): _card_points(c)
    for s in Suit for r in range(2, 15)
    for c in [Card(rank=Rank(r), suit=s)]
}


@dataclass
class Trick:
    plays: List[Tuple[int, Card]] = field(default_factory=list)
    lead_suit: Optional[Suit] = None
    complete: bool = False

    def add(self, player: int, card: Card) -> None:
        if self.lead_suit is None:
            self.lead_suit = card.suit
        self.plays.append((player, card))
        if len(self.plays) == 4:
            self.complete = True

    def plays_list(self) -> List[Tuple[int, Card]]:
        return list(self.plays)

    def winner(self) -> Optional[int]:
        if not self.complete:
            return None
        return trick_winner(self)


def trick_winner(trick: Trick) -> int:
    assert trick.lead_suit is not None and trick.plays
    # Highest card of the led suit wins.
    best_player, best_card = trick.plays[0]
    for p, c in trick.plays[1:]:
        if c.suit is trick.lead_suit and c.rank.value > best_card.rank.value:
            best_player, best_card = p, c
    return best_player


def score_trick(trick: Trick) -> int:
    return sum(_card_points(c) for _, c in trick.plays)


@dataclass
class GameState:
    num_players: int = 4
    seed: int = 0
    round_number: int = 1
    phase: Phase = Phase.PASSING
    pass_direction: PassDirection = PassDirection.LEFT
    hands: List[Hand] = field(default_factory=list)
    pending_pass: Dict[int, List[Card]] = field(default_factory=dict)
    trick: Trick = field(default_factory=Trick)
    trick_history: List[Trick] = field(default_factory=list)
    current_player_idx: int = 0
    round_scores: List[int] = field(default_factory=list)
    total_scores: List[int] = field(default_factory=list)
    hearts_broken: bool = False
    trick_points: int = 0
    player_personalities: List[str] = field(default_factory=list)
    _rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self) -> None:
        if not self.total_scores:
            self.total_scores = [0] * self.num_players
        if not self.round_scores:
            self.round_scores = [0] * self.num_players
        if not self.hands:
            self.hands = [Hand() for _ in range(self.num_players)]

    # ------------------------------------------------------------------
    # Round lifecycle
    # ------------------------------------------------------------------

    def start_round(self) -> None:
        self.pass_direction = PassDirection.cycle(self.round_number)
        self.phase = Phase.PASSING
        self.pending_pass = {}
        self.trick = Trick()
        self.trick_history = []
        self.hearts_broken = False
        self.round_scores = [0] * self.num_players
        deck = Deck.full()
        deck.shuffle(self._rng)
        dealt = deck.deal(self.num_players)
        for i, h in enumerate(dealt):
            self.hands[i] = Hand(list(h))
        # Lead: 2 of clubs holder.
        for i, h in enumerate(self.hands):
            if any(c.rank is Rank.TWO and c.suit is Suit.CLUBS for c in h):
                self.current_player_idx = i
                break
        if self.pass_direction is PassDirection.NONE:
            # No passing this round.
            self.phase = Phase.PLAYING

    def new_game(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.seed = seed
            self._rng = random.Random(seed)
        self.round_number = 1
        self.total_scores = [0] * self.num_players
        self.start_round()

    # ------------------------------------------------------------------
    # Passing
    # ------------------------------------------------------------------

    def pass_to(self, player: int) -> int:
        d = self.pass_direction
        if d is PassDirection.NONE:
            return player
        if d is PassDirection.LEFT:
            return (player + 1) % self.num_players
        if d is PassDirection.RIGHT:
            return (player - 1) % self.num_players
        if d is PassDirection.ACROSS:
            return (player + 2) % self.num_players
        return player

    def pass_cards(self, player: int, cards: List[Card]) -> None:
        if self.phase is not Phase.PASSING:
            raise IllegalMoveError("not in passing phase")
        if self.pass_direction is PassDirection.NONE:
            raise IllegalMoveError("no passing this round")
        if len(cards) != 3:
            raise IllegalMoveError(f"must pass exactly 3 cards, got {len(cards)}")
        hand_cards = list(self.hands[player].cards)
        for c in cards:
            if c not in hand_cards:
                raise IllegalMoveError(f"card {c} not in hand")
            hand_cards.remove(c)
        # Remove from hand now (state is committed).
        for c in cards:
            self.hands[player].remove(c)
        self.pending_pass[player] = list(cards)
        if len(self.pending_pass) == self.num_players:
            self._resolve_pass()

    def _resolve_pass(self) -> None:
        # Each player receives the cards passed TO them.
        for giver, cards in self.pending_pass.items():
            recipient = self.pass_to(giver)
            for c in cards:
                self.hands[recipient].add(c)
        self.pending_pass = {}
        self.phase = Phase.PLAYING
        # The 2♣ may have moved during the pass. The holder leads the first
        # trick, so re-detect the leader.
        if not self.trick_history:
            for i, h in enumerate(self.hands):
                if any(c.rank is Rank.TWO and c.suit is Suit.CLUBS
                       for c in h):
                    self.current_player_idx = i
                    break

    # ------------------------------------------------------------------
    # Trick play
    # ------------------------------------------------------------------

    def current_player(self) -> int:
        return self.current_player_idx

    def play_card(self, player: int, card: Card) -> None:
        if self.phase is Phase.GAME_OVER:
            raise IllegalMoveError("game is over")
        if player != self.current_player_idx:
            raise IllegalMoveError(f"not player {player}'s turn")
        if card not in self.hands[player].cards:
            raise IllegalMoveError(f"card {card} not in hand")
        # Use legal_plays as source of truth.
        legal = legal_plays(self, player)
        if card not in legal:
            raise IllegalMoveError(
                f"{card} is not a legal play (allowed: "
                f"{[str(c) for c in legal]})"
            )
        # Enact play
        self.hands[player].remove(card)
        self.trick.add(player, card)
        # Hearts-broken: a heart played to a non-heart trick breaks hearts.
        if card.is_heart and self.trick.lead_suit is not Suit.HEARTS:
            self.hearts_broken = True
        # Trick complete
        if self.trick.complete:
            winner = trick_winner(self.trick)
            pts = score_trick(self.trick)
            self.round_scores[winner] += pts
            self.trick_history.append(self.trick)
            # New trick
            self.trick = Trick()
            self.current_player_idx = winner
            # End of round?
            if all(len(h) == 0 for h in self.hands):
                self._end_round()
            return
        # Advance to next player
        self.current_player_idx = (self.current_player_idx + 1) % self.num_players

    # ------------------------------------------------------------------
    # Round end / scoring
    # ------------------------------------------------------------------

    def _end_round(self) -> None:
        # Apply shoot-the-moon.
        scores = list(self.round_scores)
        moon_idx = next((i for i, s in enumerate(scores) if s == 26), None)
        if moon_idx is not None:
            scores = [0 if i == moon_idx else 26 for i in range(self.num_players)]
        for i, s in enumerate(scores):
            self.total_scores[i] += s
        self.round_number += 1
        if any(s >= 100 for s in self.total_scores):
            self.phase = Phase.GAME_OVER
        else:
            self.start_round()

    def winner(self) -> Optional[int]:
        if self.phase is not Phase.GAME_OVER:
            return None
        return min(range(self.num_players), key=lambda i: self.total_scores[i])

    # ------------------------------------------------------------------
    # Test helper: build a state with explicit hands.
    # ------------------------------------------------------------------

    @classmethod
    def _new_state_for_testing(cls, player0, player1, player2, player3) -> "GameState":
        all_cards = list(player0) + list(player1) + list(player2) + list(player3)
        if len(all_cards) != 52 or len(set(all_cards)) != 52:
            raise ValueError("hands must be a valid 52-card deal (no dups)")
        gs = cls(num_players=4, seed=1, pass_direction=PassDirection.NONE)
        gs.round_number = 4  # forces pass_dir=NONE in cycle()
        gs.start_round()
        # Overwrite hands with the test hands.
        gs.hands = [Hand(list(p)) for p in (player0, player1, player2, player3)]
        # Find 2♣ holder.
        for i, h in enumerate(gs.hands):
            if any(c.rank is Rank.TWO and c.suit is Suit.CLUBS for c in h):
                gs.current_player_idx = i
                break
        return gs


# ----------------------------------------------------------------------
# Top-level helpers
# ----------------------------------------------------------------------

def new_game(seed: Optional[int] = None) -> GameState:
    gs = GameState(num_players=4, seed=seed if seed is not None else 0)
    gs.new_game(seed=seed)
    # Default personality assignment if caller doesn't override: balanced.
    gs.player_personalities = ["balanced"] * gs.num_players
    return gs


def legal_plays(state: GameState, player: int) -> List[Card]:
    """Return the legal cards player may play right now."""
    if state.phase is Phase.PASSING:
        return list(state.hands[player].cards)
    hand = state.hands[player]
    trick = state.trick
    candidates = list(hand.cards)
    # Suit-follow
    if trick.lead_suit is not None:
        held = hand.of_suit(trick.lead_suit)
        if held:
            candidates = held
    # First-trick rules
    is_first_trick = len(state.trick_history) == 0
    if is_first_trick:
        # Leading must be 2♣.
        if trick.lead_suit is None:
            two_clubs = [c for c in candidates
                         if c.rank is Rank.TWO and c.suit is Suit.CLUBS]
            return two_clubs
        # Subsequent plays: no hearts/Q♠ IF the player has any zero-point card
        # to play. Void of clubs override (any point card legal if no clubs).
        all_points = all(_card_points(c) > 0 for c in candidates)
        if all_points:
            return candidates
        # Filter out point cards.
        zero_pt = [c for c in candidates if _card_points(c) == 0]
        return zero_pt
    # Hearts-broken on lead
    if trick.lead_suit is None:
        # Determine if the player is effectively "void of safe leads": all
        # non-heart cards are Q♠ (a point card). In that case the only legal
        # lead is a heart or Q♠.
        safe_leads = [c for c in candidates
                      if not c.is_heart and not c.is_queen_of_spades]
        if state.hearts_broken:
            return candidates
        if safe_leads:
            return safe_leads
        # No safe leads: must lead a heart or Q♠. Legal = entire hand.
        return candidates
    return candidates


def pass_cards(state: GameState, player: int, cards: List[Card]) -> None:
    state.pass_cards(player, cards)


def submit_pass(state: GameState) -> None:
    """No-op: passes resolve automatically when all 4 are submitted."""
    return None


def score_game(scores: List[int]) -> List[int]:
    moon = next((i for i, s in enumerate(scores) if s == 26), None)
    if moon is not None:
        return [0 if i == moon else 26 for i in range(len(scores))]
    return list(scores)


def trick_plays(trick: Trick) -> List[Tuple[int, Card]]:
    return trick.plays_list()
