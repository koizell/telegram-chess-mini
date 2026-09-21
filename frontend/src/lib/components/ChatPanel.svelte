<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { base } from '$app/paths';

  export let gameId: string;
  export let currentUserId: number;
  export let isOpen = false;
  export let onClose: () => void = () => {};

  interface Message {
    id: string;
    sender_id: string;
    sender_telegram_id: number | null;
    content: string;
    created: string;
  }

  let messages: Message[] = [];
  let input = '';
  let sending = false;
  let messagesContainer: HTMLDivElement;
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  async function loadMessages() {
    if (!gameId) return;
    try {
      const apiUrl = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL || '');
      const res = await fetch(`${apiUrl}/api/games/${gameId}/messages?limit=50`);
      if (!res.ok) return;
      const data = await res.json();
      const newMessages = data.messages || [];
      if (newMessages.length !== messages.length) {
        messages = newMessages;
        scrollToBottom();
      }
    } catch (e) {
      console.debug('Error cargando mensajes:', e);
    }
  }

  async function sendMessage() {
    const content = input.trim();
    if (!content || sending) return;

    sending = true;
    try {
      const apiUrl = import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL || '');
      const res = await fetch(`${apiUrl}/api/games/${gameId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          telegram_id: currentUserId,
          content
        })
      });
      if (res.ok) {
        input = '';
        await loadMessages();
      }
    } catch (e) {
      console.error('Error enviando mensaje:', e);
    } finally {
      sending = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function scrollToBottom() {
    setTimeout(() => {
      if (messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
      }
    }, 50);
  }

  function formatTime(iso: string) {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return '';
    }
  }

  onMount(() => {
    loadMessages();
    pollInterval = setInterval(loadMessages, 3000);
  });

  onDestroy(() => {
    if (pollInterval) clearInterval(pollInterval);
  });

  $: if (isOpen) {
    loadMessages();
    scrollToBottom();
  }
</script>

{#if isOpen}
  <div class="chat-overlay" on:click|stopPropagation>
    <div class="drag-handle"></div>

    <div class="chat-header">
      <span>💬 Chat de la partida</span>
      <button class="close-btn" on:click={onClose} aria-label="Cerrar">✕</button>
    </div>

    <div class="messages" bind:this={messagesContainer}>
      {#if messages.length === 0}
        <div class="empty">Aún no hay mensajes. ¡Di hola! 👋</div>
      {:else}
        {#each messages as msg (msg.id)}
          <div class="message" class:own={msg.sender_telegram_id === currentUserId}>
            <div class="bubble">
              {msg.content}
              <span class="time">{formatTime(msg.created)}</span>
            </div>
          </div>
        {/each}
      {/if}
    </div>

    <div class="input-bar">
      <input
        type="text"
        bind:value={input}
        on:keydown={handleKeydown}
        placeholder="Escribe un mensaje..."
        maxlength="500"
        disabled={sending}
      />
      <button on:click={sendMessage} disabled={!input.trim() || sending}>
        {sending ? '…' : '➤'}
      </button>
    </div>
  </div>
{/if}

<style>
  .chat-overlay {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 42vh;
    max-height: 400px;
    background: rgba(31, 31, 31, 0.96);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.5);
    display: flex;
    flex-direction: column;
    z-index: 1000;
    animation: slideUp 0.25s ease-out;
  }

  @keyframes slideUp {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
  }

  .drag-handle {
    width: 36px;
    height: 4px;
    background: #555;
    border-radius: 2px;
    margin: 0.5rem auto 0;
    flex-shrink: 0;
  }

  .chat-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 1rem 0.75rem;
    border-bottom: 1px solid #3a3a3a;
    font-size: 0.875rem;
    font-weight: 600;
    color: #fff;
    flex-shrink: 0;
  }

  .close-btn {
    background: none;
    border: none;
    color: #888;
    font-size: 1.25rem;
    cursor: pointer;
    padding: 0 0.5rem;
    line-height: 1;
  }

  .close-btn:hover { color: #fff; }

  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 0.75rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .empty {
    text-align: center;
    color: #666;
    font-size: 0.875rem;
    margin-top: 2rem;
  }

  .message { display: flex; }
  .message.own { justify-content: flex-end; }

  .bubble {
    background: #2a2a2a;
    color: #fff;
    padding: 0.5rem 0.75rem;
    border-radius: 12px;
    max-width: 75%;
    font-size: 0.875rem;
    word-wrap: break-word;
    position: relative;
  }

  .message.own .bubble {
    background: #1f6f3f;
  }

  .time {
    display: block;
    font-size: 0.625rem;
    opacity: 0.6;
    margin-top: 0.25rem;
    text-align: right;
  }

  .input-bar {
    display: flex;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem 0.75rem;
    border-top: 1px solid #3a3a3a;
    background: #1a1a1a;
    flex-shrink: 0;
  }

  .input-bar input {
    flex: 1;
    background: #2a2a2a;
    border: 1px solid #3a3a3a;
    border-radius: 20px;
    padding: 0.5rem 1rem;
    color: #fff;
    font-family: inherit;
    font-size: 0.875rem;
    outline: none;
    min-width: 0;
  }

  .input-bar input:focus { border-color: #4ade80; }

  .input-bar button {
    background: #4ade80;
    color: #0a0a0a;
    border: none;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    cursor: pointer;
    font-size: 1rem;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .input-bar button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
</style>