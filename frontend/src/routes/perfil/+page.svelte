<script lang="ts">
  import { onMount } from 'svelte';
  import { base } from '$app/paths';
  import { tgUser, isTelegram } from '$lib/telegram';
  import { getUser } from '$lib/api';

  let profile: any = null;
  let loading = true;
  let error = '';

  onMount(async () => {
    if (!$isTelegram || !$tgUser) {
      error = 'Abre esta página desde Telegram para ver tu perfil.';
      loading = false;
      return;
    }

    try {
      profile = await getUser($tgUser.id);
    } catch (e) {
      error = 'No se pudo cargar tu perfil. ¿Estás registrado? Usa /start en el bot.';
      console.error(e);
    } finally {
      loading = false;
    }
  });
</script>

<main>
  <h1>👤 Mi Perfil</h1>

  {#if loading}
    <p class="status">Cargando...</p>
  {:else if error}
    <p class="error">{error}</p>
  {:else if profile}
    <div class="profile-card">
      <div class="name">{profile.display_name || 'Anónimo'}</div>
      {#if profile.telegram_username}
        <div class="username">@{profile.telegram_username}</div>
      {/if}
      <div class="elo">{profile.elo} ELO</div>

      <div class="stats">
        <div class="stat">
          <span class="label">🏆 Victorias</span>
          <span class="value">{profile.wins}</span>
        </div>
        <div class="stat">
          <span class="label">❌ Derrotas</span>
          <span class="value">{profile.losses}</span>
        </div>
        <div class="stat">
          <span class="label">🤝 Tablas</span>
          <span class="value">{profile.draws}</span>
        </div>
      </div>

      <div class="prefs">
        <div>🎨 Tema: {profile.theme_id || 'No configurado'}</div>
        <div>♟️ Skin: {profile.skin_id || 'No configurada'}</div>
      </div>
    </div>
  {/if}

  <nav>
    <a href="{base}/">← Volver al tablero</a>
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

  h1 {
    text-align: center;
    font-size: 1.5rem;
    margin-bottom: 1.5rem;
  }

  .status, .error {
    text-align: center;
    padding: 1rem;
  }

  .error {
    color: #ff6b6b;
    background: rgba(255, 107, 107, 0.1);
    border-radius: 8px;
  }

  .profile-card {
    background: #2a2a2a;
    border-radius: 12px;
    padding: 1.5rem;
    text-align: center;
  }

  .name {
    font-size: 1.25rem;
    font-weight: bold;
  }

  .username {
    font-size: 0.875rem;
    opacity: 0.6;
    margin-top: 0.25rem;
  }

  .elo {
    font-size: 2rem;
    color: #4ade80;
    font-weight: bold;
    margin: 1rem 0;
  }

  .stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.5rem;
    margin: 1rem 0;
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.5rem;
    background: #1a1a1a;
    border-radius: 8px;
  }

  .stat .label {
    font-size: 0.75rem;
    opacity: 0.6;
  }

  .stat .value {
    font-size: 1.25rem;
    font-weight: bold;
  }

  .prefs {
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #3a3a3a;
    font-size: 0.875rem;
    opacity: 0.8;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  nav {
    margin-top: 2rem;
    display: flex;
    justify-content: center;
    gap: 1rem;
  }

  nav a {
    color: #4ade80;
    text-decoration: none;
    font-size: 0.875rem;
    padding: 0.5rem 1rem;
    background: #2a2a2a;
    border-radius: 8px;
  }

  nav a:hover {
    background: #3a3a3a;
  }
</style>