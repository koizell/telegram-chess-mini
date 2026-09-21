<script lang="ts">
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { tgUser } from '$lib/telegram';
  import { getHistory } from '$lib/api';

  interface Game {
    id: string;
    date: string;
    game_type: string;
    player_color: string;
    opponent_name: string;
    outcome: string;
    result: string;
    fen: string;
    pgn: string;
    winner_name: string | null;
  }

  let games: Game[] = [];
  let loading = true;
  let error = '';

  function getUserId(): number | null {
    return import.meta.env.DEV ? 5125415147 : ($tgUser?.id ?? null);
  }

  async function loadHistory() {
    const userId = getUserId();
    if (!userId) {
      error = 'Abre esta página desde Telegram para ver tu historial.';
      loading = false;
      return;
    }

    try {
      const data = await getHistory(userId, 30);
      games = data.games || [];
    } catch (e) {
      error = 'No se pudo cargar el historial. Intenta de nuevo.';
      console.error(e);
    } finally {
      loading = false;
    }
  }

  function formatDate(iso: string): string {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString('es-CO', {
        day: 'numeric',
        month: 'short',
        year: 'numeric'
      });
    } catch {
      return '';
    }
  }

  function outcomeEmoji(outcome: string): string {
    if (outcome === 'win') return '🏆';
    if (outcome === 'loss') return '❌';
    if (outcome === 'aborted') return '🚪';
    return '🤝';
  }

  function outcomeText(outcome: string): string {
    if (outcome === 'win') return 'Victoria';
    if (outcome === 'loss') return 'Derrota';
    if (outcome === 'aborted') return 'Abandonada';
    return 'Tablas';
  }

  function outcomeColor(outcome: string): string {
    if (outcome === 'win') return 'win';
    if (outcome === 'loss') return 'loss';
    if (outcome === 'aborted') return 'aborted';
    return 'draw';
  }

  function gameTypeText(type: string): string {
    return type === 'pvp' ? '👥 vs Jugador' : '🤖 vs IA';
  }

  function colorText(color: string): string {
    return color === 'white' ? '⚪ Blancas' : '⚫ Negras';
  }

  onMount(loadHistory);
</script>

<main>
  <header>
    <a href="{base}/" class="back-link">←</a>
    <h1>📜 Mi Historial</h1>
    <span class="spacer"></span>
  </header>

  {#if loading}
    <p class="status">Cargando...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if games.length === 0}
    <div class="empty">
      <p>🎮 Aún no has jugado partidas.</p>
      <a href="{base}/" class="cta">Empezar a jugar</a>
    </div>
  {:else}
    <div class="stats-bar">
      <span>Total: <strong>{games.length}</strong></span>
      <span>🏆 {games.filter(g => g.outcome === 'win').length}</span>
      <span>❌ {games.filter(g => g.outcome === 'loss').length}</span>
      <span>🤝 {games.filter(g => g.outcome === 'draw').length}</span>
    </div>

    <ul class="games-list">
      {#each games as g (g.id)}
        <li class="game-item {outcomeColor(g.outcome)}">
          <div class="row-1">
            <span class="outcome">
              {outcomeEmoji(g.outcome)} {outcomeText(g.outcome)}
            </span>
            <span class="date">{formatDate(g.date)}</span>
          </div>

          <div class="row-2">
            <span class="opponent">vs <strong>{g.opponent_name}</strong></span>
            <span class="color">{colorText(g.player_color)}</span>
          </div>

          <div class="row-3">
            <span class="type">{gameTypeText(g.game_type)}</span>
            <span class="moves">
              {g.pgn ? `${g.pgn.split(/\d+\./).length - 1} movs` : ''}
            </span>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</main>

<style>
  main {
    padding: 1rem;
    max-width: 500px;
    margin: 0 auto;
    font-family: system-ui, -apple-system, sans-serif;
    background: #1a1a1a;
    color: #fff;
    min-height: 100vh;
  }

  header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1.5rem;
  }

  header h1 {
    flex: 1;
    text-align: center;
    font-size: 1.25rem;
    margin: 0;
  }

  .back-link {
    color: #4ade80;
    text-decoration: none;
    font-size: 1.25rem;
    padding: 0.25rem 0.5rem;
    border-radius: 6px;
    transition: background 0.15s;
  }

  .back-link:hover { background: #2a2a2a; }

  .spacer { width: 30px; }

  .status, .error {
    text-align: center;
    padding: 1rem;
  }

  .error {
    color: #ff6b6b;
    background: rgba(255, 107, 107, 0.1);
    border-radius: 8px;
  }

  .empty {
    text-align: center;
    padding: 3rem 1rem;
    opacity: 0.7;
  }

  .cta {
    display: inline-block;
    margin-top: 1rem;
    padding: 0.75rem 1.5rem;
    background: #1f6f3f;
    color: #fff;
    text-decoration: none;
    border-radius: 8px;
    font-weight: 600;
  }

  .stats-bar {
    display: flex;
    justify-content: space-around;
    gap: 0.5rem;
    padding: 0.75rem;
    background: #2a2a2a;
    border-radius: 10px;
    margin-bottom: 1rem;
    font-size: 0.875rem;
  }

  .stats-bar strong { color: #4ade80; }

  .games-list {
    list-style: none;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .game-item {
    background: #2a2a2a;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    border-left: 4px solid #555;
  }

  .game-item.win { border-left-color: #4ade80; }
  .game-item.loss { border-left-color: #ff6b6b; }
  .game-item.draw { border-left-color: #f0c040; }

  .row-1, .row-2, .row-3 {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 0.5rem;
  }

  .row-1 {
    font-weight: 600;
    margin-bottom: 0.25rem;
  }

  .row-2 {
    font-size: 0.875rem;
    margin-bottom: 0.25rem;
  }

  .row-3 {
    font-size: 0.75rem;
    opacity: 0.6;
  }

  .outcome.win { color: #4ade80; }
  .outcome.loss { color: #ff6b6b; }
  .outcome.draw { color: #f0c040; }

  .date { font-size: 0.75rem; opacity: 0.6; font-weight: normal; }

  .opponent strong { color: #fff; }

  .game-item.aborted { border-left-color: #666; opacity: 0.7; }
  .outcome.aborted { color: #888; }

</style>