"""Pygame UI for BlaksiteLab Hearts.

Features
--------
* Menu screen (start, settings, help, quit).
* Settings (seed entry, card back choice, personality shuffle).
* Game screen with:
  - Full trick animation: cards deal in sequentially and the winning card
    is highlighted + sloughed (cards shrink + fade) before the trick clears.
  - Tricks-won counter per player (with point totals).
  - Player roster on the left: avatar, name, personality, score, tricks-won.
  - Click-to-play with illegal-move shake feedback.
  - Auto-play for AI turns with a brief pause.
* Pass screen for selecting 3 cards to pass.
* Help window (F1).
* Game-over screen with rematch flow.
* Hub integration env-var: HEARTS_HUB_URL.
* FAST_MODE env-var: skips animations for headless smoke tests.
"""

from __future__ import annotations

import math
import os
import random
import sys
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pygame

# Make src/ importable when run from project root.
# ROOT is the project root, so assets/ resolves correctly regardless of cwd.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from hearts import engine as eng  # noqa: E402
from hearts import ai  # noqa: E402
from hearts import roster as roster_mod  # noqa: E402
from hearts.cards import Card, Hand, Rank, Suit  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCREEN_W = 1280
SCREEN_H = 800
CARD_W = 86
CARD_H = 124
FPS = 60
FAST_MODE = os.environ.get("HEARTS_FAST_MODE", "").lower() in ("1", "true", "yes")
HUB_URL = os.environ.get("HEARTS_HUB_URL", "https://blaksitelab.local/hearts.html")

ASSETS = ROOT / "assets"
FACE_DIR = ASSETS / "cards" / "face"
BACK_DIR = ASSETS / "cards" / "backs"
AVATAR_DIR = ASSETS / "avatars"
TABLE_IMG = ASSETS / "table" / "felt.png"

# Personality roster.
PERSONALITIES = ("aggressive", "balanced", "conservative")
PERSONALITY_DESC = {
    "aggressive": "Dumps big cards, plays offense.",
    "balanced":   "Mixes offense and defense.",
    "conservative": "Plays it safe, slow bleed.",
}
PERSONALITY_COLOR = {
    "aggressive":  (220, 70, 70),
    "balanced":    (220, 180, 60),
    "conservative": (70, 140, 220),
}


# ---------------------------------------------------------------------------
# Asset loading
# ---------------------------------------------------------------------------

class Assets:
    """Lazy-loaded pygame surfaces for cards, backs, and avatars."""

    def __init__(self):
        self.faces: Dict[str, pygame.Surface] = {}
        self.backs: Dict[str, pygame.Surface] = {}
        self.avatars: Dict[str, pygame.Surface] = {}
        self.table: Optional[pygame.Surface] = None
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        # Card faces.
        if FACE_DIR.is_dir():
            for path in FACE_DIR.glob("*.png"):
                surf = pygame.image.load(str(path)).convert_alpha()
                self.faces[path.stem] = surf
        # Backs.
        if BACK_DIR.is_dir():
            for path in BACK_DIR.glob("back_*.png"):
                surf = pygame.image.load(str(path)).convert_alpha()
                self.backs[path.stem] = surf
        # Avatars.
        if AVATAR_DIR.is_dir():
            for path in AVATAR_DIR.glob("avatar_*.png"):
                surf = pygame.image.load(str(path)).convert_alpha()
                self.avatars[path.stem] = surf
        # Table felt.
        if TABLE_IMG.is_file():
            self.table = pygame.image.load(str(TABLE_IMG)).convert()

    def get_face(self, card: Card) -> Optional[pygame.Surface]:
        return self.faces.get(self._face_key(card))

    def get_back(self, name: str) -> Optional[pygame.Surface]:
        return self.backs.get(name)

    def get_avatar(self, name: str) -> Optional[pygame.Surface]:
        # Lookups may include the .png suffix (older call sites) or not;
        # both should resolve to the same stem.
        if not name:
            return None
        if name in self.avatars:
            return self.avatars[name]
        stem = name.removesuffix(".png")
        return self.avatars.get(stem)

    @staticmethod
    def _face_key(card: Card) -> str:
        return f"{card.rank.value}{card.suit.value}{card.suit.name[0].lower()}"


ASSETS_BUNDLE = Assets()


# ---------------------------------------------------------------------------
# Animation state
# ---------------------------------------------------------------------------

@dataclass
class TrickAnimation:
    """Visual state for a trick in progress.

    play_order: list of (player_idx, card) in the order they were played.
    winning_player: the player who won the trick (set once the trick resolves).
    phase: 'playing' → 'winning' → 'cleared'.
    t: progress in [0, 1] for the current phase.
    """

    play_order: List[Tuple[int, Card]] = field(default_factory=list)
    winning_player: Optional[int] = None
    winner_index: int = -1
    phase: str = "playing"
    t: float = 0.0
    card_t: Dict[int, float] = field(default_factory=dict)
    winning_card: Optional[Card] = None

    @property
    def is_done(self) -> bool:
        return self.phase == "cleared"


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color(c1: Tuple[int, int, int], c2: Tuple[int, int, int],
               t: float) -> Tuple[int, int, int]:
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


def draw_text(surf: pygame.Surface, text: str, pos: Tuple[int, int],
              font: pygame.font.Font,
              color: Tuple[int, int, int] = (240, 240, 240),
              center: bool = False) -> pygame.Rect:
    img = font.render(text, True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surf.blit(img, rect)
    return rect


def card_surf(card: Card, assets: Assets = ASSETS_BUNDLE,
              back_name: Optional[str] = None,
              scale: float = 1.0,
              alpha: int = 255) -> pygame.Surface:
    """Return a card surface (face or back), scaled + alpha-multiplied."""
    if back_name is not None:
        src = assets.get_back(back_name) or assets.get_back("back_01")
    else:
        src = assets.get_face(card) or assets.get_back("back_01")
    if src is None:
        src = pygame.Surface((CARD_W, CARD_H))
        src.fill((200, 50, 50))
    w, h = int(CARD_W * scale), int(CARD_H * scale)
    if (w, h) != (src.get_width(), src.get_height()):
        src = pygame.transform.smoothscale(src, (w, h))
    if alpha < 255:
        src = src.copy()
        src.set_alpha(alpha)
    return src


# ---------------------------------------------------------------------------
# UI Scenes
# ---------------------------------------------------------------------------

class Scene(Enum):
    MENU = auto()
    SETTINGS = auto()
    PASS = auto()
    GAME = auto()
    GAME_OVER = auto()
    HELP = auto()


@dataclass
class Player:
    name: str
    personality: str
    avatar: str
    # Optional character flavour — present for AI (set from roster), None for
    # the human seat. UI uses these for the roster panel.
    tagline: Optional[str] = None
    bio: Optional[str] = None
    char_id: Optional[str] = None  # stable id for rematch / stats tracking
    tricks_won: int = 0
    round_points: int = 0
    total_points: int = 0


class App:
    """Top-level application — owns state, runs the main loop."""

    def __init__(self, headless: bool = False):
        self.headless = headless
        os.environ.setdefault("SDL_VIDEODRIVER",
                              "dummy" if headless else "")
        pygame.init()
        pygame.display.set_caption("BlaksiteLab Hearts")
        # We always set a real display surface so that
        # .convert()/.convert_alpha() can run during asset loading. In
        # headless mode the dummy driver makes this essentially free.
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.font_xl = pygame.font.SysFont("Arial", 48, bold=True)
        self.font_lg = pygame.font.SysFont("Arial", 28, bold=True)
        self.font_md = pygame.font.SysFont("Arial", 20)
        self.font_sm = pygame.font.SysFont("Arial", 14)
        ASSETS_BUNDLE.load()

        self.state: Optional[eng.GameState] = None
        self.players: List[Player] = []
        self.human_idx = 0
        self.scene: Scene = Scene.MENU
        self.running = True

        # Trick animation.
        self.anim: Optional[TrickAnimation] = None
        self.anim_start_ms: int = 0
        self.anim_card_t: List[float] = []  # one per slot in the trick

        # Selected cards for passing.
        self.pass_selections: List[Card] = []
        self.pass_confirmed = False

        # Shake / feedback.
        self.shake_until_ms = 0
        self.shake_message: str = ""

        # Settings.
        self.seed: Optional[int] = None
        self.back_choice = "back_01"
        self.available_backs: List[str] = []
        for path in (BACK_DIR).glob("back_*.png"):
            self.available_backs.append(path.stem)
        if not self.available_backs:
            self.available_backs = ["back_01"]

        # Menus.
        self.menu_index = 0
        self.menu_items = ["Start", "Settings", "Help", "Quit"]
        self.settings_index = 0
        self.settings_items = [
            "Seed (blank = random)",
            f"Card back: {self.back_choice}",
            "Re-shuffle personalities",
            "Back to menu",
        ]
        self.gameover_index = 0
        self.gameover_items = ["Rematch", "Back to menu"]

        # Timeouts.
        self.last_ai_play_ms = 0
        self.turn_delay_ms = 0 if FAST_MODE else 700

        # Help window state.
        self.help_shown = False

    # ------------------------------------------------------------------
    # Entry / loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while self.running:
            self.clock.tick(FPS)
            self._handle_events()
            self._update()
            if self.screen is not None:
                self._draw()
        pygame.quit()

    def capture_screenshot(self, path: str) -> str:
        """Force a draw and save the current frame. Returns the saved path."""
        # Make sure the screen is created even if headless.
        if self.screen is None:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self._draw()
        pygame.image.save(self.screen, path)
        return path

    def drive_step(self, frames: int = 1) -> None:
        """Run N update frames without a real clock. For headless tests."""
        for _ in range(frames):
            self._update()

    def force_human_to_act(self) -> None:
        """Test helper: place the AI to play a full trick ending with human
        about to act, by making current_player_idx = 0. Sets a fresh anim."""
        if self.state is None:
            return
        self.anim = None
        if self.state.phase is eng.Phase.PLAYING:
            self.state.current_player_idx = 0

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_click(event)

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_F1:
            self.scene = Scene.HELP
            return
        if event.key == pygame.K_ESCAPE:
            if self.scene is Scene.HELP:
                self.scene = Scene.GAME
                return
            if self.scene in (Scene.GAME, Scene.PASS, Scene.GAME_OVER):
                self.scene = Scene.MENU
                return
        if self.scene is Scene.MENU:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index - 1) % len(self.menu_items)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = (self.menu_index + 1) % len(self.menu_items)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate_menu()
        elif self.scene is Scene.SETTINGS:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.settings_index = (self.settings_index - 1) % len(
                    self.settings_items)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.settings_index = (self.settings_index + 1) % len(
                    self.settings_items)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate_settings()
        elif self.scene is Scene.GAME_OVER:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.gameover_index = (
                    self.gameover_index - 1) % len(self.gameover_items)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.gameover_index = (
                    self.gameover_index + 1) % len(self.gameover_items)
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self._activate_gameover()

    def _handle_click(self, event: pygame.event.Event) -> None:
        pos = event.pos
        if self.scene is Scene.MENU:
            self._click_menu(pos)
        elif self.scene is Scene.SETTINGS:
            self._click_settings(pos)
        elif self.scene is Scene.GAME:
            self._click_game(pos)
        elif self.scene is Scene.PASS:
            self._click_pass(pos)
        elif self.scene is Scene.GAME_OVER:
            self._click_gameover(pos)
        elif self.scene is Scene.HELP:
            # Click anywhere to close.
            self.scene = Scene.GAME

    # ------------------------------------------------------------------
    # Per-scene click dispatch
    # ------------------------------------------------------------------

    def _click_menu(self, pos) -> None:
        rects = self._menu_rects()
        for i, r in enumerate(rects):
            if r.collidepoint(pos):
                self.menu_index = i
                self._activate_menu()
                return

    def _click_settings(self, pos) -> None:
        rects = self._settings_rects()
        for i, r in enumerate(rects):
            if r.collidepoint(pos):
                self.settings_index = i
                self._activate_settings()
                return

    def _click_game(self, pos) -> None:
        # Only the human can click — and only if it's their turn AND no
        # animation is running.
        if not self._human_can_act():
            return
        for card, rect in self._hand_card_rects():
            if rect.collidepoint(pos):
                self._try_human_play(card)
                return

    def _click_pass(self, pos) -> None:
        for card, rect in self._hand_card_rects():
            if rect.collidepoint(pos):
                self._toggle_pass_selection(card)
                return
        # Confirm button.
        confirm_rect = pygame.Rect(SCREEN_W // 2 - 80, SCREEN_H - 100,
                                   160, 50)
        if confirm_rect.collidepoint(pos) and len(self.pass_selections) == 3:
            self._confirm_pass()

    def _click_gameover(self, pos) -> None:
        rects = self._gameover_rects()
        for i, r in enumerate(rects):
            if r.collidepoint(pos):
                self.gameover_index = i
                self._activate_gameover()
                return

    # ------------------------------------------------------------------
    # Activations
    # ------------------------------------------------------------------

    def _activate_menu(self) -> None:
        choice = self.menu_items[self.menu_index]
        if choice == "Start":
            self._start_new_game()
        elif choice == "Settings":
            self.scene = Scene.SETTINGS
        elif choice == "Help":
            self.scene = Scene.HELP
        elif choice == "Quit":
            self.running = False

    def _activate_settings(self) -> None:
        choice = self.settings_items[self.settings_index]
        if choice.startswith("Seed"):
            # Cycle through: 1, 7, 42, 100, 999, None.
            seeds = [1, 7, 42, 100, 999, None]
            current = seeds.index(self.seed) if self.seed in seeds else 5
            self.seed = seeds[(current + 1) % len(seeds)]
            self.settings_items[0] = f"Seed: {self.seed}"
        elif choice.startswith("Card back"):
            if self.available_backs:
                i = self.available_backs.index(self.back_choice)
                self.back_choice = self.available_backs[
                    (i + 1) % len(self.available_backs)]
                self.settings_items[1] = (
                    f"Card back: {self.back_choice}")
        elif choice == "Re-shuffle personalities":
            self._reshuffle_personalities()
        elif choice == "Back to menu":
            self.scene = Scene.MENU

    def _activate_gameover(self) -> None:
        choice = self.gameover_items[self.gameover_index]
        if choice == "Rematch":
            self._start_new_game(rematch=True)
        else:
            self.scene = Scene.MENU

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _reshuffle_personalities(self) -> None:
        pool = list(PERSONALITIES) * 2  # 6 entries
        random.shuffle(pool)
        # Human is "balanced" by default (the first entry).
        for i, p in enumerate(self.players):
            p.personality = pool[i]
        if self.state is not None:
            # Apply in-game too.
            self.state.player_personalities = [p.personality
                                               for p in self.players]

    def _start_new_game(self, rematch: bool = False) -> None:
        # On a rematch, keep the same players and personalities. On a fresh
        # start, pick 3 random characters from the roster and seat them at
        # indices 1..3 (index 0 is the human).
        if not rematch:
            picks = roster_mod.draw_ai_three()
            self.players = []
            # Human seat first.
            self.players.append(Player(
                name="You",
                personality="balanced",
                avatar="",  # human has no avatar
                char_id="human",
            ))
            for c in picks:
                self.players.append(Player(
                    name=c.name,
                    personality=c.personality,
                    avatar=c.avatar_file,
                    tagline=c.tagline,
                    bio=c.bio,
                    char_id=c.id,
                ))
        # Always reset per-game scores and tricks.
        for p in self.players:
            p.tricks_won = 0
            p.round_points = 0
            p.total_points = 0
        # Build engine state.
        self.state = eng.new_game(seed=self.seed)
        # Sync engine personalities (human at index 0).
        for i, p in enumerate(self.players):
            if i == 0:
                continue
            self.state.player_personalities[i] = p.personality
        # Sync totals.
        for i, p in enumerate(self.players):
            p.total_points = self.state.total_scores[i]
        self.anim = None
        self.pass_selections = []
        self.pass_confirmed = False
        self.scene = Scene.PASS
        self.last_ai_play_ms = pygame.time.get_ticks() if not self.headless else 0

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def _update(self) -> None:
        if self.state is None or self.state.phase is eng.Phase.GAME_OVER:
            if self.state is not None and self.state.phase is eng.Phase.GAME_OVER:
                if self.scene is not Scene.GAME_OVER:
                    self._enter_gameover()
            return

        # Update engine-driven phase transitions.
        if self.state.phase is eng.Phase.PASSING:
            # If every AI has already submitted but the human hasn't, prompt.
            pending = self.state.pending_pass
            for i in range(1, self.state.num_players):
                if i not in pending and not FAST_MODE:
                    picks = ai.choose_pass(self.state, i,
                                           self.players[i].personality)
                    self.state.pass_cards(i, picks)
            return

        # Playing.
        cur = self.state.current_player_idx
        # Skip AI turns automatically.
        # In FAST_MODE, ignore anim state — we collapse the animation timeline
        # to a single tick per frame so we can play through quickly.
        anim_in_progress = self.anim is not None and not self.anim.is_done
        can_ai_play = cur != 0 and (not anim_in_progress or FAST_MODE or self.headless)
        if can_ai_play:
            now = pygame.time.get_ticks() if not self.headless else 0
            if now - self.last_ai_play_ms >= self.turn_delay_ms:
                self._ai_play()
                self.last_ai_play_ms = now

        # Animate trick. In FAST_MODE/headless, finalize immediately
        # once the trick is complete. The engine resets the current trick
        # to a new empty one as soon as the 4th card lands, so we detect
        # completion by comparing the anim's recorded plays against the
        # engine's live trick: if the anim has 4 plays and the engine's
        # trick has fewer than 4 (or is empty), the engine has already
        # finalised and reset, so we should clear the anim.
        if self.anim and not self.anim.is_done:
            if FAST_MODE or self.headless:
                anim_n = len(self.anim.play_order)
                live_n = len(self.state.trick.plays)
                trick_done = (
                    self.anim.winning_card is not None
                    or (anim_n >= 4 and live_n < 4)
                )
                if trick_done:
                    self.anim.phase = "cleared"
                    self._finalize_trick()
                # else: wait for more cards to fill the trick.
            else:
                self._update_anim()

    def _ai_play(self) -> None:
        if not self.anim or self.anim.is_done:
            self.anim = TrickAnimation()
            self.anim.play_order = []
            self.anim.card_t = {}
        # If the anim is stale (engine has reset the trick to a new one
        # without us finalising the old anim), reset it before recording
        # the new play. Same logic as _try_human_play.
        if (self.anim is not None
                and not self.anim.is_done
                and len(self.state.trick.plays) <= len(self.anim.play_order)):
            self.anim = TrickAnimation()
        cur = self.state.current_player_idx
        if any(p_idx == cur for p_idx, _ in self.anim.play_order):
            return  # already played
        card = ai.choose_play(self.state, cur,
                              self.players[cur].personality)
        # Record before playing.
        slot = len(self.anim.play_order)
        self.anim.play_order.append((cur, card))
        self.anim.card_t[slot] = 0.0
        try:
            self.state.play_card(cur, card)
        except eng.IllegalMoveError as e:
            self._flash(f"AI error: {e}")
        if self.state.trick.complete:
            # Resolve: determine winner.
            winner = self.state.trick.winner()
            self.anim.winning_player = winner
            # Find which slot in the play_order the winner is at.
            for i, (p, _c) in enumerate(self.anim.play_order):
                if p == winner:
                    self.anim.winner_index = i
                    self.anim.winning_card = _c
                    break
            self.anim.phase = "winning"

    def _update_anim(self) -> None:
        a = self.anim
        now = pygame.time.get_ticks() if not self.headless else 0
        dt = self.clock.get_time() / 1000.0
        if FAST_MODE:
            dt = 0.05
        a.t += dt
        # Update per-card t (for entry animation).
        for i in range(len(a.play_order)):
            target_t = 1.0
            # Stagger: each card starts 0.2s after the previous.
            entry_start = 0.15 * i
            a.card_t[i] = min(1.0, max(0.0,
                                       (a.t - entry_start) / 0.25))
        if a.phase == "winning":
            highlight_t = 0.4
            if a.t >= highlight_t:
                a.phase = "slough"
                a.t = 0.0
        elif a.phase == "slough":
            slough_t = 0.6 if not FAST_MODE else 0.05
            if a.t >= slough_t:
                a.phase = "cleared"
                self._finalize_trick()

    def _finalize_trick(self) -> None:
        # The engine has already scored this trick and created a new one.
        # Look up the winner from the just-finalised trick in history.
        if not self.state.trick_history:
            self.anim = None
            return
        completed = self.state.trick_history[-1]
        winner = completed.winner()
        # Update player view: tricks won.
        self.players[winner].tricks_won += 1
        # Sync totals to engine (engine tracks the source of truth).
        for i, p in enumerate(self.players):
            p.round_points = self.state.round_scores[i]
            p.total_points = self.state.total_scores[i]
        # The engine sets current_player_idx to the winner of the completed
        # trick; nothing else to do here.
        self.state.trick_points = 0
        # Detect hearts-broken for next trick (if a heart was in the play).
        if self.anim is not None:
            self.state.hearts_broken = (
                self.state.hearts_broken
                or any(c.is_heart for _, c in self.anim.play_order)
            )
        # Round complete?
        if all(len(h) == 0 for h in self.state.hands):
            self._end_round()
        self.anim = None

    def _end_round(self) -> None:
        # Tally round → total.
        for i, p in enumerate(self.players):
            p.round_points = self.state.round_scores[i]
            p.total_points += self.state.round_scores[i]
            self.state.total_scores[i] = p.total_points
        # Check game over.
        if any(p.total_points >= 100 for p in self.players):
            self.state.phase = eng.Phase.GAME_OVER
            return
        # Next round.
        self.state.round_number += 1
        self.state.start_round()
        for i in range(1, self.state.num_players):
            self.state.player_personalities[i] = (
                self.players[i].personality)
        # Reset pass selection.
        self.pass_selections = []
        self.pass_confirmed = False
        self.scene = Scene.PASS

    def _enter_gameover(self) -> None:
        self.scene = Scene.GAME_OVER

    # ------------------------------------------------------------------
    # Pass selection
    # ------------------------------------------------------------------

    def _toggle_pass_selection(self, card: Card) -> None:
        if card in self.pass_selections:
            self.pass_selections.remove(card)
        elif len(self.pass_selections) < 3:
            self.pass_selections.append(card)
        else:
            self._flash("Pick exactly 3 cards.")

    def _confirm_pass(self) -> None:
        if len(self.pass_selections) != 3:
            self._flash("Pick exactly 3 cards.")
            return
        self.state.pass_cards(0, self.pass_selections)
        self.pass_selections = []
        self.pass_confirmed = True
        # If all AI have passed (likely — they pass immediately when phase
        # changes), we can move to GAME.
        if self.state.phase is eng.Phase.PLAYING:
            self.scene = Scene.GAME
            self.anim = None
        else:
            # AI pass for all 3.
            for i in range(1, self.state.num_players):
                picks = ai.choose_pass(self.state, i,
                                       self.players[i].personality)
                self.state.pass_cards(i, picks)
            self.scene = Scene.GAME
            self.anim = None

    # ------------------------------------------------------------------
    # Human play
    # ------------------------------------------------------------------

    def _human_can_act(self) -> bool:
        if FAST_MODE or self.headless:
            # In FAST_MODE we collapse animation; human can act whenever
            # it's their turn.
            return (
                self.state is not None
                and self.state.phase is eng.Phase.PLAYING
                and self.state.current_player_idx == 0
            )
        return (
            self.state is not None
            and self.state.phase is eng.Phase.PLAYING
            and self.state.current_player_idx == 0
            and (self.anim is None or self.anim.is_done)
        )

    def _try_human_play(self, card: Card) -> None:
        if card not in self.state.hands[0].cards:
            return
        try:
            self.state.play_card(0, card)
        except eng.IllegalMoveError as e:
            self._flash(str(e))
            return
        # If the anim is stale (engine has reset the trick to a new one
        # without us finalising the old anim), reset it before recording
        # the new play. The engine resets state.trick to a fresh empty
        # Trick as soon as the 4th card of a trick lands, so the
        # discrepancy between len(anim.play_order) and
        # len(state.trick.plays) tells us the anim is from an old trick.
        if (self.anim is not None
                and not self.anim.is_done
                and len(self.state.trick.plays) <= len(self.anim.play_order)):
            self.anim = TrickAnimation()
        # Start a new trick animation if we don't have one.
        if self.anim is None or self.anim.is_done:
            self.anim = TrickAnimation()
        if not self.anim.play_order and self.anim.phase != "playing":
            self.anim.phase = "playing"
            self.anim.t = 0.0
        self.anim.play_order.append((0, card))
        slot = len(self.anim.play_order) - 1
        self.anim.card_t[slot] = 0.0
        # If this play just completed a trick (4 cards in the live trick),
        # record the winner and transition to "winning" phase so the
        # anim can play out the highlight before being cleared.
        if self.state.trick.complete:
            winner = self.state.trick.winner()
            self.anim.winning_player = winner
            for i, (p, _c) in enumerate(self.anim.play_order):
                if p == winner:
                    self.anim.winner_index = i
                    self.anim.winning_card = _c
            # In FAST_MODE / headless, finalize immediately so the
            # next iteration starts with a clean anim. Otherwise the
            # stale anim blocks subsequent AI plays.
            if FAST_MODE or self.headless:
                self._finalize_trick()
                return
            self.anim.phase = "winning"

    def _flash(self, message: str) -> None:
        self.shake_message = message
        self.shake_until_ms = (pygame.time.get_ticks() + 1500
                               if not self.headless else 1500)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        if self.screen is None:
            return
        # Background.
        if ASSETS_BUNDLE.table is not None:
            self.screen.blit(pygame.transform.scale(
                ASSETS_BUNDLE.table, (SCREEN_W, SCREEN_H)), (0, 0))
        else:
            self.screen.fill((10, 60, 35))
        if self.scene is Scene.MENU:
            self._draw_menu()
        elif self.scene is Scene.SETTINGS:
            self._draw_settings()
        elif self.scene is Scene.PASS:
            self._draw_pass()
        elif self.scene is Scene.GAME:
            self._draw_game()
        elif self.scene is Scene.GAME_OVER:
            self._draw_gameover()
        elif self.scene is Scene.HELP:
            self._draw_help()
        # Shake message.
        if self.shake_until_ms and pygame.time.get_ticks() < self.shake_until_ms:
            draw_text(self.screen, self.shake_message,
                      (SCREEN_W // 2, 60), self.font_md,
                      color=(255, 200, 100), center=True)
        pygame.display.flip()

    def _menu_rects(self) -> List[pygame.Rect]:
        rects = []
        cx = SCREEN_W // 2
        cy = SCREEN_H // 2 - 40
        for i, item in enumerate(self.menu_items):
            rects.append(pygame.Rect(cx - 150, cy + i * 70, 300, 50))
        return rects

    def _draw_menu(self) -> None:
        draw_text(self.screen, "BlaksiteLab Hearts", (SCREEN_W // 2, 120),
                  self.font_xl, color=(255, 255, 200), center=True)
        draw_text(self.screen, "A round of 4-player Hearts",
                  (SCREEN_W // 2, 170), self.font_md,
                  color=(220, 220, 220), center=True)
        rects = self._menu_rects()
        for i, (item, r) in enumerate(zip(self.menu_items, rects)):
            color = (255, 220, 100) if i == self.menu_index else (200, 200, 200)
            pygame.draw.rect(self.screen, (40, 40, 60), r,
                             border_radius=8)
            pygame.draw.rect(self.screen, color, r, width=2, border_radius=8)
            draw_text(self.screen, item, r.center, self.font_lg, color=color,
                      center=True)
        draw_text(self.screen,
                  "F1 help · ESC menu · ENTER select",
                  (SCREEN_W // 2, SCREEN_H - 50), self.font_sm,
                  color=(180, 180, 180), center=True)

    def _settings_rects(self) -> List[pygame.Rect]:
        rects = []
        cx = SCREEN_W // 2
        cy = SCREEN_H // 2 - 100
        for i in range(len(self.settings_items)):
            rects.append(pygame.Rect(cx - 200, cy + i * 70, 400, 50))
        return rects

    def _draw_settings(self) -> None:
        draw_text(self.screen, "Settings", (SCREEN_W // 2, 100),
                  self.font_xl, color=(255, 255, 200), center=True)
        rects = self._settings_rects()
        for i, (item, r) in enumerate(zip(self.settings_items, rects)):
            color = (255, 220, 100) if i == self.settings_index else (
                200, 200, 200)
            pygame.draw.rect(self.screen, (40, 40, 60), r, border_radius=8)
            pygame.draw.rect(self.screen, color, r, width=2, border_radius=8)
            draw_text(self.screen, item, r.center, self.font_lg, color=color,
                      center=True)

    def _draw_pass(self) -> None:
        if self.state is None:
            return
        direction = self.state.pass_direction.name
        draw_text(self.screen, f"Pass 3 cards ({direction})",
                  (SCREEN_W // 2, 80), self.font_xl,
                  color=(255, 255, 200), center=True)
        draw_text(self.screen,
                  f"Selected: {len(self.pass_selections)}/3",
                  (SCREEN_W // 2, 120), self.font_md,
                  color=(220, 220, 220), center=True)
        self._draw_player_roster()
        self._draw_hand(highlight_selected=True)
        # Confirm button.
        confirm = pygame.Rect(SCREEN_W // 2 - 80, SCREEN_H - 100,
                              160, 50)
        ready = len(self.pass_selections) == 3
        color = (80, 180, 80) if ready else (90, 90, 90)
        pygame.draw.rect(self.screen, color, confirm, border_radius=8)
        draw_text(self.screen, "Confirm", confirm.center, self.font_lg,
                  color=(255, 255, 255), center=True)

    def _draw_gameover(self) -> None:
        if self.state is None:
            return
        # Winner = lowest total.
        totals = [p.total_points for p in self.players]
        winner_idx = totals.index(min(totals))
        draw_text(self.screen, "Game Over", (SCREEN_W // 2, 100),
                  self.font_xl, color=(255, 220, 100), center=True)
        draw_text(self.screen,
                  f"{self.players[winner_idx].name} wins!",
                  (SCREEN_W // 2, 160), self.font_lg,
                  color=(180, 255, 180), center=True)
        # Roster with scores.
        y = 240
        for i, p in enumerate(self.players):
            color = (180, 255, 180) if i == winner_idx else (220, 220, 220)
            line = f"{p.name:8s}  {p.personality:14s}  {p.total_points} pts"
            draw_text(self.screen, line, (SCREEN_W // 2 - 200, y),
                      self.font_lg, color=color)
            y += 40
        # Buttons.
        rects = self._gameover_rects()
        for i, (item, r) in enumerate(zip(self.gameover_items, rects)):
            color = (255, 220, 100) if i == self.gameover_index else (
                200, 200, 200)
            pygame.draw.rect(self.screen, (40, 40, 60), r, border_radius=8)
            pygame.draw.rect(self.screen, color, r, width=2, border_radius=8)
            draw_text(self.screen, item, r.center, self.font_lg, color=color,
                      center=True)

    def _gameover_rects(self) -> List[pygame.Rect]:
        rects = []
        cx = SCREEN_W // 2
        cy = 480
        for i in range(len(self.gameover_items)):
            rects.append(pygame.Rect(cx - 120, cy + i * 70, 240, 50))
        return rects

    def _draw_help(self) -> None:
        # Translucent overlay.
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        self.screen.blit(overlay, (0, 0))
        # Help box.
        box = pygame.Rect(120, 80, SCREEN_W - 240, SCREEN_H - 160)
        pygame.draw.rect(self.screen, (30, 30, 50), box, border_radius=12)
        pygame.draw.rect(self.screen, (200, 200, 100), box, width=2,
                         border_radius=12)
        lines = [
            ("BlaksiteLab Hearts — Help", True),
            ("", False),
            ("Goal:  Avoid taking hearts and the Queen of Spades.",
             False),
            ("Each heart is worth 1 point, the Q♠ is worth 13.",
             False),
            ("First to 100 loses. Shoot the moon (take all 26) and",
             False),
            ("everyone else gets 26 instead.", False),
            ("", False),
            ("Controls", True),
            ("  Click a card to play it (when it's your turn).", False),
            ("  F1 to toggle this help. ESC to return to menu.", False),
            ("  Pass direction cycles: Left, Right, Across, Hold.", False),
            ("", False),
            ("Click anywhere to close.",
             False),
        ]
        y = box.top + 30
        for line, is_header in lines:
            color = (255, 220, 100) if is_header else (220, 220, 220)
            font = self.font_lg if is_header else self.font_md
            draw_text(self.screen, line, (box.left + 40, y), font,
                      color=color)
            y += 32 if is_header else 26

    # ------------------------------------------------------------------
    # Game scene
    # ------------------------------------------------------------------

    def _draw_game(self) -> None:
        if self.state is None:
            return
        self._draw_player_roster()
        # Trick in centre.
        self._draw_trick()
        # Player 0's hand.
        self._draw_hand(highlight_selected=False)
        # Header.
        self._draw_header()

    def _draw_header(self) -> None:
        if self.state is None:
            return
        # Top: round number, pass direction, current player.
        text = (
            f"Round {self.state.round_number}   |   "
            f"Pass: {self.state.pass_direction.name}   |   "
            f"Turn: {self.players[self.state.current_player_idx].name} "
            f"({self.players[self.state.current_player_idx].personality})"
        )
        draw_text(self.screen, text, (SCREEN_W // 2, 30), self.font_md,
                  color=(220, 220, 220), center=True)
        # Hearts broken indicator.
        if self.state.hearts_broken:
            draw_text(self.screen, "♥ Broken", (SCREEN_W - 200, 30),
                      self.font_sm, color=(255, 100, 100))
        # F1 hint.
        draw_text(self.screen, "F1 Help · ESC Menu", (40, 30),
                  self.font_sm, color=(180, 180, 180))

    def _draw_player_roster(self) -> None:
        """Draw the left sidebar with player avatars + scores + tricks won.

        Each row shows: avatar, name, personality chip, tagline (or
        personality desc for the human seat), score, and tricks won.
        """
        if self.state is None:
            return
        x0 = 20
        y0 = 80
        w = 220
        h = 140
        for i, p in enumerate(self.players):
            r = pygame.Rect(x0, y0 + i * (h + 10), w, h)
            bg_color = (40, 50, 70) if i == self.state.current_player_idx else (
                30, 30, 50)
            pygame.draw.rect(self.screen, bg_color, r, border_radius=10)
            border_color = PERSONALITY_COLOR.get(p.personality,
                                                 (200, 200, 200))
            pygame.draw.rect(self.screen, border_color, r, width=2,
                             border_radius=10)
            # Avatar (skip for the human seat, which has no avatar).
            av = ASSETS_BUNDLE.get_avatar(p.avatar) if p.avatar else None
            if av is not None:
                av_scaled = pygame.transform.smoothscale(av, (80, 80))
                self.screen.blit(av_scaled, (r.left + 10, r.top + 25))
            else:
                # Fall back to a circular initial for the human seat.
                initial = (p.name[:1] or "Y").upper()
                font_init = pygame.font.SysFont("Arial", 48, bold=True)
                draw_text(self.screen, initial,
                          (r.left + 50, r.top + 65), font_init,
                          color=border_color, center=True)
            # Name (top right).
            draw_text(self.screen, p.name, (r.left + 100, r.top + 12),
                      self.font_lg, color=(255, 255, 255))
            # Personality chip (just below name).
            draw_text(self.screen, p.personality,
                      (r.left + 100, r.top + 38),
                      self.font_sm, color=border_color)
            # Tagline for AI, personality desc for human.
            flavor = p.tagline or PERSONALITY_DESC.get(p.personality, "")
            if flavor:
                draw_text(self.screen, f"\u201C{flavor}\u201D",
                          (r.left + 100, r.top + 56),
                          self.font_sm, color=(200, 200, 200))
            # Score / tricks (bottom right).
            draw_text(self.screen, f"Score: {p.total_points}",
                      (r.left + 100, r.top + 86),
                      self.font_sm, color=(220, 220, 220))
            draw_text(self.screen, f"Tricks: {p.tricks_won}",
                      (r.left + 100, r.top + 106),
                      self.font_sm, color=(220, 220, 220))

    def _hand_card_rects(self) -> List[Tuple[Card, pygame.Rect]]:
        if self.state is None:
            return []
        hand = self.state.hands[0].sorted_cards()
        n = len(hand)
        if n == 0:
            return []
        total_w = n * (CARD_W // 2) + CARD_W // 2
        x0 = (SCREEN_W - total_w) // 2
        y0 = SCREEN_H - CARD_H - 40
        out = []
        for i, c in enumerate(hand):
            x = x0 + i * (CARD_W // 2)
            r = pygame.Rect(x, y0, CARD_W, CARD_H)
            out.append((c, r))
        return out

    def _draw_hand(self, highlight_selected: bool) -> None:
        if self.state is None:
            return
        # AI players (1, 2, 3) don't render full hands — just the count and
        # the player's avatar slot already shows in the roster.
        for card, r in self._hand_card_rects():
            surf = card_surf(card, back_name=None)
            # Highlight selected (pass screen) or hover-equivalent.
            selected = card in self.pass_selections
            if highlight_selected and selected:
                glow = pygame.Surface((r.width + 8, r.height + 8),
                                      pygame.SRCALPHA)
                pygame.draw.rect(glow, (255, 220, 100, 100),
                                 glow.get_rect(), border_radius=12)
                self.screen.blit(glow, (r.left - 4, r.top - 4))
            self.screen.blit(surf, r)

    def _draw_trick(self) -> None:
        """Draw the 4 cards in the current trick with animation."""
        if self.state is None:
            return
        # Always show all 4 cards in the trick once they've been played.
        # If we're in the middle of a new trick, show only what's been
        # played so far.
        if self.anim is None:
            return
        # Layout positions: south (0), west (1), north (2), east (3).
        positions = self._trick_positions()
        for i, (player_idx, card) in enumerate(self.anim.play_order):
            pos = positions[player_idx]
            t = self.anim.card_t.get(i, 1.0)
            entry = ease_out_cubic(t)
            if self.anim.phase == "slough" and i != self.anim.winner_index:
                # Non-winning cards shrink and fade.
                slough_t = min(1.0, self.anim.t / 0.6)
                scale = 1.0 - 0.6 * slough_t
                alpha = int(255 * (1.0 - slough_t))
            elif self.anim.phase == "winning" and i == self.anim.winner_index:
                # Winner pulses slightly.
                pulse = 1.0 + 0.06 * math.sin(self.anim.t * 10)
                scale = pulse
                alpha = 255
            elif self.anim.phase in ("winning", "slough") and i != self.anim.winner_index:
                # Non-winners dim.
                scale = 0.92
                alpha = 180
            else:
                scale = 1.0
                alpha = 255
            surf = card_surf(card, back_name=None, scale=scale, alpha=alpha)
            rect = surf.get_rect(center=pos)
            self.screen.blit(surf, rect)
            # Winner's golden glow.
            if (self.anim.phase in ("winning", "slough")
                    and i == self.anim.winner_index):
                glow = pygame.Surface((rect.width + 24, rect.height + 24),
                                      pygame.SRCALPHA)
                glow_color = (255, 200, 80, 100) if (
                    self.anim.phase == "winning") else (255, 200, 80, 60)
                pygame.draw.rect(glow, glow_color, glow.get_rect(),
                                 border_radius=14)
                self.screen.blit(glow, (rect.left - 12, rect.top - 12))
            # Hide entry-t=0 cards (we don't have the "from off-screen"
            # position) — the entry_t eases from nothing.
            if t <= 0.01:
                # Just don't draw — or draw tiny.
                tiny = card_surf(card, back_name=None, scale=0.4, alpha=60)
                self.screen.blit(tiny, tiny.get_rect(center=pos))

    def _trick_positions(self) -> Dict[int, Tuple[int, int]]:
        """Return anchor positions for each player's card slot in the trick."""
        cx, cy = SCREEN_W // 2, SCREEN_H // 2
        return {
            0: (cx, cy + 80),       # South (human)
            1: (cx - 250, cy),      # West
            2: (cx, cy - 80),       # North
            3: (cx + 250, cy),      # East
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(headless: bool = False) -> int:
    app = App(headless=headless)
    if headless:
        # Run a few frames then exit (for smoke tests).
        for _ in range(3):
            app._handle_events()
            app._update()
        return 0
    app.run()
    return 0


if __name__ == "__main__":
    headless = "--headless" in sys.argv
    sys.exit(main(headless=headless))
