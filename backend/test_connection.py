import requests

# ============================================
# CONFIGURACIÓN
# ============================================
PB_URL = "http://192.168.0.102:8090"
ADMIN_EMAIL = "puertasaezj@gmail.com"
ADMIN_PASSWORD = "Estupidos@1"


# ============================================
# FUNCIÓN DE PRUEBA
# ============================================
def test_connection():
    print("🔍 Probando conexión a PocketBase...")
    print(f"   URL: {PB_URL}")
    print(f"   Admin: {ADMIN_EMAIL}")
    print()

    auth_url = f"{PB_URL}/api/admins/auth-with-password"
    auth_data = {
        "identity": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }

    try:
        response = requests.post(auth_url, json=auth_data)

        if response.status_code != 200:
            print(f"❌ Error de autenticación: {response.status_code}")
            print(f"   Detalle: {response.text}")
            return

        token = response.json()["token"]
        print("✅ Autenticación exitosa")
        print(f"   Token: {token[:40]}...")
        print()

        headers = {"Authorization": f"Bearer {token}"}
        collections_url = f"{PB_URL}/api/collections"
        response = requests.get(collections_url, headers=headers)

        if response.status_code == 200:
            collections = response.json()["items"]
            print(f"📚 Colecciones encontradas ({len(collections)}):")
            for col in collections:
                print(f"   • {col['name']} ({col['type']})")
            print()
            print("✅ ¡Todo funciona correctamente!")
        else:
            print(f"❌ Error al listar colecciones: {response.status_code}")
            print(f"   Detalle: {response.text}")

    except requests.exceptions.ConnectionError:
        print("❌ No se pudo conectar a PocketBase.")
        print("   Verifica que la BTT Pi esté encendida y PocketBase corriendo.")

    except requests.exceptions.Timeout:
        print("❌ Timeout: PocketBase tardó demasiado en responder.")

    except Exception as e:
        print(f"❌ Error inesperado: {e}")


if __name__ == "__main__":
    test_connection()