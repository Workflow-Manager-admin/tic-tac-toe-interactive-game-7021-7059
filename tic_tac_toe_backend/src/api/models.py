"""
Database models and ORM schema for the Tic Tac Toe application.
Uses SQLAlchemy for ORM mapping.

Models:
    - User: Authentication and account.
    - Game: Session for a game, includes participants and result.
    - BoardState: Board configuration per move.
    - Move: Individual user move with sequence and metadata.

PUBLIC_INTERFACE: All models and helper base are intended for import by DB/session logic and CRUD functions.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Enum,
    UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


class GameResultEnum(str, enum.Enum):
    in_progress = "in_progress"
    draw = "draw"
    player1_win = "player1_win"
    player2_win = "player2_win"

# PUBLIC_INTERFACE
class User(Base):
    """Database user account."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    games_as_player1 = relationship('Game', back_populates='player1', foreign_keys='Game.player1_id')
    games_as_player2 = relationship('Game', back_populates='player2', foreign_keys='Game.player2_id')
    moves = relationship('Move', back_populates='user')

# PUBLIC_INTERFACE
class Game(Base):
    """Tic Tac Toe game session (could be vs player or AI)."""
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    player1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    player2_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    result = Column(Enum(GameResultEnum), default=GameResultEnum.in_progress, nullable=False)

    player1 = relationship('User', foreign_keys=[player1_id], back_populates='games_as_player1')
    player2 = relationship('User', foreign_keys=[player2_id], back_populates='games_as_player2')
    moves = relationship('Move', back_populates='game', cascade="all, delete-orphan")
    board_states = relationship('BoardState', back_populates='game', cascade="all, delete-orphan")

# PUBLIC_INTERFACE
class Move(Base):
    """Represents a player's move in a game"""
    __tablename__ = "moves"
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    move_number = Column(Integer, nullable=False)  # the nth move of the game
    cell_index = Column(Integer, nullable=False)   # Board position (0-8 for 3x3)
    symbol = Column(String(1), nullable=False)     # X or O
    created_at = Column(DateTime, default=datetime.utcnow)

    game = relationship('Game', back_populates='moves')
    user = relationship('User', back_populates='moves')

    __table_args__ = (
        UniqueConstraint("game_id", "move_number", name="uq_game_move_number"),
    )

# PUBLIC_INTERFACE
class BoardState(Base):
    """Tracks the board state after each move for move history or undo feature."""
    __tablename__ = "board_states"
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    state_repr = Column(String(32), nullable=False)  # e.g., "XOX/ XO/   " or a serialized board
    move_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    game = relationship('Game', back_populates='board_states')
    __table_args__ = (
        UniqueConstraint("game_id", "move_number", name="uq_boardstate_move"),
    )
