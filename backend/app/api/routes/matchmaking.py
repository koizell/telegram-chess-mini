"""
Endpoints de matchmaking para PvP.
"""
import logging
import requests
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db.client import pb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matchmaking", tags=["matchmaking"])


# ============================================
# MODELOS
# ============================================
class JoinRequest(BaseModel):
    telegram_id: int


class CancelRequest(BaseModel):
    telegram_id: int


# ============================================
# HELPERS
# ============================================
def _get_player(telegram_id: int):
    """Devuelve el usuario o None."""
    return pb.get_user_by_telegram_id(telegram_id)


def _find_opponent(player_id: str, elo: int, exclude_telegram_id: int):
    """
    Busca un oponente en la cola con ELO similar (±200), excluyendo al jugador.
    Devuelve el registro de la cola o None.
    """
    url = f"{pb.url}/api/collections/matchmaking_queue/records"
    elo_min = max(0, elo - 200)
    elo_max = elo + 200

    # Buscar candidatos que estén esperando, con ELO similar, que no sean el jugador
    params = {
        "filter": (
            f'status="waiting" && '
            f'user_id != "{player_id}" && '
            f'elo >= {elo_min} && '
            f'elo <= {elo_max}'
        ),
        "sort": "created",  # el más antiguo primero
        "perPage": 1,
    }

    response = requests.get(url, headers=pb._headers(), params=params)
    if response.status_code != 200:
        logger.error(f"Error buscando oponente: {response.text}")
        return None

    items = response.json().get("items", [])
    return items[0] if items else None


# Tiempo inicial del reloj: 5 minutos
INITIAL_TIME_MS = 600000   # 10 minutos
INCREMENT_MS = 10000       # +10 segundos por movimiento (Fischer)


def _create_pvp_game(player_a_id: str, player_b_id: str):
    """Crea una partida PvP con reloj inicial de 5 minutos."""
    url = f"{pb.url}/api/collections/games/records"
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.000Z")

    data = {
        "white_player": player_a_id,
        "black_player": player_b_id,
        "game_type": "pvp",
        "status": "active",
        "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "time_white_ms": INITIAL_TIME_MS,
        "time_black_ms": INITIAL_TIME_MS,
        "time_control_ms": INITIAL_TIME_MS,
        "increment_ms": INCREMENT_MS,
        "last_move_at": now_iso,
    }
    response = requests.post(url, json=data, headers=pb._headers())
    if response.status_code != 200:
        logger.error(f"Error creando partida PvP: {response.text}")
        return None
    return response.json()


def _update_queue_entry(entry_id: str, **fields):
    """Actualiza un registro de la cola."""
    url = f"{pb.url}/api/collections/matchmaking_queue/records/{entry_id}"
    response = requests.patch(url, json=fields, headers=pb._headers())
    if response.status_code != 200:
        logger.error(f"Error actualizando cola: {response.text}")
        return None
    return response.json()


# ============================================
# ENDPOINT: Entrar a la cola
# ============================================
@router.post("/join")
async def join_queue(req: JoinRequest):
    """Añade al jugador a la cola de matchmaking. Si hay oponente, crea partida."""
    try:
        pb.authenticate()

        player = _get_player(req.telegram_id)
        if not player:
            raise HTTPException(status_code=404, detail="Jugador no encontrado")

        player_id = player["id"]
        player_elo = player.get("elo", 1200)

        # 1. Verificar si el jugador ya está en la cola
        url = f"{pb.url}/api/collections/matchmaking_queue/records"
        params = {
            "filter": f'user_id="{player_id}" && status="waiting"',
            "perPage": 1,
        }
        existing = requests.get(url, headers=pb._headers(), params=params)
        if existing.status_code == 200:
            items = existing.json().get("items", [])
            if items:
                # Ya está en cola, devolver el estado actual
                return {
                    "status": "waiting",
                    "queue_id": items[0]["id"],
                    "message": "Ya estás en la cola"
                }

        # 2. Buscar oponente
        opponent_entry = _find_opponent(player_id, player_elo, req.telegram_id)

        # 3. Crear entrada en la cola para el jugador actual
        queue_data = {
            "user_id": player_id,
            "telegram_id": str(req.telegram_id),
            "elo": player_elo,
            "status": "waiting",
        }
        create_response = requests.post(url, json=queue_data, headers=pb._headers())
        if create_response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error creando entrada: {create_response.text}")

        my_entry = create_response.json()

        # 4. Si no hay oponente, esperar
        if not opponent_entry:
            return {
                "status": "waiting",
                "queue_id": my_entry["id"],
                "message": "Buscando oponente..."
            }

        # 5. Hay oponente: crear la partida
        opponent_id = opponent_entry["user_id"]
        opponent_entry_id = opponent_entry["id"]

        game = _create_pvp_game(player_id, opponent_id)
        if not game:
            raise HTTPException(status_code=500, detail="Error creando partida PvP")

        game_id = game["id"]

        # 6. Marcar ambas entradas como matched con el game_id
        _update_queue_entry(my_entry["id"], status="matched", game_id=game_id)
        _update_queue_entry(opponent_entry_id, status="matched", game_id=game_id)

        logger.info(f"✅ Partida PvP creada: {game_id} ({player_id} vs {opponent_id})")

        return {
            "status": "matched",
            "game_id": game_id,
            "opponent_id": opponent_id,
            "player_color": "white",  # el jugador actual es blancas
            "message": "¡Oponente encontrado!"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en join_queue: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


# ============================================
# ENDPOINT: Consultar estado del matchmaking
# ============================================
@router.get("/status/{telegram_id}")
async def matchmaking_status(telegram_id: int):
    """Consulta si el jugador ya fue emparejado."""
    try:
        pb.authenticate()

        player = _get_player(telegram_id)
        if not player:
            raise HTTPException(status_code=404, detail="Jugador no encontrado")

        player_id = player["id"]

        # Buscar la entrada más reciente del jugador
        url = f"{pb.url}/api/collections/matchmaking_queue/records"
        params = {
            "filter": f'user_id="{player_id}"',
            "sort": "-created",
            "perPage": 1,
            "expand": "game_id,user_id",
        }
        response = requests.get(url, headers=pb._headers(), params=params)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error consultando estado")

        items = response.json().get("items", [])
        if not items:
            return {"status": "not_in_queue"}

        entry = items[0]
        status = entry.get("status")

        if status == "matched":
            game_id = entry.get("game_id")
            game_expanded = entry.get("expand", {}).get("game_id", {})

            # Determinar el color del jugador
            white = game_expanded.get("white_player")
            black = game_expanded.get("black_player")
            player_color = "white" if white == player_id else "black"

            # Obtener datos del oponente
            opponent_id = black if player_color == "white" else white
            opponent_url = f"{pb.url}/api/collections/users/records/{opponent_id}"
            opponent_res = requests.get(opponent_url, headers=pb._headers())
            opponent = opponent_res.json() if opponent_res.status_code == 200 else {}

            return {
                "status": "matched",
                "game_id": game_id,
                "player_color": player_color,
                "opponent_name": opponent.get("display_name", "Oponente"),
                "opponent_elo": opponent.get("elo", 1200),
            }

        elif status == "cancelled":
            return {"status": "cancelled"}

        return {"status": "waiting"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en matchmaking_status: {e}")
        raise HTTPException(status_code=500, detail="Error interno")


# ============================================
# ENDPOINT: Cancelar búsqueda
# ============================================
@router.post("/cancel")
async def cancel_matchmaking(req: CancelRequest):
    """Cancela la búsqueda de oponente."""
    try:
        pb.authenticate()

        player = _get_player(req.telegram_id)
        if not player:
            raise HTTPException(status_code=404, detail="Jugador no encontrado")

        player_id = player["id"]

        # Buscar entradas en waiting
        url = f"{pb.url}/api/collections/matchmaking_queue/records"
        params = {
            "filter": f'user_id="{player_id}" && status="waiting"',
        }
        response = requests.get(url, headers=pb._headers(), params=params)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error consultando cola")

        items = response.json().get("items", [])
        for entry in items:
            _update_queue_entry(entry["id"], status="cancelled")

        return {"status": "ok", "cancelled": len(items)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en cancel_matchmaking: {e}")
        raise HTTPException(status_code=500, detail="Error interno")