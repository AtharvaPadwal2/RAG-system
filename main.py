import traceback

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from question_router import answer_question
from fastapi import Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi import _rate_limit_exceeded_handler

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Chess RAG API")

app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class LessonSource(BaseModel):
    citation: int
    title: str
    similarity: float


class BoardExample(BaseModel):
    lesson_title: str
    fen: str
    moves: list[str]
    arrows: list[list[str]]
    highlights: list[str]
    caption: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[LessonSource]
    board_examples: list[BoardExample] = Field(default_factory=list)
    status: str


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "chessrag"}


@app.post("/api/chat", response_model=ChatResponse)
@limiter.limit("5/minute")
def chat(request: Request, payload: ChatRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter a question.",
        )

    try:
        return answer_question(question)

    except Exception as error:
        print(
            "Chat failure:",
            type(error).__name__,
            "| HTTP status:",
            getattr(error, "status_code", None),
            flush=True,
        )

        if isinstance(error, UnboundLocalError):
            print("Variable error:", str(error), flush=True)

        elif isinstance(error, NameError):
            print("Undefined name:", error.name, flush=True)

        # Print locations only, without local variables or source contents.
        for frame in traceback.extract_tb(error.__traceback__):
            print(
                f"Location: {frame.filename}, "
                f"line {frame.lineno}, in {frame.name}",
                flush=True,
            )

        raise HTTPException(
            status_code=503,
            detail="The chess assistant is temporarily unavailable.",
        ) from None

from opening_search import search_openings


@app.get(
    "/api/openings",
    response_model=list[BoardExample],
)
def get_openings(name: str = "Italian Game"):
    name = name.strip()

    if not name or len(name) > 100:
        raise HTTPException(
            status_code=400,
            detail="Enter an opening name between 1 and 100 characters.",
        )

    try:
        return search_openings(name, limit=5)

    except Exception as error:
        print(
            "Opening search failed:",
            type(error).__name__,
            flush=True,
        )

        raise HTTPException(
            status_code=503,
            detail="Opening search is temporarily unavailable.",
        ) from None

from game_search import search_games


@app.get(
    "/api/games",
    response_model=list[BoardExample],
)
def get_games(name: str = "Italian Game"):
    name = name.strip()

    if not name or len(name) > 100:
        raise HTTPException(
            status_code=400,
            detail="Enter an opening name between 1 and 100 characters.",
        )

    try:
        return search_games(name, limit=3)

    except Exception as error:
        print(
            "Game search failed:",
            type(error).__name__,
            flush=True,
        )

        raise HTTPException(
            status_code=503,
            detail="Game search is temporarily unavailable.",
        ) from None