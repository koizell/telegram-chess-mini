"""
Motor de ajedrez - Wrapper sobre python-chess y Stockfish.
Detecta automáticamente la ruta de Stockfish según el sistema operativo.
"""
import os
import platform
import logging
import chess
import chess.engine
from app.config import STOCKFISH_PATH

logger = logging.getLogger(__name__)


# ============================================
# DETECCIÓN AUTOMÁTICA DE STOCKFISH
# ============================================
def _get_stockfish_path():
    """Detecta la ruta correcta de Stockfish según el SO."""
    # 1. Si STOCKFISH_PATH está configurado y es un archivo válido, usarlo
    if STOCKFISH_PATH and os.path.isfile(STOCKFISH_PATH):
        return STOCKFISH_PATH

    # 2. Rutas por defecto según el sistema operativo
    if platform.system() == "Windows":
        # Cambia esta ruta si instalaste Stockfish en otro sitio en Windows
        return r"C:\Users\Koizell\stockfish\stockfish.exe"
    else:
        # Linux (BTT Pi)
        return "/usr/games/stockfish"


STOCKFISH_BIN = _get_stockfish_path()


# ============================================
# CLASE PRINCIPAL
# ============================================
class ChessGame:
    """Representa una partida de ajedrez."""

    def __init__(self, fen: str = None):
        self.board = chess.Board(fen) if fen else chess.Board()
        self._engine = None

    # ---------- Estado ----------
    @property
    def fen(self):
        return self.board.fen()

    @property
    def turn(self):
        return "white" if self.board.turn == chess.WHITE else "black"

    @property
    def is_game_over(self):
        return self.board.is_game_over()

    # ---------- Movimientos ----------
    def is_legal_move(self, from_sq: str, to_sq: str, promotion: str = None):
        """Verifica si un movimiento es legal."""
        try:
            uci = f"{from_sq}{to_sq}{promotion or ''}"
            move = chess.Move.from_uci(uci)
            return move in self.board.legal_moves
        except Exception:
            return False

    def make_move(self, from_sq: str, to_sq: str, promotion: str = None):
        """Aplica un movimiento. Devuelve True si fue válido."""
        if not self.is_legal_move(from_sq, to_sq, promotion):
            return False
        uci = f"{from_sq}{to_sq}{promotion or ''}"
        move = chess.Move.from_uci(uci)
        self.board.push(move)
        return True

    def get_legal_moves_from(self, square: str):
        """Devuelve los destinos legales desde una casilla (ej: 'e2')."""
        try:
            sq = chess.parse_square(square)
        except Exception:
            return []
        moves = set()
        for move in self.board.legal_moves:
            if move.from_square == sq:
                moves.add(chess.square_name(move.to_square))
        return sorted(list(moves))

    # ---------- Resultado ----------
    def get_result(self):
        """Devuelve 'white_wins', 'black_wins', 'draw' o None."""
        if not self.board.is_game_over():
            return None
        outcome = self.board.outcome()
        if outcome is None:
            return None
        if outcome.winner is None:
            return "draw"
        return "white_wins" if outcome.winner else "black_wins"

    def get_status_message(self):
        """Mensaje del estado actual si es relevante."""
        if self.board.is_checkmate():
            ganador = "Blancas" if self.board.turn == chess.BLACK else "Negras"
            return f"♚ ¡JAQUE MATE! Ganaron las {ganador}."
        if self.board.is_stalemate():
            return "🤝 Tablas por ahogado (rey sin movimientos)."
        if self.board.is_insufficient_material():
            return "🤝 Tablas por material insuficiente."
        if self.board.is_seventyfive_moves():
            return "🤝 Tablas por 75 movimientos sin captura."
        if self.board.is_fivefold_repetition():
            return "🤝 Tablas por repetición."
        if self.board.is_check():
            return "⚠️ ¡JAQUE!"
        return None

    # ---------- Stockfish ----------
    def get_stockfish_move(self, difficulty: str = "medium"):
        """Calcula y aplica el movimiento de Stockfish. Devuelve el move o None."""
        if self._engine is None:
            try:
                self._engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_BIN)
            except Exception as e:
                logger.error(f"❌ Error abriendo Stockfish ({STOCKFISH_BIN}): {e}")
                return None

        limits = self._get_difficulty_limits(difficulty)
        try:
            result = self._engine.play(self.board, chess.engine.Limit(**limits))
            move = result.move
            self.board.push(move)
            return move
        except Exception as e:
            logger.error(f"❌ Error calculando movimiento: {e}")
            return None

    @staticmethod
    def _get_difficulty_limits(difficulty: str):
        """Límites de Stockfish según la dificultad."""
        niveles = {
            "easy":   {"depth": 1,  "time": 0.1},
            "medium": {"depth": 5,  "time": 0.5},
            "hard":   {"depth": 10, "time": 1.0},
            "expert": {"depth": 15, "time": 2.0},
        }
        return niveles.get(difficulty, niveles["medium"])

    def close(self):
        """Cierra el motor de Stockfish."""
        if self._engine:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None