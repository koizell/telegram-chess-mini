from app.modules.game.engine import ChessGame, STOCKFISH_BIN
from app.modules.game.renderer import render_board

print(f"🔍 Stockfish detectado en: {STOCKFISH_BIN}")
print()

game = ChessGame()
print("=== Tablero inicial ===")
print(render_board(game.board))
print()

print("=== Movimientos legales desde e2 ===")
print(game.get_legal_moves_from("e2"))
print()

print("=== Hacer movimiento e2-e4 ===")
ok = game.make_move("e2", "e4")
print(f"Resultado: {ok}")
print(render_board(game.board))
print()

print("=== Movimiento ilegal a2-a5 ===")
ok = game.make_move("a2", "a5")
print(f"Resultado: {ok}")
print()

print("=== Movimiento de Stockfish (medium) ===")
move = game.get_stockfish_move("medium")
print(f"Stockfish jugó: {move}")
print(render_board(game.board))

game.close()