<script lang="ts">
  import { onMount } from 'svelte';
  import { Chessground } from 'chessground';
  import { Chess } from 'chess.js';
  import 'chessground/assets/chessground.base.css';
  import 'chessground/assets/chessground.brown.css';
  import 'chessground/assets/chessground.cburnett.css';

  let boardElement: HTMLElement;
  let game = new Chess();
  let ground: ReturnType<typeof Chessground> | null = null;

  onMount(() => {
    if (!boardElement) return;

    ground = Chessground(boardElement, {
      fen: game.fen(),
      orientation: 'white',
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
  });

  function getLegalMoves() {
    const dests = new Map<string, string[]>();
    game.moves({ verbose: true }).forEach((move) => {
      if (!dests.has(move.from)) dests.set(move.from, []);
      dests.get(move.from)!.push(move.to);
    });
    return dests;
  }
</script>

<main>
  <h1>♟️ Telegram Chess Pi</h1>
  <div class="board-wrapper">
    <div bind:this={boardElement} class="chess-board"></div>
  </div>
  <p class="hint">Haz clic en una pieza blanca para moverla.</p>
  <nav>
    <a href="/ranking">🏆 Ver Ranking</a>
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
    margin-bottom: 1rem;
  }

  .board-wrapper {
    width: 100%;
    aspect-ratio: 1;
  }

  .chess-board {
    width: 100%;
    height: 100%;
  }

  .hint {
    text-align: center;
    font-size: 0.875rem;
    opacity: 0.6;
    margin-top: 1rem;
  }

  nav {
    margin-top: 1.5rem;
    text-align: center;
  }

  nav a {
    color: #4ade80;
    text-decoration: none;
    font-size: 0.875rem;
    padding: 0.5rem 1rem;
    background: #2a2a2a;
    border-radius: 8px;
    display: inline-block;
  }

  nav a:hover {
    background: #3a3a3a;
  }
</style>