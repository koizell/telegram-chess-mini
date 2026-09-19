"""
Endpoints para usuarios.
"""
import logging
from fastapi import APIRouter, HTTPException
from app.db.client import pb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/{telegram_id}")
async def get_user(telegram_id: int):
    """Devuelve el perfil público de un usuario."""
    try:
        user = pb.get_user_by_telegram_id(telegram_id)
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        return {
            "telegram_id": user.get("telegram_id"),
            "display_name": user.get("display_name"),
            "telegram_username": user.get("telegram_username"),
            "elo": user.get("elo", 1200),
            "wins": user.get("wins", 0),
            "losses": user.get("losses", 0),
            "draws": user.get("draws", 0),
            "theme_id": user.get("theme_id"),
            "skin_id": user.get("skin_id"),
            "streak_days": user.get("streak_days", 0),
            "avatar": user.get("avatar"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en get_user: {e}")
        raise HTTPException(status_code=500, detail="Error interno")