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

    # ============================================
# MODELO: Finalizar partida
# ============================================
class FinishGameRequest(BaseModel):
    result: str  # "white_wins" | "black_wins" | "draw"
    fen: str
    pgn: str
    winner_id: Optional[str] = None
    game_type: str = "vs_bot"  # "vs_bot" | "pvp"


# ============================================
# ENDPOINT: Finalizar partida
# ============================================
@router.post("/{game_id}/finish")
async def finish_game(game_id: str, req: FinishGameRequest):
    """Marca la partida como finalizada con el resultado."""
    try:
        pb.authenticate()

        # Validar result
        if req.result not in ("white_wins", "black_wins", "draw", "aborted"):
            raise HTTPException(status_code=400, detail="Result inválido")

        is_aborted = req.result == "aborted"

        # Construir datos según si es aborted o no
        data = {
            "fen": req.fen,
            "pgn": req.pgn,
            "game_type": req.game_type,
        }

        if is_aborted:
            # Partida abandonada: status aborted, sin resultado, sin winner
            data["status"] = "aborted"
        else:
            # Partida finalizada normalmente
            data["status"] = "finished"
            data["result"] = req.result
            if req.winner_id:
                data["winner"] = req.winner_id

        # Actualizar la partida
        url = f"{pb.url}/api/collections/games/records/{game_id}"
        response = requests.patch(url, json=data, headers=pb._headers())
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error guardando: {response.text}")

        return {"status": "ok", "game_id": game_id, "aborted": is_aborted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en finish_game: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


# ============================================
# ENDPOINT: Historial de partidas
# ============================================
@router.get("/history/{telegram_id}")
async def get_history(telegram_id: int, limit: int = 20):
    """Devuelve las últimas partidas de un usuario."""
    try:
        pb.authenticate()

        # Buscar el usuario
        player = pb.get_user_by_telegram_id(telegram_id)
        if not player:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        player_id = player["id"]

        # Buscar partidas donde sea white_player o black_player
        url = f"{pb.url}/api/collections/games/records"
        params = {
            "filter": f'(white_player="{player_id}" || black_player="{player_id}") && status="finished"',
            "sort": "-updated",
            "perPage": limit,
            "expand": "white_player,black_player,winner",
        }
        response = requests.get(url, headers=pb._headers(), params=params)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error consultando historial")

        items = response.json().get("items", [])
        games = []
        for g in items:
            white = g.get("expand", {}).get("white_player", {})
            black = g.get("expand", {}).get("black_player", {})
            winner_exp = g.get("expand", {}).get("winner", {})

            # Determinar si el jugador fue blancas o negras
            is_white = white.get("telegram_id") == str(telegram_id)
            opponent = black if is_white else white
            player_color = "white" if is_white else "black"

            # Determinar resultado desde la perspectiva del jugador
            result = g.get("result")
            status = g.get("status")
            if status == "aborted":
                outcome = "aborted"
            elif result == "draw":
                outcome = "draw"
            elif (result == "white_wins" and is_white) or (result == "black_wins" and not is_white):
                outcome = "win"
            else:
                outcome = "loss"

            games.append({
                "id": g["id"],
                "date": g.get("updated", ""),
                "game_type": g.get("game_type", "vs_bot"),
                "player_color": player_color,
                "opponent_name": opponent.get("display_name", "Desconocido"),
                "opponent_telegram_id": opponent.get("telegram_id"),
                "outcome": outcome,
                "result": result,
                "status": status,
                "fen": g.get("fen", ""),
                "pgn": g.get("pgn", ""),
                "winner_name": winner_exp.get("display_name") if winner_exp else None,
            })

        return {"games": games, "total": len(games)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en get_history: {e}")
        raise HTTPException(status_code=500, detail="Error interno")