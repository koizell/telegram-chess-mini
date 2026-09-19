"""
Endpoints para rankings.
"""
import logging
import requests
from fastapi import APIRouter, HTTPException
from app.db.client import pb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ranking", tags=["ranking"])


@router.get("")
async def get_ranking(limit: int = 10):
    """Devuelve el top N de jugadores por ELO."""
    try:
        pb.authenticate()
        url = f"{pb.url}/api/collections/users/records"
        params = {
            "sort": "-elo",
            "perPage": limit,
            "filter": 'telegram_id != ""',
        }
        response = requests.get(url, headers=pb._headers(), params=params)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error consultando ranking")

        items = response.json().get("items", [])
        ranking = []
        for i, user in enumerate(items, start=1):
            ranking.append({
                "rank": i,
                "telegram_id": user.get("telegram_id"),
                "display_name": user.get("display_name"),
                "elo": user.get("elo", 1200),
                "wins": user.get("wins", 0),
                "losses": user.get("losses", 0),
                "draws": user.get("draws", 0),
            })

        return {"ranking": ranking, "total": len(ranking)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en get_ranking: {e}")
        raise HTTPException(status_code=500, detail="Error interno")