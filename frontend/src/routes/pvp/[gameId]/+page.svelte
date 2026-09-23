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
	let lastFen = '';
	let chatOpen = false;
	let chatPanelRef: ChatPanel;

	let currentTheme: Theme = THEMES[0];
	let currentSkin: Skin = SKINS[0];

	// Relojes
	let timeWhiteMs = 600000;
	let timeBlackMs = 600000;
	let timeControlMs = 600000;
	let lastMoveAt = '';
	let clockInterval: ReturnType<typeof setInterval> | null = null;
	let nowMs = Date.now();
	let clockOffsetMs = 0;
	let showSurrenderModal = false;

	// SSE
	let eventSource: EventSource | null = null;

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

	// Display reactivo de los relojes
	$: displayWhite = getDisplayTime('white', nowMs);
	$: displayBlack = getDisplayTime('black', nowMs);

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

	function getApiUrl(): string {
		return import.meta.env.DEV ? '' : import.meta.env.VITE_API_URL || '';
	}

	async function loadGame() {
		try {
			const data = await getGame(gameId);
			game = new Chess(data.fen);
			lastFen = data.fen;
			currentTurn = game.turn() === 'w' ? 'white' : 'black';
			gameOver = data.status === 'finished' || data.status === 'aborted';
			gameResult = data.result || null;

			timeWhiteMs = data.time_white_ms || 600000;
			timeBlackMs = data.time_black_ms || 600000;
			timeControlMs = data.time_control_ms || 600000;
			lastMoveAt = data.last_move_at || '';

			if (data.current_turn) {
				currentTurn = data.current_turn;
			}

			if (data.server_now) {
				clockOffsetMs = new Date(data.server_now).getTime() - Date.now();
				console.log('⏰ Clock offset:', clockOffsetMs, 'ms');
			}

			nowMs = Date.now();

			const userId = getUserId();
			const isWhite = String(data.white_player_telegram_id) === String(userId);
			playerColor = isWhite ? 'white' : 'black';
			playerColorLabel = isWhite ? '⚪ Blancas' : '⚫ Negras';
			opponentName = (isWhite ? data.black_player_name : data.white_player_name) || 'Oponente';

			loading = false;
			await tick();
			await new Promise((r) => setTimeout(r, 50));

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
							after: (orig, dest) => handlePlayerMove(orig, dest)
						}
					}
				});
			}

			if (!gameOver) {
				startSSE();
				startClock();
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
		if (gameOver) {
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		if (currentTurn !== playerColor) {
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		const userId = getUserId();
		if (!userId) {
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		const piece = game.get(orig as any);
		const isPromotion =
			piece?.type === 'p' &&
			((piece.color === 'w' && dest[1] === '8') || (piece.color === 'b' && dest[1] === '1'));

		const moveInput: any = { from: orig, to: dest };
		if (isPromotion) moveInput.promotion = 'q';

		let move;
		try {
			move = game.move(moveInput);
		} catch (e) {
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		if (!move) {
			if (ground) ground.set({ fen: game.fen() });
			return;
		}

		sounds.play(move.captured ? 'capture' : 'move');

		ground?.set({
			fen: game.fen(),
			turnColor: currentTurn === 'white' ? 'black' : 'white',
			movable: {
				color: undefined,
				dests: new Map()
			}
		});

		try {
			const res = await makePvpMove(gameId, userId, orig, dest, isPromotion ? 'q' : undefined);

			lastFen = res.fen;

			// Actualizar estado local tras nuestro movimiento
			currentTurn = game.turn() === 'w' ? 'white' : 'black';
			lastMoveAt = new Date(Date.now() + clockOffsetMs).toISOString();
			nowMs = Date.now();

			if (res.is_game_over) {
				handleGameOver(res.result);
				return;
			}

			updateBoardState();
		} catch (e: any) {
			console.warn('Error sincronizando movimiento:', e.message);
			game = new Chess(lastFen);
			currentTurn = game.turn() === 'w' ? 'white' : 'black';
			updateBoardState();
		}
	}

	// ═══════════════════════════════════════════════════════
	// SSE (Server-Sent Events)
	// ═══════════════════════════════════════════════════════
	function startSSE() {
		const userId = getUserId();
		if (!userId) return;

		const url = `${getApiUrl()}/api/games/${gameId}/stream?telegram_id=${userId}`;
		console.log('🔌 Iniciando SSE:', url);

		eventSource = new EventSource(url);

		eventSource.addEventListener('open', () => {
			console.log('✅ SSE conectado');
		});

		eventSource.addEventListener('fen_update', (e: MessageEvent) => {
			try {
				const data = JSON.parse(e.data);

				if (typeof data.time_white_ms === 'number') timeWhiteMs = data.time_white_ms;
				if (typeof data.time_black_ms === 'number') timeBlackMs = data.time_black_ms;
				if (data.last_move_at) lastMoveAt = data.last_move_at;

				if (data.fen && data.fen !== lastFen) {
					game = new Chess(data.fen);
					lastFen = data.fen;
					currentTurn = game.turn() === 'w' ? 'white' : 'black';
					nowMs = Date.now();
					sounds.play('move');
					updateBoardState();

					if (data.status === 'finished' || data.status === 'aborted') {
						handleGameOver(data.result);
					}
				}
			} catch (err) {
				console.error('Error procesando fen_update:', err);
			}
		});

		eventSource.addEventListener('status_change', (e: MessageEvent) => {
			try {
				const data = JSON.parse(e.data);
				if (data.status === 'finished' || data.status === 'aborted') {
					handleGameOver(data.result);
				}
			} catch (err) {
				console.error('Error procesando status_change:', err);
			}
		});

		eventSource.addEventListener('chat_message', (e: MessageEvent) => {
			console.log('💬 Nuevo mensaje de chat recibido');
			if (chatPanelRef && chatOpen) {
				chatPanelRef.refresh();
			}
		});

		eventSource.addEventListener('heartbeat', () => {
			// Mantiene viva la conexión
		});

		eventSource.addEventListener('error', () => {
			console.warn('⚠️ SSE error, el navegador reconectará automáticamente');
		});
	}

	function stopSSE() {
		if (eventSource) {
			eventSource.close();
			eventSource = null;
			console.log('🔌 SSE cerrado');
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

	function startClock() {
		if (clockInterval) clearInterval(clockInterval);
		clockInterval = setInterval(() => {
			nowMs = Date.now();
		}, 100);
	}

	function stopClock() {
		if (clockInterval) {
			clearInterval(clockInterval);
			clockInterval = null;
		}
	}

	function getDisplayTime(color: 'white' | 'black', _nowMs: number): string {
		const base = color === 'white' ? timeWhiteMs : timeBlackMs;
		let remaining = base;

		if (!gameOver && currentTurn === color && lastMoveAt) {
			const serverNowEstimate = _nowMs + clockOffsetMs;
			const lastMoveMs = new Date(lastMoveAt).getTime();
			const elapsed = Math.max(0, serverNowEstimate - lastMoveMs);
			remaining = Math.max(0, base - elapsed);
		}

		if (remaining <= 0) return '0:00';
		const totalSec = Math.ceil(remaining / 1000);
		const m = Math.floor(totalSec / 60);
		const s = totalSec % 60;
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	function isLowTime(color: 'white' | 'black'): boolean {
		const display = getDisplayTime(color, nowMs);
		const [m, s] = display.split(':').map(Number);
		return m === 0 && s <= 30;
	}

	function handleGameOver(result: string | null) {
		gameOver = true;
		gameResult = result;
		stopSSE();
		stopClock();

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

	function openSurrenderModal() {
		showSurrenderModal = true;
	}

	function closeSurrenderModal() {
		showSurrenderModal = false;
	}

	async function confirmSurrender() {
		showSurrenderModal = false;
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

	onDestroy(() => {
		stopSSE();
		stopClock();
	});
</script>

<main>
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
			<div class="player-info">
				<span class="name">{opponentName}</span>
				<span class="color-label">{playerColor === 'white' ? '⚫ Negras' : '⚪ Blancas'}</span>
			</div>
			<div
				class="clock"
				class:low={isLowTime(playerColor === 'white' ? 'black' : 'white')}
				class:active={!gameOver && currentTurn !== playerColor}
			>
				{playerColor === 'white' ? displayBlack : displayWhite}
			</div>
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
			<div class="player-info">
				<span class="name">Tú</span>
				<span class="color-label">{playerColorLabel}</span>
			</div>
			<div
				class="clock"
				class:low={isLowTime(playerColor)}
				class:active={!gameOver && currentTurn === playerColor}
			>
				{playerColor === 'white' ? displayWhite : displayBlack}
			</div>
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
				<button class="action-btn danger" on:click={openSurrenderModal}>🏳️ Rendirse</button>
			{:else}
				<a href="{base}/pvp" class="action-btn">🔄 Nueva partida</a>
			{/if}
		</div>
	{/if}
</main>

{#if showSurrenderModal}
	<div class="confirm-modal">
		<div class="confirm-content">
			<div class="confirm-emoji">🏳️</div>
			<h3 class="confirm-title">¿Rendirse?</h3>
			<p class="confirm-text">Perderás la partida y perderás ELO.</p>
			<div class="confirm-actions">
				<button class="confirm-btn cancel" on:click={closeSurrenderModal}>Cancelar</button>
				<button class="confirm-btn danger" on:click={confirmSurrender}>Sí, rendirse</button>
			</div>
		</div>
	</div>
{/if}

{#if chatOpen && gameId && !loading}
	<button class="chat-backdrop" aria-label="Cerrar chat" on:click={() => (chatOpen = false)}></button>
	<div>
		<ChatPanel
			bind:this={chatPanelRef}
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

	.player-info {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.name {
		font-weight: 600;
	}

	.color-label {
		font-size: 0.75rem;
		opacity: 0.7;
	}

	.clock {
		font-family: 'Courier New', monospace;
		font-size: 1.25rem;
		font-weight: bold;
		padding: 0.25rem 0.75rem;
		background: #1a1a1a;
		border-radius: 6px;
		color: #ccc;
		min-width: 70px;
		text-align: center;
		transition: all 0.2s;
	}

	.clock.active {
		background: #1f6f3f;
		color: #fff;
		box-shadow: 0 0 12px rgba(74, 222, 128, 0.5);
	}

	.clock.low {
		background: #7a2a2a;
		color: #fff;
		animation: pulse 1s infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.6;
		}
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

	.chat-backdrop {
		position: fixed;
		inset: 0;
		width: 100%;
		height: 100%;
		padding: 0;
		border: 0;
		background: transparent;
		cursor: default;
		z-index: 999;
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
		100% {
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

	/* Modal de confirmación (rendirse) */
	.confirm-modal {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.75);
		backdrop-filter: blur(4px);
		-webkit-backdrop-filter: blur(4px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 2500;
		padding: 1rem;
		animation: fadeIn 0.2s ease-out;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	.confirm-content {
		background: #2a2a2a;
		border-radius: 16px;
		padding: 1.75rem 1.5rem;
		text-align: center;
		max-width: 320px;
		width: 100%;
		border: 1px solid #3a3a3a;
		box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
	}

	.confirm-emoji {
		font-size: 3rem;
		margin-bottom: 0.5rem;
	}

	.confirm-title {
		font-size: 1.25rem;
		font-weight: bold;
		margin: 0 0 0.5rem;
		color: #fff;
	}

	.confirm-text {
		font-size: 0.875rem;
		opacity: 0.7;
		margin-bottom: 1.5rem;
	}

	.confirm-actions {
		display: flex;
		gap: 0.5rem;
	}

	.confirm-btn {
		flex: 1;
		padding: 0.75rem 1rem;
		border-radius: 10px;
		font-size: 0.875rem;
		font-weight: 600;
		cursor: pointer;
		font-family: inherit;
		border: 1px solid transparent;
	}

	.confirm-btn.cancel {
		background: #3a3a3a;
		color: #fff;
	}

	.confirm-btn.cancel:hover {
		background: #4a4a4a;
	}

	.confirm-btn.danger {
		background: #7a2a2a;
		color: #fff;
		border-color: #a03a3a;
	}

	.confirm-btn.danger:hover {
		background: #a03a3a;
	}
</style>