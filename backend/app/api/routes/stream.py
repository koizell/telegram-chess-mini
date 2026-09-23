"""
Endpoint SSE para notificaciones en tiempo real de partidas PvP.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from sse_starlette.sse import EventSourceResponse
from app.db.client import pb
from app.modules.game.engine import ChessGame

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/games", tags=["stream"])


def _get_game_state(game_id: str):
    """Obtiene el estado actual de la partida desde PocketBase."""
    url = f"{pb.url}/api/collections/games/records/{game_id}"
    params = {"expand": "white_player,black_player,winner"}
    response = requests.get(url, headers=pb._headers(), params=params)
    if response.status_code != 200:
        return None
    return response.json()


def _get_last_message(game_id: str):
    """Obtiene el último mensaje del chat de la partida."""
    url = f"{pb.url}/api/collections/messages/records"
    params = {
        "filter": f'game_id="{game_id}"',
        "sort": "-created",
        "perPage": 1,
    }
    response = requests.get(url, headers=pb._headers(), params=params)
    if response.status_code != 200:
        return None
    items = response.json().get("items", [])
    return items[0] if items else None


@router.get("/{game_id}/stream")
async def stream_game(game_id: str, telegram_id: int = Query(...)):
    """
    Stream SSE con el estado de la partida.
    Envía eventos cuando:
    - Cambia el FEN (movimiento)
    - Termina la partida
    - Llega un nuevo mensaje de chat
    """
    pb.authenticate()

    # Verificar que el jugador existe
    player = pb.get_user_by_telegram_id(telegram_id)
    if not player:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")

    async def event_generator():
        last_fen = ""
        last_status = ""
        last_message_id = ""
        heartbeat_counter = 0

        while True:
            try:
                game = _get_game_state(game_id)
                if not game:
                    yield {
                        "event": "error",
                        "data": json.dumps({"message": "Partida no encontrada"})
                    }
                    break

                fen = game.get("fen", "")
                status = game.get("status", "")
                result = game.get("result", "")

                # ── Enviar si el FEN cambió (movimiento) ──
                if fen and fen != last_fen:
                    last_fen = fen
                    yield {
                        "event": "fen_update",
                        "data": json.dumps({
                            "fen": fen,
                            "status": status,
                            "result": result,
                            "time_white_ms": game.get("time_white_ms", 0),
                            "time_black_ms": game.get("time_black_ms", 0),
                            "last_move_at": game.get("last_move_at", ""),
                        })
                    }

                # ── Enviar si el estado cambió (fin de partida) ──
                if status != last_status:
                    last_status = status
                    yield {
                        "event": "status_change",
                        "data": json.dumps({
                            "status": status,
                            "result": result,
                        })
                    }

                # ── Enviar si hay nuevo mensaje de chat ──
                msg = _get_last_message(game_id)
                if msg:
                    msg_id = msg.get("id", "")
                    if msg_id and msg_id != last_message_id:
                        last_message_id = msg_id
                        yield {
                            "event": "chat_message",
                            "data": json.dumps({
                                "id": msg_id,
                                "sender_id": msg.get("sender"),
                                "content": msg.get("content", ""),
                                "created": msg.get("created", ""),
                            })
                        }

                # ── Heartbeat cada 15s para mantener viva la conexión ──
                heartbeat_counter += 1
                if heartbeat_counter >= 30:  # 30 * 0.5s = 15s
                    heartbeat_counter = 0
                    yield {"event": "heartbeat", "data": "{}"}

                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                logger.info(f"SSE conexión cerrada para game {game_id}")
                break
            except Exception as e:
                logger.error(f"Error en SSE stream: {e}")
                await asyncio.sleep(1)

    return EventSourceResponse(event_generator(), ping=15)


import requests  # Movido arriba si no estaba