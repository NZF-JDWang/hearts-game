"""
Hearts game session manager — wraps HeartsEngine + AIs, manages
a single game-in-progress from creation to game-over.

One GameSession == one browser tab == one game.
The human is always player 0 (south). Players 1, 2, 3 are AIs.
"""

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from engine import (
    HeartsEngine, GameState, Card, Phase, PassDirection,
    QUEEN_OF_SPADES, TWO_OF_CLUBS, SUITS, HEARTS, SPADES, CLUBS, DIAMONDS,
)
from ai import CautiousAI, AggressiveAI, RandomAI
from roster import draw_ai_three
from ai import AI_CLASS_MAP


@dataclass
class GameEvent:
    """An event the client should react to (UI updates, animations, etc.)."""
    kind: str
    data: dict = field(default_factory=dict)


class GameSession:
    """A single in-progress game. Human is P0, AIs are P1/P2/P3."""

    HUMAN = 0

    def __init__(self):
        self.id = uuid.uuid4().hex[:12]
        self.engine = HeartsEngine()
        self._lock = asyncio.Lock()

        # Draw 3 roster characters for this game
        opponents = draw_ai_three()

        # AI class instances mapped by personality
        self.ais = [AI_CLASS_MAP[c.personality]() for c in opponents]
        self.ai_names = [c.name for c in opponents]
        self.ai_characters = opponents  # keep full Character objects for state
        self.player_names = ["You"] + self.ai_names  # P0..P3

        # State
        self.state: GameState = self.engine.new_game()
        self.events: List[GameEvent] = []
        self.ai_think_delay_ms = 700

    # ── State / serialization ───────────────────────────────────────

    def snapshot(self, viewer: int = 0) -> dict:
        """View of the game for the given player."""
        hands = []
        for p, hand in enumerate(self.state.hands):
            if p == viewer:
                hands.append([str(c) for c in hand])
            elif self.state.phase in (Phase.TRICK_END, Phase.ROUND_END, Phase.GAME_OVER):
                hands.append([str(c) for c in hand])
            else:
                # Send just the count for hidden hands
                hands.append(len(hand))

        s = self.state.to_dict()
        s["hands"] = hands
        s["player_names"] = self.player_names
        s["session_id"] = self.id
        s["valid_plays"] = [str(c) for c in self.engine.valid_plays(self.state, viewer)]
        s["ai_think_delay_ms"] = self.ai_think_delay_ms

        # Include roster character info for each AI (players 1-3)
        s["ai_roster"] = [c.to_dict() for c in self.ai_characters]

        # Pass direction name
        pass_names = {0: "Left", 1: "Right", 2: "Across", 3: "Hold (no pass)"}
        pd = s.get("pass_direction")
        if pd is not None:
            s["pass_direction_name"] = pass_names.get(pd, "Left")

        return s

    # ── Human actions ───────────────────────────────────────────────

    def pass_cards(self, player: int, cards: List[Card]) -> bool:
        if player != self.HUMAN:
            return False
        return self.engine.pass_cards(self.state, player, cards)

    def play_card(self, player: int, card: Card) -> bool:
        if player != self.HUMAN:
            return False
        return self.engine.play_card(self.state, player, card)

    def next_round(self) -> bool:
        if self.state.phase != Phase.ROUND_END:
            return False
        self.engine.next_round(self.state)
        return True

    # ── AI actions ──────────────────────────────────────────────────

    def _ai_pass(self, player: int) -> List[Card]:
        return self.ais[player - 1].choose_pass_cards(self.state.hands[player])

    def _ai_play(self, player: int) -> Card:
        return self.ais[player - 1].choose_play(self.engine, self.state, player)

    def ai_autoplay_until_human(self) -> List[GameEvent]:
        """Run all AI turns until it's the human's turn (or hand is over)."""
        events: List[GameEvent] = []

        if self.state.phase == Phase.PASSING:
            for p in range(1, 4):
                if p not in self.state.passed_cards:
                    cards = self._ai_pass(p)
                    self.engine.pass_cards(self.state, p, cards)
                    events.append(GameEvent("ai_passed", {"player": p, "cards": [str(c) for c in cards]}))

        max_safety = 200
        steps = 0
        while self.state.phase in (Phase.PLAYING, Phase.TRICK_END) and steps < max_safety:
            p = self.state.current_player
            if p == self.HUMAN:
                break

            if self.state.phase == Phase.TRICK_END:
                winner = self.engine.resolve_trick(self.state)
                events.append(GameEvent("trick_won", {"player": winner}))
                if self.state.phase == Phase.ROUND_END:
                    events.append(GameEvent("round_ended", {"scores": list(self.state.scores)}))
                    break
                continue

            card = self._ai_play(p)
            ok = self.engine.play_card(self.state, p, card)
            if not ok:
                events.append(GameEvent("ai_illegal", {"player": p, "card": str(card)}))
                break
            events.append(GameEvent("card_played", {"player": p, "card": str(card)}))

            if self.state.phase == Phase.TRICK_END:
                events.append(GameEvent("trick_complete", {"player": p}))
            steps += 1

        if self.state.phase == Phase.GAME_OVER:
            events.append(GameEvent("game_over", {"scores": list(self.state.scores), "names": list(self.player_names)}))
        elif self.state.phase == Phase.ROUND_END:
            if not any(e.kind == "round_ended" for e in events):
                events.append(GameEvent("round_ended", {"scores": list(self.state.scores)}))

        return events

    def resolve_pending_trick(self) -> Optional[GameEvent]:
        if self.state.phase != Phase.TRICK_END:
            return None
        winner = self.engine.resolve_trick(self.state)
        ev = GameEvent("trick_won", {"player": winner, "scores": list(self.state.scores)})
        if self.state.phase == Phase.GAME_OVER:
            self.events.append(ev)
            self.events.append(GameEvent("game_over", {"scores": list(self.state.scores), "names": list(self.player_names)}))
            return self.events[-1]
        if self.state.phase == Phase.ROUND_END:
            self.events.append(ev)
            self.events.append(GameEvent("round_ended", {"scores": list(self.state.scores)}))
            return self.events[-1]
        return ev


def create_session() -> GameSession:
    return GameSession()