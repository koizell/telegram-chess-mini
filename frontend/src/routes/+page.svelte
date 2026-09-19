<script lang="ts">
  import { onMount } from 'svelte';
  import { Chessground } from 'chessground';
  import { Chess } from 'chess.js';
  import { base } from '$app/paths';
  import 'chessground/assets/chessground.base.css';
  import 'chessground/assets/chessground.brown.css';
  import 'chessground/assets/chessground.cburnett.css';
  import { THEMES, getTheme, type Theme } from '$lib/themes';
  import { SKINS, getSkin, type Skin } from '$lib/skins';
  import '$lib/themes.css';
  import '$lib/skins.css';

  let boardElement: HTMLElement;
  let game = new Chess();
  let ground: ReturnType<typeof Chessground> | null = null;

  let currentTheme: Theme = THEMES[0];
  let currentSkin: Skin = SKINS[0];
  let showThemeSelector = false;
  let showSkinSelector = false;

  const ranks = [8, 7, 6, 5, 4, 3, 2, 1];
  const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];

  // Genera las variables CSS con las URLs de las piezas
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

  onMount(() => {
    if (!boardElement) return;

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
          after: (orig, dest) => {
            const move = game.move({ from: orig, to: dest, promotion: 'q' });
            if (move) {
              ground?.set({
                fen: game.fen(),
                turnColor: game.turn() === 'w' ? 'white' : 'black',
                movable: {
                  color: game.turn() === 'w' ? 'white' : 'black',
                  dests: getLegalMoves()
                }
              });
            }
          }
        }
      }
    });

    // Cargar preferencias guardadas
    if (typeof localStorage !== 'undefined') {
      const savedTheme = localStorage.getItem('chess_theme');
      if (savedTheme) currentTheme = getTheme(savedTheme);
      const savedSkin = localStorage.getItem('chess_skin');
      if (savedSkin) currentSkin = getSkin(savedSkin);
    }
  });

  function getLegalMoves() {
    const dests = new Map<string, string[]>();
    game.moves({ verbose: true }).forEach((move) => {
      if (!dests.has(move.from)) dests.set(move.from, []);
      dests.get(move.from)!.push(move.to);
    });
    return dests;
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
</script>

<main>
  <h1>♟️ Telegram Chess Pi</h1>

  <div class="board-layout">
    <div class="rank-labels">
      {#each ranks as rank}<span>{rank}</span>{/each}
    </div>

    <div class="board-column">
      <div
        class="board-wrapper theme-{currentTheme.id}"
        style={pieceStyles}
      >
        <div bind:this={boardElement} class="chess-board"></div>
      </div>

      <div class="file-labels">
        {#each files as file}<span>{file}</span>{/each}
      </div>
    </div>
  </div>

  <p class="hint">Haz clic en una pieza blanca para moverla.</p>

  <div class="selector-bar">
    <button class="selector-btn" on:click={() => { showThemeSelector = !showThemeSelector; showSkinSelector = false; }}>
      🎨 <strong>{currentTheme.name}</strong>
    </button>
    <button class="selector-btn" on:click={() => { showSkinSelector = !showSkinSelector; showThemeSelector = false; }}>
      ♟️ <strong>{currentSkin.name}</strong>
    </button>
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
            <img
              src="{base}/pieces/{skin.id}/wN.svg"
              alt={skin.name}
              class="skin-preview-img"
            />
            <div class="option-name">{skin.emoji} {skin.name}</div>
          </button>
        {/each}
      </div>
      <button class="close-btn" on:click={() => (showSkinSelector = false)}>Cerrar</button>
    </div>
  {/if}

  <nav>
    <a href="/perfil">👤 Mi Perfil</a>
    <a href="/ranking">🏆 Ranking</a>
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

  .hint { text-align: center; font-size: 0.875rem; opacity: 0.6; margin-top: 1rem; }

  .selector-bar {
    display: flex; justify-content: center; gap: 0.5rem; margin-top: 1rem;
  }
  .selector-btn {
    background: #2a2a2a; color: #fff; border: 1px solid #3a3a3a;
    border-radius: 8px; padding: 0.5rem 1rem; font-size: 0.875rem;
    cursor: pointer; font-family: inherit;
  }
  .selector-btn:hover { background: #3a3a3a; }

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
</style>