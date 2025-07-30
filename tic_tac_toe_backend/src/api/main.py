from fastapi import FastAPI, Depends, HTTPException, Body, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from src.api.db import get_db
from src.api.models import User, Game, Move, BoardState, GameResultEnum
from src.api.game_logic import (
    apply_move, BoardResult,
)
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

# Constants for JWT setup
SECRET_KEY = os.getenv("SECRET_KEY", "change_this_secret_key_for_prod__replace_me_123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60*24  # 24 hours

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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# ==== Utility functions for password hashing (using passlib) ====
def hash_password(password: str) -> str:
    """Hash the password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a signed JWT token, setting expiry."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

# PUBLIC_INTERFACE
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Dependency for extracting current user from JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

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
    if get_user_by_username(db, user_in.username):
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
          description="Login existing user and get a JWT token. This token must be passed as a bearer token to all protected endpoints.")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id}
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- Game Creation ---
# PUBLIC_INTERFACE
@app.post("/games", response_model=GameOut, summary="Create Game", tags=["games"],
          description="Create a new Tic Tac Toe game. Set 'as_ai' true for solo/AI play (not yet implemented).")
def create_game(
    req: GameCreate = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)):
    # Use actual authenticated user
    new_game = Game(player1_id=current_user.id)
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    return new_game

# --- Join Game ---
# PUBLIC_INTERFACE
@app.post("/games/{game_id}/join", response_model=GameOut, summary="Join Game", tags=["games"],
          description="Join an open Tic Tac Toe game as the second player.")
def join_game(
    game_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    uid = current_user.id
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
@app.get("/users/me/games", response_model=List[GameOut], summary="User's Games", tags=["games"],
         description="Get all games for the current authenticated user.")
def get_games_for_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_id = current_user.id
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
         description="Submit a move for the specified game. Must be authenticated user.")
def submit_move(
    game_id: int,
    move_in: MoveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a move with full game logic validation (turn, win, draw, current player, move legality, and board updating).
    Updates game result if win/tie is detected.
    """
    uid = current_user.id
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")
    # Who is which symbol?
    player1_symbol = "X"
    if game.player1_id != uid and (game.player2_id != uid if game.player2_id else True):
        raise HTTPException(status_code=403, detail="Player is not in this game.")

    # Only in-progress games can receive moves
    if game.result != GameResultEnum.in_progress:
        raise HTTPException(status_code=400, detail="Game already finished.")

    # Retrieve all previous moves (chronological order)
    moves = db.query(Move).filter(Move.game_id == game_id).order_by(Move.move_number.asc()).all()
    prior_moves = [
        {"cell_index": m.cell_index, "symbol": m.symbol, "move_number": m.move_number, "user_id": m.user_id}
        for m in moves
    ]

    # Proper turn logic: alternates X/O, correct user for correct symbol
    last_symbol = prior_moves[-1]["symbol"] if prior_moves else None
    move_data = {"cell_index": move_in.cell_index, "symbol": move_in.symbol}

    # Enforce symbol turn and user mapping
    current_turn_symbol = "X" if not prior_moves else ("O" if last_symbol == "X" else "X")
    if move_in.symbol != current_turn_symbol:
        raise HTTPException(status_code=400, detail=f"It's {current_turn_symbol}'s turn.")

    # Check user and symbol mapping: player1 always 'X', player2 always 'O'
    if (move_in.symbol == "X" and uid != game.player1_id) or (move_in.symbol == "O" and (game.player2_id is None or uid != game.player2_id)):
        raise HTTPException(status_code=400, detail=f"User not permitted to play as {move_in.symbol} in this game.")

    # Validate move and check game status
    final_board, result, err = apply_move(prior_moves, move_data, player1_symbol=player1_symbol)
    if err:
        raise HTTPException(status_code=400, detail=err)

    move_number = len(prior_moves) + 1
    # -- Save Move --
    move = Move(
        game_id=game_id,
        user_id=uid,
        move_number=move_number,
        cell_index=move_in.cell_index,
        symbol=move_in.symbol
    )
    db.add(move)

    # -- Save Board State after the move --
    state_repr = "".join(final_board)
    board_state = BoardState(
        game_id=game_id,
        state_repr=state_repr,
        move_number=move_number
    )
    db.add(board_state)

    # -- Update Result if needed --
    if result == BoardResult.X_WIN:
        game.result = GameResultEnum.player1_win
    elif result == BoardResult.O_WIN:
        game.result = GameResultEnum.player2_win
    elif result == BoardResult.DRAW:
        game.result = GameResultEnum.draw
    # No change if still in_progress.

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
