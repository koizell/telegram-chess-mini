import os
from dotenv import load_dotenv

# Cargar las variables del archivo .env
load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# PocketBase
POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://192.168.0.102:8090")
POCKETBASE_ADMIN_EMAIL = os.getenv("POCKETBASE_ADMIN_EMAIL")
POCKETBASE_ADMIN_PASSWORD = os.getenv("POCKETBASE_ADMIN_PASSWORD")

# Stockfish
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/usr/games/stockfish")

# Validación básica
if not TELEGRAM_TOKEN:
    raise ValueError("❌ Falta TELEGRAM_TOKEN en el archivo .env")

if not POCKETBASE_ADMIN_EMAIL or not POCKETBASE_ADMIN_PASSWORD:
    raise ValueError("❌ Faltan las credenciales de PocketBase en el archivo .env")