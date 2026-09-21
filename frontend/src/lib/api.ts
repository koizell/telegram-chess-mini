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


/**
 * Finaliza una partida guardando el resultado.
 */
export async function finishGame(
  gameId: string,
  payload: {
    result: string;
    fen: string;
    pgn: string;
    winner_id?: string | null;
    game_type?: string;
  }
) {
  const res = await fetch(`${API_URL}/api/games/${gameId}/finish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_type: 'vs_bot',
      ...payload
    })
  });
  if (!res.ok) throw new Error('Error finalizando partida');
  return res.json();
}

/**
 * Obtiene el historial de partidas de un usuario.
 */
export async function getHistory(telegramId: number, limit: number = 20) {
  const res = await fetch(`${API_URL}/api/games/history/${telegramId}?limit=${limit}`);
  if (!res.ok) throw new Error('Error obteniendo historial');
  return res.json();
}


// ============================================
// MATCHMAKING (PvP)
// ============================================
export async function joinMatchmaking(telegramId: number) {
  const res = await fetch(`${API_URL}/api/matchmaking/join`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telegram_id: telegramId })
  });
  if (!res.ok) throw new Error('Error entrando a la cola');
  return res.json();
}

export async function getMatchmakingStatus(telegramId: number) {
  const res = await fetch(`${API_URL}/api/matchmaking/status/${telegramId}`);
  if (!res.ok) throw new Error('Error consultando estado');
  return res.json();
}

export async function cancelMatchmaking(telegramId: number) {
  const res = await fetch(`${API_URL}/api/matchmaking/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ telegram_id: telegramId })
  });
  if (!res.ok) throw new Error('Error cancelando búsqueda');
  return res.json();
}

// ============================================
// PARTIDAS PvP
// ============================================
export async function getGame(gameId: string) {
  const res = await fetch(`${API_URL}/api/games/${gameId}`);
  if (!res.ok) throw new Error('Error cargando partida');
  return res.json();
}

export async function makePvpMove(
  gameId: string,
  telegramId: number,
  fromSquare: string,
  toSquare: string,
  promotion?: string
) {
  const res = await fetch(`${API_URL}/api/games/${gameId}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      telegram_id: telegramId,
      from_square: fromSquare,
      to_square: toSquare,
      promotion: promotion || null
    })
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Error aplicando movimiento');
  }
  return res.json();
}

export async function finishPvpGame(gameId: string, payload: {
  result: string;
  fen: string;
  pgn: string;
  winner_id?: string | null;
  game_type?: string;
}) {
  const res = await fetch(`${API_URL}/api/games/${gameId}/finish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_type: 'pvp', ...payload })
  });
  if (!res.ok) throw new Error('Error finalizando partida');
  return res.json();
}