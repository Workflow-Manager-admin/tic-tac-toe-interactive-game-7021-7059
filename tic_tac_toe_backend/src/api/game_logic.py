"""
Core logic for Tic Tac Toe game state, move validation, progression, and result detection.

PUBLIC_INTERFACE:
    - validate_move
    - get_next_player_symbol
    - check_win
    - check_draw
    - apply_move
    - make_board_from_moves
    - get_game_status

Used by REST API service for moves, board state, and progression.
"""

from enum import Enum
from typing import List, Optional, Tuple


class BoardResult(Enum):
    IN_PROGRESS = "in_progress"
    DRAW = "draw"
    X_WIN = "X_win"
    O_WIN = "O_win"


# PUBLIC_INTERFACE
def make_board_from_moves(moves: List[dict]) -> List[str]:
    """
    Construct the board as a list of 'X', 'O', or ' ' (empty) from move history.
    :param moves: list of move dicts with cell_index and symbol
    """
    board = [" "] * 9
    for move in moves:
        idx, symbol = move["cell_index"], move["symbol"]
        board[idx] = symbol
    return board

# PUBLIC_INTERFACE
def validate_move(board: List[str], cell_index: int, symbol: str, last_symbol: Optional[str], player1_symbol: str) -> Tuple[bool, Optional[str]]:
    """
    Returns (valid: bool, error_msg: Optional[str]). Checks:
      - turn alternates between 'X' and 'O'
      - cell is empty
      - correct player's symbol
    """
    if cell_index < 0 or cell_index > 8:
        return False, "Cell index must be between 0 and 8."
    if board[cell_index] != " ":
        return False, "Cell already taken."
    if symbol not in ("X", "O"):
        return False, "Symbol must be 'X' or 'O'."
    if last_symbol and symbol == last_symbol:
        return False, f"It's not {symbol}'s turn."
    # First move: must match player1_symbol
    if last_symbol is None and symbol != player1_symbol:
        return False, f"First move must be played by '{player1_symbol}'."
    return True, None

# PUBLIC_INTERFACE
def get_next_player_symbol(last_symbol: Optional[str], player1_symbol: str) -> str:
    """Given the last played symbol, what is the next symbol?"""
    if last_symbol is None:
        return player1_symbol
    return "O" if last_symbol == "X" else "X"

# PUBLIC_INTERFACE
def check_win(board: List[str]) -> Optional[str]:
    """
    Checks the board for a winner.
    Returns 'X', 'O', or None.
    """
    wins = [
        [0,1,2], [3,4,5], [6,7,8],  # rows
        [0,3,6], [1,4,7], [2,5,8],  # columns
        [0,4,8], [2,4,6]            # diagonals
    ]
    for w in wins:
        a, b, c = w
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return None

# PUBLIC_INTERFACE
def check_draw(board: List[str]) -> bool:
    """True if all cells filled and no winner."""
    return all(cell != " " for cell in board) and not check_win(board)

# PUBLIC_INTERFACE
def get_game_status(board: List[str]) -> BoardResult:
    """Return the current status of the board."""
    winner = check_win(board)
    if winner == "X":
        return BoardResult.X_WIN
    elif winner == "O":
        return BoardResult.O_WIN
    elif check_draw(board):
        return BoardResult.DRAW
    else:
        return BoardResult.IN_PROGRESS

# PUBLIC_INTERFACE
def apply_move(moves: List[dict], move: dict, player1_symbol: str) -> Tuple[List[str], BoardResult, Optional[str]]:
    """
    Applies the move if valid, returns (board, status, error_msg).
    'moves' should be ordered list of prior moves; 'move' is dict: {'cell_index', 'symbol'}
    """
    board = make_board_from_moves(moves)
    last_symbol = moves[-1]["symbol"] if moves else None
    valid, err = validate_move(board, move["cell_index"], move["symbol"], last_symbol, player1_symbol)
    if not valid:
        return board, get_game_status(board), err
    # Apply move
    board[move["cell_index"]] = move["symbol"]
    result = get_game_status(board)
    return board, result, None

