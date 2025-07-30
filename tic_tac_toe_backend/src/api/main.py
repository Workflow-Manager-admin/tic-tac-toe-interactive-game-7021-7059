from fastapi import FastAPI, Depends, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from src.api.db import get_db
from src.api.models import User, Game, Move, BoardState, GameResultEnum
import hashlib
import secrets

app = FastAPI(
    title="Tic Tac Toe API",
    description="Backend API for Tic Tac Toe game. Handles user management, game sessions, moves, board state, and history.",
    version="1.0.0",
    openapi_tags=[
        {"name": "users", "description": "User registration and authentication"},
        {"name": "games", "description": "Game management"},
        {"name": "moves", "description": "Moving and board state"},
        {"name": "utility", "description": "Health and support"}
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==== Utility functions for password hashing (replaceable with passlib etc) ====
def hash_password(password: str) -> str:
    """Simple salted SHA256 (for demonstration only, not production safe)."""
    salt = secrets.token_hex(8)
    hash_ = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${hash_}"

def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, hash_ = hashed.split("$")
        return hashlib.sha256((salt + password).encode()).hexdigest() == hash_
    except Exception:
        return False

# ==== Pydantic Schemas ====

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, description="Unique user identifier")
    password: str = Field(..., min_length=4, max_length=64, description="User password (plain text, not recommended in production)")

class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class GameCreate(BaseModel):
    as_ai: Optional[bool] = Field(default=False, description="If true, start vs AI, otherwise wait for opponent")

class GameOut(BaseModel):
    id: int
    player1_id: int
    player2_id: Optional[int]
    created_at: datetime
    result: GameResultEnum
    class Config:
        orm_mode = True

class MoveCreate(BaseModel):
    cell_index: int = Field(..., ge=0, le=8, description="Board position (0-8)")
    symbol: str = Field(..., regex="^[XO]$", description="Symbol for move (X or O)")

class MoveOut(BaseModel):
    id: int
    game_id: int
    user_id: int
    move_number: int
    cell_index: int
    symbol: str
    created_at: datetime
    class Config:
        orm_mode = True

class BoardStateOut(BaseModel):
    move_number: int
    state_repr: str
    created_at: datetime
    class Config:
        orm_mode = True

# ======================== ROUTES ========================

# PUBLIC_INTERFACE
@app.get("/", tags=["utility"], summary="Health Check", description="Check if the API is running.")
def health_check():
    return {"message": "Healthy"}

# --- User Registration ---
# PUBLIC_INTERFACE
@app.post("/register", response_model=UserOut, summary="Register User", tags=["users"],
          description="Register a new user with a username and password.")
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Ensure unique username
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=409, detail="Username already exists.")
    new_user = User(
        username=user_in.username,
        hashed_password=hash_password(user_in.password)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# --- User Login ---
# PUBLIC_INTERFACE
@app.post("/login", response_model=Token, summary="User Login", tags=["users"],
          description="Login existing user and get a simple session token (stub, not real JWT/OAuth).")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user: User = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    # Simple pseudo-token (insecure), replace with JWT or secure session for prod use
    dummy_token = secrets.token_urlsafe(24)
    return {"access_token": dummy_token, "token_type": "bearer"}

# --- Game Creation ---
# PUBLIC_INTERFACE
@app.post("/games", response_model=GameOut, summary="Create Game", tags=["games"],
          description="Create a new Tic Tac Toe game. Set 'as_ai' true for solo/AI play (not yet implemented).")
def create_game(req: GameCreate = Body(...), db: Session = Depends(get_db), user_id: Optional[int] = None):
    # NOTE: For demo, no real auth; replace 'user_id' with actual current user in production
    # Simulate user_id; in production use token auth to get current user
    uid = user_id if user_id is not None else 1
    new_game = Game(player1_id=uid)
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    return new_game

# --- Join Game ---
# PUBLIC_INTERFACE
@app.post("/games/{game_id}/join", response_model=GameOut, summary="Join Game", tags=["games"],
          description="Join an open Tic Tac Toe game as the second player.")
def join_game(game_id: int, db: Session = Depends(get_db), user_id: Optional[int] = None):
    uid = user_id if user_id is not None else 2
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")
    if game.player2_id is not None:
        raise HTTPException(status_code=409, detail="Game already has two players.")
    if game.player1_id == uid:
        raise HTTPException(status_code=400, detail="Player is already player1.")
    game.player2_id = uid
    db.commit()
    db.refresh(game)
    return game

# --- Get User's Active Games ---
# PUBLIC_INTERFACE
@app.get("/users/{user_id}/games", response_model=List[GameOut], summary="User's Games", tags=["games"],
         description="Get all games for a given user.")
def get_games_for_user(user_id: int, db: Session = Depends(get_db)):
    games = db.query(Game).filter(
        (Game.player1_id == user_id) | (Game.player2_id == user_id)
    ).order_by(Game.created_at.desc()).all()
    return games

# --- List All Open Games (no player2 yet) ---
# PUBLIC_INTERFACE
@app.get("/games/open", response_model=List[GameOut], summary="List Open Games", tags=["games"],
         description="Get list of all open games waiting for a second player.")
def get_open_games(db: Session = Depends(get_db)):
    games = db.query(Game).filter(Game.player2_id == None, Game.result == GameResultEnum.in_progress).all()
    return games

# --- Submit Move ---
# PUBLIC_INTERFACE
@app.post("/games/{game_id}/moves", response_model=MoveOut, summary="Submit Move", tags=["moves"],
         description="Submit a move for the specified game. Demo: user_id required as query (simulate authentication).")
def submit_move(game_id: int, move_in: MoveCreate, db: Session = Depends(get_db), user_id: Optional[int] = None):
    # NOTE: In prod, use token auth to get user! Here for demonstration.
    uid = user_id if user_id is not None else 1
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")
    # Check move validity (for demo, simplistic)
    moves = db.query(Move).filter(Move.game_id == game_id).all()
    if any(m.cell_index == move_in.cell_index for m in moves):
        raise HTTPException(status_code=400, detail="Cell already taken.")
    move_number = len(moves) + 1
    move = Move(
        game_id=game_id,
        user_id=uid,
        move_number=move_number,
        cell_index=move_in.cell_index,
        symbol=move_in.symbol
    )
    db.add(move)
    # -- Save board state representation after move --
    board = [' '] * 9
    for m in moves:
        board[m.cell_index] = m.symbol
    board[move_in.cell_index] = move_in.symbol
    state_repr = "".join(board)
    board_state = BoardState(
        game_id=game_id,
        state_repr=state_repr,
        move_number=move_number
    )
    db.add(board_state)
    db.commit()
    db.refresh(move)
    return move

# --- Get Board State ---
# PUBLIC_INTERFACE
@app.get("/games/{game_id}/board", response_model=BoardStateOut, summary="Current Board State", tags=["moves"],
         description="Get latest board state for a game.")
def get_board_state(game_id: int, db: Session = Depends(get_db)):
    state = (
        db.query(BoardState)
        .filter(BoardState.game_id == game_id)
        .order_by(BoardState.move_number.desc())
        .first()
    )
    if not state:
        raise HTTPException(status_code=404, detail="No board state found.")
    return state

# --- Get Move History ---
# PUBLIC_INTERFACE
@app.get("/games/{game_id}/moves", response_model=List[MoveOut], summary="Get Move History", tags=["moves"],
         description="Get full move history for a game (chronological order).")
def get_move_history(game_id: int, db: Session = Depends(get_db)):
    moves = db.query(Move).filter(Move.game_id == game_id).order_by(Move.move_number.asc()).all()
    return moves
