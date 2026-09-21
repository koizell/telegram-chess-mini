"""
Endpoints para partidas.
"""
import logging
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.db.client import pb
from app.modules.game.engine import ChessGame

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/games", tags=["games"])


# ============================================
# MODELOS
# ============================================
class MoveRequest(BaseModel):
    telegram_id: int
    from_square: str
    to_square: str
    promotion: Optional[str] = None


class CreateGameRequest(BaseModel):
    telegram_id: int
    opponent_id: str


class MessageRequest(BaseModel):
    telegram_id: int
    content: str


# ============================================
# ENDPOINT: Crear partida
# ============================================
@router.post("")
async def create_game(req: CreateGameRequest):
    """Crea una partida nueva."""
    try:
        pb.authenticate()

        player = pb.get_user_by_telegram_id(req.telegram_id)
        if not player:
            raise HTTPException(status_code=404, detail="Jugador no encontrado")

        url = f"{pb.url}/api/collections/games/records"
        data = {
            "white_player": player["id"],
            "black_player": req.opponent_id,
            "game_type": "vs_bot",
            "status": "active",
            "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        }
        response = requests.post(url, json=data, headers=pb._headers())
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error creando partida: {response.text}")

        game = response.json()
        return {"game_id": game["id"], "fen": game["fen"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en create_game: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


# ============================================
# ENDPOINT: Estado de una partida
# ============================================
@router.get("/{game_id}")
async def get_game(game_id: str):
    """Devuelve el estado de una partida por ID."""
    try:
        pb.authenticate()
        url = f"{pb.url}/api/collections/games/records/{game_id}"
        response = requests.get(url, headers=pb._headers())
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Partida no encontrada")

        game = response.json()
        return {
            "id": game.get("id"),
            "fen": game.get("fen"),
            "status": game.get("status"),
            "game_type": game.get("game_type"),
            "white_player": game.get("white_player"),
            "black_player": game.get("black_player"),
            "winner": game.get("winner"),
            "result": game.get("result"),
            "pgn": game.get("pgn"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en get_game: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


# ============================================
# ENDPOINT: Movimiento
# ============================================
@router.post("/{game_id}/move")
async def make_move(game_id: str, move: MoveRequest):
    """Aplica un movimiento a una partida."""
    try:
        pb.authenticate()

        url = f"{pb.url}/api/collections/games/records/{game_id}"
        response = requests.get(url, headers=pb._headers())
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Partida no encontrada")

        game_data = response.json()
        fen = game_data.get("fen")

        board_game = ChessGame(fen)

        if not board_game.make_move(move.from_square, move.to_square, move.promotion):
            legal = board_game.get_legal_moves_from(move.from_square)
            raise HTTPException(
                status_code=400,
                detail=f"Movimiento inválido. Legales desde {move.from_square}: {legal}"
            )

        update_data = {
            "fen": board_game.fen,
            "pgn": (game_data.get("pgn") or "") + " " + f"{move.from_square}{move.to_square}",
        }

        if board_game.is_game_over:
            update_data["status"] = "finished"
            update_data["result"] = board_game.get_result()

        update_response = requests.patch(url, json=update_data, headers=pb._headers())
        if update_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error guardando movimiento")

        return {
            "status": "ok",
            "fen": board_game.fen,
            "is_game_over": board_game.is_game_over,
            "result": board_game.get_result(),
            "status_message": board_game.get_status_message(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en make_move: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


# ============================================
# ENDPOINT: Listar mensajes
# ============================================
@router.get("/{game_id}/messages")
async def get_messages(game_id: str, limit: int = 50):
    """Lista los mensajes de una partida."""
    try:
        pb.authenticate()
        url = f"{pb.url}/api/collections/messages/records"
        params = {
            "filter": f'game_id="{game_id}"',
            "sort": "created",
            "perPage": limit,
            "expand": "sender",
        }
        response = requests.get(url, headers=pb._headers(), params=params)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error listando mensajes")

        items = response.json().get("items", [])
        messages = []
        for msg in items:
            # El sender expandido viene en msg["expand"]["sender"]
            sender_expanded = msg.get("expand", {}).get("sender", {})
            sender_telegram_id = sender_expanded.get("telegram_id")

            messages.append({
                "id": msg["id"],
                "sender_id": msg.get("sender"),
                "sender_telegram_id": int(sender_telegram_id) if sender_telegram_id else None,
                "content": msg.get("content", ""),
                "created": msg.get("created", ""),
            })
        return {"messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en get_messages: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


# ============================================
# ENDPOINT: Enviar mensaje
# ============================================
@router.post("/{game_id}/messages")
async def send_message(game_id: str, msg: MessageRequest):
    """Guarda un mensaje en la partida."""
    try:
        pb.authenticate()

        sender = pb.get_user_by_telegram_id(msg.telegram_id)
        if not sender:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        content = msg.content.strip()
        if not content or len(content) > 500:
            raise HTTPException(status_code=400, detail="Mensaje inválido (1-500 caracteres)")

        url = f"{pb.url}/api/collections/messages/records"
        data = {
            "game_id": game_id,
            "sender": sender["id"],
            "content": content,
        }
        response = requests.post(url, json=data, headers=pb._headers())
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error guardando: {response.text}")

        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en send_message: {e}")
        raise HTTPException(status_code=500, detail="Error interno")