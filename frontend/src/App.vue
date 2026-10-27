<script setup>
import { defineAsyncComponent, ref } from "vue";
import { Chess } from "chess.js";
import AuthPanel from "./components/AuthPanel.vue";
import { useAuth } from "./composables/useAuth";
import PlayChess from "./components/PlayChess.vue";
const ChessBoard = defineAsyncComponent(() => import("./components/ChessBoard.vue"));

const currentView = ref("play");
const selectedMode = ref("medium");

const showAuth = ref(false);
const logoutBusy = ref(false);
const accountError = ref("");

const {
  user,
  isLoggedIn,
  loading: authLoading,
  authError,
  signOut,
} = useAuth();

async function logout() {
  if (logoutBusy.value) return;

  logoutBusy.value = true;
  accountError.value = "";

  try {
    await signOut();
    showAuth.value = false;
  } catch {
    accountError.value = "Could not log out. Please try again.";
  } finally {
    logoutBusy.value = false;
  }
}

function syncMode(mode) {
  selectedMode.value = mode;
}

const question = ref("");
const messages = ref([]);
const loading = ref(false);
const error = ref("");

function prepareBoard(example) {
  const game = new Chess(example.fen);
  const positions = [game.fen()];

  for (const move of example.moves) {
    game.move({
      from: move.slice(0, 2),
      to: move.slice(2, 4),
      ...(move.length === 5 ? { promotion: move[4] } : {}),
    });
    positions.push(game.fen());
  }

  return { ...example, positions, step: 0 };
}

async function sendQuestion() {
  const text = question.value.trim();
  if (!text || loading.value) return;

  loading.value = true;
  error.value = "";

  try {
    const response = await fetch("http://127.0.0.1:8000/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: text }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "The request failed. Please try again."
      );
    }

    const boards = [];
    let boardError = "";

    for (const example of data.board_examples ?? []) {
      try {
        boards.push(prepareBoard(example));
      } catch {
        boardError = "A board example could not be displayed.";
      }
    }

    messages.value.push({
      question: text,
      answer: data.answer,
      sources: data.sources ?? [],
      boards,
      boardError,
    });

    question.value = "";
  } catch (err) {
    error.value =
      err instanceof TypeError
        ? "Cannot reach the backend. Check that FastAPI is running."
        : err.message || "Something went wrong.";
  } finally {
    loading.value = false;
  }
}
const openingName = ref("");
const openingBoards = ref([]);
const openingLoading = ref(false);
const openingError = ref("");

async function findOpenings() {
  const name = openingName.value.trim();

  if (!name || openingLoading.value) return;

  openingLoading.value = true;
  openingError.value = "";
  openingBoards.value = [];

  try {
    const response = await fetch(
      `http://127.0.0.1:8000/api/openings?name=${encodeURIComponent(name)}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "Opening search failed."
      );
    }

    openingBoards.value = data.map(prepareBoard);

    if (openingBoards.value.length === 0) {
      openingError.value = "No matching openings found in our dataset.";
    }
  } catch (err) {
    openingError.value =
      err instanceof TypeError
        ? "Cannot reach the backend. Check that FastAPI is running."
        : err.message || "Opening search failed.";
  } finally {
    openingLoading.value = false;
  }
}
const gameOpeningName = ref("");
const gameBoards = ref([]);
const gameLoading = ref(false);
const gameError = ref("");

async function findGames() {
  const name = gameOpeningName.value.trim();

  if (!name || gameLoading.value) return;

  gameLoading.value = true;
  gameError.value = "";
  gameBoards.value = [];

  try {
    const response = await fetch(
      `http://127.0.0.1:8000/api/games?name=${encodeURIComponent(name)}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        typeof data.detail === "string"
          ? data.detail
          : "Game search failed."
      );
    }

    gameBoards.value = data.map(prepareBoard);

    if (gameBoards.value.length === 0) {
      gameError.value = "No matching games found in our dataset.";
    }
  } catch (err) {
    gameError.value =
      err instanceof TypeError
        ? "Cannot reach the backend. Check that FastAPI is running."
        : err.message || "Game search failed.";
  } finally {
    gameLoading.value = false;
  }
}
const analysisLoading = ref(false);
const analysisError = ref("");
const analysisResult = ref(null);

async function analyseBoard(board) {
  if (analysisLoading.value) return;

  analysisLoading.value = true;
  analysisError.value = "";
  analysisResult.value = null;

  try {
    const response = await fetch("http://127.0.0.1:8000/api/analyse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fen: board.positions[board.step],
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        response.status === 429
          ? "Analysis limit reached. Please wait a minute."
          : typeof data.detail === "string"
            ? data.detail
            : "Analysis failed."
      );
    }

    analysisResult.value = data;
  } catch (error) {
    analysisError.value =
      error instanceof TypeError
        ? "Cannot reach the backend. Check that FastAPI is running."
        : error.message || "Analysis failed.";
  } finally {
    analysisLoading.value = false;
  }
}
</script>


  <template>
  <div class="site-shell">
    <div class="account-area">
      <p
        v-if="authError || accountError"
        class="error"
        role="alert"
      >
        {{ accountError || authError }}
      </p>

      <div
        v-if="showAuth && !isLoggedIn"
        id="account-panel"
      >
        <AuthPanel @close="showAuth = false" />
      </div>
    </div>

        <nav class="site-nav" aria-label="Main navigation">
      <a class="site-brand" href="#home" @click.prevent="currentView = 'home'">
        <span class="brand-mark" aria-hidden="true">♞</span>
        <span>Chess<span class="brand-accent">RAG</span></span>
      </a>
      <div class="nav-links">
        <button type="button" :class="{ selected: currentView === 'home' }" @click="currentView = 'home'">Home</button>
        <button type="button" :class="{ selected: currentView === 'learn' }" @click="currentView = 'learn'">Learn Chess</button>
        <button type="button" :class="{ selected: currentView === 'play' }" @click="currentView = 'play'">Play</button>
      </div>
      <div class="account-controls">
  <span v-if="authLoading" role="status">
    Checking login…
  </span>

  <template v-else-if="isLoggedIn">
    <span class="account-email">{{ user.email }}</span>

    <button
      type="button"
      :disabled="logoutBusy"
      @click="logout"
    >
      {{ logoutBusy ? "Logging out…" : "Log out" }}
    </button>
  </template>

  <button
    v-else
    type="button"
    :aria-expanded="showAuth"
    aria-controls="account-panel"
    @click="showAuth = !showAuth"
  >
    {{ showAuth ? "Close login" : "Log in / Sign up" }}
  </button>
</div>
    </nav>

    <section v-show="currentView === 'home'" class="home-view" id="home">
      <div class="home-copy">
        <span class="home-eyebrow">A calmer way to get better</span>
        <h1>Learn the board.<br /><em>Trust your next move.</em></h1>
        <p>Explore ideas, replay classic lines, and put your instincts to work against Stockfish.</p>
        <div class="home-actions">
          <button type="button" class="home-primary" @click="currentView = 'play'">Play a game <span aria-hidden="true">→</span></button>
          <button type="button" class="home-secondary" @click="currentView = 'learn'">Explore lessons</button>
        </div>
      </div>
      <div class="home-board-art" aria-hidden="true">
        <span class="home-piece home-piece-one">♞</span>
        <span class="home-piece home-piece-two">♟</span>
        <span class="home-orbit"></span>
        <span class="home-caption">YOUR NEXT MOVE STARTS HERE</span>
      </div>
    </section>

    <main v-show="currentView === 'learn'" class="app learn-view">
      <header>
      <span class="badge">CHESS RAG</span>
      <h1>Understand your next move.</h1>
      <p>Ask about chess concepts and explore visual examples.</p>
      


    </header>
    

    <form class="question-form" @submit.prevent="sendQuestion">
      <label for="question">Your chess question</label>

      <div class="input-row">
        <input
          id="question"
          v-model="question"
          maxlength="1000"
          placeholder="Explain en passant."
          :disabled="loading"
          required
        />
        <button :disabled="loading || !question.trim()">
          {{ loading ? "Thinking…" : "Ask" }}
        </button>
      </div>
    </form>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">Searching lessons and preparing an answer…</p>

    <section
      v-for="(message, index) in messages"
      :key="index"
      class="answer-card"
    >
      <h2>{{ message.question }}</h2>
      <p class="answer">{{ message.answer }}</p>

      <div v-if="message.sources.length" class="sources">
        <strong>Retrieved lessons</strong>
        <p v-for="source in message.sources" :key="source.citation">
          [{{ source.citation }}] {{ source.title }}
        </p>
      </div>

      <p v-if="message.boardError" class="error">
        {{ message.boardError }}
      </p>

      <article
        v-for="(board, boardIndex) in message.boards"
        :key="boardIndex"
        class="example"
      >
        <h3>{{ board.lesson_title }}</h3>

        <ChessBoard
          :fen="board.positions[board.step]"
          :highlights="board.step === 0 ? board.highlights : []"
          :arrows="board.step === 0 ? board.arrows : []"
        />

        <p>{{ board.caption }}</p>

        <div v-if="board.positions.length > 1" class="controls">
          <button
            type="button"
            :disabled="board.step === 0"
            @click="board.step--"
          >
            Previous
          </button>

          <span>
            Position {{ board.step + 1 }} / {{ board.positions.length }}
          </span>

          <button
            type="button"
            :disabled="board.step === board.positions.length - 1"
            @click="board.step++"
          >
            Next
          </button>
        </div>
      </article>
    </section>
<section class="answer-card">
  <h2>Explore openings</h2>

  <form @submit.prevent="findOpenings">
    <label for="opening-name">Opening name</label>

    <div class="input-row">
      <input
        id="opening-name"
        v-model="openingName"
        maxlength="100"
        placeholder="Italian Game"
        :disabled="openingLoading"
        required
      />

      <button :disabled="openingLoading || !openingName.trim()">
        {{ openingLoading ? "Searching…" : "Find openings" }}
      </button>
    </div>
  </form>

  <p v-if="openingError" class="error" role="alert">
    {{ openingError }}
  </p>

  <p v-if="openingLoading" role="status">
    Finding opening lines…
  </p>

  <article
    v-for="(board, index) in openingBoards"
    :key="index"
    class="example"
  >
    <h3>{{ board.lesson_title }}</h3>

    <ChessBoard
      :fen="board.positions[board.step]"
      :highlights="[]"
      :arrows="[]"
    />

    <p>{{ board.caption }}</p>

    <div class="controls">
      <button
        type="button"
        :disabled="board.step === 0"
        @click="board.step--"
      >
        Previous
      </button>

      <span>
        Move {{ board.step }} / {{ board.positions.length - 1 }}
      </span>

      <button
        type="button"
        :disabled="board.step === board.positions.length - 1"
        @click="board.step++"
      >
        Next
      </button>
    </div>
  </article>
</section>
<section class="answer-card">
  <h2>Replay example games</h2>

  <form @submit.prevent="findGames">
    <label for="game-opening">Find games by opening</label>

    <div class="input-row">
      <input
        id="game-opening"
        v-model="gameOpeningName"
        maxlength="100"
        placeholder="Italian Game"
        :disabled="gameLoading"
        required
      />

      <button :disabled="gameLoading || !gameOpeningName.trim()">
        {{ gameLoading ? "Searching…" : "Find games" }}
      </button>
    </div>
  </form>

  <p v-if="gameError" class="error" role="alert">
    {{ gameError }}
  </p>

  <p v-if="gameLoading" role="status">
    Finding example games…
  </p>

  <article
    v-for="(board, index) in gameBoards"
    :key="index"
    class="example"
  >
    <h3>{{ board.lesson_title }}</h3>

    <ChessBoard
      :fen="board.positions[board.step]"
      :highlights="[]"
      :arrows="[]"
    />

    <p>{{ board.caption }}</p>

    <div class="controls">
      <button
        type="button"
        :disabled="board.step === 0"
        @click="board.step = 0"
      >
        Start
      </button>
      <button
  type="button"
  :disabled="analysisLoading"
  @click="analyseBoard(board)"
>
  {{ analysisLoading ? "Analysing…" : "Analyse position" }}
</button>

<p v-if="analysisError" class="error" role="alert">
  {{ analysisError }}
</p>

<div
  v-if="
    analysisResult &&
    analysisResult.fen === board.positions[board.step]
  "
>
  <template v-if="analysisResult.status === 'game_over'">
    <p>Game over: {{ analysisResult.result }}</p>
  </template>

  <template v-else>
    <p>
      <strong>Suggested move:</strong>
      {{ analysisResult.best_move_san }}
    </p>

    <p v-if="analysisResult.mate_in !== null">
      <strong>Mate score (White’s perspective):</strong>
      {{ analysisResult.mate_in }}
    </p>

    <p v-else-if="analysisResult.score_cp !== null">
      <strong>Evaluation (White’s perspective):</strong>
      {{ (analysisResult.score_cp / 100).toFixed(2) }} pawns
    </p>

    <p><strong>Search depth:</strong> {{ analysisResult.depth }}</p>
  </template>
</div>

      <button
        type="button"
        :disabled="board.step === 0"
        @click="board.step--"
      >
        Previous
      </button>

      <span>
        Half-move {{ board.step }} /
        {{ board.positions.length - 1 }}
      </span>

      <button
        type="button"
        :disabled="board.step === board.positions.length - 1"
        @click="board.step++"
      >
        Next
      </button>

      <button
        type="button"
        :disabled="board.step === board.positions.length - 1"
        @click="board.step = board.positions.length - 1"
      >
        End
      </button>
    </div>
  </article>
</section>
    <p class="footnote">
      Prototype: answers come from a small lesson collection and may contain errors.
      Each question is handled independently.
    </p>
    </main>

   <PlayChess
  v-show="currentView === 'play'"
  :mode="selectedMode"
  @mode-change="syncMode"
  @mode-rejected="syncMode"
/>
  </div>
</template>

<style scoped>
.app {
  max-width: 900px;
  margin: 0 auto;
  padding: 48px 20px;
  color: #e8eee9;
}

.badge {
  color: #a7d78c;
  font-weight: 700;
  letter-spacing: 0.15em;
}

h1 {
  font-size: clamp(30px, 5vw, 48px);
  line-height: 1.15;
}

header p,
.footnote {
  color: #acbbae;
}

.question-form,
.answer-card {
  margin-top: 28px;
  padding: 24px;
  border: 1px solid #344638;
  border-radius: 16px;
  background: #1b2820;
}

label {
  display: block;
  margin-bottom: 12px;
  font-weight: 600;
}

.input-row,
.controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

input {
  flex: 1;
  min-width: 0;
  padding: 14px;
  border: 1px solid #526953;
  border-radius: 8px;
  background: #101a14;
  color: #fff;
  font: inherit;
}

button {
  padding: 12px 18px;
  border: 0;
  border-radius: 8px;
  background: #a7d78c;
  color: #152111;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.answer {
  white-space: pre-wrap;
  line-height: 1.8;
}

.sources {
  color: #b3cba9;
  font-size: 14px;
}

.example {
  margin-top: 28px;
}

.example p {
  max-width: 60ch;
  line-height: 1.6;
}

.controls {
  flex-wrap: wrap;
}

.error {
  color: #ffb4a9;
}

.footnote {
  font-size: 13px;
  line-height: 1.6;
}

@media (max-width: 500px) {
  .input-row {
    flex-direction: column;
    align-items: stretch;
  }
}

.site-shell { min-height: 100vh; color: #e8eee9; }
.site-nav {
  position: relative;
  z-index: 20;
  min-height: 62px;
  padding: 0 clamp(14px, 3vw, 42px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  border-bottom: 1px solid rgba(208, 226, 198, .1);
  background: rgba(15, 25, 18, .96);
}
.site-brand { display: inline-flex; align-items: center; gap: 9px; color: #f1f3e9; text-decoration: none; font-size: 16px; font-weight: 800; letter-spacing: -.04em; }
.brand-mark { display: grid; width: 31px; height: 31px; place-items: center; border-radius: 10px; background: #b9d39a; color: #172116; font-size: 19px; }
.brand-accent { color: #b9d39a; }
.nav-links { display: flex; align-items: center; gap: 5px; }
.nav-links button { padding: 9px 13px; border: 0; border-radius: 8px; background: transparent; color: #a8b5a5; font-size: 12px; font-weight: 650; cursor: pointer; }
.nav-links button:hover { background: rgba(185,211,154,.08); color: #f1f3e9; }
.nav-links button.selected { background: #223528; color: #d7e5c7; }
.site-nav button:focus-visible, .home-view button:focus-visible { outline: 2px solid #d8ef9b; outline-offset: 3px; }
.app.learn-view { padding-top: 38px; }
.home-view {
  width: min(1320px, calc(100% - 40px));
  min-height: calc(100dvh - 62px);
  margin: 0 auto;
  padding: clamp(42px, 8vw, 100px) 0;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(310px, .95fr);
  align-items: center;
  gap: clamp(32px, 8vw, 110px);
}
.home-copy { position: relative; z-index: 1; }
.home-eyebrow { color: #b9d39a; font-size: 10px; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; }
.home-copy h1 { margin: 18px 0; color: #f1f3e9; font-size: clamp(44px, 6.2vw, 78px); line-height: 1.03; letter-spacing: -.065em; }
.home-copy h1 em { color: #b9d39a; font-family: Georgia, serif; font-weight: 500; }
.home-copy > p { max-width: 450px; color: #a8b5a5; font-size: 15px; line-height: 1.75; }
.home-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 28px; }
.home-actions button { min-height: 46px; padding: 0 18px; border-radius: 10px; font: inherit; font-size: 12px; font-weight: 750; cursor: pointer; }
.home-primary { border: 1px solid #b9d39a; background: #b9d39a; color: #172116; }
.home-primary span { margin-left: 10px; font-size: 17px; }
.home-secondary { border: 1px solid rgba(190,211,174,.2); background: transparent; color: #d9e1d4; }
.home-board-art { position: relative; display: grid; place-items: center; width: min(100%, 490px); aspect-ratio: 1; justify-self: center; overflow: hidden; border: 1px solid rgba(190,211,174,.12); border-radius: 34px; background: radial-gradient(ellipse at 52% 48%, rgba(103,139,95,.24), transparent 58%), linear-gradient(145deg,#1b2d20,#101a13 75%); box-shadow: 0 30px 90px rgba(0,0,0,.25); }
.home-board-art::before { content: ""; position: absolute; inset: 13%; border: 1px solid rgba(185,211,154,.22); border-radius: 50%; box-shadow: 0 0 0 32px rgba(185,211,154,.025), 0 0 0 68px rgba(185,211,154,.02); }
.home-orbit { position: absolute; width: 82%; height: 38%; border: 1px solid rgba(216,231,193,.23); border-radius: 50%; transform: rotate(-34deg); }
.home-piece { position: absolute; z-index: 1; line-height: 1; filter: drop-shadow(0 15px 13px rgba(0,0,0,.4)); }
.home-piece-one { left: 25%; top: 18%; color: #e9eedf; font-size: clamp(110px, 17vw, 190px); transform: rotate(-12deg); }
.home-piece-two { right: 18%; bottom: 16%; color: #91ab7e; font-size: clamp(90px, 13vw, 145px); transform: rotate(9deg); }
.home-caption { position: absolute; right: 24px; bottom: 22px; color: #91a38a; font-size: 9px; font-weight: 700; letter-spacing: .18em; }
@media (max-width: 760px) {
  .home-view { min-height: calc(100dvh - 58px); grid-template-columns: 1fr; gap: 36px; padding-top: 48px; }
  .home-board-art { width: min(100%, 410px); }
}
@media (max-width: 480px) {
  .site-nav { min-height: 58px; gap: 8px; }
  .site-brand { gap: 6px; font-size: 14px; }
  .brand-mark { width: 28px; height: 28px; }
  .nav-links { gap: 0; }
  .nav-links button { padding: 8px 7px; font-size: 10px; }
  .home-view { width: calc(100% - 28px); }
  .home-copy h1 { font-size: clamp(40px, 11vw, 56px); }
}

.account-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

.account-email {
  max-width: 100%;
  color: #afc4a9;
  overflow-wrap: anywhere;
}

.site-shell {
  display: flex;
  flex-direction: column;
}

.site-nav {
  order: -1;
  flex-wrap: wrap;
  padding-top: 10px;
  padding-bottom: 10px;
}

.account-controls {
  margin-top: 0;
}

.account-area > .error {
  padding: 0 20px;
}

.account-area:empty {
  display: none;
}
</style>
