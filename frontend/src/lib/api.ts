/**
 * Cliente de la API de Telegram Chess Pi.
 */

// En desarrollo: URL relativa (el proxy de Vite se encarga)
// En producción: viene de la variable de entorno VITE_API_URL
//                configurada en GitHub Actions
const API_URL = import.meta.env.DEV
  ? ''
  : (import.meta.env.VITE_API_URL || '');

if (!import.meta.env.DEV && !API_URL) {
  console.warn('⚠️ VITE_API_URL no está configurada. Las llamadas a la API fallarán.');
}

export async function getHealth() {
  const res = await fetch(`${API_URL}/api/health`);
  if (!res.ok) throw new Error('API no disponible');
  return res.json();
}

export async function getRanking(limit: number = 10) {
  const res = await fetch(`${API_URL}/api/ranking?limit=${limit}`);
  if (!res.ok) throw new Error('Error obteniendo ranking');
  return res.json();
}

export async function getUser(telegramId: number) {
  const res = await fetch(`${API_URL}/api/users/${telegramId}`);
  if (!res.ok) throw new Error('Usuario no encontrado');
  return res.json();
}