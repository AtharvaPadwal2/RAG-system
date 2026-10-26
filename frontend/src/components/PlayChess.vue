<script setup>
import {
  computed,
  defineAsyncComponent,
  nextTick,
  onBeforeUnmount,
  reactive,
  ref,
  watch,
} from "vue";
import { Chess } from "chess.js";
import ChessBoard2D from "./ChessBoard2D.vue";

const ChessBoard = defineAsyncComponent(() => import("./ChessBoard.vue"));

/* ------------------------------------------------------------------ */
/* Props / emits                                                       */
/* ------------------------------------------------------------------ */

const props = defineProps({
  mode: { type: String, required: true },
});

// Emitted when the parent asked for a different mode but the player chose
// to keep the current game. The parent should set its selected mode back
// to the payload so its UI matches the game that is still running.
const emit = defineEmits(["mode-rejected", "mode-change"]);

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const PLAY_TIMEOUT_MS = 45000;
const ANALYSE_TIMEOUT_MS = 20000;
const MAX_BUSY_RETRIES = 2; // HTTP 503: at most 2 extra attempts
const MAX_BUSY_WAIT_S = 10;
const DEFAULT_COOLDOWN_S = 60; // HTTP 429 without Retry-After
const UCI_RE = /^[a-h][1-8][a-h][1-8][qrbn]?$/;

const MODE_LABELS = {
  easy: "Easy",
  medium: "Medium",
  hard: "Hard",
  extreme: "Extreme",
  analysis: "Analysis",
};

/* ------------------------------------------------------------------ */
/* Core game state                                                     */
/* ------------------------------------------------------------------ */

// The single authoritative game. It is NOT reactive: every mutation goes
// through refresh(), which publishes the pieces the template needs.
const game = new Chess();

const activeMode = ref(props.mode);
const boardType = ref("2d");
const checkmateCelebration = ref(false);
const checkmateAnimationReady = ref(false);
const humanColor = ref("w");
const flipped = ref(false);

const liveFen = ref(game.fen());
const historyMoves = ref([]); // [{ from, to, promotion, san, color }]
const redoStack = ref([]); // analysis only: [{ from, to, promotion }]
const viewPly = ref(null); // null = live position, number = viewing history

const selectedSquare = ref("");
const legalTargets = ref([]);
const pendingPromotion = ref(null);

const showArrow = ref(true);
const confirmState = ref(null);

const isAnalysis = computed(() => activeMode.value === "analysis");
const difficulty = computed(() =>
  isAnalysis.value ? null : activeMode.value,
);

function refresh() {
  liveFen.value = game.fen();
  historyMoves.value = game.history({ verbose: true }).map((m) => ({
    from: m.from,
    to: m.to,
    promotion: m.promotion,
    san: m.san,
    color: m.color,
  }));
  if (viewPly.value !== null && viewPly.value >= historyMoves.value.length) {
    viewPly.value = null;
  }
  clearSelection();
}

function clearSelection() {
  selectedSquare.value = "";
  legalTargets.value = [];
}

/* ------------------------------------------------------------------ */
/* Position helpers                                                    */
/* ------------------------------------------------------------------ */

// Cache key: placement, side, castling, en passant (no move counters).
function posKey(fen) {
  const fields = fen.trim().split(/\s+/);

  // Keep the half-move clock; omit only full-move numbering.
  return fields.slice(0, 5).join(" ");
}

// Comparison key for backend FENs: placement, side, castling only, so
// differing en-passant conventions and move counters cannot cause a
// false mismatch.
function normFen(fen) {
  return String(fen).trim().split(/\s+/).slice(0, 3).join(" ");
}

function outcomeOf(chess) {
  if (chess.isCheckmate()) {
    const whiteWins = chess.turn() === "b";
    return {
      result: whiteWins ? "1-0" : "0-1",
      text: `Checkmate — ${whiteWins ? "White" : "Black"} wins`,
    };
  }
  if (chess.isStalemate()) {
    return { result: "1/2-1/2", text: "Draw by stalemate" };
  }
  if (chess.isInsufficientMaterial()) {
    return { result: "1/2-1/2", text: "Draw by insufficient material" };
  }
  if (chess.isThreefoldRepetition()) {
    return { result: "1/2-1/2", text: "Draw by threefold repetition" };
  }
  if (
    typeof chess.isDrawByFiftyMoves === "function" &&
    chess.isDrawByFiftyMoves()
  ) {
    return { result: "1/2-1/2", text: "Draw by the fifty-move rule" };
  }
  if (chess.isDraw()) return { result: "1/2-1/2", text: "Draw" };
  return null;
}

function replayTo(ply) {
  const chess = new Chess();
  const moves = historyMoves.value;
  for (let i = 0; i < ply && i < moves.length; i += 1) {
    chess.move({
      from: moves[i].from,
      to: moves[i].to,
      promotion: moves[i].promotion,
    });
  }
  return chess;
}

/* ------------------------------------------------------------------ */
/* Displayed (possibly historical) position                            */
/* ------------------------------------------------------------------ */

const isLive = computed(() => viewPly.value === null);
const displayPly = computed(() =>
  viewPly.value === null ? historyMoves.value.length : viewPly.value,
);

const displayChess = computed(() => {
  void liveFen.value;
  void historyMoves.value;
  return viewPly.value === null ? game : replayTo(viewPly.value);
});

const displayFen = computed(() => {
  void liveFen.value;
  return displayChess.value.fen();
});
const displayKey = computed(() => posKey(displayFen.value));

const displayOutcome = computed(() => outcomeOf(displayChess.value));
const liveOutcome = computed(() => {
  void liveFen.value;
  return outcomeOf(game);
});
const liveResultTitle = computed(() => {
  if (!liveOutcome.value) return "";
  if (liveOutcome.value.result === "1/2-1/2") return "Draw";
  const humanWon =
    (liveOutcome.value.result === "1-0" && humanColor.value === "w") ||
    (liveOutcome.value.result === "0-1" && humanColor.value === "b");
  return humanWon ? "You win" : "Stockfish wins";
});

const displayInCheck = computed(() => displayChess.value.isCheck());
const displayCheckSquare = computed(() =>
  displayInCheck.value
    ? kingSquare(displayChess.value, displayChess.value.turn())
    : "",
);

function kingSquare(chess, color) {
  for (const row of chess.board()) {
    for (const cell of row) {
      if (cell && cell.type === "k" && cell.color === color) {
        return cell.square;
      }
    }
  }
  return "";
}

const lastMove = computed(() => {
  const idx = displayPly.value - 1;
  return idx >= 0 ? historyMoves.value[idx] : null;
});

// The board has one highlight style, so we never mix meanings: while a
// piece is selected it shows selection + legal destinations; otherwise it
// shows the last move and the king in check.
const boardHighlights = computed(() => {
  if (selectedSquare.value && isLive.value) {
    return [selectedSquare.value, ...legalTargets.value];
  }
  const squares = [];
  if (lastMove.value) squares.push(lastMove.value.from, lastMove.value.to);
  if (displayInCheck.value) {
    const sq = kingSquare(displayChess.value, displayChess.value.turn());
    if (sq) squares.push(sq);
  }
  return [...new Set(squares)];
});

/* ------------------------------------------------------------------ */
/* Request coordination                                                */
/* ------------------------------------------------------------------ */

class ApiError extends Error {
  constructor(kind, message, extra = {}) {
    super(message);
    this.kind = kind;
    Object.assign(this, extra);
  }
}
class StaleError extends Error {}

let opGen = 0; // generation token: bumped by every new/cancelled operation
let currentController = null;
const sleepers = new Set();

const requestInFlight = ref(false);
const engineBusy = ref(false);
const engineError = ref(null); // { kind, message }
const evalLoading = ref(false);
const evalError = ref(null); // { key, kind, message }

const evalCache = reactive(new Map()); // posKey -> analysis entry
const lastAnalysed = ref(null); // { key, entry } most recent result

// Rate-limit cooldowns (ms timestamps) with a 1 s ticker used only while
// a cooldown is running. No polling otherwise.
const now = ref(Date.now());
const playCooldownUntil = ref(0);
const evalCooldownUntil = ref(0);
let ticker = null;

const playRemaining = computed(() =>
  Math.max(0, Math.ceil((playCooldownUntil.value - now.value) / 1000)),
);
const evalRemaining = computed(() =>
  Math.max(0, Math.ceil((evalCooldownUntil.value - now.value) / 1000)),
);

function startCooldown(target, seconds) {
  now.value = Date.now();
  const until = Date.now() + Math.max(1, seconds) * 1000;
  if (target === "play") playCooldownUntil.value = until;
  else evalCooldownUntil.value = until;
  if (!ticker) {
    ticker = setInterval(() => {
      now.value = Date.now();
      if (playRemaining.value === 0 && evalRemaining.value === 0) {
        clearInterval(ticker);
        ticker = null;
      }
    }, 1000);
  }
}

// Invalidates everything in flight: aborts the active fetch, wakes any
// sleeping retry (which then sees a stale generation) and returns the new
// generation for the operation that is about to start.
function beginOperation() {
  opGen += 1;
  if (currentController) {
    currentController.abort();
    currentController = null;
  }
  for (const s of sleepers) {
    clearTimeout(s.timer);
    s.resolve();
  }
  sleepers.clear();
  requestInFlight.value = false;
  engineBusy.value = false;
  evalLoading.value = false;
  return opGen;
}

function sleep(ms) {
  return new Promise((resolve) => {
    const entry = { resolve, timer: null };
    entry.timer = setTimeout(() => {
      sleepers.delete(entry);
      resolve();
    }, ms);
    sleepers.add(entry);
  });
}

function parseRetryAfter(value) {
  if (!value) return null;
  const n = Number(value);
  if (Number.isFinite(n) && n >= 0) return Math.ceil(n);
  const date = Date.parse(value);
  if (!Number.isNaN(date)) {
    return Math.max(0, Math.ceil((date - Date.now()) / 1000));
  }
  return null;
}

async function postJson(path, body, gen, timeoutMs) {
  let busyAttempts = 0;

  for (;;) {
    if (gen !== opGen) throw new StaleError();

    const controller = new AbortController();
    currentController = controller;
    requestInFlight.value = true;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    let waitSeconds = 0;

    try {
      let res;
      try {
        res = await fetch(`${API_BASE_URL}${path}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
      } catch {
        if (gen !== opGen) throw new StaleError();
        if (timedOut) {
          throw new ApiError("timeout", "The server took too long to respond.");
        }
        throw new ApiError(
          "network",
          "Can't reach the server. Check your connection and that the backend is running.",
        );
      }

      if (gen !== opGen) throw new StaleError();

      if (res.ok) {
        let data;
        try {
          data = await res.json();
        } catch {
          if (gen !== opGen) throw new StaleError();
          if (timedOut) {
            throw new ApiError("timeout", "The server took too long to respond.");
          }
          throw new ApiError("invalid", "The server sent an unreadable response.");
        }
        if (gen !== opGen) throw new StaleError();
        return data;
      }

      const retryAfter = parseRetryAfter(res.headers.get("Retry-After"));

      if (res.status === 429) {
        throw new ApiError("rate", "Rate limit reached.", { retryAfter });
      }

      if (res.status === 503) {
        if (busyAttempts < MAX_BUSY_RETRIES) {
          busyAttempts += 1;
          const requestedWait = retryAfter ?? 2;

if (requestedWait > MAX_BUSY_WAIT_S) {
  throw new ApiError(
    "busy",
    `Engine unavailable. Retry after ${requestedWait} seconds.`,
    { retryAfter: requestedWait },
  );
}

waitSeconds = requestedWait;
        } else {
          throw new ApiError("busy", "The engine is busy right now.", {
            retryAfter,
          });
        }
      } else {
        throw new ApiError("http", `Server error (${res.status}).`);
      }
    } finally {
      clearTimeout(timer);
      if (currentController === controller) {
        currentController = null;
        requestInFlight.value = false;
      }
    }

    // Only reached for a 503 that is still within the retry budget.
    await sleep(Math.max(1, waitSeconds) * 1000);
    if (gen !== opGen) throw new StaleError();
  }
}

/* ------------------------------------------------------------------ */
/* Evaluation                                                          */
/* ------------------------------------------------------------------ */

function validateAnalysis(data, requestedFen) {
  const bad = () => new ApiError("invalid", "The server sent an unexpected analysis.");
  if (!data || typeof data !== "object") throw bad();
  if (typeof data.fen !== "string" || normFen(data.fen) !== normFen(requestedFen)) {
    throw bad();
  }

  if (data.status === "game_over") {
    if (!["1-0", "0-1", "1/2-1/2"].includes(data.result)) throw bad();
    return { status: "game_over", result: data.result };
  }
  if (data.status !== "analysed") throw bad();

  const cp = Number.isFinite(data.score_cp) ? data.score_cp : null;
  const mate = Number.isInteger(data.mate_in) ? data.mate_in : null;
  // mate_in === 0 on a non-terminal result is meaningless; never infer a winner.
  if (mate === 0 || (cp === null && mate === null)) throw bad();

  return {
    status: "analysed",
    score_cp: cp,
    mate_in: mate,
    best_move_uci:
      typeof data.best_move_uci === "string" && UCI_RE.test(data.best_move_uci)
        ? data.best_move_uci
        : null,
    best_move_san:
      typeof data.best_move_san === "string" ? data.best_move_san : null,
    depth: Number.isFinite(data.depth) ? data.depth : null,
  };
}

function handleEvalError(err, key) {
  if (err instanceof StaleError) return;
  if (err instanceof ApiError) {
    if (err.kind === "rate") {
      startCooldown("eval", err.retryAfter ?? DEFAULT_COOLDOWN_S);
    }
    evalError.value = { key, kind: err.kind, message: err.message };
    return;
  }
  evalError.value = {
    key,
    kind: "unknown",
    message: "Evaluation failed unexpectedly.",
  };
}

// Evaluate one position. Never throws: an optional evaluation must not
// stop the game. Terminal positions are decided locally, not requested.
async function evaluateFen(fen, gen) {
  if (gen !== opGen || !isAnalysis.value) return null;
  const key = posKey(fen);
  if (evalCache.has(key)) return evalCache.get(key);
  if (outcomeOf(new Chess(fen))) return null;

  if (evalRemaining.value > 0) {
    evalError.value = {
      key,
      kind: "rate",
      message: "Evaluation is rate-limited.",
    };
    return null;
  }

  evalError.value = null;
  evalLoading.value = true;
  try {
    const data = await postJson("/api/analyse", { fen }, gen, ANALYSE_TIMEOUT_MS);
    if (gen !== opGen) return null;
    const entry = validateAnalysis(data, fen);
    evalCache.set(key, entry);
    lastAnalysed.value = { key, entry };
    return entry;
  } catch (err) {
    handleEvalError(err, key);
    return null;
  } finally {
    if (gen === opGen) evalLoading.value = false;
  }
}

const displayEntry = computed(() => evalCache.get(displayKey.value) ?? null);

const visibleEvalError = computed(() => {
  const err = evalError.value;
  return err && err.key === displayKey.value ? err : null;
});

const canAnalyse = computed(
  () =>
    !requestInFlight.value &&
    !engineBusy.value &&
    !displayOutcome.value &&
    !displayEntry.value &&
    evalRemaining.value === 0,
);

async function analyseDisplayed() {
  if (!canAnalyse.value) return;
  const gen = beginOperation();
  await evaluateFen(displayFen.value, gen);
}

/* Display mapping ---------------------------------------------------- */
// Monotonic logistic mapping of centipawns to the white share of the bar:
//   whiteShare = 100 / (1 + exp(-cp / 300)), clamped to 2–98 %.
// This visualises advantage; it is NOT a calibrated win probability.
function shareFromCp(cp) {
  const share = 100 / (1 + Math.exp(-cp / 300));
  return Math.min(98, Math.max(2, share));
}

function formatCp(cp) {
  const pawns = cp / 100;
  const sign = pawns > 0 ? "+" : pawns < 0 ? "−" : "";
  return `${sign}${Math.abs(pawns).toFixed(2)}`;
}

function describeEntry(entry) {
  if (entry.status === "game_over") {
    return resultView(entry.result);
  }
  if (entry.mate_in !== null) {
    const white = entry.mate_in > 0;
    const n = Math.abs(entry.mate_in);
    return {
      share: white ? 98 : 2,
      label: `${white ? "White" : "Black"} mates in ${n}`,
      short: `M${n}`,
    };
  }
  return {
    share: shareFromCp(entry.score_cp),
    label: formatCp(entry.score_cp),
    short: formatCp(entry.score_cp),
  };
}

function resultView(result, text) {
  if (result === "1-0") {
    return { share: 100, label: text || "White wins (1-0)", short: "1-0" };
  }
  if (result === "0-1") {
    return { share: 0, label: text || "Black wins (0-1)", short: "0-1" };
  }
  return { share: 50, label: text || "Draw (½-½)", short: "½-½" };
}

const evalView = computed(() => {
  const outcome = displayOutcome.value;
  if (outcome) {
    return {
      ...resultView(outcome.result, outcome.text),
      state: "terminal",
      faded: false,
      detail: "Game finished.",
    };
  }

  const entry = displayEntry.value;
  if (entry) {
    return {
      ...describeEntry(entry),
      state: "result",
      faded: false,
      detail:
        entry.status === "analysed" && entry.depth
          ? `Depth ${entry.depth}`
          : "",
    };
  }

  const prev = lastAnalysed.value;
  const prevView =
    prev && prev.key !== displayKey.value ? describeEntry(prev.entry) : null;
  const baseShare = prevView ? prevView.share : 50;
  const previousLabel = prevView
    ? `Previous position: ${prevView.label}`
    : "";

  if (evalLoading.value) {
    return {
      share: baseShare,
      label: "Evaluating…",
      short: "…",
      state: "evaluating",
      faded: true,
      detail: previousLabel,
    };
  }

  if (displayPly.value === 0 && historyMoves.value.length === 0) {
    return {
      share: 50,
      label: "0.00",
      short: "0.00",
      state: "baseline",
      faded: false,
      detail: "Starting baseline — not analysed yet.",
    };
  }
  if (displayPly.value === 0) {
    return {
      share: 50,
      label: "0.00",
      short: "0.00",
      state: "baseline",
      faded: false,
      detail: "Starting baseline.",
    };
  }

  return {
    share: baseShare,
    label: visibleEvalError.value ? "Unavailable" : "Not analysed",
    short: "?",
    state: "unavailable",
    faded: true,
    detail: previousLabel,
  };
});

const evalAria = computed(
  () =>
    `Evaluation from White's perspective: ${evalView.value.label}. ` +
    `${evalView.value.state === "evaluating" ? "" : evalView.value.detail}`,
);

const evalErrorText = computed(() => {
  const err = visibleEvalError.value;
  if (!err) return "";
  if (err.kind === "rate" || evalRemaining.value > 0) {
    return evalRemaining.value > 0
      ? `Evaluation is rate-limited. You can retry in ${evalRemaining.value}s. Play continues normally.`
      : "Evaluation was rate-limited. You can retry now.";
  }
  return `${err.message} Play continues without it.`;
});

/* Best move suggestion (analysis) ------------------------------------ */
const suggestion = computed(() => {
  const entry = displayEntry.value;
  if (!isAnalysis.value || !entry || entry.status !== "analysed") return null;
  if (!entry.best_move_uci) return null;
  const from = entry.best_move_uci.slice(0, 2);
  const to = entry.best_move_uci.slice(2, 4);
  const promotion = entry.best_move_uci[4];
  const legal = displayChess.value
    .moves({ verbose: true })
    .some(
      (m) =>
        m.from === from && m.to === to && (m.promotion || undefined) === promotion,
    );
  if (!legal) return null;
  return { san: entry.best_move_san, from, to, depth: entry.depth };
});

const boardArrows = computed(() =>
  showArrow.value && suggestion.value
    ? [[suggestion.value.from, suggestion.value.to]]
    : [],
);

/* ------------------------------------------------------------------ */
/* Moves                                                               */
/* ------------------------------------------------------------------ */

const engineTurn = computed(() => {
  void liveFen.value;
  return !isAnalysis.value && game.turn() !== humanColor.value;
});

const needsEngineMove = computed(
  () =>
    isLive.value &&
    engineTurn.value &&
    !liveOutcome.value &&
    !engineBusy.value &&
    !engineError.value &&
    !requestInFlight.value,
);

const canHumanMove = computed(() => {
  if (!isLive.value || liveOutcome.value || confirmState.value) {
    return false;
  }
  if (isAnalysis.value) return true;
  return !engineTurn.value && !engineBusy.value && !engineError.value;
});

function selectPiece(square) {
  selectedSquare.value = square;
  legalTargets.value = [
    ...new Set(game.moves({ square, verbose: true }).map((m) => m.to)),
  ];
}

function onBoardMove({ from, to }) {
  if (!canHumanMove.value || pendingPromotion.value) return;
  const candidates = game
    .moves({ square: from, verbose: true })
    .filter((move) => move.to === to);
  if (!candidates.length) return;
  selectedSquare.value = from;
  if (candidates.some((move) => move.promotion)) {
    pendingPromotion.value = { from, to };
    nextTick(() => promoQueenBtn.value?.focus());
    return;
  }
  playHumanMove({ from, to });
}

function onSquareClick(square) {
  if (!canHumanMove.value || pendingPromotion.value) return;

  if (square === selectedSquare.value) {
    clearSelection();
    return;
  }

  if (selectedSquare.value) {
    const candidates = game
      .moves({ square: selectedSquare.value, verbose: true })
      .filter((m) => m.to === square);

    if (candidates.length) {
      if (candidates.some((m) => m.promotion)) {
        pendingPromotion.value = { from: selectedSquare.value, to: square };
        nextTick(() => promoQueenBtn.value?.focus());
        return;
      }
      playHumanMove({ from: selectedSquare.value, to: square });
      return;
    }
  }

  const piece = game.get(square);
  if (piece && piece.color === game.turn()) selectPiece(square);
  else clearSelection();
}

function promote(piece) {
  if (!pendingPromotion.value || !canHumanMove.value) return;
  const { from, to } = pendingPromotion.value;
  pendingPromotion.value = null;
  playHumanMove({ from, to, promotion: piece });
}

function cancelPromotion() {
  pendingPromotion.value = null;
  clearSelection();
}

function playHumanMove(input) {
  let move;
  try {
    move = game.move(input);
  } catch {
    clearSelection();
    return;
  }
  if (!move) {
    clearSelection();
    return;
  }

  // Keep redo only when the player replays exactly the next redo move.
  const next = redoStack.value[redoStack.value.length - 1];
  if (
    isAnalysis.value &&
    next &&
    next.from === move.from &&
    next.to === move.to &&
    next.promotion === move.promotion
  ) {
    redoStack.value = redoStack.value.slice(0, -1);
  } else {
    redoStack.value = [];
  }

  const gen = beginOperation();
  engineError.value = null;
  refresh();

  if (liveOutcome.value) return; // result is decided locally

  if (isAnalysis.value) {
    void evaluateFen(game.fen(), gen);
  } else {
    void runEngineFlow(gen);
  }
}

/* ------------------------------------------------------------------ */
/* Engine replies                                                      */
/* ------------------------------------------------------------------ */

function applyEngineData(data) {
  const invalid = (msg) =>
    new ApiError("invalid", msg || "Stockfish sent an unexpected reply.");

  if (!data || typeof data !== "object") throw invalid();

  // A game-ending engine reply still contains a move to apply.
if (
  !["played", "game_over"].includes(data.status) ||
  typeof data.move_uci !== "string" ||
  !UCI_RE.test(data.move_uci) ||
  typeof data.fen !== "string"
) {
  throw invalid("Stockfish returned no valid move.");
}
  const from = data.move_uci.slice(0, 2);
  const to = data.move_uci.slice(2, 4);
  const promotion = data.move_uci[4];

  const legal = game
    .moves({ verbose: true })
    .find(
      (m) =>
        m.from === from && m.to === to && (m.promotion || undefined) === promotion,
    );
  if (!legal) throw invalid("Stockfish suggested an illegal move.");

  // Validate the returned FEN against a scratch board before touching the
  // live game.
  const scratch = new Chess(game.fen());
  scratch.move({ from, to, promotion });
  if (normFen(scratch.fen()) !== normFen(data.fen)) {
    throw invalid("Stockfish's reply didn't match the expected position.");
  }

  // Apply to the live game so the full history is preserved.
  game.move({ from, to, promotion });
}

function handleEngineError(err) {
  if (err instanceof StaleError) return;
  if (err instanceof ApiError) {
    if (err.kind === "rate") {
      startCooldown("play", err.retryAfter ?? DEFAULT_COOLDOWN_S);
    }
    engineError.value = { kind: err.kind, message: err.message };
    return;
  }
  engineError.value = {
    kind: "unknown",
    message: "Stockfish failed unexpectedly.",
  };
}

async function runEngineFlow(gen) {
  if (gen !== opGen) return;
  engineError.value = null;
  engineBusy.value = true;

  try {
    if (liveOutcome.value || !engineTurn.value) return;


    if (playRemaining.value > 0) {
      throw new ApiError("rate", "Rate limit reached.");
    }

    const expectedFen = game.fen();
    const expectedPly = game.history().length;
    const data = await postJson(
      "/api/play",
      { fen: expectedFen, difficulty: difficulty.value },
      gen,
      PLAY_TIMEOUT_MS,
    );

    // Position check: same generation AND the exact position we asked about.
    if (gen !== opGen) return;
    if (game.fen() !== expectedFen || game.history().length !== expectedPly) {
      return;
    }

    applyEngineData(data);
    refresh();
    engineBusy.value = false;
  } catch (err) {
    handleEngineError(err);
    return;
  } finally {
    if (gen === opGen) engineBusy.value = false;
  }

  if (gen === opGen && isAnalysis.value && !liveOutcome.value) {
    await evaluateFen(game.fen(), gen);
  }
}

function retryEngine() {
  if (
    playRemaining.value > 0 ||
    requestInFlight.value ||
    engineBusy.value ||
    confirmState.value
  ) {
    return;
  }

  if (!engineTurn.value || liveOutcome.value) return;

  const gen = beginOperation();
  void runEngineFlow(gen);
}

const engineErrorText = computed(() => {
  const err = engineError.value;
  if (!err) return "";
  if (err.kind === "rate" || playRemaining.value > 0) {
    return playRemaining.value > 0
      ? `Stockfish is rate-limited. You can retry in ${playRemaining.value}s.`
      : "Stockfish was rate-limited. You can retry now.";
  }
  return err.message;
});

/* ------------------------------------------------------------------ */
/* Undo / redo                                                         */
/* ------------------------------------------------------------------ */

function undoMove() {
  if (!game.history().length) return;
  beginOperation();
  checkmateCelebration.value = false;
  checkmateAnimationReady.value = false;
  pendingPromotion.value = null;
  engineError.value = null;
  evalError.value = null;
  viewPly.value = null;

  if (isAnalysis.value) {
    const undone = game.undo();
    if (undone) {
      redoStack.value = [
        ...redoStack.value,
        { from: undone.from, to: undone.to, promotion: undone.promotion },
      ];
    }
  } else {
    const hist = game.history({ verbose: true });
    const last = hist[hist.length - 1];
    game.undo();
    // Last move was the engine's: also remove the human move before it.
    // If the last move was the human's (waiting, error, or game ended by
    // the human) only that move is removed. Never auto-replay the engine.
    if (last.color !== humanColor.value && hist.length >= 2) {
      game.undo();
    }
  }

  refresh();

  // Restore the cached evaluation (automatic via the cache); otherwise
  // request one only when permitted.
  if (
    isAnalysis.value &&
    game.history().length > 0 &&
    !liveOutcome.value &&
    !evalCache.has(posKey(game.fen())) &&
    evalRemaining.value === 0
  ) {
    const gen = beginOperation();
    void evaluateFen(game.fen(), gen);
  }
}

function redoMove() {
  if (!isAnalysis.value || !isLive.value || !redoStack.value.length) return;
  const next = redoStack.value[redoStack.value.length - 1];
  beginOperation();
  try {
    game.move(next);
  } catch {
    redoStack.value = [];
    return;
  }
  redoStack.value = redoStack.value.slice(0, -1);
  refresh();
  if (!liveOutcome.value && !evalCache.has(posKey(game.fen()))) {
    const gen = beginOperation();
    void evaluateFen(game.fen(), gen);
  }
}

/* ------------------------------------------------------------------ */
/* History navigation                                                  */
/* ------------------------------------------------------------------ */

function goToPly(ply) {
  const len = historyMoves.value.length;
  const target = Math.min(Math.max(ply, 0), len);
  viewPly.value = target === len ? null : target;
  pendingPromotion.value = null;
  clearSelection();
}

function continueFromHere() {
  if (!isAnalysis.value || isLive.value) return;
  const target = viewPly.value;
  beginOperation();
  while (game.history().length > target) game.undo();
  redoStack.value = [];
  viewPly.value = null;
  refresh();
}

const movePairs = computed(() => {
  const pairs = [];
  historyMoves.value.forEach((m, i) => {
    if (i % 2 === 0) {
      pairs.push({ no: i / 2 + 1, white: { san: m.san, ply: i + 1 }, black: null });
    } else {
      pairs[pairs.length - 1].black = { san: m.san, ply: i + 1 };
    }
  });
  return pairs;
});

const moveListEl = ref(null);
watch([displayPly, () => historyMoves.value.length], () => {
  nextTick(() => {
    const list = moveListEl.value;
    const el = list?.querySelector('[aria-current="step"]');
    if (!list || !el) {
      if (list) list.scrollTop = 0;
      return;
    }
    list.scrollTop = el.offsetTop - list.clientHeight / 2;
  });
});

/* ------------------------------------------------------------------ */
/* New game / colour / mode changes                                    */
/* ------------------------------------------------------------------ */

const confirmYesBtn = ref(null);
const promoQueenBtn = ref(null);

const hasActiveGame = computed(
  () => historyMoves.value.length > 0 && !liveOutcome.value,
);

function resetGame({ mode = activeMode.value, color = humanColor.value } = {}) {
  beginOperation();
  checkmateCelebration.value = false;
  checkmateAnimationReady.value = false;
  activeMode.value = mode;
  humanColor.value = mode === "analysis" ? "w" : color;
  game.reset();
  redoStack.value = [];
  viewPly.value = null;
  pendingPromotion.value = null;
  engineError.value = null;
  evalError.value = null;
  evalCache.clear();
  lastAnalysed.value = null;
  confirmState.value = null;
  flipped.value = mode !== "analysis" && humanColor.value === "b";
  refresh();

  // Human is Black: Stockfish makes White's opening move.
  if (mode !== "analysis" && humanColor.value === "b") {
    const gen = beginOperation();
    void runEngineFlow(gen);
  }
}

function askConfirm(state) {
  confirmState.value = { blocking: false, ...state };
  nextTick(() => confirmYesBtn.value?.focus());
}

function requestNewGame() {
  if (hasActiveGame.value) {
    askConfirm({
      kind: "new",
      title: "Start a new game?",
      text: "The current game will be discarded.",
      yes: "Start new game",
      no: "Keep playing",
    });
  } else {
    resetGame();
  }
}

function requestColor(color) {
  if (color === humanColor.value) return;
  if (hasActiveGame.value) {
    askConfirm({
      kind: "color",
      color,
      title: `Play as ${color === "w" ? "White" : "Black"}?`,
      text: "This starts a new game and discards the current one.",
      yes: "Start new game",
      no: "Keep playing",
    });
  } else {
    resetGame({ color });
  }
}

function acceptConfirm() {
  const state = confirmState.value;
  if (!state) return;
  if (state.kind === "new") resetGame();
  else if (state.kind === "color") resetGame({ color: state.color });
  else if (state.kind === "mode") resetGame({ mode: state.mode });
}

function cancelConfirm() {
  const state = confirmState.value;
  confirmState.value = null;
  if (state?.kind === "mode") emit("mode-rejected", activeMode.value);
}

// The parent may change the selected mode while a game is running. Never
// lose an active game silently: ask first.
watch(
  () => props.mode,
  (next) => {
    if (next === activeMode.value) return;
    if (hasActiveGame.value) {
      askConfirm({
        kind: "mode",
        mode: next,
        title: `Switch to ${MODE_LABELS[next] || next}?`,
        text: "This starts a new game and discards the current one.",
        yes: "Switch and start new game",
        no: "Keep current game",
      });
    } else {
      resetGame({ mode: next });
    }
  },
);

function flipBoard() {
  flipped.value = !flipped.value;
}

function setBoardType(type) {
  if (type === boardType.value) return;
  boardType.value = type;
  pendingPromotion.value = null;
  clearSelection();
}

watch(liveFen, () => {
  if (!isAnalysis.value && game.isCheckmate()) {
    checkmateCelebration.value = true;
    checkmateAnimationReady.value = true;
    setTimeout(() => { checkmateAnimationReady.value = false; }, 600);
  }
});

/* ------------------------------------------------------------------ */
/* Status text                                                         */
/* ------------------------------------------------------------------ */

const sideName = (c) => (c === "w" ? "White" : "Black");

const turnText = computed(() => {
  void liveFen.value;
  if (liveOutcome.value) return liveOutcome.value.text;
  const check = game.isCheck() ? " — check!" : "";
  if (isAnalysis.value) return `${sideName(game.turn())} to move${check}`;
  if (engineBusy.value) return "Stockfish is thinking…";
  if (engineError.value) return "Stockfish couldn't move";
  if (engineTurn.value) return "Stockfish to move";
  return `Your move (${sideName(humanColor.value)})${check}`;
});

const modeTitle = computed(() => (isAnalysis.value ? "Analysis board" : "Play chess"));

/* ------------------------------------------------------------------ */
/* Cleanup                                                             */
/* ------------------------------------------------------------------ */

onBeforeUnmount(() => {
  beginOperation();
  if (ticker) clearInterval(ticker);
  ticker = null;
});

</script>

<template>
  <section class="play-chess">
    <header class="play-header">
      <div>
        <span class="play-eyebrow">CHESS RAG · GAME ROOM</span>
        <h2>{{ modeTitle }}</h2>
        <p v-if="!isAnalysis" class="subtle">Choose your side and play a focused game against Stockfish.</p>
        <p v-else class="subtle">Explore positions freely with Stockfish analysis.</p>
      </div>
      <div class="board-mode-switch" role="group" aria-label="Board display">
        <button type="button" :aria-pressed="boardType === '2d'" :class="{ active: boardType === '2d' }" @click="setBoardType('2d')">2D</button>
        <button type="button" :aria-pressed="boardType === '3d'" :class="{ active: boardType === '3d' }" @click="setBoardType('3d')">3D</button>
      </div>
    </header>

    <div
      v-show="checkmateCelebration && isLive && liveOutcome?.text"
      class="mate-toast"
      :class="{ 'mate-toast--animate': checkmateAnimationReady }"
      role="status"
    >
      <span class="mate-mark" aria-hidden="true">♔</span>
        <div><strong>Checkmate</strong><span>{{ liveOutcome?.text || "" }}</span></div>
    </div>

    <div
      v-if="confirmState"
      class="confirm"
      role="alertdialog"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-text"
      @keydown.esc="cancelConfirm"
    >
      <p id="confirm-title" class="confirm-title">{{ confirmState.title }}</p>
      <p id="confirm-text">{{ confirmState.text }}</p>
      <div class="row">
        <button
          ref="confirmYesBtn"
          type="button"
          class="btn danger"
          @click="acceptConfirm"
        >
          {{ confirmState.yes }}
        </button>
        <button type="button" class="btn secondary" @click="cancelConfirm">
          {{ confirmState.no }}
        </button>
      </div>
    </div>

    <div class="play-layout">
      <!-- Board area -->
      <div class="board-area">
        <div
          v-if="isAnalysis"
          class="eval-bar"
          :class="{ flipped, faded: evalView.faded }"
          role="img"
          :aria-label="evalAria"
        >
          <div
            class="eval-white"
            :style="{ '--share': evalView.share + '%' }"
          ></div>
          <span class="eval-pill" aria-hidden="true">{{ evalView.short }}</span>
        </div>

        <div class="board-wrap">
          <ChessBoard2D
            v-if="boardType === '2d'"
            :fen="displayFen"
            :interactive="canHumanMove && !pendingPromotion"
            :disabled="!!confirmState"
            :highlights="boardHighlights"
            :arrows="boardArrows"
            :flipped="flipped"
            :selected-square="selectedSquare"
            :legal-targets="legalTargets"
            :last-move="lastMove"
            :check-square="displayCheckSquare"
            @square-click="onSquareClick"
            @move="onBoardMove"
          />
          <ChessBoard
            v-else
            :fen="displayFen"
            :interactive="canHumanMove && !pendingPromotion"
            :disabled="!!confirmState"
            :highlights="boardHighlights"
            :arrows="boardArrows"
            :flipped="flipped"
            :check-square="displayCheckSquare"
            @square-click="onSquareClick"
          />
        </div>
      </div>

      <!-- Side panel -->
      <aside class="side-panel" aria-label="Game panel">
        <div class="card status-card">
          <div class="opponent-row">
            <span class="opponent-piece" aria-hidden="true">{{ isAnalysis ? "✦" : "♟" }}</span>
            <div class="opponent-copy">
              <strong>{{ isAnalysis ? "Analysis mode" : "Stockfish" }}</strong>
              <span>{{ isAnalysis ? "Move both sides freely" : "Engine opponent" }}</span>
            </div>
            <label class="difficulty-select">
              <span class="sr-only">Game mode or opponent difficulty</span>
              <select :value="activeMode" @change="emit('mode-change', $event.target.value)">
                <option value="analysis">Analysis</option>
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
                <option value="extreme">Extreme</option>
              </select>
            </label>
          </div>
          <p class="turn" role="status" aria-live="polite" aria-atomic="true">
            <span
              v-if="engineBusy"
              class="spinner"
              aria-hidden="true"
            ></span>
            {{ turnText }}
          </p>

          <p v-if="!isLive" class="banner">
            Viewing earlier position (after move {{ displayPly }} of
            {{ historyMoves.length }}). Moves are disabled until you return to
            the latest position.
          </p>

          <p v-if="isLive && !isAnalysis && liveOutcome" class="result-note">
            <strong>{{ liveResultTitle }}</strong>
            <span>{{ liveOutcome.text }} · {{ historyMoves.length }} half-moves</span>
            <button type="button" class="btn secondary small" @click="goToPly(0)">Review game</button>
          </p>

          <p v-if="engineErrorText" class="error" role="alert">
            {{ engineErrorText }}
          </p>

          <p v-if="isLive && !liveOutcome && canHumanMove" class="subtle small">
            Select a piece and destination, or drag to move. Use the board switch above for 2D or 3D.
          </p>
        </div>

        <!-- Promotion -->
        <div
          v-if="pendingPromotion"
          class="card promotion-picker"
          role="group"
          aria-label="Choose a promotion piece"
          @keydown.esc="cancelPromotion"
        >
          <p>Promote pawn to:</p>
          <div class="row">
            <button
              ref="promoQueenBtn"
              type="button"
              class="btn"
              @click="promote('q')"
            >
              <span aria-hidden="true">♕</span> Queen
            </button>
            <button type="button" class="btn" @click="promote('r')">
              <span aria-hidden="true">♖</span> Rook
            </button>
            <button type="button" class="btn" @click="promote('b')">
              <span aria-hidden="true">♗</span> Bishop
            </button>
            <button type="button" class="btn" @click="promote('n')">
              <span aria-hidden="true">♘</span> Knight
            </button>
            <button type="button" class="btn secondary" @click="cancelPromotion">
              Cancel
            </button>
          </div>
        </div>

        <!-- Evaluation -->
        <div v-if="isAnalysis" class="card eval-card">
          <h3>Evaluation</h3>
          <p class="eval-label" :class="{ faded: evalView.faded }">
            {{ evalView.label }}
          </p>
          <p v-if="evalView.detail" class="subtle small">
            {{ evalView.detail }}
          </p>
          <p class="subtle small">
            White's perspective. The bar shows relative advantage, not win
            probability.
          </p>

          <p v-if="evalErrorText" class="error small">{{ evalErrorText }}</p>

          <div v-if="isAnalysis && suggestion" class="suggestion">
            <p>
              Stockfish suggests <strong>{{ suggestion.san }}</strong>
              <span v-if="suggestion.depth" class="subtle">
                (depth {{ suggestion.depth }})
              </span>
            </p>
          </div>

          <label v-if="isAnalysis" class="checkbox">
            <input v-model="showArrow" type="checkbox" />
            Show best-move arrow
          </label>

          <button
            v-if="!displayEntry && !displayOutcome && displayPly > 0"
            type="button"
            class="btn secondary"
            :disabled="!canAnalyse"
            @click="analyseDisplayed"
          >
            {{
              visibleEvalError
                ? "Retry evaluation"
                : isLive
                  ? "Analyse position"
                  : "Analyse this position"
            }}
          </button>
          <button
            v-else-if="!displayEntry && !displayOutcome && displayPly === 0"
            type="button"
            class="btn secondary"
            :disabled="!canAnalyse"
            @click="analyseDisplayed"
          >
            Analyse starting position
          </button>
        </div>

        <!-- Moves -->
        <div class="card moves-card">
          <h3>Moves</h3>

          <div class="nav-row" role="group" aria-label="Move history navigation">
            <button
              type="button"
              class="btn secondary small"
              :disabled="!historyMoves.length || displayPly === 0"
              @click="goToPly(0)"
            >
              Start
            </button>
            <button
              type="button"
              class="btn secondary small"
              :disabled="!historyMoves.length || displayPly === 0"
              @click="goToPly(displayPly - 1)"
            >
              Previous
            </button>
            <button
              type="button"
              class="btn secondary small"
              :disabled="isLive"
              @click="goToPly(displayPly + 1)"
            >
              Next
            </button>
            <button
              type="button"
              class="btn secondary small"
              :disabled="isLive"
              @click="goToPly(historyMoves.length)"
            >
              Latest
            </button>
          </div>

          <ol
            ref="moveListEl"
            class="move-list"
            aria-label="Move list"
          >
            <li v-if="!movePairs.length" class="empty">No moves yet.</li>
            <li v-for="pair in movePairs" :key="pair.no" class="move-pair">
              <span class="move-no">{{ pair.no }}.</span>
              <button
                type="button"
                class="move"
                :aria-current="displayPly === pair.white.ply ? 'step' : undefined"
                :class="{ current: displayPly === pair.white.ply }"
                @click="goToPly(pair.white.ply)"
              >
                {{ pair.white.san }}
              </button>
              <button
                v-if="pair.black"
                type="button"
                class="move"
                :aria-current="displayPly === pair.black.ply ? 'step' : undefined"
                :class="{ current: displayPly === pair.black.ply }"
                @click="goToPly(pair.black.ply)"
              >
                {{ pair.black.san }}
              </button>
            </li>
          </ol>

          <button
            v-if="isAnalysis && !isLive"
            type="button"
            class="btn secondary"
            @click="continueFromHere"
          >
            Continue from here (discards later moves)
          </button>
        </div>

        <!-- Controls -->
        <div class="card controls-card">
          <h3>Controls</h3>

          <div v-if="!isAnalysis" class="color-pick">
            <span id="color-label" class="subtle small">Play as</span>
            <div class="row" role="group" aria-labelledby="color-label">
              <button
                type="button"
                class="btn secondary small"
                :aria-pressed="humanColor === 'w'"
                :class="{ active: humanColor === 'w' }"
                @click="requestColor('w')"
              >
                White
              </button>
              <button
                type="button"
                class="btn secondary small"
                :aria-pressed="humanColor === 'b'"
                :class="{ active: humanColor === 'b' }"
                @click="requestColor('b')"
              >
                Black
              </button>
            </div>
          </div>

          <div class="row">
            <button
              type="button"
              class="btn"
              :disabled="!historyMoves.length"
              @click="undoMove"
            >
              Undo
            </button>
            <button
              v-if="isAnalysis"
              type="button"
              class="btn secondary"
              :disabled="!redoStack.length || !isLive"
              @click="redoMove"
            >
              Redo
            </button>
            <button type="button" class="btn secondary" @click="flipBoard">
              Flip board
            </button>
            <button type="button" class="btn" @click="requestNewGame">
              New game
            </button>
          </div>

          <div v-if="engineError || needsEngineMove" class="row">
            <button
  type="button"
  class="btn"
  :disabled="
    playRemaining > 0 ||
    requestInFlight ||
    engineBusy ||
    !!confirmState
  "
  @click="retryEngine"
>
              {{
                engineError
                  ? "Retry Stockfish move"
                  : "Let Stockfish move"
              }}
            </button>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.play-chess {
  --bg-card: #17301f;
  --bg-deep: #0e1f14;
  --border: #2f5a3d;
  --text: #e8f3e4;
  --muted: #a9c2a2;
  --accent: #a7d78c;
  --accent-ink: #152111;
  --danger: #f2a39a;

  margin-top: 24px;
  color: var(--text);
  max-width: 100%;
}

h2,
h3 {
  margin: 0 0 8px;
}

h3 {
  font-size: 1rem;
  color: var(--accent);
}

p {
  margin: 0 0 8px;
  line-height: 1.5;
}

.subtle {
  color: var(--muted);
}

.small {
  font-size: 0.85rem;
}

.play-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
  gap: 20px;
  align-items: start;
}

.board-area {
  display: flex;
  gap: 12px;
  align-items: stretch;
  min-width: 0;
}

.board-wrap {
  flex: 1;
  min-width: 0;
}

/* Evaluation bar */
.eval-bar {
  position: relative;
  flex: 0 0 30px;
  min-height: 260px;
  background: #101510;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}

.eval-white {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: var(--share);
  background: #f3f3ec;
  transition:
    height 0.5s ease,
    width 0.5s ease;
}

.eval-bar.flipped .eval-white {
  bottom: auto;
  top: 0;
}

.eval-bar.faded .eval-white {
  opacity: 0.45;
}

.eval-pill {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 2px 4px;
  border-radius: 4px;
  background: rgba(14, 31, 20, 0.88);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.eval-label {
  font-size: 1.6rem;
  font-weight: 800;
  margin-bottom: 4px;
}

.eval-label.faded {
  opacity: 0.6;
}

/* Cards / panels */
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.card {
  padding: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  min-width: 0;
}

.turn {
  font-size: 1.1rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 8px;
}

.banner {
  padding: 8px 10px;
  border-radius: 8px;
  background: #3a3a14;
  border: 1px solid #8a8a2e;
  color: #fff7c2;
}

.error {
  padding: 8px 10px;
  border-radius: 8px;
  background: #3b1b1b;
  border: 1px solid #a14a4a;
  color: var(--danger);
}

.suggestion {
  margin: 8px 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--bg-deep);
  border: 1px solid var(--border);
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}

.checkbox input {
  width: 18px;
  height: 18px;
  accent-color: var(--accent);
}

.confirm {
  margin-bottom: 16px;
  padding: 14px;
  border-radius: 10px;
  background: #2b2a12;
  border: 2px solid #c9b84a;
}

.confirm-title {
  font-weight: 800;
}

/* Buttons */
.row,
.nav-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}

.btn {
  padding: 10px 16px;
  border: 2px solid var(--accent);
  border-radius: 8px;
  background: var(--accent);
  color: var(--accent-ink);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.btn.small {
  padding: 6px 12px;
}

.btn.secondary {
  background: transparent;
  color: var(--accent);
}

.btn.secondary.active {
  background: var(--accent);
  color: var(--accent-ink);
}

.btn.danger {
  background: #e7c85a;
  border-color: #e7c85a;
  color: #231d00;
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn:focus-visible,
.move:focus-visible,
.checkbox input:focus-visible {
  outline: 3px solid #fff;
  outline-offset: 3px;
}

/* Move list */
.move-list {
  position: relative;
  list-style: none;
  margin: 8px 0;
  padding: 6px;
  max-height: 220px;
  overflow-y: auto;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.move-pair {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 1px 0;
}

.move-no {
  width: 2.2em;
  color: var(--muted);
  text-align: right;
}

.move {
  min-width: 4.2em;
  padding: 4px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
}

.move:hover {
  background: #24452f;
}

.move.current {
  background: var(--accent);
  color: var(--accent-ink);
}

.empty {
  color: var(--muted);
  padding: 4px;
}

/* Spinner */
.spinner {
  width: 14px;
  height: 14px;
  border: 3px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.9s linear infinite;
  flex: 0 0 auto;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Mobile: stack panels, horizontal eval bar */
@media (max-width: 860px) {
  .play-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .board-area {
    flex-direction: column;
  }

  .eval-bar {
    flex: 0 0 auto;
    width: 100%;
    min-height: 0;
    height: 24px;
  }

  .eval-white {
    top: 0;
    bottom: 0;
    left: 0;
    right: auto;
    width: var(--share);
    height: auto;
  }

  .eval-bar.flipped .eval-white {
    left: auto;
    right: 0;
    top: 0;
    bottom: 0;
  }

  .btn {
    padding: 10px 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .eval-white { transition: none; }
  .spinner { animation: none; }
}

/* Full-viewport game room */
.play-chess {
  --bg-card: #1b2b20;
  --bg-deep: #111c15;
  --border: rgba(190, 211, 174, .14);
  --text: #f1f3e9;
  --muted: #a8b5a5;
  --accent: #b9d39a;
  --accent-ink: #172116;
  --danger: #f4a09a;
  width: 100%;
  max-width: none;
  min-height: calc(100dvh - 66px);
  margin: 0;
  padding: clamp(18px, 2.5vw, 34px) clamp(14px, 3vw, 46px) 40px;
  color: var(--text);
}
.play-header {
  max-width: 1500px;
  margin: 0 auto 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}
.play-header h2 { margin: 5px 0 3px; font-size: clamp(22px, 2vw, 30px); letter-spacing: -.04em; }
.play-header p { margin: 0; }
.play-eyebrow { color: #b9d39a; font-size: 10px; font-weight: 800; letter-spacing: .16em; }
.play-layout {
  max-width: 1500px;
  margin: 0 auto;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 360px);
  gap: clamp(16px, 2.2vw, 32px);
}
.board-area { justify-content: center; align-items: center; min-width: 0; }
.board-wrap {
  width: min(100%, calc(100dvh - 235px), calc((100vw - 430px) * .92));
  max-width: 900px;
  aspect-ratio: 1;
  flex: 0 1 auto;
  margin: 0 auto;
}
.board-wrap :deep(.board3d) { width: 100%; max-width: none; height: 100%; aspect-ratio: 1; }
.side-panel { max-height: calc(100dvh - 110px); overflow-y: auto; padding-right: 3px; scrollbar-color: #49604b transparent; scrollbar-width: thin; }
.side-panel .card { border-radius: 13px; padding: 15px; background: linear-gradient(145deg, #1d3023, #18271d); box-shadow: 0 8px 20px rgba(0,0,0,.12); }
.side-panel .status-card { order: 0; }
.side-panel .promotion-picker { order: 1; }
.side-panel .controls-card { order: 2; }
.side-panel .moves-card { order: 3; }
.side-panel .eval-card { order: 4; }
.status-card .turn { margin-top: 12px; font-size: 15px; }
.opponent-row { display: flex; align-items: center; gap: 10px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
.opponent-piece { display: grid; width: 38px; height: 38px; place-items: center; border-radius: 11px; background: #2b4431; color: #e8eedc; font-size: 23px; }
.opponent-copy { display: flex; min-width: 0; flex: 1; flex-direction: column; gap: 2px; }
.opponent-copy strong { font-size: 13px; }
.opponent-copy span { color: var(--muted); font-size: 11px; }
.difficulty-select select { max-width: 105px; padding: 7px 25px 7px 9px; border: 1px solid var(--border); border-radius: 8px; background: #122017; color: var(--text); font: inherit; font-size: 11px; }
.board-mode-switch { flex: 0 0 auto; display: inline-flex; gap: 3px; padding: 4px; border: 1px solid rgba(190,211,174,.14); border-radius: 11px; background: #111c15; }
.board-mode-switch button { min-width: 54px; padding: 8px 13px; border: 0; border-radius: 8px; background: transparent; color: #a8b5a5; font: inherit; font-size: 12px; font-weight: 750; cursor: pointer; }
.board-mode-switch button.active { background: #b9d39a; color: #172116; }
.board-mode-switch button:focus-visible { outline: 2px solid #eef4dd; outline-offset: 2px; }
.btn { min-height: 38px; padding: 8px 12px; border: 1px solid #b9d39a; border-radius: 8px; font-size: 12px; transition: background .16s ease, border-color .16s ease, transform .16s ease; }
.btn:not(:disabled):hover { transform: translateY(-1px); }
.btn.secondary { border-color: rgba(190,211,174,.22); color: #d8e1d2; }
.btn.secondary:hover:not(:disabled) { background: rgba(185,211,154,.1); }
.side-panel .row { gap: 7px; }
.side-panel .nav-row { gap: 5px; }
.move-list { max-height: min(245px, 28dvh); }
.result-note { display: flex; flex-direction: column; align-items: flex-start; gap: 5px; margin-top: 10px; padding: 11px 12px; border: 1px solid rgba(185,211,154,.25); border-radius: 9px; background: rgba(185,211,154,.08); color: #d9e8c9; font-size: 12px; font-weight: 700; }
.result-note span { color: var(--muted); font-size: 11px; font-weight: 500; }
.mate-toast { max-width: 1500px; margin: 0 auto 16px; display: flex; align-items: center; gap: 13px; padding: 13px 17px; border: 1px solid rgba(229,183,93,.44); border-radius: 12px; background: linear-gradient(100deg, rgba(126,91,31,.3), rgba(38,48,30,.88)); box-shadow: 0 12px 35px rgba(0,0,0,.16); }
.mate-toast--animate { animation: mate-in .38s cubic-bezier(.2,.8,.2,1) both; }
.mate-mark { display: grid; width: 38px; height: 38px; place-items: center; border-radius: 50%; background: #d9b568; color: #29311e; font-size: 23px; }
.mate-toast div { display: flex; flex-direction: column; gap: 2px; }
.mate-toast strong { color: #f3dfad; font-size: 14px; }
.mate-toast span:not(.mate-mark) { color: #d8d6c8; font-size: 12px; }
@keyframes mate-in { from { opacity: 0; transform: translateY(-7px) scale(.99); } to { opacity: 1; transform: translateY(0) scale(1); } }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }

@media (max-width: 980px) {
  .play-layout { grid-template-columns: minmax(0, 1fr) minmax(300px, 340px); }
  .board-wrap { width: min(100%, 76dvh, calc((100vw - 390px) * .9)); }
}
@media (max-width: 820px) {
  .play-chess { min-height: calc(100dvh - 58px); padding: 18px clamp(12px, 3vw, 24px) 32px; }
  .play-layout { grid-template-columns: minmax(0, 1fr); }
  .board-area { flex-direction: row; align-items: stretch; }
  .board-wrap { width: min(100%, calc(100vw - 76px), 72dvh); max-width: 760px; }
  .side-panel { max-height: none; overflow: visible; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
  .status-card, .controls-card { grid-column: 1 / -1; }
  .side-panel .controls-card { order: 1; }
  .side-panel .moves-card { order: 2; }
  .side-panel .eval-card { order: 3; }
}
@media (max-width: 560px) {
  .play-header { align-items: flex-start; gap: 10px; }
  .play-header h2 { font-size: 23px; }
  .play-header p { max-width: 34ch; font-size: 12px; }
  .board-mode-switch button { min-width: 44px; padding: 8px 10px; }
  .board-area { flex-direction: column; gap: 9px; }
  .eval-bar { order: 0; width: 100%; }
  .board-wrap { order: 1; width: min(100%, calc(100vw - 28px)); max-width: none; }
  .side-panel { grid-template-columns: minmax(0, 1fr); }
  .side-panel > .card { grid-column: 1; }
  .side-panel .row > .btn { flex: 1 1 auto; }
  .mate-toast { padding: 10px 12px; }
}
@media (prefers-reduced-motion: reduce) {
  .mate-toast--animate { animation: none; }
  .btn { transition: none; }
}
</style>
