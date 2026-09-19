import requests
from app.config import (
    POCKETBASE_URL,
    POCKETBASE_ADMIN_EMAIL,
    POCKETBASE_ADMIN_PASSWORD,
)


class PocketBaseClient:
    def __init__(self):
        self.url = POCKETBASE_URL
        self.token = None

    def authenticate(self):
        """Autentica como admin/superusuario."""
        auth_url = f"{self.url}/api/admins/auth-with-password"
        data = {
            "identity": POCKETBASE_ADMIN_EMAIL,
            "password": POCKETBASE_ADMIN_PASSWORD,
        }
        response = requests.post(auth_url, json=data)
        if response.status_code != 200:
            raise Exception(f"Error de autenticación: {response.text}")
        self.token = response.json()["token"]
        return self.token

    def _headers(self):
        if not self.token:
            self.authenticate()
        return {"Authorization": f"Bearer {self.token}"}

    def get_user_by_telegram_id(self, telegram_id):
        """Busca un usuario por su telegram_id."""
        url = f"{self.url}/api/collections/users/records"
        params = {"filter": f'telegram_id="{telegram_id}"'}
        response = requests.get(url, headers=self._headers(), params=params)
        if response.status_code != 200:
            return None
        items = response.json().get("items", [])
        return items[0] if items else None

    def create_user(self, telegram_id, telegram_username, display_name):
        """Crea un usuario nuevo."""
        url = f"{self.url}/api/collections/users/records"
        data = {
            "telegram_id": str(telegram_id),
            "telegram_username": telegram_username or "",
            "display_name": display_name,
            "elo": 1200,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "referral_count": 0,
            "referral_points": 0,
            "streak_days": 0,
            "email": f"{telegram_id}@bttpi.local",
            "password": f"pb_{telegram_id}_secret",
            "passwordConfirm": f"pb_{telegram_id}_secret",
        }
        response = requests.post(url, json=data, headers=self._headers())
        if response.status_code != 200:
            raise Exception(f"Error al crear usuario: {response.text}")
        return response.json()

    def get_or_create_user(self, telegram_id, telegram_username, display_name):
        """Devuelve el usuario existente o lo crea si no existe."""
        user = self.get_user_by_telegram_id(telegram_id)
        if user:
            return user, False
        user = self.create_user(telegram_id, telegram_username, display_name)
        return user, True


# Instancia global
pb = PocketBaseClient()