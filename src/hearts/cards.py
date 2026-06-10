"""Card primitives: Card, Suit, Rank, Deck, Hand."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Iterable, List


class Suit(IntEnum):
    CLUBS = 0
    DIAMONDS = 1
    SPADES = 2
    HEARTS = 3

    @property
    def char(self) -> str:
        return "♣♦♠♥"[self.value]

    @property
    def letter(self) -> str:
        return "cdsh"[self.value]

    @property
    def color(self) -> str:
        return "black" if self in (Suit.CLUBS, Suit.SPADES) else "red"


class Rank(IntEnum):
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13
    ACE = 14

    @property
    def short(self) -> str:
        return {2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8",
                9: "9", 10: "10", 11: "J", 12: "Q", 13: "K", 14: "A"}[self.value]


@dataclass(frozen=True, order=True)
class Card:
    rank: Rank
    suit: Suit

    @property
    def is_heart(self) -> bool:
        return self.suit is Suit.HEARTS

    @property
    def is_queen_of_spades(self) -> bool:
        return self.suit is Suit.SPADES and self.rank is Rank.QUEEN

    def __str__(self) -> str:
        return f"{self.rank.short}{self.suit.char}"


@dataclass
class Deck:
    cards: List[Card] = field(default_factory=list)

    @classmethod
    def full(cls) -> "Deck":
        return cls([Card(rank=Rank(r), suit=Suit(s))
                    for s in Suit for r in range(2, 15)])

    def shuffle(self, rng) -> None:
        import random
        for i in range(len(self.cards) - 1, 0, -1):
            j = rng.randrange(i + 1) if hasattr(rng, "randrange") else rng.randint(0, i)
            self.cards[i], self.cards[j] = self.cards[j], self.cards[i]

    def deal(self, n_players: int) -> List[List[Card]]:
        """Deal round-robin to n_players hands."""
        hands = [[] for _ in range(n_players)]
        for i, card in enumerate(self.cards):
            hands[i % n_players].append(card)
        for h in hands:
            h.sort()
        return hands


@dataclass
class Hand:
    cards: List[Card] = field(default_factory=list)

    def add(self, card: Card) -> None:
        self.cards.append(card)
        self.cards.sort()

    def remove(self, card: Card) -> None:
        self.cards.remove(card)

    def has(self, card: Card) -> bool:
        return card in self.cards

    def of_suit(self, suit: Suit) -> List[Card]:
        return [c for c in self.cards if c.suit is suit]

    def non_suit(self, suit: Suit) -> List[Card]:
        return [c for c in self.cards if c.suit is not suit]

    def only_hearts(self) -> bool:
        return all(c.is_heart for c in self.cards) and bool(self.cards)

    def has_only_suit(self, suit: Suit) -> bool:
        return all(c.suit is suit for c in self.cards) and bool(self.cards)

    def has_only_hearts(self) -> bool:
        return self.only_hearts()

    def cards_of_suit(self, suit: Suit) -> List[Card]:
        return self.of_suit(suit)

    def sorted_cards(self) -> List[Card]:
        return sorted(self.cards)

    def to_list(self) -> List[Card]:
        return list(self.cards)

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self):
        return iter(self.cards)

    def __contains__(self, card) -> bool:
        return card in self.cards
