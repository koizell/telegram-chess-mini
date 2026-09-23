"""
API REST para la Mini App de Telegram Chess Pi.
Este archivo es el que ejecuta uvicorn: app.api.main:app
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.client import pb
from app.api.routes import users, ranking, games, matchmaking, stream

# ============================================
# CONFIGURACIÓN DE LOGGING
# ============================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ============================================
# APLICACIÓN FASTAPI
# ============================================
app = FastAPI(
    title="Telegram Chess Pi API",
    description="API REST para la Mini App de ajedrez en Telegram",
    version="0.1.0",
)


# ============================================
# CORS
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://koizell.github.io",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# ENDPOINT: /
# ============================================
@app.get("/")
async def root():
    """Página de bienvenida."""
    return {
        "message": "♟️ Telegram Chess Pi API",
        "docs": "/docs",
        "health": "/api/health",
        "ranking": "/api/ranking",
    }


# ============================================
# ENDPOINT: /api/health
# ============================================
@app.get("/api/health")
async def health():
    """Verifica que la API está funcionando."""
    return {
        "status": "ok",
        "service": "telegram-chess-pi",
        "version": "0.1.0",
    }


# ============================================
# ENDPOINT: /api/pocketbase/status
# ============================================
@app.get("/api/pocketbase/status")
async def pocketbase_status():
    """Verifica la conexión con PocketBase."""
    try:
        pb.authenticate()
        import requests
        url = f"{pb.url}/api/collections/users/records"
        response = requests.get(url, headers=pb._headers(), params={"perPage": 1})
        total = response.json().get("totalItems", 0)
        return {
            "status": "ok",
            "pocketbase_url": pb.url,
            "total_users": total,
        }
    except Exception as e:
        logger.error(f"❌ Error conectando con PocketBase: {e}")
        return {
            "status": "error",
            "message": str(e),
        }


# ============================================
# REGISTRAR ROUTERS
# ============================================
app.include_router(users.router)
app.include_router(ranking.router)
app.include_router(games.router)
app.include_router(matchmaking.router)
app.include_router(stream.router)   
