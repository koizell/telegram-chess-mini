<script lang="ts">
	import { page } from '$app/stores';
	import { base } from '$app/paths';
	import { Chessground } from 'chessground';
	import { Chess } from 'chess.js';
	import 'chessground/assets/chessground.base.css';
	import 'chessground/assets/chessground.brown.css';
	import 'chessground/assets/chessground.cburnett.css';
	import { THEMES, getTheme, type Theme } from '$lib/themes';
	import { SKINS, getSkin, type Skin } from '$lib/skins';
	import { sounds } from '$lib/sounds';
	import { tgUser } from '$lib/telegram';
	import ChatPanel from '$lib/components/ChatPanel.svelte';
	import { getGame, makePvpMove, finishPvpGame } from '$lib/api';
	import '$lib/themes.css';
	import '$lib/skins.css';
	import { onMount, onDestroy, tick } from 'svelte';

	let boardElement: HTMLElement;
	let game = new Chess();
	let ground: ReturnType<typeof Chessground> | null = null;
	let gameId = '';

	let loading = true;
	let error = '';
	let opponentName = 'Oponente';
	let playerColor: 'white' | 'black' = 'white';
	let playerColorLabel = '⚪ Blancas';
	let currentTurn: 'white' | 'black' = 'white';
	let gameOver = false;
	let gameResult: string | null = null;
	let pollingInterval: ReturnType<typeof setInterval> | null = null;
	let lastFen = '';
	let chatOpen = false;

	let currentTheme: Theme = THEMES[0];
	let currentSkin: Skin = SKINS[0];

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

	function getUserId(): number | null {
		if (import.meta.env.DEV) {
			if (typeof window !== 'undefined') {
				const params = new URLSearchParams(window.location.search);
				const override = params.get('dev_user');
				if (override) return parseInt(override);
			}
			return 5125415147;
		}
		return $tgUser?.id ?? null;
	}

	async function loadGame() {
		try {
			const data = await getGame(gameId);
			game = new Chess(data.fen);
			lastFen = data.fen;
			currentTurn = game.turn() === 'w' ? 'white' : 'black';
			gameOver = data.status === 'finished' || data.status === 'aborted';
			gameResult = data.result || null;

			const userId = getUserId();
			const isWhite = String(data.white_player_telegram_id) === String(userId);
			playerColor = isWhite ? 'white' : 'black';
			playerColorLabel = isWhite ? '⚪ Blancas' : '⚫ Negras';
			opponentName = (isWhite ? data.black_player_name : data.white_player_name) || 'Oponente';

			// 1. Primero renderizar el DOM (quitar el loading)
			loading = false;

			// 2. Esperar a que Svelte actualice el DOM
			await tick();
			await new Promise((r) => setTimeout(r, 50)); // pequeño delay extra

			// 3. Ahora sí, inicializar Chessground
			if (boardElement) {
				const myColor = playerColor;
				const canMove = !gameOver && currentTurn === myColor;

				ground = Chessground(boardElement, {
					fen: game.fen(),
					orientation: playerColor,
					coordinates: false,
					movable: {
						free: false,
						color: canMove ? myColor : undefined,
						dests: canMove ? getLegalMoves() : new Map()
					}
				});

				ground.set({
					movable: {
						events: {
							select: () => sounds.play('select'),
							after: (orig, dest) => handlePlayerMove(orig, dest)
						}
					}
				});
			}

			if (!gameOver) {
				startPolling();
			}
		} catch (e: any) {
			error = e.message || 'Error cargando la partida';
			loading = false;
		}
	}

	function getLegalMoves() {
		const dests = new Map<string, string[]>();
		game.moves({ verbose: true }).forEach((move) => {
			if (!dests.has(move.from)) dests.set(move.from, []);
			dests.get(move.from)!.push(move.to);
		});
		return dests;
	}

	async function handlePlayerMove(orig: string, dest: string) {
		// ─── CAPA 1: Verificaciones previas ───
		if (gameOver) {
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		if (currentTurn !== playerColor) {
			// No es tu turno: silenciosamente ignorar (Chessground ya lo bloquea)
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		const userId = getUserId();
		if (!userId) {
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		// ─── CAPA 2: Validación local con chess.js ───
		// Detectar si es una promoción (peón llegando a última fila)
		const piece = game.get(orig as any);
		const isPromotion =
			piece?.type === 'p' &&
			((piece.color === 'w' && dest[1] === '8') || (piece.color === 'b' && dest[1] === '1'));

		// Construir el movimiento en chess.js
		const moveInput: any = { from: orig, to: dest };
		if (isPromotion) moveInput.promotion = 'q';

		// Validar localmente: si chess.js lo rechaza, no enviamos nada
		let move;
		try {
			move = game.move(moveInput);
		} catch (e) {
			// Movimiento ilegal, revertir visual
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		if (!move) {
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		// Si llegamos aquí, el movimiento es válido localmente
		sounds.play(move.captured ? 'capture' : 'move');

		// Actualizar tablero (bloquear movimientos durante el envío)
		ground?.set({
			fen: game.fen(),
			turnColor: currentTurn === 'white' ? 'black' : 'white',
			movable: {
				color: undefined,
				dests: new Map()
			}
		});

		// ─── CAPA 3: Enviar al backend ───
		try {
			const res = await makePvpMove(gameId, userId, orig, dest, isPromotion ? 'q' : undefined);

			lastFen = res.fen;

			if (res.is_game_over) {
				handleGameOver(res.result);
				return;
			}

			// Cambiar turno y desbloquear si vuelve a ser tu turno (nunca en PvP)
			currentTurn = currentTurn === 'white' ? 'black' : 'white';
			updateBoardState();
		} catch (e: any) {
			// Solo log en consola, sin mostrar error al usuario
			console.warn('Error sincronizando movimiento:', e.message);

			// Revertir tablero al estado anterior
			game = new Chess(lastFen);
			currentTurn = game.turn() === 'w' ? 'white' : 'black';
			updateBoardState();
		}
	}

	async function checkOpponentMove() {
		if (gameOver) return;
		try {
			const data = await getGame(gameId);

			if (data.fen !== lastFen) {
				game = new Chess(data.fen);
				lastFen = data.fen;
				currentTurn = game.turn() === 'w' ? 'white' : 'black';
				sounds.play('move');
				updateBoardState();

				if (data.status === 'finished' || data.status === 'aborted') {
					handleGameOver(data.result);
				}
			}
		} catch (e) {
			console.debug('Error en polling:', e);
		}
	}

	function updateBoardState() {
		if (!ground) return;
		const canMove = !gameOver && currentTurn === playerColor;
		ground.set({
			fen: game.fen(),
			turnColor: currentTurn,
			movable: {
				color: canMove ? playerColor : undefined,
				dests: canMove ? getLegalMoves() : new Map()
			}
		});
	}

	function startPolling() {
		// Polling cada 1 segundo (baja latencia)
		pollingInterval = setInterval(checkOpponentMove, 1000);
	}

	function stopPolling() {
		if (pollingInterval) {
			clearInterval(pollingInterval);
			pollingInterval = null;
		}
	}

	function handleGameOver(result: string | null) {
		gameOver = true;
		gameResult = result;
		stopPolling();

		if (ground) {
			ground.set({
				fen: game.fen(),
				movable: { color: undefined, dests: new Map() }
			});
		}

		if (result) {
			const isWinner =
				(result === 'white_wins' && playerColor === 'white') ||
				(result === 'black_wins' && playerColor === 'black');
			if (result === 'draw') sounds.play('draw');
			else if (isWinner) sounds.play('victory');
			else sounds.play('defeat');
		}
	}

	function getResultText(): string {
		if (gameResult === 'draw') return 'TABLAS';
		const isWinner =
			(gameResult === 'white_wins' && playerColor === 'white') ||
			(gameResult === 'black_wins' && playerColor === 'black');
		return isWinner ? '¡GANASTE!' : 'PERDISTE';
	}

	function getResultEmoji(): string {
		if (gameResult === 'draw') return '🤝';
		const isWinner =
			(gameResult === 'white_wins' && playerColor === 'white') ||
			(gameResult === 'black_wins' && playerColor === 'black');
		return isWinner ? '🏆' : '😢';
	}

	async function surrender() {
		if (!confirm('¿Seguro que quieres rendirte?')) return;
		const userId = getUserId();
		if (!userId) return;

		try {
			const result = playerColor === 'white' ? 'black_wins' : 'white_wins';
			await finishPvpGame(gameId, {
				result,
				fen: game.fen(),
				pgn: game.pgn(),
				game_type: 'pvp'
			});
			handleGameOver(result);
		} catch (e) {
			console.error('Error rindiéndose:', e);
		}
	}

	onMount(() => {
		gameId = $page.params.gameId || '';
		if (!gameId) {
			error = 'ID de partida no válido';
			loading = false;
			return;
		}

		if (typeof localStorage !== 'undefined') {
			const savedTheme = localStorage.getItem('chess_theme');
			if (savedTheme) currentTheme = getTheme(savedTheme);
			const savedSkin = localStorage.getItem('chess_skin');
			if (savedSkin) currentSkin = getSkin(savedSkin);
		}

		setTimeout(loadGame, 100);
	});

	onDestroy(stopPolling);
</script>

<main on:click={() => (chatOpen = false)}>
	{#if loading}
		<div class="loading-state">
			<div class="spinner"></div>
			<p>Cargando partida...</p>
		</div>
	{:else if error}
		<div class="error-state">
			<p>❌ {error}</p>
			<a href="{base}/pvp" class="cta">← Volver</a>
		</div>
	{:else}
		<header>
			<a href="{base}/pvp" class="back-link">←</a>
			<h1>👥 Partida PvP</h1>
			<span class="spacer"></span>
		</header>

		<div class="player-bar">
			<span class="name">{opponentName}</span>
			<span class="color-label">{playerColor === 'white' ? '⚫ Negras' : '⚪ Blancas'}</span>
		</div>

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

		<div class="player-bar">
			<span class="name">Tú</span>
			<span class="color-label">{playerColorLabel}</span>
		</div>

    <div class="status-bar">
      {#if gameOver}
        <span class="status-end">{getResultEmoji()} Partida terminada</span>
      {:else if currentTurn === playerColor}
        <span class="status-turn">🎯 Tu turno</span>
      {:else}
        <span class="status-wait">
          ⏳ {opponentName} pensando
          <span class="dots">
            <span>.</span><span>.</span><span>.</span>
          </span>
        </span>
      {/if}
    </div>

		<div class="action-bar">
			<button class="action-btn" on:click={() => (chatOpen = !chatOpen)}>💬 Chat</button>
			{#if !gameOver}
				<button class="action-btn danger" on:click={surrender}>🏳️ Rendirse</button>
			{:else}
				<a href="{base}/pvp" class="action-btn">🔄 Nueva partida</a>
			{/if}
		</div>
	{/if}
</main>

{#if chatOpen && gameId && !loading}
	<div on:click|stopPropagation>
		<ChatPanel
			{gameId}
			currentUserId={getUserId() || 0}
			isOpen={chatOpen}
			onClose={() => (chatOpen = false)}
		/>
	</div>
{/if}

{#if gameOver && !loading}
	<div class="game-over-modal">
		<div class="modal-content">
			<div class="modal-emoji">{getResultEmoji()}</div>
			<h2 class="modal-title">{getResultText()}</h2>
			<p class="modal-subtitle">vs {opponentName}</p>
			<div class="modal-actions">
				<a href="{base}/pvp" class="modal-btn primary">🔄 Nueva partida</a>
				<a href="{base}/" class="modal-btn">🏠 Menú</a>
			</div>
		</div>
	</div>
{/if}

<style>
	main {
		padding: 1rem;
		max-width: 500px;
		margin: 0 auto;
		font-family:
			system-ui,
			-apple-system,
			sans-serif;
		background: #1a1a1a;
		color: #fff;
		min-height: 100vh;
	}

	header {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1rem;
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

	.back-link:hover {
		background: #2a2a2a;
	}

	.spacer {
		width: 30px;
	}

	.player-bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.5rem 0.75rem;
		background: #2a2a2a;
		border-radius: 8px;
		margin-bottom: 0.5rem;
		font-size: 0.875rem;
	}

	.name {
		font-weight: 600;
	}
	.color-label {
		font-size: 0.75rem;
		opacity: 0.7;
	}

	.board-layout {
		display: flex;
		gap: 4px;
		width: 100%;
	}
	.rank-labels {
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		width: 14px;
		padding: 2px 0;
		font-size: 0.75rem;
		font-weight: 600;
		color: #888;
		user-select: none;
	}
	.board-column {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-width: 0;
	}
	.board-wrapper {
		width: 100%;
		aspect-ratio: 1;
		border-radius: 6px;
		overflow: hidden;
	}
	.chess-board {
		width: 100%;
		height: 100%;
	}
	.file-labels {
		display: flex;
		justify-content: space-around;
		padding: 0 2px;
		font-size: 0.75rem;
		font-weight: 600;
		color: #888;
		user-select: none;
	}

	.status-bar {
		text-align: center;
		padding: 0.75rem;
		margin: 0.75rem 0;
		background: #2a2a2a;
		border-radius: 8px;
		font-size: 0.875rem;
	}

	.status-turn {
		color: #4ade80;
		font-weight: 600;
	}
	.status-wait {
		color: #f0c040;
	}
	.status-end {
		color: #ff6b6b;
		font-weight: 600;
	}

	.action-bar {
		display: flex;
		gap: 0.5rem;
		justify-content: center;
		margin-top: 0.5rem;
	}

	.action-btn {
		flex: 1;
		background: #2a2a2a;
		color: #fff;
		border: 1px solid #3a3a3a;
		border-radius: 8px;
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		cursor: pointer;
		font-family: inherit;
		text-decoration: none;
		text-align: center;
	}

	.action-btn:hover {
		background: #3a3a3a;
	}
	.action-btn.danger {
		color: #ff6b6b;
	}

	.loading-state,
	.error-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 60vh;
		gap: 1rem;
		text-align: center;
	}

	.spinner {
		width: 50px;
		height: 50px;
		border: 4px solid #3a3a3a;
		border-top-color: #4ade80;
		border-radius: 50%;
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.cta {
		display: inline-block;
		padding: 0.75rem 1.5rem;
		background: #1f6f3f;
		color: #fff;
		text-decoration: none;
		border-radius: 8px;
		font-weight: 600;
	}

	.game-over-modal {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.85);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 2000;
		padding: 1rem;
	}

	.modal-content {
		background: #1f1f1f;
		border-radius: 20px;
		padding: 2rem 1.5rem;
		text-align: center;
		max-width: 340px;
		width: 100%;
		box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
		border: 1px solid #3a3a3a;
	}

	.modal-emoji {
		font-size: 4rem;
		line-height: 1;
		margin-bottom: 0.5rem;
	}
	.modal-title {
		font-size: 1.75rem;
		font-weight: bold;
		margin: 0.5rem 0;
		color: #4ade80;
		letter-spacing: 1px;
	}
	.modal-subtitle {
		font-size: 0.875rem;
		opacity: 0.7;
		margin-bottom: 1.5rem;
	}
	.modal-actions {
		display: flex;
		gap: 0.5rem;
		justify-content: center;
	}

	.modal-btn {
		flex: 1;
		background: #2a2a2a;
		color: #fff;
		border: 1px solid #3a3a3a;
		border-radius: 10px;
		padding: 0.75rem 1rem;
		font-size: 0.875rem;
		cursor: pointer;
		font-family: inherit;
		font-weight: 600;
		text-decoration: none;
		text-align: center;
	}

	.modal-btn:hover {
		background: #3a3a3a;
	}
	.modal-btn.primary {
		background: #1f6f3f;
		border-color: #4ade80;
	}
	.modal-btn.primary:hover {
		background: #2a8f4f;
	}

	.dots span {
		animation: blink 1.4s infinite;
		animation-fill-mode: both;
	}
	.dots span:nth-child(2) {
		animation-delay: 0.2s;
	}
	.dots span:nth-child(3) {
		animation-delay: 0.4s;
	}

	@keyframes blink {
		0%,
		80%,
		100% {
			opacity: 0;
		}
		40% {
			opacity: 1;
		}
	}
</style>
