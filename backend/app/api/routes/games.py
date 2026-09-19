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


class MoveRequest(BaseModel):
    telegram_id: int
    from_square: str
    to_square: str
    promotion: Optional[str] = None


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