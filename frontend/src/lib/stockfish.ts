/**
 * Gestor de Stockfish.js (WASM) como Web Worker.
 * Corre en el navegador del usuario, sin cargar la API.
 */

export type Difficulty = 'easy' | 'medium' | 'hard' | 'expert';

const DIFFICULTY_CONFIG: Record<Difficulty, { depth: number; time: number }> = {
  easy:   { depth: 1,  time: 100 },
  medium: { depth: 5,  time: 500 },
  hard:   { depth: 10, time: 1000 },
  expert: { depth: 15, time: 2000 },
};

export class StockfishEngine {
  private worker: Worker | null = null;
  private ready = false;
  private onReadyCallbacks: (() => void)[] = [];
  private onBestMoveCallbacks: ((move: string) => void)[] = [];

  constructor() {
    this.init();
  }

  private init() {
    if (typeof window === 'undefined') return;

    // ⚠️ En desarrollo la ruta base es '', en producción es '/telegram-chess-mini'
    const basePath = import.meta.env.DEV ? '' : '/telegram-chess-mini';
    const workerUrl = `${basePath}/stockfish/stockfish-19-lite-single.js`;

    console.log('🐟 Cargando Stockfish desde:', workerUrl);

    this.worker = new Worker(workerUrl);

    this.worker.addEventListener('message', (e) => {
      const line = typeof e.data === 'string' ? e.data : '';
      console.debug('🐟 Stockfish:', line);

      if (line === 'uciok') {
        this.sendUciCommands();
      } else if (line === 'readyok') {
        this.ready = true;
        console.log('✅ Stockfish listo');
        this.onReadyCallbacks.forEach((cb) => cb());
        this.onReadyCallbacks = [];
      } else if (line.startsWith('bestmove')) {
        const parts = line.split(' ');
        const move = parts[1];
        console.log('🐟 Mejor movimiento:', move);
        this.onBestMoveCallbacks.forEach((cb) => cb(move));
        this.onBestMoveCallbacks = [];
      }
    });

    this.worker.addEventListener('error', (e) => {
      console.error('❌ Error en Stockfish worker:', e);
    });

    // Inicializar UCI
    this.worker.postMessage('uci');
  }

  private sendUciCommands() {
    this.worker?.postMessage('setoption name Threads value 1');
    this.worker?.postMessage('setoption name Hash value 32');
    this.worker?.postMessage('isready');
  }

  onReady(cb: () => void) {
    if (this.ready) cb();
    else this.onReadyCallbacks.push(cb);
  }

  getBestMove(fen: string, difficulty: Difficulty = 'medium'): Promise<string> {
    return new Promise((resolve, reject) => {
      if (!this.worker || !this.ready) {
        reject(new Error('Stockfish no está listo'));
        return;
      }

      const config = DIFFICULTY_CONFIG[difficulty];

      if (difficulty === 'easy') {
        this.worker.postMessage('setoption name Skill Level value 0');
      } else if (difficulty === 'medium') {
        this.worker.postMessage('setoption name Skill Level value 5');
      } else if (difficulty === 'hard') {
        this.worker.postMessage('setoption name Skill Level value 12');
      } else {
        this.worker.postMessage('setoption name Skill Level value 20');
      }

      this.onBestMoveCallbacks.push(resolve);
      this.worker.postMessage(`position fen ${fen}`);
      this.worker.postMessage(`go depth ${config.depth} movetime ${config.time}`);
    });
  }

  quit() {
    if (this.worker) {
      this.worker.postMessage('quit');
      this.worker.terminate();
      this.worker = null;
      this.ready = false;
    }
  }
}