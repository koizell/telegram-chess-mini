<script lang="ts">
  import { onMount } from 'svelte';
  import { initTelegram, tgUser, isTelegram } from '$lib/telegram';

  onMount(() => {
    initTelegram();
  });
</script>

<header>
  {#if $isTelegram && $tgUser}
    <span class="user">👤 {$tgUser.first_name}</span>
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