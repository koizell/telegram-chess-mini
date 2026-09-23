"""
Endpoints para partidas.
"""
import logging
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
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
# HELPERS: Fechas de PocketBase
# ============================================
def _parse_pb_date(iso_str: str):
    if not iso_str:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def _format_pb_date(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.000Z")


# ============================================
# HELPERS: ELO
# ============================================
def _calculate_elo(player_elo: int, opponent_elo: int, score: float, k: int = 32) -> int:
    expected = 1 / (1 + 10 ** ((opponent_elo - player_elo) / 400))
    new_elo = player_elo + k * (score - expected)
    return round(new_elo)


def _update_elo_after_pvp(game_data: dict, result: str):
    white_id = game_data.get("white_player")
    black_id = game_data.get("black_player")

    if not white_id or not black_id:
        logger.warning("No se puede actualizar ELO: jugadores faltantes")
        return

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
    else:
        white_score, black_score = 0.5, 0.5
        white_draws = white.get("draws", 0) + 1
        black_draws = black.get("draws", 0) + 1
        white_wins = white.get("wins", 0)
        black_wins = black.get("wins", 0)
        white_losses = white.get("losses", 0)
        black_losses = black.get("losses", 0)

    new_white_elo = _calculate_elo(white_elo, black_elo, white_score)
    new_black_elo = _calculate_elo(black_elo, white_elo, black_score)

    requests.patch(f"{url}/{white_id}", json={
        "elo": new_white_elo,
        "wins": white_wins,
        "losses": white_losses,
        "draws": white_draws,
    }, headers=pb._headers())

    requests.patch(f"{url}/{black_id}", json={
        "elo": new_black_elo,
        "wins": black_wins,
        "losses": black_losses,
        "draws": black_draws,
    }, headers=pb._headers())

    logger.info(f"✅ ELO actualizado: {white_elo}→{new_white_elo} (W), {black_elo}→{new_black_elo} (B)")


# ============================================
# HELPERS: Respuesta de partida
# ============================================
def _build_game_response(game, white, black, current_turn=None, timeout=False):
    """Construye la respuesta JSON estandarizada de una partida."""
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
        "time_white_ms": game.get("time_white_ms", 0) or 0,
        "time_black_ms": game.get("time_black_ms", 0) or 0,
        "time_control_ms": game.get("time_control_ms", 0) or 0,
        "last_move_at": game.get("last_move_at"),
        "current_turn": current_turn,
        "server_now": datetime.now(timezone.utc).isoformat(),
        "timeout": timeout,
    }


# ============================================
# ENDPOINT: Crear partida (vs bot)
# ============================================
@router.post("")
async def create_game(req: CreateGameRequest):
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
    """Devuelve el estado de una partida. Detecta timeouts."""
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

        game_type = game.get("game_type")
        status = game.get("status")

        time_white = game.get("time_white_ms", 0) or 0
        time_black = game.get("time_black_ms", 0) or 0
        time_control = game.get("time_control_ms", 0) or 0
        last_move_at_str = game.get("last_move_at")

        current_turn = None

        # Detección de timeout (solo PvP activas)
        if game_type == "pvp" and status == "active" and time_control > 0:
            board = ChessGame(game.get("fen", ""))
            current_turn = board.turn

            last_move_at = _parse_pb_date(last_move_at_str)
            now = datetime.now(timezone.utc)
            elapsed_ms = max(0, int((now - last_move_at).total_seconds() * 1000))

            live_white = max(0, time_white - elapsed_ms) if current_turn == "white" else time_white
            live_black = max(0, time_black - elapsed_ms) if current_turn == "black" else time_black

            # Timeout de blancas
            if current_turn == "white" and live_white == 0:
                update = {
                    "status": "finished",
                    "result": "black_wins",
                    "winner": game.get("black_player"),
                    "time_white_ms": 0,
                    "time_black_ms": time_black,
                    "pgn": (game.get("pgn") or "") + " {Blancas perdieron por tiempo}",
                }
                requests.patch(url, json=update, headers=pb._headers())
                _update_elo_after_pvp(game, "black_wins")

                # Recargar para devolver estado actualizado
                response = requests.get(url, headers=pb._headers(), params=params)
                game = response.json()
                return _build_game_response(game, white, black, current_turn=None, timeout=True)

            # Timeout de negras
            if current_turn == "black" and live_black == 0:
                update = {
                    "status": "finished",
                    "result": "white_wins",
                    "winner": game.get("white_player"),
                    "time_white_ms": time_white,
                    "time_black_ms": 0,
                    "pgn": (game.get("pgn") or "") + " {Negras perdieron por tiempo}",
                }
                requests.patch(url, json=update, headers=pb._headers())
                _update_elo_after_pvp(game, "white_wins")

                response = requests.get(url, headers=pb._headers(), params=params)
                game = response.json()
                return _build_game_response(game, white, black, current_turn=None, timeout=True)

        return _build_game_response(game, white, black, current_turn=current_turn, timeout=False)

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
    """Aplica un movimiento con gestión de reloj."""
    try:
        pb.authenticate()

        url = f"{pb.url}/api/collections/games/records/{game_id}"
        response = requests.get(url, headers=pb._headers())
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Partida no encontrada")

        game_data = response.json()
        game_type = game_data.get("game_type", "vs_bot")

        if game_data.get("status") != "active":
            raise HTTPException(status_code=400, detail="La partida no está activa")

        board_game = ChessGame(game_data.get("fen"))
        turn = board_game.turn

        # ── Validación de turno (PvP) ──
        if game_type == "pvp":
            player = pb.get_user_by_telegram_id(move.telegram_id)
            if not player:
                raise HTTPException(status_code=404, detail="Jugador no encontrado")

            player_id = player["id"]
            white_id = game_data.get("white_player")
            black_id = game_data.get("black_player")

            if player_id not in (white_id, black_id):
                raise HTTPException(status_code=403, detail="No eres jugador de esta partida")

            is_white = player_id == white_id
            if (is_white and turn != "white") or (not is_white and turn != "black"):
                raise HTTPException(status_code=400, detail="No es tu turno")

        # ── Gestión del reloj (PvP) ──
        update_data = {}
        if game_type == "pvp":
            time_white = game_data.get("time_white_ms", 0) or 0
            time_black = game_data.get("time_black_ms", 0) or 0
            time_control = game_data.get("time_control_ms", 0) or 0
            last_move_at = _parse_pb_date(game_data.get("last_move_at"))

            if time_white == 0 and time_black == 0 and time_control == 0:
                time_white = time_black = time_control = 300000

            now = datetime.now(timezone.utc)
            elapsed_ms = max(0, int((now - last_move_at).total_seconds() * 1000))

            # Obtener incremento (Fischer)
            increment_ms = game_data.get("increment_ms", 0) or 0

            if turn == "white":
                time_white = max(0, time_white - elapsed_ms) + increment_ms
            else:
                time_black = max(0, time_black - elapsed_ms) + increment_ms

            # Timeout del que mueve
            if (turn == "white" and time_white == 0) or (turn == "black" and time_black == 0):
                winner_id = game_data.get("black_player") if turn == "white" else game_data.get("white_player")
                result = "black_wins" if turn == "white" else "white_wins"

                timeout_update = {
                    "status": "finished",
                    "result": result,
                    "winner": winner_id,
                    "time_white_ms": time_white,
                    "time_black_ms": time_black,
                    "pgn": (game_data.get("pgn") or "") + " {Timeout}",
                }
                requests.patch(url, json=timeout_update, headers=pb._headers())
                _update_elo_after_pvp(game_data, result)

                return {
                    "status": "ok",
                    "fen": board_game.fen,
                    "is_game_over": True,
                    "result": result,
                    "status_message": "⏰ Tiempo agotado",
                }

            update_data["time_white_ms"] = time_white
            update_data["time_black_ms"] = time_black
            update_data["last_move_at"] = _format_pb_date(now)

        # ── Aplicar el movimiento ──
        if not board_game.make_move(move.from_square, move.to_square, move.promotion):
            legal = board_game.get_legal_moves_from(move.from_square)
            raise HTTPException(
                status_code=400,
                detail=f"Movimiento inválido. Legales desde {move.from_square}: {legal}"
            )

        update_data["fen"] = board_game.fen
        update_data["pgn"] = (game_data.get("pgn") or "") + " " + f"{move.from_square}{move.to_square}"

        game_over = board_game.is_game_over

        if game_over:
            result = board_game.get_result()
            update_data["status"] = "finished"
            update_data["result"] = result

            if result == "white_wins":
                update_data["winner"] = game_data.get("white_player")
            elif result == "black_wins":
                update_data["winner"] = game_data.get("black_player")

        update_response = requests.patch(url, json=update_data, headers=pb._headers())
        if update_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error guardando movimiento")

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
# ENDPOINT: Finalizar partida (vs bot o abandono)
# ============================================
@router.post("/{game_id}/finish")
async def finish_game(game_id: str, req: FinishGameRequest):
    try:
        pb.authenticate()

        if req.result not in ("white_wins", "black_wins", "draw", "aborted"):
            raise HTTPException(status_code=400, detail="Result inválido")

        is_aborted = req.result == "aborted"

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