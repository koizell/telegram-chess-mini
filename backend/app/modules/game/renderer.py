"""
Renderizador del tablero como texto con emojis.
"""
import chess


# Símbolos Unicode para las piezas
SYMBOLS = {
    (chess.PAWN, chess.WHITE): "♙",
    (chess.KNIGHT, chess.WHITE): "♘",
    (chess.BISHOP, chess.WHITE): "♗",
    (chess.ROOK, chess.WHITE): "♖",
    (chess.QUEEN, chess.WHITE): "♕",
    (chess.KING, chess.WHITE): "♔",
    (chess.PAWN, chess.BLACK): "♟",
    (chess.KNIGHT, chess.BLACK): "♞",
    (chess.BISHOP, chess.BLACK): "♝",
    (chess.ROOK, chess.BLACK): "♜",
    (chess.QUEEN, chess.BLACK): "♛",
    (chess.KING, chess.BLACK): "♚",
}

EMPTY = "·"


def render_board(board: chess.Board, orientation: str = "white") -> str:
    """Renderiza el tablero como texto con emojis y coordenadas.
    
    Args:
        board: tablero de python-chess.
        orientation: 'white' (desde blancas) o 'black' (desde negras).
    """
    lines = []

    if orientation == "white":
        ranks = list(range(7, -1, -1))
        files = list(range(8))
        file_labels = "  a b c d e f g h"
    else:
        ranks = list(range(0, 8))
        files = list(range(7, -1, -1))
        file_labels = "  h g f e d c b a"

    for rank in ranks:
        row = []
        for file in files:
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            row.append(SYMBOLS[(piece.piece_type, piece.color)] if piece else EMPTY)
        lines.append(f"{rank + 1} " + " ".join(row))

    return "\n".join(lines) + "\n" + file_labels