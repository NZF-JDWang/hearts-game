"""
Hearts web backend — FastAPI + WebSocket game server.

Each browser tab = one game session. State lives server-side.
WebSocket protocol: JSON messages for create game, play card, pass cards, etc.
AI auto-plays and pushes state updates to client.
Roster: each game draws 3 named AI opponents with avatars and personalities.
"""

import asyncio
import json
import random
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from engine import Card, Phase
from session import GameSession, create_session

# Resolve static directory relative to this file's location
from pathlib import Path
STATIC_DIR = Path(__file__).parent / "static"

# ── Game sessions ────────────────────────────────────────────────────

sessions: Dict[str, GameSession] = {}

# ── App ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def send_state(ws: WebSocket, session: GameSession, msg_type: str = "state"):
    """Helper to send current game state to client."""
    await ws.send_text(json.dumps({
        "type": msg_type,
        "state": session.snapshot(),
    }))


async def handle_trick_resolution(session: GameSession, ws: WebSocket):
    """If the trick is complete, resolve it and send updates.
    Returns True if round/game ended, False otherwise."""
    if session.state.phase != Phase.TRICK_END:
        return False

    winner = session.engine.resolve_trick(session.state)

    # Brief pause so the last card is visible before resolution
    await asyncio.sleep(0.6)

    await ws.send_text(json.dumps({
        "type": "trick_won",
        "winner": winner,
        "state": session.snapshot(),
    }))

    if session.state.phase == Phase.ROUND_END:
        await ws.send_text(json.dumps({
            "type": "round_end",
            "state": session.snapshot(),
        }))
        return True

    if session.state.phase == Phase.GAME_OVER:
        await ws.send_text(json.dumps({
            "type": "game_over",
            "state": session.snapshot(),
        }))
        return True

    # Small pause before next trick starts
    await asyncio.sleep(0.4)

    return False


async def _auto_play_ai(session: GameSession, ws: WebSocket):
    """Auto-play all consecutive AI turns with random thinking delays."""
    max_safety = 52
    steps = 0

    while steps < max_safety:
        # Resolve trick if needed
        if session.state.phase == Phase.TRICK_END:
            ended = await handle_trick_resolution(session, ws)
            if ended:
                return
            if session.state.phase == Phase.PLAYING and session.state.current_player == 0:
                break
            steps += 1
            continue

        # If human's turn, stop
        if session.state.phase != Phase.PLAYING:
            break
        if session.state.current_player == 0:
            break

        # AI "thinks" for a random delay
        think_time = random.uniform(0.6, 1.8)
        await asyncio.sleep(think_time)

        player = session.state.current_player
        card = session._ai_play(player)
        if card is None:
            break

        ok = session.engine.play_card(session.state, player, card)
        if not ok:
            break

        await ws.send_text(json.dumps({
            "type": "card_played",
            "player": player,
            "card": str(card),
            "player_name": session.player_names[player],
            "state": session.snapshot(),
        }))

        # Check if this play ended the trick
        if session.state.phase == Phase.TRICK_END:
            # Don't resolve yet — let the client see the last card briefly
            # Resolution happens on next loop iteration
            steps += 1
            continue

        if session.state.phase in (Phase.ROUND_END, Phase.GAME_OVER):
            # Brief pause then show round/game end
            await asyncio.sleep(0.5)
            await ws.send_text(json.dumps({
                "type": "round_end" if session.state.phase == Phase.ROUND_END else "game_over",
                "state": session.snapshot(),
            }))
            return

        steps += 1

    # Final state push
    await send_state(ws, session)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    session: Optional[GameSession] = None

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            action = msg.get("action")

            if action == "new_game":
                session = create_session()
                sessions[session.id] = session

                # AI auto-pass if in passing phase
                if session.state.phase == Phase.PASSING:
                    for p in range(1, 4):
                        if p not in session.state.passed_cards:
                            cards = session._ai_pass(p)
                            session.engine.pass_cards(session.state, p, cards)

                await send_state(ws, session)

                # If game already transitioned to PLAYING and AI leads, auto-play
                if session.state.phase == Phase.PLAYING and session.state.current_player != 0:
                    await _auto_play_ai(session, ws)

            elif action == "pass_cards" and session:
                cards = [Card.from_str(c) for c in msg.get("cards", [])]
                ok = session.engine.pass_cards(session.state, 0, cards)
                if ok:
                    await send_state(ws, session)
                    # After passing, game transitions to PLAYING
                    if session.state.phase == Phase.PLAYING and session.state.current_player != 0:
                        await _auto_play_ai(session, ws)

            elif action == "play_card" and session:
                card = Card.from_str(msg.get("card", ""))
                ok = session.engine.play_card(session.state, 0, card)
                if ok:
                    await ws.send_text(json.dumps({
                        "type": "card_played",
                        "player": 0,
                        "card": str(card),
                        "state": session.snapshot(),
                    }))

                    # Check if trick ended
                    if session.state.phase == Phase.TRICK_END:
                        ended = await handle_trick_resolution(session, ws)
                        if ended:
                            return  # round/game over
                        # After resolution, check if AIs need to play
                        if session.state.phase == Phase.PLAYING and session.state.current_player != 0:
                            await _auto_play_ai(session, ws)
                        else:
                            await send_state(ws, session)
                    elif session.state.phase == Phase.PLAYING and session.state.current_player != 0:
                        await _auto_play_ai(session, ws)
                    else:
                        await send_state(ws, session)

            elif action == "next_round" and session:
                session.engine.next_round(session.state)
                # AI auto-pass
                if session.state.phase == Phase.PASSING:
                    for p in range(1, 4):
                        if p not in session.state.passed_cards:
                            cards = session._ai_pass(p)
                            session.engine.pass_cards(session.state, p, cards)
                    await send_state(ws, session)
                else:
                    await send_state(ws, session)
                    # If AI leads, auto-play
                    if session.state.phase == Phase.PLAYING and session.state.current_player != 0:
                        await _auto_play_ai(session, ws)

            elif action == "get_state" and session:
                await send_state(ws, session)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
        except:
            pass


# ── Static files ─────────────────────────────────────────────────────

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")