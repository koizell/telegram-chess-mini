<script lang="ts">
  import { onMount } from 'svelte';
  import { getRanking } from '$lib/api';
  import { base } from '$app/paths';

  let ranking: any[] = [];
  let loading = true;
  let error = '';

  onMount(async () => {
    try {
      const data = await getRanking(10);
      ranking = data.ranking;
    } catch (e) {
      error = 'No se pudo cargar el ranking. ¿Está la API corriendo?';
      console.error(e);
    } finally {
      loading = false;
    }
  });
</script>

<main>
  <h1>🏆 Ranking Global</h1>

  {#if loading}
    <p class="status">Cargando...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if ranking.length === 0}
    <p class="status">No hay jugadores todavía.</p>
  {:else}
    <ol class="ranking-list">
      {#each ranking as player, i (player.telegram_id)}
        <li class="ranking-item">
          <span class="position">#{i + 1}</span>
          <span class="name">{player.display_name || 'Anónimo'}</span>
          <span class="elo">{player.elo} ELO</span>
          <span class="stats">{player.wins}V / {player.losses}D</span>
        </li>
      {/each}
    </ol>
  {/if}

  <nav>
     <a href="{base}/">← Volver al tablero</a>
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

  h1 {
    text-align: center;
    font-size: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .status {
    text-align: center;
    opacity: 0.6;
  }

  .error {
    text-align: center;
    color: #ff6b6b;
    padding: 1rem;
    background: rgba(255, 107, 107, 0.1);
    border-radius: 8px;
  }

  .ranking-list {
    list-style: none;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .ranking-item {
    display: grid;
    grid-template-columns: 40px 1fr auto auto;
    gap: 0.75rem;
    align-items: center;
    padding: 0.75rem;
    background: #2a2a2a;
    border-radius: 8px;
  }

  .position {
    font-weight: bold;
    color: #f0c040;
  }

  .name {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .elo {
    font-weight: bold;
    color: #4ade80;
    font-size: 0.875rem;
  }

  .stats {
    font-size: 0.75rem;
    opacity: 0.6;
  }

  nav {
    margin-top: 2rem;
    text-align: center;
  }

  nav a {
    color: #4ade80;
    text-decoration: none;
    font-size: 0.875rem;
  }

  nav a:hover {
    text-decoration: underline;
  }
</style>