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


class FinishGameRequest(BaseModel):
    result: str
    fen: str
    pgn: str
    winner_id: Optional[str] = None
    game_type: str = "vs_bot"


# ============================================
# HELPERS: ELO
# ============================================
def _calculate_elo(player_elo: int, opponent_elo: int, score: float, k: int = 32) -> int:
    """
    Calcula el nuevo ELO de un jugador.
    score: 1.0 victoria, 0.5 tablas, 0.0 derrota
    """
    expected = 1 / (1 + 10 ** ((opponent_elo - player_elo) / 400))
    new_elo = player_elo + k * (score - expected)
    return round(new_elo)


def _update_elo_after_pvp(game_data: dict, result: str):
    """
    Actualiza el ELO de ambos jugadores tras una partida PvP.
    result: 'white_wins', 'black_wins', 'draw'
    """
    white_id = game_data.get("white_player")
    black_id = game_data.get("black_player")

    if not white_id or not black_id:
        logger.warning("No se puede actualizar ELO: jugadores faltantes")
        return

    # Obtener ambos jugadores
    url = f"{pb.url}/api/collections/users/records"
    white_res = requests.get(f"{url}/{white_id}", headers=pb._headers())
    black_res = requests.get(f"{url}/{black_id}", headers=pb._headers())

    if white_res.status_code != 200 or black_res.status_code != 200:
        logger.error("No se pudo obtener los jugadores para actualizar ELO")
        return

    white = white_res.json()
    black = black_res.json()

    white_elo = white.get("elo", 1200)
    black_elo = black.get("elo", 1200)

    # Determinar score
    if result == "white_wins":
        white_score, black_score = 1.0, 0.0
        white_wins = white.get("wins", 0) + 1
        black_losses = black.get("losses", 0) + 1
        white_draws = white.get("draws", 0)
        black_draws = black.get("draws", 0)
    elif result == "black_wins":
        white_score, black_score = 0.0, 1.0
        white_losses = white.get("losses", 0) + 1
        black_wins = black.get("wins", 0) + 1
        white_draws = white.get("draws", 0)
        black_draws = black.get("draws", 0)
    else:  # draw
        white_score, black_score = 0.5, 0.5
        white_draws = white.get("draws", 0) + 1
        black_draws = black.get("draws", 0) + 1
        white_wins = white.get("wins", 0)
        black_wins = black.get("wins", 0)
        white_losses = white.get("losses", 0)
        black_losses = black.get("losses", 0)

    new_white_elo = _calculate_elo(white_elo, black_elo, white_score)
    new_black_elo = _calculate_elo(black_elo, white_elo, black_score)

    # Actualizar blanco
    white_update = {
        "elo": new_white_elo,
        "wins": white_wins,
        "losses": white_losses,
        "draws": white_draws,
    }
    requests.patch(f"{url}/{white_id}", json=white_update, headers=pb._headers())

    # Actualizar negro
    black_update = {
        "elo": new_black_elo,
        "wins": black_wins,
        "losses": black_losses,
        "draws": black_draws,
    }
    requests.patch(f"{url}/{black_id}", json=black_update, headers=pb._headers())

    logger.info(f"✅ ELO actualizado: {white_elo}→{new_white_elo} (W), {black_elo}→{new_black_elo} (B)")


# ============================================
# ENDPOINT: Crear partida (vs bot)
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
        params = {"expand": "white_player,black_player,winner"}
        response = requests.get(url, headers=pb._headers(), params=params)
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Partida no encontrada")

        game = response.json()
        expand = game.get("expand", {})
        white = expand.get("white_player", {})
        black = expand.get("black_player", {})

        return {
            "id": game.get("id"),
            "fen": game.get("fen"),
            "status": game.get("status"),
            "game_type": game.get("game_type"),
            "white_player_id": game.get("white_player"),
            "black_player_id": game.get("black_player"),
            "white_player_name": white.get("display_name"),
            "black_player_name": black.get("display_name"),
            "white_player_telegram_id": white.get("telegram_id"),
            "black_player_telegram_id": black.get("telegram_id"),
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
# ENDPOINT: Movimiento (PvP y vs bot)
# ============================================
@router.post("/{game_id}/move")
async def make_move(game_id: str, move: MoveRequest):
    """Aplica un movimiento. Valida turno y jugador en PvP."""
    try:
        pb.authenticate()

        # 1. Obtener la partida
        url = f"{pb.url}/api/collections/games/records/{game_id}"
        response = requests.get(url, headers=pb._headers())
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Partida no encontrada")

        game_data = response.json()
        game_type = game_data.get("game_type", "vs_bot")

        if game_data.get("status") != "active":
            raise HTTPException(status_code=400, detail="La partida no está activa")

        # 2. En PvP, verificar que el jugador sea uno de los dos y que sea su turno
        if game_type == "pvp":
            player = pb.get_user_by_telegram_id(move.telegram_id)
            if not player:
                raise HTTPException(status_code=404, detail="Jugador no encontrado")

            player_id = player["id"]
            white_id = game_data.get("white_player")
            black_id = game_data.get("black_player")

            if player_id not in (white_id, black_id):
                raise HTTPException(status_code=403, detail="No eres jugador de esta partida")

            # Determinar si es su turno según el FEN
            board_game = ChessGame(game_data.get("fen"))
            turn = board_game.turn  # "white" o "black"

            is_white = player_id == white_id
            if (is_white and turn != "white") or (not is_white and turn != "black"):
                raise HTTPException(status_code=400, detail="No es tu turno")
        else:
            board_game = ChessGame(game_data.get("fen"))

        # 3. Aplicar el movimiento
        if not board_game.make_move(move.from_square, move.to_square, move.promotion):
            legal = board_game.get_legal_moves_from(move.from_square)
            raise HTTPException(
                status_code=400,
                detail=f"Movimiento inválido. Legales desde {move.from_square}: {legal}"
            )

        # 4. Construir actualización
        update_data = {
            "fen": board_game.fen,
            "pgn": (game_data.get("pgn") or "") + " " + f"{move.from_square}{move.to_square}",
        }

        game_over = board_game.is_game_over

        if game_over:
            result = board_game.get_result()
            update_data["status"] = "finished"
            update_data["result"] = result

            # Determinar winner
            if result == "white_wins":
                update_data["winner"] = game_data.get("white_player")
            elif result == "black_wins":
                update_data["winner"] = game_data.get("black_player")

        # 5. Guardar en PocketBase
        update_response = requests.patch(url, json=update_data, headers=pb._headers())
        if update_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error guardando movimiento")

        # 6. Si terminó y es PvP, actualizar ELO
        if game_over and game_type == "pvp":
            result = board_game.get_result()
            if result:
                _update_elo_after_pvp(game_data, result)

        return {
            "status": "ok",
            "fen": board_game.fen,
            "is_game_over": game_over,
            "result": board_game.get_result(),
            "status_message": board_game.get_status_message(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en make_move: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


# ============================================
# ENDPOINT: Finalizar partida (para partidas vs bot)
# ============================================
@router.post("/{game_id}/finish")
async def finish_game(game_id: str, req: FinishGameRequest):
    """Marca la partida como finalizada. Solo actualiza ELO si es PvP."""
    try:
        pb.authenticate()

        if req.result not in ("white_wins", "black_wins", "draw", "aborted"):
            raise HTTPException(status_code=400, detail="Result inválido")

        is_aborted = req.result == "aborted"

        # Obtener la partida para saber si es PvP
        url = f"{pb.url}/api/collections/games/records/{game_id}"
        game_res = requests.get(url, headers=pb._headers())
        if game_res.status_code != 200:
            raise HTTPException(status_code=404, detail="Partida no encontrada")
        game_data = game_res.json()

        data = {
            "fen": req.fen,
            "pgn": req.pgn,
            "game_type": req.game_type,
        }

        if is_aborted:
            data["status"] = "aborted"
        else:
            data["status"] = "finished"
            data["result"] = req.result
            if req.winner_id:
                data["winner"] = req.winner_id

        response = requests.patch(url, json=data, headers=pb._headers())
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error guardando: {response.text}")

        # Actualizar ELO solo si es PvP y no es aborted
        if not is_aborted and req.game_type == "pvp":
            _update_elo_after_pvp(game_data, req.result)

        return {"status": "ok", "game_id": game_id, "aborted": is_aborted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en finish_game: {e}")
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
# ENDPOINT: Historial de partidas
# ============================================
@router.get("/history/{telegram_id}")
async def get_history(telegram_id: int, limit: int = 20):
    """Devuelve las últimas partidas de un usuario."""
    try:
        pb.authenticate()

        player = pb.get_user_by_telegram_id(telegram_id)
        if not player:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        player_id = player["id"]

        url = f"{pb.url}/api/collections/games/records"
        params = {
            "filter": f'(white_player="{player_id}" || black_player="{player_id}") && (status="finished" || status="aborted")',
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

            is_white = white.get("telegram_id") == str(telegram_id)
            opponent = black if is_white else white
            player_color = "white" if is_white else "black"

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