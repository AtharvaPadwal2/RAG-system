<script setup>
import { ref } from "vue";
import { Chess } from "chess.js";
import ChessBoard from "./components/ChessBoard.vue";

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
</script>

<template>
  <main class="app">
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
</style>