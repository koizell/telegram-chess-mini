<script lang="ts">
  import { onMount } from 'svelte';
  import { initTelegram, tgUser, isTelegram } from '$lib/telegram';
  import { getUser } from '$lib/api';

  let displayName = '';

  onMount(() => {
    setTimeout(async () => {
      initTelegram();

      // Cuando detectemos al usuario, buscar su display_name en PocketBase
      const unsubscribe = tgUser.subscribe(async (user) => {
        if (user) {
          try {
            const profile = await getUser(user.id);
            if (profile?.display_name) {
              displayName = profile.display_name;
            } else if (user.first_name && user.first_name !== '...') {
              displayName = user.first_name;
            } else {
              displayName = `Jugador${user.id}`;
            }
          } catch (e) {
            // Si no tiene perfil en PocketBase, usar el nombre de Telegram
            displayName = (user.first_name && user.first_name !== '...')
              ? user.first_name
              : `Jugador${user.id}`;
          }
        }
      });

      return () => unsubscribe();
    }, 100);
  });
</script>

<header>
  {#if $isTelegram}
    {#if displayName}
      <span class="user">👤 {displayName}</span>
    {:else}
      <span class="user">👤 Cargando...</span>
    {/if}
  {:else}
    <span class="user dev">🧪 Modo desarrollo</span>
  {/if}
</header>

<slot />

<style>
  header {
    padding: 0.5rem 1rem;
    background: #0f0f0f;
    border-bottom: 1px solid #2a2a2a;
    font-family: system-ui, sans-serif;
    font-size: 0.75rem;
    text-align: right;
  }

  .user {
    color: #4ade80;
    font-weight: 500;
  }

  .dev {
    color: #f0c040;
  }
</style>