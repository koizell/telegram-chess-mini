/**
 * Cliente de la API de Telegram Chess Pi.
 */

// En desarrollo: URL relativa (el proxy de Vite se encarga)
// En producción: URL completa de tu API (túnel Cloudflare)
const API_URL = import.meta.env.DEV
  ? ''
  : 'https://TU_DOMINIO_CLOUDFLARE.pages.dev'; // ← lo cambiaremos al desplegar

/**
 * Health check de la API.
 */
export async function getHealth() {
  const res = await fetch(`${API_URL}/api/health`);
  if (!res.ok) throw new Error('API no disponible');
  return res.json();
}

/**
 * Obtiene el ranking global.
 */
export async function getRanking(limit: number = 10) {
  const res = await fetch(`${API_URL}/api/ranking?limit=${limit}`);
  if (!res.ok) throw new Error('Error obteniendo ranking');
  return res.json();
}

/**
 * Obtiene el perfil de un usuario por su telegram_id.
 */
export async function getUser(telegramId: number) {
  const res = await fetch(`${API_URL}/api/users/${telegramId}`);
  if (!res.ok) throw new Error('Usuario no encontrado');
  return res.json();
}