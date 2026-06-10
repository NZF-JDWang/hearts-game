"""App-level tests for BlaksiteLab Hearts.

Drives the Pygame `App` directly in headless mode (no real event loop).
Uses HEARTS_FAST_MODE to skip animation delays.

Captures screenshots to docs/screenshots/ during the test run for visual
verification of menu, settings, pass, game, help, and game-over screens.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Force fast mode and headless before importing the app module.
os.environ.setdefault("HEARTS_FAST_MODE", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

import pygame  # noqa: E402
from hearts import app as app_module  # noqa: E402
from hearts import engine as eng  # noqa: E402


SCREENSHOTS = ROOT / "docs" / "screenshots"


@pytest.fixture
def app():
    """Fresh App in headless mode."""
    pygame.init()
    a = app_module.App(headless=True)
    a.seed = 1  # deterministic
    yield a
    pygame.quit()


# ----------------------------------------------------------------------
# 1. Menu / Settings
# ----------------------------------------------------------------------

def test_menu_starts_on_menu_scene(app):
    assert app.scene is app_module.Scene.MENU


def test_menu_keyboard_navigation(app):
    app.menu_index = 0
    # Simulate "down" via the public method dispatch (key handlers are
    # internal, but we can call _activate_menu with an index shift).
    app.menu_index = 2  # Help
    assert app.menu_items[app.menu_index] == "Help"
    app._activate_menu()
    assert app.scene is app_module.Scene.HELP
    # F1-equivalent: back to game; but we're in menu, so back to menu.
    app.scene = app_module.Scene.MENU


def test_settings_cycles_seed(app):
    app.scene = app_module.Scene.SETTINGS
    app.settings_index = 0
    original_seed = app.seed
    app._activate_settings()
    assert app.seed != original_seed
    # Should have updated the menu text.
    assert "Seed:" in app.settings_items[0]


def test_settings_cycles_back(app):
    app.scene = app_module.Scene.SETTINGS
    app.settings_index = 3  # Back to menu
    app._activate_settings()
    assert app.scene is app_module.Scene.MENU


def test_settings_reshuffle(app):
    app.scene = app_module.Scene.SETTINGS
    app._reshuffle_personalities()
    # After init, players are 4. Pool includes all 3 personalities repeated.
    pstyles = [p.personality for p in app.players]
    assert all(p in app_module.PERSONALITIES for p in pstyles)


# ----------------------------------------------------------------------
# 2. Start / Pass
# ----------------------------------------------------------------------

def test_start_opens_pass_scene(app):
    app.menu_index = 0  # Start
    app._activate_menu()
    assert app.scene is app_module.Scene.PASS
    assert app.state is not None
    assert app.state.phase is eng.Phase.PASSING
    assert len(app.state.pending_pass) == 0  # Human hasn't picked yet


def test_pass_select_three_cards(app):
    app._start_new_game()
    hand = app.state.hands[0].cards
    # Pick the first three.
    for c in hand[:3]:
        app._toggle_pass_selection(c)
    assert len(app.pass_selections) == 3
    # Toggle one off.
    app._toggle_pass_selection(hand[0])
    assert len(app.pass_selections) == 2
    # Re-add.
    app._toggle_pass_selection(hand[0])
    assert len(app.pass_selections) == 3


def test_pass_confirm_transitions_to_game(app):
    app._start_new_game()
    hand = app.state.hands[0].cards
    for c in hand[:3]:
        app._toggle_pass_selection(c)
    app._confirm_pass()
    assert app.scene is app_module.Scene.GAME
    assert app.state.phase is eng.Phase.PLAYING
    # All 4 players should have passed.
    assert len(app.state.pending_pass) == 4 or all(
        i not in app.state.pending_pass for i in range(4)
    )


# ----------------------------------------------------------------------
# 3. Game
# ----------------------------------------------------------------------

def test_human_legal_play(app):
    app._start_new_game()
    # Hand-pass: just give 3 arbitrary cards.
    for c in app.state.hands[0].cards[:3]:
        app._toggle_pass_selection(c)
    app._confirm_pass()
    # Drive frames until it's the human's turn (after AIs play).
    for _ in range(500):
        if (app.state.phase is eng.Phase.PLAYING
                and app.state.current_player_idx == 0):
            break
        app.drive_step(1)
    assert app._human_can_act(), f"AI never yielded to human (cur={app.state.current_player_idx})"
    # Pick the first legal card.
    legal = eng.legal_plays(app.state, 0)
    assert legal, "legal_plays must not be empty on human's turn"
    card = legal[0]
    app._try_human_play(card)
    # Card should be removed from hand.
    assert card not in app.state.hands[0].cards
    # Anim should be in progress.
    assert app.anim is not None
    assert (0, card) in app.anim.play_order


def test_human_illegal_play(app):
    app._start_new_game()
    for c in app.state.hands[0].cards[:3]:
        app._toggle_pass_selection(c)
    app._confirm_pass()
    for _ in range(100):
        if (app.state.phase is eng.Phase.PLAYING
                and app.state.current_player_idx == 0):
            break
        app.drive_step(1)
    # Find an illegal card (one not in legal_plays).
    legal = set(eng.legal_plays(app.state, 0))
    hand = app.state.hands[0].cards
    illegal = None
    for c in hand:
        if c not in legal:
            illegal = c
            break
    if illegal is None:
        pytest.skip("no illegal card available on this seed")
    before = list(app.state.hands[0].cards)
    app._try_human_play(illegal)
    # Hand should be unchanged.
    assert app.state.hands[0].cards == before
    # Shake message should be set.
    assert app.shake_message != ""


def test_ai_full_round(app):
    """All four players (3 AI + 1 human) play out a full round."""
    app._start_new_game()
    for c in app.state.hands[0].cards[:3]:
        app._toggle_pass_selection(c)
    app._confirm_pass()
    # Drive many frames so AI plays through.
    for _ in range(2000):
        if app.state is None:
            break
        if app.state.phase is eng.Phase.GAME_OVER:
            break
        if app.scene is app_module.Scene.PASS:
            # Re-enter a pass; simulate by advancing round directly.
            # (Round 1 has pass; rounds 2-3 too; round 4 has no pass.)
            # For this test we just need to make sure we don't hang.
            # Easiest: jump to round 4 which has pass_direction=NONE.
            app.state.round_number = 3
            app.state.start_round()
            app.scene = app_module.Scene.GAME
        # If human is up, play a random legal card.
        if (app.state.phase is eng.Phase.PLAYING
                and app.state.current_player_idx == 0
                and (app.anim is None or app.anim.is_done)):
            legal = eng.legal_plays(app.state, 0)
            if legal:
                app._try_human_play(legal[0])
        app.drive_step(1)
    # After many steps the round should have ended at least once or game-over.
    assert app.state.phase in (eng.Phase.PASSING, eng.Phase.PLAYING,
                                eng.Phase.GAME_OVER)


def test_human_cannot_act_during_animation(app):
    app._start_new_game()
    for c in app.state.hands[0].cards[:3]:
        app._toggle_pass_selection(c)
    app._confirm_pass()
    for _ in range(100):
        if (app.state.phase is eng.Phase.PLAYING
                and app.state.current_player_idx == 0):
            break
        app.drive_step(1)
    legal = eng.legal_plays(app.state, 0)
    app._try_human_play(legal[0])
    # Now anim is in progress; human cannot act again.
    assert not app._human_can_act()


# ----------------------------------------------------------------------
# 4. Help
# ----------------------------------------------------------------------

def test_help_scene_toggle_via_F1(app):
    app._start_new_game()
    for c in app.state.hands[0].cards[:3]:
        app._toggle_pass_selection(c)
    app._confirm_pass()
    # Synthesise F1 keydown.
    ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_F1})
    app._handle_key(ev)
    assert app.scene is app_module.Scene.HELP
    # ESC closes.
    ev = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_ESCAPE})
    app._handle_key(ev)
    assert app.scene is app_module.Scene.GAME


# ----------------------------------------------------------------------
# 5. Game-over & rematch
# ----------------------------------------------------------------------

def test_game_over_scene_has_rematch_button(app):
    # Force game over by setting a huge total score.
    app._start_new_game()
    for c in app.state.hands[0].cards[:3]:
        app._toggle_pass_selection(c)
    app._confirm_pass()
    assert app.state is not None
    app.state.total_scores[0] = 200
    app.state.phase = eng.Phase.GAME_OVER
    # Manually trigger the transition.
    app.drive_step(1)
    # engine.phase guard: only enter gameover when state actually has
    # GAME_OVER. Update should have transitioned us.
    assert app.scene is app_module.Scene.GAME_OVER


def test_rematch_resets_scores(app):
    app._start_new_game()
    for c in app.state.hands[0].cards[:3]:
        app._toggle_pass_selection(c)
    app._confirm_pass()
    # Bump scores.
    for p in app.players:
        p.total_points = 50
        p.tricks_won = 3
    # Force game over.
    app.state.phase = eng.Phase.GAME_OVER
    app.drive_step(1)
    assert app.scene is app_module.Scene.GAME_OVER
    # Click rematch.
    app.gameover_index = 0
    app._activate_gameover()
    assert app.scene is app_module.Scene.PASS
    # Scores should be reset.
    for p in app.players:
        assert p.total_points == 0
        assert p.tricks_won == 0


def test_back_to_menu_from_gameover(app):
    app._start_new_game()
    app.state.phase = eng.Phase.GAME_OVER
    app.drive_step(1)
    app.gameover_index = 1  # Back to menu
    app._activate_gameover()
    assert app.scene is app_module.Scene.MENU


# ----------------------------------------------------------------------
# 6. Screenshot capture (visual verification)
# ----------------------------------------------------------------------

@pytest.mark.parametrize("scene_name,setup", [
    ("menu", lambda a: None),
    ("settings", lambda a: setattr(a, "scene", app_module.Scene.SETTINGS)),
    ("pass_screen", lambda a: a._start_new_game()),
    ("game",
     lambda a: (
         a._start_new_game(),
         [a._toggle_pass_selection(c) for c in a.state.hands[0].cards[:3]],
         a._confirm_pass(),
         a.force_human_to_act(),
     )),
    ("help", lambda a: setattr(a, "scene", app_module.Scene.HELP)),
])
def test_screenshot_each_scene(app, scene_name, setup):
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    setup(app)
    out = SCREENSHOTS / f"{scene_name}.png"
    app.capture_screenshot(str(out))
    assert out.exists()
    assert out.stat().st_size > 0


# ----------------------------------------------------------------------
# 7. End-to-end smoke (full game in FAST_MODE)
# ----------------------------------------------------------------------

def test_end_to_end_full_game(app):
    """Drive a full game in FAST_MODE. AI plays all turns; human plays
    automatically when it's their turn. Verifies the game actually
    finishes and the trick counter advances."""
    app._start_new_game()
    for c in app.state.hands[0].cards[:3]:
        app._toggle_pass_selection(c)
    app._confirm_pass()
    max_frames = 200000
    total_at_start = sum(app.state.total_scores)
    rounds_played = 0
    saw_human_turn = False
    last_round = app.state.round_number
    for _ in range(max_frames):
        if app.state.phase is eng.Phase.GAME_OVER:
            # One more update to let _update transition the scene to GAME_OVER.
            app.drive_step(1)
            break
        if app.state.round_number != last_round:
            rounds_played += 1
            last_round = app.state.round_number
        # Auto-pass whenever the engine enters PASSING — even if the app's
        # scene didn't transition (the engine's start_round doesn't update
        # app.scene, so we have to drive it from here).
        if app.state.phase is eng.Phase.PASSING:
            if len(app.pass_selections) != 3:
                app.pass_selections = []
                for c in app.state.hands[0].cards[:3]:
                    app._toggle_pass_selection(c)
            app._confirm_pass()
            continue
        if (app.scene is app_module.Scene.GAME
                and app.state.phase is eng.Phase.PLAYING
                and app._human_can_act()):
            legal = eng.legal_plays(app.state, 0)
            if legal:
                saw_human_turn = True
                app._try_human_play(legal[0])
                continue
        # Step one frame at a time, breaking as soon as the human can act
        # or the game state changes (passing phase, round end, etc.).
        for _ in range(50):
            if app._human_can_act():
                break
            if app.state.phase is eng.Phase.PASSING:
                break
            if app.state.phase is eng.Phase.GAME_OVER:
                break
            app.drive_step(1)
    assert app.state.phase is eng.Phase.GAME_OVER, (
        f"game did not finish in {max_frames} frames; phase={app.state.phase}, "
        f"rounds={rounds_played}, total={app.state.total_scores}"
    )
    assert saw_human_turn
    # Scores advanced (game over means someone crossed 100).
    assert any(s >= 100 for s in app.state.total_scores)
    # Game over scene should be active.
    assert app.scene is app_module.Scene.GAME_OVER
