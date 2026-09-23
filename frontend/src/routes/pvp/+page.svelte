<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';
  import { tgUser } from '$lib/telegram';
  import { joinMatchmaking, getMatchmakingStatus, cancelMatchmaking } from '$lib/api';

  let state: 'idle' | 'searching' | 'matched' | 'error' = 'idle';
  let error = '';
  let queueId = '';
  let elapsed = 0;
  let pollInterval: ReturnType<typeof setInterval> | null = null;
  let timerInterval: ReturnType<typeof setInterval> | null = null;

  function getUserId(): number | null {
    if (import.meta.env.DEV) {
      // En desarrollo, permitir override por URL: ?dev_user=123
      if (typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search);
        const override = params.get('dev_user');
        if (override) return parseInt(override);
      }
      return 5125415147;
    }
    return $tgUser?.id ?? null;
  }

  async function startSearch() {
    const userId = getUserId();
    if (!userId) {
      error = 'Abre esta página desde Telegram para jugar PvP.';
      state = 'error';
      return;
    }

    state = 'searching';
    elapsed = 0;

    try {
      const res = await joinMatchmaking(userId);
      queueId = res.queue_id || '';

      if (res.status === 'matched' && res.game_id) {
        // Emparejado inmediatamente
        goToGame(res.game_id);
        return;
      }

      // Empezar polling
      pollInterval = setInterval(() => checkStatus(userId), 2000);
      timerInterval = setInterval(() => elapsed++, 1000);
    } catch (e: any) {
      error = e.message || 'Error al buscar oponente';
      state = 'error';
    }
  }

  async function checkStatus(userId: number) {
    try {
      const res = await getMatchmakingStatus(userId);

      if (res.status === 'matched' && res.game_id) {
        stopPolling();
        goToGame(res.game_id);
      } else if (res.status === 'cancelled') {
        stopPolling();
        state = 'idle';
      }
    } catch (e) {
      console.debug('Error consultando estado:', e);
    }
  }

  async function cancel() {
    const userId = getUserId();
    if (!userId) return;

    stopPolling();
    try {
      await cancelMatchmaking(userId);
    } catch (e) {
      console.debug('Error cancelando:', e);
    }
    state = 'idle';
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
  }

  function goToGame(gameId: string) {
    // Preservar el parámetro dev_user si existe
    let query = '';
    if (typeof window !== 'undefined') {
      const devUser = new URLSearchParams(window.location.search).get('dev_user');
      if (devUser) query = `?dev_user=${devUser}`;
    }
    window.location.href = `${base}/pvp/${gameId}${query}`;
  }

  function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  onMount(() => {
    if (import.meta.env.DEV) {
      // En dev, no auto-iniciar; solo mostrar el botón
    }
  });

  onDestroy(stopPolling);
</script>

<main>
  <header>
    <a href="{base}/" class="back-link">←</a>
    <h1>👥 Jugar PvP</h1>
    <span class="spacer"></span>
  </header>

  {#if state === 'idle'}
    <div class="card">
      <div class="icon">👥</div>
      <h2>Buscar oponente</h2>
      <p class="description">
        Te emparejaremos con un jugador de ELO similar.
        El ELO se ajusta según el resultado.
      </p>

      <button class="primary-btn" on:click={startSearch}>
        🔍 Buscar oponente
      </button>
    </div>
  {:else if state === 'searching'}
    <div class="card">
      <div class="spinner"></div>
      <h2>Buscando oponente...</h2>
      <p class="timer">⏱️ {formatTime(elapsed)}</p>
      <p class="description">
        Emparejamos por ELO cercano. Suele tardar menos de 30 segundos.
      </p>

      <button class="cancel-btn" on:click={cancel}>
        ❌ Cancelar búsqueda
      </button>
    </div>
  {:else if state === 'error'}
    <div class="card error-card">
      <div class="icon">😕</div>
      <h2>Algo salió mal</h2>
      <p class="description">{error}</p>

      <button class="primary-btn" on:click={() => (state = 'idle')}>
        Volver a intentar
      </button>
    </div>
  {/if}

  <nav>
    <a href="{base}/">🏠 Tablero</a>
    <a href="{base}/ranking">🏆 Ranking</a>
  </nav>
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
  }

  .back-link:hover { background: #2a2a2a; }

  .spacer { width: 30px; }

  .card {
    background: #2a2a2a;
    border-radius: 16px;
    padding: 2rem 1.5rem;
    text-align: center;
    margin-bottom: 1.5rem;
  }

  .error-card { background: rgba(255, 107, 107, 0.1); }

  .icon {
    font-size: 3rem;
    margin-bottom: 0.5rem;
  }

  h2 {
    font-size: 1.25rem;
    margin: 0.5rem 0 1rem;
  }

  .description {
    font-size: 0.875rem;
    opacity: 0.7;
    margin-bottom: 1.5rem;
    line-height: 1.5;
  }

  .timer {
    font-size: 1.5rem;
    font-weight: bold;
    color: #4ade80;
    margin: 1rem 0;
  }

  .primary-btn, .cancel-btn {
    width: 100%;
    padding: 0.875rem 1rem;
    border: none;
    border-radius: 10px;
    font-size: 0.95rem;
    font-weight: 600;
    cursor: pointer;
    font-family: inherit;
  }

  .primary-btn {
    background: #1f6f3f;
    color: #fff;
  }

  .primary-btn:hover { background: #2a8f4f; }

  .cancel-btn {
    background: #3a3a3a;
    color: #fff;
  }

  .cancel-btn:hover { background: #4a4a4a; }

  .spinner {
    width: 50px;
    height: 50px;
    border: 4px solid #3a3a3a;
    border-top-color: #4ade80;
    border-radius: 50%;
    margin: 0 auto 1rem;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  nav {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
  }

  nav a {
    color: #4ade80;
    text-decoration: none;
    font-size: 0.875rem;
    padding: 0.5rem 1rem;
    background: #2a2a2a;
    border-radius: 8px;
  }

  nav a:hover { background: #3a3a3a; }
</style>