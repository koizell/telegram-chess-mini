<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Chessground } from 'chessground';
  import { Chess } from 'chess.js';
  import { base } from '$app/paths';
  import 'chessground/assets/chessground.base.css';
  import 'chessground/assets/chessground.brown.css';
  import 'chessground/assets/chessground.cburnett.css';
  import { THEMES, getTheme, type Theme } from '$lib/themes';
  import { SKINS, getSkin, type Skin } from '$lib/skins';
  import { sounds } from '$lib/sounds';
  import { tgUser } from '$lib/telegram';
  import ChatPanel from '$lib/components/ChatPanel.svelte';
  import { StockfishEngine, type Difficulty } from '$lib/stockfish';
  import { finishGame } from '$lib/api';
  import '$lib/themes.css';
  import '$lib/skins.css';

  let boardElement: HTMLElement;
  let game = new Chess();
  let ground: ReturnType<typeof Chessground> | null = null;

  let currentTheme: Theme = THEMES[0];
  let currentSkin: Skin = SKINS[0];
  let showThemeSelector = false;
  let showSkinSelector = false;
  let soundEnabled = true;

  // Modo de juego
  type GameMode = 'free' | 'vs_ai';
  let gameMode: GameMode = 'free';
  let difficulty: Difficulty = 'medium';
  let thinking = false;
  let engine: StockfishEngine | null = null;

  // Partida guardada en PocketBase
  let aiGameId: string | null = null;
  let gameSaved = false;
  let creatingGame = false;

  // Chat
  let gameId: string | null = null;
  let chatOpen = false;

  const ranks = [8, 7, 6, 5, 4, 3, 2, 1];
  const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];

  $: pieceStyles = currentSkin
    ? `
      --wp: url('${base}/pieces/${currentSkin.id}/wP.svg');
      --wn: url('${base}/pieces/${currentSkin.id}/wN.svg');
      --wb: url('${base}/pieces/${currentSkin.id}/wB.svg');
      --wr: url('${base}/pieces/${currentSkin.id}/wR.svg');
      --wq: url('${base}/pieces/${currentSkin.id}/wQ.svg');
      --wk: url('${base}/pieces/${currentSkin.id}/wK.svg');
      --bp: url('${base}/pieces/${currentSkin.id}/bP.svg');
      --bn: url('${base}/pieces/${currentSkin.id}/bN.svg');
      --bb: url('${base}/pieces/${currentSkin.id}/bB.svg');
      --br: url('${base}/pieces/${currentSkin.id}/bR.svg');
      --bq: url('${base}/pieces/${currentSkin.id}/bQ.svg');
      --bk: url('${base}/pieces/${currentSkin.id}/bK.svg');
    `
    : '';

  function getApiUrl() {
    return import.meta.env.DEV ? '' : (import.meta.env.VITE_API_URL || '');
  }

  function getUserId(): number | null {
    return import.meta.env.DEV ? 5125415147 : ($tgUser?.id ?? null);
  }

  onMount(() => {
    if (!boardElement) return;

    soundEnabled = sounds.isEnabled();

    ground = Chessground(boardElement, {
      fen: game.fen(),
      orientation: 'white',
      coordinates: false,
      movable: {
        free: false,
        color: 'white',
        dests: getLegalMoves()
      }
    });

    ground.set({
      movable: {
        events: {
          select: () => sounds.play('select'),
          after: (orig, dest) => {
            const move = game.move({ from: orig, to: dest, promotion: 'q' });
            if (move) {
              sounds.play(move.captured ? 'capture' : 'move');
              updateBoard();

              if (gameMode === 'vs_ai') {
                if (game.isGameOver()) {
                  saveGameResult();
                } else if (game.turn() === 'b') {
                  makeAiMove();
                }
              }
            }
          }
        }
      }
    });

    if (typeof localStorage !== 'undefined') {
      const savedTheme = localStorage.getItem('chess_theme');
      if (savedTheme) currentTheme = getTheme(savedTheme);
      const savedSkin = localStorage.getItem('chess_skin');
      if (savedSkin) currentSkin = getSkin(savedSkin);
      const savedDifficulty = localStorage.getItem('chess_difficulty');
      if (savedDifficulty) difficulty = savedDifficulty as Difficulty;
    }
  });

  onDestroy(() => {
    engine?.quit();
  });

  function updateBoard() {
    ground?.set({
      fen: game.fen(),
      turnColor: game.turn() === 'w' ? 'white' : 'black',
      movable: {
        color: game.turn() === 'w' ? 'white' : 'black',
        dests: getLegalMoves()
      }
    });
  }

  function getLegalMoves() {
    const dests = new Map<string, string[]>();
    game.moves({ verbose: true }).forEach((move) => {
      if (!dests.has(move.from)) dests.set(move.from, []);
      dests.get(move.from)!.push(move.to);
    });
    return dests;
  }

  async function makeAiMove() {
    if (thinking || game.isGameOver()) return;
    thinking = true;

    if (!engine) {
      engine = new StockfishEngine();
      await new Promise<void>((resolve) => engine!.onReady(resolve));
    }

    try {
      const bestMove = await engine.getBestMove(game.fen(), difficulty);
      if (bestMove && bestMove !== '(none)') {
        const from = bestMove.slice(0, 2);
        const to = bestMove.slice(2, 4);
        const promotion = bestMove.length > 4 ? bestMove[4] : 'q';

        const move = game.move({ from, to, promotion });
        if (move) {
          sounds.play(move.captured ? 'capture' : 'move');
          updateBoard();

          if (game.isGameOver()) {
            saveGameResult();
          }
        }
      }
    } catch (e) {
      console.error('Error con Stockfish:', e);
    } finally {
      thinking = false;
    }
  }

  async function startVsAI() {
    // Si había una partida activa sin terminar, marcarla como abandonada
    if (aiGameId && !gameSaved) {
      try {
        const apiUrl = getApiUrl();
        await fetch(`${apiUrl}/api/games/${aiGameId}/finish`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            result: 'aborted',
            fen: game.fen(),
            pgn: game.pgn(),
            game_type: 'vs_bot'
          })
        });
        console.log('🗑️ Partida anterior marcada como terminada');
      } catch (e) {
        console.warn('No se pudo cerrar la partida anterior:', e);
      }
    }

    // Reiniciar estado
    game = new Chess();
    gameMode = 'vs_ai';
    thinking = false;
    gameSaved = false;
    aiGameId = null;
    updateBoard();

    // Crear la nueva partida en PocketBase
    const userId = getUserId();
    if (!userId) return;

    creatingGame = true;
    try {
      const res = await fetch(`${getApiUrl()}/api/games`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telegram_id: userId, opponent_id: 'zkjaozazfd9as3v' })
      });
      if (res.ok) {
        const data = await res.json();
        aiGameId = data.game_id;
        console.log('✅ Partida creada:', aiGameId);
      } else {
        console.error('Error creando partida:', await res.text());
      }
    } catch (e) {
      console.error('Error creando partida:', e);
    } finally {
      creatingGame = false;
    }
  }

    async function saveGameResult() {
    if (!aiGameId || gameSaved) return;
    gameSaved = true;

    // Reproducir sonido según el resultado
    if (game.isCheckmate()) {
      if (game.turn() === 'b') {
        // El jugador ganó (Stockfish quedó en jaque mate)
        sounds.play('victory');
      } else {
        // El jugador perdió
        sounds.play('defeat');
      }
    } else if (game.isDraw()) {
      sounds.play('draw');
    }

    try {
      let result: string;
      if (game.isCheckmate()) {
        result = game.turn() === 'b' ? 'white_wins' : 'black_wins';
      } else {
        result = 'draw';
      }

      await finishGame(aiGameId, {
        result,
        fen: game.fen(),
        pgn: game.pgn(),
        game_type: 'vs_bot'
      });

      console.log('✅ Partida guardada:', result);
    } catch (e) {
      console.error('Error guardando partida:', e);
    }
  }

  async function resetBoard() {
    // Si había una partida activa sin terminar, marcarla como terminada
    if (aiGameId && !gameSaved) {
      try {
        const apiUrl = getApiUrl();
        await fetch(`${apiUrl}/api/games/${aiGameId}/finish`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            result: 'aborted',
            fen: game.fen(),
            pgn: game.pgn(),
            game_type: 'vs_bot'
          })
        });
        console.log('🗑️ Partida anterior cerrada (desde Menú)');
      } catch (e) {
        console.warn('No se pudo cerrar la partida anterior:', e);
      }
    }

    // Reiniciar estado
    game = new Chess();
    gameMode = 'free';
    thinking = false;
    gameSaved = false;
    aiGameId = null;
    updateBoard();
  }

  function setDifficulty(d: Difficulty) {
    difficulty = d;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('chess_difficulty', d);
    }
  }

  function selectTheme(theme: Theme) {
    currentTheme = theme;
    showThemeSelector = false;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('chess_theme', theme.id);
    }
  }

  function selectSkin(skin: Skin) {
    currentSkin = skin;
    showSkinSelector = false;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('chess_skin', skin.id);
    }
  }

  function toggleSound() {
    soundEnabled = !soundEnabled;
    sounds.setEnabled(soundEnabled);
    if (soundEnabled) sounds.play('select');
  }

  async function openChat() {
    const userId = getUserId();
    if (!userId) {
      alert('Abre esta página desde Telegram para usar el chat.');
      return;
    }

    if (!gameId) {
      creatingGame = true;
      try {
        const res = await fetch(`${getApiUrl()}/api/games`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ telegram_id: userId, opponent_id: 'zkjaozazfd9as3v' })
        });
        if (res.ok) {
          const data = await res.json();
          gameId = data.game_id;
        } else {
          console.error('Error creando partida:', await res.text());
          return;
        }
      } catch (e) {
        console.error(e);
        return;
      } finally {
        creatingGame = false;
      }
    }
    chatOpen = true;
  }
</script>

<main on:click={() => (chatOpen = false)}>
  <h1>♟️ Telegram Chess Pi</h1>

  <div class="board-layout">
    <div class="rank-labels">
      {#each ranks as rank}<span>{rank}</span>{/each}
    </div>

    <div class="board-column">
      <div class="board-wrapper theme-{currentTheme.id}" style={pieceStyles}>
        <div bind:this={boardElement} class="chess-board"></div>
      </div>

      <div class="file-labels">
        {#each files as file}<span>{file}</span>{/each}
      </div>
    </div>
  </div>

  {#if gameMode === 'vs_ai'}
    <div class="ai-status">
      {#if thinking}
        <span class="thinking">🤔 Stockfish pensando...</span>
      {:else if game.isGameOver()}
        <span class="game-over">
          {game.isCheckmate() ? '♚ ¡Jaque mate!' : game.isDraw() ? '🤝 Tablas' : 'Fin de partida'}
        </span>
      {:else}
        <span class="turn">{game.turn() === 'w' ? '⚪ Tu turno' : '⚫ Turno de Stockfish'}</span>
      {/if}
    </div>
  {/if}

  <p class="hint">
    {gameMode === 'vs_ai' ? 'Juega contra Stockfish. Mueve una pieza blanca.' : 'Haz clic en una pieza blanca para moverla.'}
  </p>

  <div class="selector-bar">
    <button class="selector-btn" on:click={() => { showThemeSelector = !showThemeSelector; showSkinSelector = false; }}>
      🎨 <strong>{currentTheme.name}</strong>
    </button>
    <button class="selector-btn" on:click={() => { showSkinSelector = !showSkinSelector; showThemeSelector = false; }}>
      ♟️ <strong>{currentSkin.name}</strong>
    </button>
    <button class="selector-btn icon-only" on:click={toggleSound} title="Sonido">
      {soundEnabled ? '🔊' : '🔇'}
    </button>
    <button class="selector-btn icon-only" on:click={openChat} title="Chat">
      💬
    </button>
  </div>

  <div class="game-modes">
    {#if gameMode === 'free'}
      <button class="mode-btn primary" on:click={startVsAI} disabled={creatingGame}>
        {creatingGame ? '⏳ Creando...' : '🤖 Jugar vs IA'}
      </button>
    {:else}
      <button class="mode-btn" on:click={resetBoard}>
        🔄 Nueva partida
      </button>
      <div class="difficulty-selector">
        {#each ['easy', 'medium', 'hard', 'expert'] as d}
          <button
            class="diff-btn {d === difficulty ? 'active' : ''}"
            on:click={() => setDifficulty(d as Difficulty)}
          >
            {d === 'easy' ? '🟢' : d === 'medium' ? '🟡' : d === 'hard' ? '🔴' : '⚫'}
          </button>
        {/each}
      </div>
    {/if}
  </div>

  {#if showThemeSelector}
    <div class="selector-panel">
      <h3>Tema del tablero</h3>
      <div class="theme-grid">
        {#each THEMES as theme (theme.id)}
          <button
            class="theme-option {theme.id === currentTheme.id ? 'active' : ''}"
            on:click={() => selectTheme(theme)}
          >
            <div class="theme-preview theme-{theme.id}">
              <div class="preview-board">
                <div class="preview-light"></div>
                <div class="preview-dark"></div>
              </div>
            </div>
            <div class="option-name">{theme.emoji} {theme.name}</div>
          </button>
        {/each}
      </div>
      <button class="close-btn" on:click={() => (showThemeSelector = false)}>Cerrar</button>
    </div>
  {/if}

  {#if showSkinSelector}
    <div class="selector-panel">
      <h3>Skin de piezas</h3>
      <div class="skin-grid">
        {#each SKINS as skin (skin.id)}
          <button
            class="skin-option {skin.id === currentSkin.id ? 'active' : ''}"
            on:click={() => selectSkin(skin)}
          >
            <img src="{base}/pieces/{skin.id}/wN.svg" alt={skin.name} class="skin-preview-img" />
            <div class="option-name">{skin.emoji} {skin.name}</div>
          </button>
        {/each}
      </div>
      <button class="close-btn" on:click={() => (showSkinSelector = false)}>Cerrar</button>
    </div>
  {/if}

  <nav>
    <a href="{base}/pvp" class="pvp-link">👥 Jugar PvP</a>
    <a href="{base}/perfil">👤 Mi Perfil</a>
    <a href="{base}/ranking">🏆 Ranking</a>
    <a href="{base}/historial">📜 Historial</a>
  </nav>
</main>

{#if chatOpen && gameId && (import.meta.env.DEV || $tgUser)}
  <div on:click|stopPropagation>
    <ChatPanel
      {gameId}
      currentUserId={import.meta.env.DEV ? 5125415147 : $tgUser!.id}
      isOpen={chatOpen}
      onClose={() => (chatOpen = false)}
    />
  </div>
{/if}

{#if gameMode === 'vs_ai' && game.isGameOver() && !thinking}
  <div class="game-over-modal">
    <div class="modal-content">
      <div class="modal-emoji">
        {#if game.isCheckmate()}
          {game.turn() === 'b' ? '🏆' : '😢'}
        {:else if game.isDraw()}
          🤝
        {:else}
          🏁
        {/if}
      </div>

      <h2 class="modal-title">
        {#if game.isCheckmate()}
          {game.turn() === 'b' ? '¡GANASTE!' : 'PERDISTE'}
        {:else if game.isDraw()}
          TABLAS
        {:else}
          FIN DE PARTIDA
        {/if}
      </h2>

      <p class="modal-subtitle">
        {#if game.isCheckmate()}
          {game.turn() === 'b' ? 'Jaque mate a Stockfish' : 'Stockfish te dio jaque mate'}
        {:else if game.isDraw()}
          {game.isStalemate() ? 'Rey ahogado' : 'Material insuficiente'}
        {:else}
          Partida terminada
        {/if}
      </p>

      <div class="modal-actions">
        <button class="modal-btn primary" on:click={startVsAI}>
          🔄 Revancha
        </button>
        <button class="modal-btn" on:click={resetBoard}>
          🏠 Menú
        </button>
      </div>
    </div>
  </div>
{/if}

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

  h1 { text-align: center; font-size: 1.5rem; margin-bottom: 1rem; }

  .board-layout { display: flex; gap: 4px; width: 100%; }
  .rank-labels {
    display: flex; flex-direction: column; justify-content: space-around;
    width: 14px; padding: 2px 0;
    font-size: 0.75rem; font-weight: 600; color: #888; user-select: none;
  }
  .board-column { flex: 1; display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .board-wrapper { width: 100%; aspect-ratio: 1; border-radius: 6px; overflow: hidden; }
  .chess-board { width: 100%; height: 100%; }
  .file-labels {
    display: flex; justify-content: space-around; padding: 0 2px;
    font-size: 0.75rem; font-weight: 600; color: #888; user-select: none;
  }

  .ai-status {
    text-align: center; padding: 0.75rem; margin-top: 0.75rem;
    background: #2a2a2a; border-radius: 8px; font-size: 0.875rem;
  }
  .thinking { color: #f0c040; }
  .turn { color: #4ade80; font-weight: 600; }
  .game-over { color: #ff6b6b; font-weight: bold; font-size: 1rem; }

  .hint { text-align: center; font-size: 0.875rem; opacity: 0.6; margin-top: 0.5rem; }

  .selector-bar {
    display: flex; justify-content: center; gap: 0.5rem; margin-top: 1rem;
    flex-wrap: wrap;
  }
  .selector-btn {
    background: #2a2a2a; color: #fff; border: 1px solid #3a3a3a;
    border-radius: 8px; padding: 0.5rem 1rem; font-size: 0.875rem;
    cursor: pointer; font-family: inherit;
  }
  .selector-btn:hover { background: #3a3a3a; }
  .selector-btn.icon-only { padding: 0.5rem 0.75rem; font-size: 1rem; }

  .game-modes {
    display: flex; justify-content: center; align-items: center;
    gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap;
  }

  .mode-btn {
    background: #2a2a2a; color: #fff; border: 1px solid #3a3a3a;
    border-radius: 8px; padding: 0.6rem 1.2rem; font-size: 0.875rem;
    cursor: pointer; font-family: inherit;
  }
  .mode-btn:hover { background: #3a3a3a; }
  .mode-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .mode-btn.primary { background: #1f6f3f; border-color: #4ade80; }
  .mode-btn.primary:hover:not(:disabled) { background: #2a8f4f; }

  .difficulty-selector { display: flex; gap: 0.25rem; }
  .diff-btn {
    background: #2a2a2a; color: #fff; border: 1px solid #3a3a3a;
    border-radius: 6px; padding: 0.4rem 0.6rem; font-size: 0.75rem;
    cursor: pointer; font-family: inherit;
  }
  .diff-btn.active { border-color: #4ade80; background: #1f3a28; }

  .selector-panel {
    margin-top: 1rem; padding: 1rem; background: #2a2a2a; border-radius: 12px;
  }
  .selector-panel h3 { text-align: center; margin-bottom: 1rem; font-size: 1rem; }

  .theme-grid, .skin-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem;
  }
  .skin-grid { grid-template-columns: repeat(2, 1fr); }

  .theme-option, .skin-option {
    background: #1a1a1a; border: 2px solid transparent; border-radius: 8px;
    padding: 0.5rem; cursor: pointer; color: #fff; font-family: inherit;
    display: flex; flex-direction: column; align-items: center; gap: 0.5rem;
  }
  .theme-option:hover, .skin-option:hover { border-color: #4ade80; }
  .theme-option.active, .skin-option.active { border-color: #4ade80; background: #1f3a28; }

  .theme-preview { width: 100%; aspect-ratio: 1; border-radius: 4px; overflow: hidden; }
  .preview-board { width: 100%; height: 100%; display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }
  .preview-light, .preview-dark { width: 100%; height: 100%; }

  .theme-clasico .preview-light { background: #f0d9b5; }
  .theme-clasico .preview-dark { background: #b58863; }
  .theme-nocturno .preview-light { background: #b8c4cc; }
  .theme-nocturno .preview-dark { background: #5a6b78; }
  .theme-bosque .preview-light { background: #e8e0c8; }
  .theme-bosque .preview-dark { background: #6b8e4e; }
  .theme-oceano .preview-light { background: #c8e0ec; }
  .theme-oceano .preview-dark { background: #4a7ba6; }
  .theme-neon .preview-light { background: #c8b0e8; }
  .theme-neon .preview-dark { background: #7a5ab8; }
  .theme-papel .preview-light { background: #f5f0e6; }
  .theme-papel .preview-dark { background: #c9b99a; }

  .skin-preview-img {
    width: 60%; max-width: 60px; height: auto;
    filter: drop-shadow(0 0 2px rgba(255,255,255,0.3));
  }

  .option-name { font-size: 0.75rem; text-align: center; }

  .close-btn {
    width: 100%; margin-top: 1rem; padding: 0.5rem;
    background: #3a3a3a; color: #fff; border: none; border-radius: 8px;
    cursor: pointer; font-family: inherit;
  }
  .close-btn:hover { background: #4a4a4a; }

  nav {
    margin-top: 1.5rem; display: flex; justify-content: center;
    gap: 0.5rem; flex-wrap: wrap;
  }
  nav a {
    color: #4ade80; text-decoration: none; font-size: 0.875rem;
    padding: 0.5rem 1rem; background: #2a2a2a; border-radius: 8px;
    display: inline-block;
  }
  nav a:hover { background: #3a3a3a; }

  /* Modal de fin de partida */
  .game-over-modal {
    position: fixed; inset: 0;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    display: flex; align-items: center; justify-content: center;
    z-index: 2000; animation: fadeIn 0.3s ease-out; padding: 1rem;
  }
  @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

  .modal-content {
    background: #1f1f1f; border-radius: 20px; padding: 2rem 1.5rem;
    text-align: center; max-width: 340px; width: 100%;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
    animation: scaleIn 0.3s ease-out;
    border: 1px solid #3a3a3a;
  }
  @keyframes scaleIn {
    from { transform: scale(0.85); opacity: 0; }
    to { transform: scale(1); opacity: 1; }
  }

  .modal-emoji { font-size: 4rem; line-height: 1; margin-bottom: 0.5rem; }
  .modal-title {
    font-size: 1.75rem; font-weight: bold; margin: 0.5rem 0;
    color: #4ade80; letter-spacing: 1px;
  }
  .modal-subtitle { font-size: 0.875rem; opacity: 0.7; margin-bottom: 1.5rem; }
  .modal-actions { display: flex; gap: 0.5rem; justify-content: center; }
  .modal-btn {
    flex: 1; background: #2a2a2a; color: #fff; border: 1px solid #3a3a3a;
    border-radius: 10px; padding: 0.75rem 1rem; font-size: 0.875rem;
    cursor: pointer; font-family: inherit; font-weight: 600;
  }
  .modal-btn:hover { background: #3a3a3a; }
  .modal-btn.primary { background: #1f6f3f; border-color: #4ade80; }
  .modal-btn.primary:hover { background: #2a8f4f; }

  nav a.pvp-link {
    background: #1f6f3f;
    color: #fff;
    font-weight: 600;
  }

  nav a.pvp-link:hover { background: #2a8f4f; }


</style>