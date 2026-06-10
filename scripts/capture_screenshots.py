"""Capture screenshots of all 6 scenes."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['HEARTS_FAST_MODE'] = '1'

import sys
import pygame
sys.path.insert(0, '/home/jd/.hermes/kanban/workspaces/t_hearts_polish/src')

from hearts import app as app_module
from hearts.app import App, Scene, SCREEN_W, SCREEN_H
import hearts.engine as eng

OUT = '/home/jd/.hermes/kanban/workspaces/t_hearts_polish/docs/screenshots'
os.makedirs(OUT, exist_ok=True)

# Need a real (non-headless) screen for screenshots, but we can use
# a Surface in headless mode and just call the draw methods directly.
# Actually, App.headless=True sets self.screen = None. We need a Surface.
# Trick: run the app with a dummy SDL driver — it still creates a real Surface.

a = App(headless=False)  # Will use dummy driver from env
a._start_new_game()

# MENU
a.scene = Scene.MENU
a._update()
a._draw()
pygame.image.save(a.screen, f'{OUT}/01_menu.png')
print('Saved 01_menu.png')

# SETTINGS
a.scene = Scene.SETTINGS
a._update()
a._draw()
pygame.image.save(a.screen, f'{OUT}/02_settings.png')
print('Saved 02_settings.png')

# PASS — need to set up the pass state
a.scene = Scene.PASS
# Give the human 3 cards selected
a.pass_selections = []
for c in a.state.hands[0].cards[:3]:
    a._toggle_pass_selection(c)
a._update()
a._draw()
pygame.image.save(a.screen, f'{OUT}/03_pass.png')
print('Saved 03_pass.png')
a._confirm_pass()  # complete the pass to enter GAME

# GAME
a.scene = Scene.GAME
a._update()
a._draw()
pygame.image.save(a.screen, f'{OUT}/04_game.png')
print('Saved 04_game.png')

# HELP
a.scene = Scene.HELP
a._update()
a._draw()
pygame.image.save(a.screen, f'{OUT}/05_help.png')
print('Saved 05_help.png')

# GAME_OVER — force it
a.scene = Scene.GAME_OVER
a._update()
a._draw()
pygame.image.save(a.screen, f'{OUT}/06_gameover.png')
print('Saved 06_gameover.png')

print(f'\nAll 6 screenshots saved to {OUT}')
