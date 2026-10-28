# ♟️ ChessRAG — Learn, Play & Explore Chess

An interactive chess learning application combining **retrieval-augmented explanations**, **opening exploration**, **game replay**, and **Stockfish-powered gameplay**.

Learn chess concepts through visual examples, practise against Stockfish, and explore positions on interactive 2D and 3D boards.

> Currently developed and tested locally. Cloud game saving and post-game review are planned.

## Features

### Learn Chess

- Ask chess questions through a RAG-powered tutor.
- Receive explanations with retrieved lesson citations.
- Explore board examples with move-by-move playback.
- Search **2,803 opening records**.
- Replay examples from **19,113 validated dataset games**.
- Analyse positions from replayed games using Stockfish.

### Play Against Stockfish

- Four difficulty levels: **Easy, Medium, Hard, Extreme**.
- Play as White or Black.
- Switch between **2D and 3D boards**.
- Legal move validation, castling, en passant, and promotion.
- Undo moves and try alternative ideas.
- Move history and position navigation.
- Check highlighting and checkmate feedback.
- Time controls and premove support.

### Analysis Mode

- Move both sides to explore positions.
- View evaluations from White’s perspective.
- See suggested moves and best-move arrows.
- Inspect an evaluation bar and engine search depth.

### Authentication

- Email/password registration and login through Supabase Auth.
- Email confirmation.
- Persistent login sessions.
- Logout and guest play.

Authentication provides account access; saving games to accounts is a separate feature under development.

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | Vue 3, Vite, JavaScript |
| Chess rules | chess.js |
| 3D rendering | Three.js |
| Backend | Python, FastAPI, Uvicorn |
| Chess engine | Stockfish through python-chess |
| Database | Supabase PostgreSQL |
| Vector search | pgvector |
| Embeddings | FastEmbed |
| Answer generation | Groq with optional OpenRouter fallback |
| Authentication | Supabase Auth |
| API rate limiting | SlowAPI |

## How It Works

### Chess Learning

1. The user asks a chess question.
2. FastEmbed generates a query embedding.
3. PostgreSQL and pgvector retrieve relevant lesson content.
4. The language model generates an explanation grounded in that content.
5. The frontend displays citations and available board examples.

Opening and game commands query the database directly.

Example questions and commands:

- `What is a knight fork?`
- `Explain en passant.`
- `Show opening Italian Game`
- `Show games Italian Game`

### Stockfish Gameplay

1. The frontend validates and applies the human move.
2. It sends the resulting FEN and difficulty to FastAPI.
3. Stockfish selects a reply.
4. The frontend validates and applies that move while preserving game history.

Normal bot games hide the evaluation bar. Analysis mode requests position evaluations separately.

## Project Structure

```text
chessrag/
├── main.py
├── database.py
├── analysis_engine.py
├── chat_rag.py
├── llm_client.py
├── question_router.py
├── opening_search.py
├── game_search.py
├── board_examples.py
├── requirements.txt
├── engines/
│   └── stockfish/
└── frontend/
    ├── package.json
    └── src/
        ├── App.vue
        ├── components/
        │   ├── AuthPanel.vue
        │   ├── ChessBoard.vue
        │   ├── ChessBoard2D.vue
        │   └── PlayChess.vue
        ├── composables/
        │   └── useAuth.js
        └── lib/
            └── supabase.js
```

## Local Setup

### Prerequisites

- Python compatible with the project's dependencies.
- Node.js compatible with the installed Vite version.
- A Supabase project.
- A Stockfish executable compatible with your operating system.
- A Groq API key.
- An OpenRouter API key if fallback generation is required.

### 1. Install Backend Dependencies

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The current dependency snapshot was generated on Windows. Other platforms may require adjustments to platform-specific dependencies.

### 2. Configure Backend Environment

Create `.env` in the project root:

```env
DATABASE_URL=your_supabase_postgresql_connection_string

GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b

OPENROUTER_API_KEY=your_optional_openrouter_api_key
OPENROUTER_MODEL=openrouter/free
```

Use a model available to your provider account. The application uses Groq first and OpenRouter as a configured fallback for supported temporary failures.

### 3. Configure Stockfish

Install Stockfish and ensure `ENGINE_PATH` in `analysis_engine.py` points to its executable.

The current Windows configuration expects:

```text
engines/stockfish/stockfish/stockfish-windows-x86-64-universal.exe
```

A Windows executable will not run on Linux hosting. Adjust the executable and path for the deployment environment.

### 4. Prepare the Database

A fresh Supabase project needs the application schema and imported data.

The project includes scripts for importing games, openings, lessons, and lesson embeddings. Inspect their inputs and configuration before running them.

Existing development data includes:

| Dataset | Records |
|---|---:|
| Validated games | 19,113 |
| Opening records | 2,803 |

The lesson corpus is currently small and can be expanded.

### 5. Install Frontend Dependencies

```powershell
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=your_supabase_publishable_key
```

In Supabase Auth, enable email authentication and configure the local site and allowed redirect URLs.

Use the same frontend origin consistently during testing.

### 6. Start the Backend

From the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

### 7. Start the Frontend

In a separate terminal:

```powershell
cd frontend
npm run dev
```

Open the local URL printed by Vite, usually:

```text
http://localhost:5173
```

Keep both servers running.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Basic service health |
| POST | `/api/chat` | RAG questions and routed database commands |
| GET | `/api/openings?name=Italian%20Game` | Search opening lines |
| GET | `/api/games?name=Italian%20Game` | Search example games |
| POST | `/api/analyse` | Evaluate a chess position |
| POST | `/api/play` | Request a Stockfish move |

### Request a Stockfish Move

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "difficulty": "medium"
}
```

### Analyse a Position

```json
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
}
```

Evaluation scores use **White’s perspective**:

- Positive: White is favoured.
- Negative: Black is favoured.
- `score_cp / 100`: score expressed in pawns.
- `mate_in`: forced-mate distance when reported.

The evaluation bar visualises advantage; it is not a calibrated winning probability.

## Security & Configuration

- Keep database credentials and model API keys on the backend.
- Never expose Supabase secret or `service_role` keys in frontend code.
- Supabase publishable keys are intended for browser use.
- Protect user-owned database records with authentication and RLS policies.
- Do not commit `.env`, `.env.local`, or virtual environments.
- API endpoints apply rate limits.
- Stockfish operations share a process-local lock.

Frontend login does not automatically secure FastAPI endpoints. Protected game-storage routes will require backend token verification and ownership checks.

## Current Limitations

- The application has not yet been verified in production.
- Some learning API URLs are still configured for localhost.
- Saved games and resume across browser refreshes are not yet implemented.
- Completed-game batch review and move grading are planned.
- Position analysis is limited by backend rate limits and engine availability.
- The engine lock is local to one Python process, not shared across workers.
- FEN-only requests do not preserve repetition history.
- Bot difficulty settings are relative strengths, not verified Elo ratings.
- Clocks are intended for local bot practice, not competitive server-authoritative timing.
- RAG answers depend on a small lesson collection and may contain errors.

## Roadmap

- [ ] Save and resume account-owned games.
- [ ] Add a My Games library.
- [ ] Verify access tokens in protected backend routes.
- [ ] Analyse completed games through a single review request.
- [ ] Cache reviews for later viewing.
- [ ] Add evaluation graphs and move-quality classifications.
- [ ] Add varied bot personalities and opening preferences.
- [ ] Expand the lesson corpus.
- [ ] Complete password recovery.
- [ ] Prepare and verify cloud deployment.

## Acknowledgements

- Stockfish and python-chess for chess engine integration.
- chess.js for frontend chess rules.
- Vue and Three.js for the interface and board rendering.
- Supabase and pgvector for authentication and data infrastructure.
- FastEmbed, Groq, and OpenRouter for the learning pipeline.
- The datasnaek chess dataset on Kaggle for example game data.

Third-party software and datasets retain their respective licenses. Review the applicable terms before redistributing engine binaries or datasets.
