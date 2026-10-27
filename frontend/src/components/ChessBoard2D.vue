<script setup>
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from "vue";
import { Chess } from "chess.js";

const props = defineProps({
  fen: { type: String, required: true },
  highlights: { type: Array, default: () => [] },
  arrows: { type: Array, default: () => [] },
  flipped: { type: Boolean, default: false },
  interactive: { type: Boolean, default: false },
  selectedSquare: { type: String, default: "" },
  legalTargets: { type: Array, default: () => [] },
  lastMove: { type: [Object, Array], default: null },
  checkSquare: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  premoveHighlights: { type: Array, default: () => [] },
  premoveEnabled: { type: Boolean, default: false },
});

const emit = defineEmits(["square-click", "move", "cancel-premove"]);
const FILES = "abcdefgh";
const PIECES = {
  w: { k: "♔", q: "♕", r: "♖", b: "♗", n: "♘", p: "♙", name: "White" },
  b: { k: "♚", q: "♛", r: "♜", b: "♝", n: "♞", p: "♟", name: "Black" },
};
const boardEl = ref(null);
const keyboardSquare = ref("e2");
const gesture = ref(null);
const dragPoint = ref(null);
const suppressPointerClick = ref(false);
let suppressClickTimer = null;
const uid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
const arrowMarkerId = `chess-arrow-${uid}`;
const inputBlocked = computed(() => !props.interactive || props.disabled);

function parsePosition(fen) {
  try {
    const chess = new Chess(fen);
    const cells = new Map();
    chess.board().forEach((row) => row.forEach((piece) => {
      if (piece) cells.set(piece.square, piece);
    }));
    return cells;
  } catch {
    return new Map();
  }
}
const position = computed(() => parsePosition(props.fen));

const boardSquares = computed(() => {
  const squares = [];
  for (let row = 0; row < 8; row += 1) {
    for (let col = 0; col < 8; col += 1) {
      const fileIndex = props.flipped ? 7 - col : col;
      const rank = props.flipped ? row + 1 : 8 - row;
      const square = `${FILES[fileIndex]}${rank}`;
      const piece = position.value.get(square);
      squares.push({
        square,
        piece,
        row,
        col,
        fileLabel: row === 7 ? FILES[fileIndex] : "",
        rankLabel: col === 0 ? String(rank) : "",
        dark: (fileIndex + rank) % 2 === 1,
        label: `${piece ? `${PIECES[piece.color].name} ${piece.type === "n" ? "knight" : ({ k: "king", q: "queen", r: "rook", b: "bishop", p: "pawn" }[piece.type])}` : "Empty"} square ${square}`,
      });
    }
  }
  return squares;
});

const highlightSet = computed(() => new Set(props.highlights));
const premoveSet = computed(() => new Set(props.premoveHighlights));
const targetSet = computed(() => new Set(props.legalTargets));
const lastMoveSet = computed(() => {
  const move = props.lastMove;
  if (Array.isArray(move)) return new Set(move.slice(0, 2));
  if (move && typeof move === "object") return new Set([move.from, move.to].filter(Boolean));
  return new Set();
});
const sourcePiece = computed(() =>
  gesture.value ? position.value.get(gesture.value.from) : null,
);
const dragGlyph = computed(() => {
  const piece = sourcePiece.value;
  return piece ? PIECES[piece.color][piece.type] : "";
});

function displayCoordinate(square) {
  const file = FILES.indexOf(square[0]);
  const rank = Number(square[1]);
  return props.flipped
    ? { col: 7 - file, row: rank - 1 }
    : { col: file, row: 8 - rank };
}

const validArrows = computed(() =>
  props.arrows
    .filter((arrow) => Array.isArray(arrow) && arrow.length >= 2)
    .map(([from, to]) => ({ from: displayCoordinate(from), to: displayCoordinate(to) }))
    .filter(({ from, to }) => from.col >= 0 && from.row >= 0 && to.col >= 0 && to.row >= 0),
);

function squareAtPoint(clientX, clientY) {
  const el = boardEl.value;
  const rect = el?.getBoundingClientRect();
  const width = el?.clientWidth;
  const height = el?.clientHeight;
  if (!rect || !width || !height) return "";
  const x = clientX - rect.left - el.clientLeft;
  const y = clientY - rect.top - el.clientTop;
  if (x < 0 || y < 0 || x >= width || y >= height) return "";
  const col = Math.min(7, Math.floor((x / width) * 8));
  const row = Math.min(7, Math.floor((y / height) * 8));
  return boardSquares.value[row * 8 + col]?.square || "";
}

function onPointerDown(event) {
  if (inputBlocked.value || !event.isPrimary || event.button !== 0) return;
  const squareEl = event.target.closest?.("[data-square]");
  const from = squareEl?.dataset.square;
  if (!from) return;
  gesture.value = {
    pointerId: event.pointerId,
    from,
    startX: event.clientX,
    startY: event.clientY,
    dragging: false,
  };
  keyboardSquare.value = from;
  suppressPointerClick.value = true;
  try {
    boardEl.value?.setPointerCapture(event.pointerId);
  } catch {
    // Some embedded browsers do not support pointer capture.
  }
  event.preventDefault();
}

function onPointerMove(event) {
  const current = gesture.value;
  if (!current || current.pointerId !== event.pointerId) return;
  const dx = event.clientX - current.startX;
  const dy = event.clientY - current.startY;
  if (
    !current.dragging &&
    position.value.has(current.from) &&
    Math.hypot(dx, dy) >= 7
  ) current.dragging = true;
  if (current.dragging) {
    dragPoint.value = { x: event.clientX, y: event.clientY };
    event.preventDefault();
  }
}

function clearGesture() {
  gesture.value = null;
  dragPoint.value = null;
}

function suppressGeneratedClick() {
  suppressPointerClick.value = true;
  clearTimeout(suppressClickTimer);
  suppressClickTimer = setTimeout(() => {
    suppressPointerClick.value = false;
    suppressClickTimer = null;
  }, 0);
}

function onPointerUp(event) {
  const current = gesture.value;
  if (!current || current.pointerId !== event.pointerId) return;
  const target = current.dragging ? squareAtPoint(event.clientX, event.clientY) : "";
  const from = current.from;
  const wasDragging = current.dragging;
  clearGesture();
  suppressGeneratedClick();
  if (wasDragging) {
    if (target && target !== from && !inputBlocked.value) emit("move", { from, to: target });
  } else if (!inputBlocked.value) {
    emit("square-click", from);
  }
  try {
    if (boardEl.value?.hasPointerCapture(event.pointerId)) {
      boardEl.value.releasePointerCapture(event.pointerId);
    }
  } catch {
    // Capture may already have been released by the browser.
  }
}

function onPointerCancel(event) {
  if (gesture.value?.pointerId === event.pointerId) {
    clearGesture();
    suppressPointerClick.value = false;
    clearTimeout(suppressClickTimer);
    suppressClickTimer = null;
  }
}

function squareClick(event, square) {
  // Pointer activation is routed through pointer capture above. This handler
  // intentionally keeps native keyboard-generated button activation.
  if (event.detail !== 0 || suppressPointerClick.value) {
    suppressPointerClick.value = false;
    clearTimeout(suppressClickTimer);
    suppressClickTimer = null;
    return;
  }
  if (!inputBlocked.value) emit("square-click", square);
}

function onSquareKeydown(event, square) {
  if (!["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(event.key)) return;
  event.preventDefault();
  const current = boardSquares.value.findIndex((item) => item.square === square);
  const row = Math.floor(current / 8);
  const col = current % 8;
  const nextRow = row + (event.key === "ArrowUp" ? -1 : event.key === "ArrowDown" ? 1 : 0);
  const nextCol = col + (event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0);
  if (nextRow < 0 || nextRow > 7 || nextCol < 0 || nextCol > 7) return;
  const next = boardSquares.value[nextRow * 8 + nextCol]?.square;
  if (!next) return;
  keyboardSquare.value = next;
  nextTick(() => boardEl.value?.querySelector(`[data-square="${next}"]`)?.focus());
}

function onSquareFocus(square) {
  keyboardSquare.value = square;
}

function onContextMenu(event) {
  if (!props.premoveEnabled) return;
  event.preventDefault();
  emit("cancel-premove");
}

watch(inputBlocked, (blocked) => {
  if (blocked) clearGesture();
});
watch(() => [props.fen, props.flipped], () => clearGesture());
onBeforeUnmount(() => {
  clearTimeout(suppressClickTimer);
  suppressClickTimer = null;
});
</script>

<template>
  <div
    ref="boardEl"
    class="chess-board-2d"
    :class="{ 'is-disabled': inputBlocked, 'is-dragging': gesture?.dragging }"
    role="grid"
    aria-label="Chessboard"
    :aria-disabled="inputBlocked"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerCancel"
    @lostpointercapture="onPointerCancel"
    @contextmenu="onContextMenu"
  >
    <svg class="board-arrows" viewBox="0 0 8 8" aria-hidden="true">
      <defs>
        <marker :id="arrowMarkerId" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L5,2.5 L0,5 z" fill="#f6c85f" />
        </marker>
      </defs>
      <line
        v-for="(arrow, index) in validArrows"
        :key="index"
        :x1="arrow.from.col + 0.5"
        :y1="arrow.from.row + 0.5"
        :x2="arrow.to.col + 0.5"
        :y2="arrow.to.row + 0.5"
        :marker-end="`url(#${arrowMarkerId})`"
      />
    </svg>

    <button
      v-for="cell in boardSquares"
      :key="cell.square"
      type="button"
      class="board-square"
      :class="{
        'square-light': !cell.dark,
        'square-dark': cell.dark,
        'is-highlighted': highlightSet.has(cell.square),
        'is-last-move': lastMoveSet.has(cell.square),
        'is-selected': selectedSquare === cell.square,
        'is-check': checkSquare === cell.square,
        'is-premove': premoveSet.has(cell.square),
        'is-drag-source': !!gesture?.dragging && gesture.from === cell.square,
        'is-legal-target': targetSet.has(cell.square),
        'has-piece-target': targetSet.has(cell.square) && !!cell.piece,
        'keyboard-square': keyboardSquare === cell.square,
      }"
      :data-square="cell.square"
      :aria-label="cell.label"
      :aria-selected="selectedSquare === cell.square"
      :tabindex="keyboardSquare === cell.square ? 0 : -1"
      :disabled="inputBlocked"
      role="gridcell"
      @focus="onSquareFocus(cell.square)"
      @keydown="onSquareKeydown($event, cell.square)"
      @click="squareClick($event, cell.square)"
    >
      <span v-if="cell.rankLabel" class="coordinate coordinate-rank" aria-hidden="true">{{ cell.rankLabel }}</span>
      <span v-if="cell.fileLabel" class="coordinate coordinate-file" aria-hidden="true">{{ cell.fileLabel }}</span>
      <span
        v-if="cell.piece"
        class="chess-piece"
        :class="cell.piece.color === 'w' ? 'piece-white' : 'piece-black'"
        aria-hidden="true"
      >{{ PIECES[cell.piece.color][cell.piece.type] }}</span>
      <span
        v-if="targetSet.has(cell.square)"
        class="move-marker"
        :class="cell.piece ? 'capture-ring' : 'move-dot'"
        aria-hidden="true"
      ></span>
    </button>

    <div
      v-if="gesture?.dragging && dragPoint && dragGlyph"
      class="drag-piece"
      :class="sourcePiece?.color === 'w' ? 'piece-white' : 'piece-black'"
      :style="{ left: `${dragPoint.x}px`, top: `${dragPoint.y}px` }"
      aria-hidden="true"
    >{{ dragGlyph }}</div>
  </div>
</template>

<style scoped>
  .chess-board-2d {
  --light-square: #e8dfc9;
  --dark-square: #73916d;
  position: relative;
  container-type: inline-size;
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  grid-template-rows: repeat(8, minmax(0, 1fr));
  width: 100%;
  aspect-ratio: 1;
  overflow: hidden;
  border: clamp(5px, .8vw, 9px) solid #253a2b;
  border-radius: 10px;
  background: #253a2b;
  box-shadow: 0 18px 42px rgba(0,0,0,.34), inset 0 0 0 1px rgba(255,255,255,.11);
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
  -webkit-tap-highlight-color: transparent;
}
.board-square {
  position: relative;
  display: grid;
  min-width: 0;
  min-height: 0;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 0;
  color: inherit;
  cursor: pointer;
  touch-action: none;
  user-select: none;
  -webkit-user-select: none;
}
.board-square.square-light { background: var(--light-square); }
.board-square.square-dark { background: var(--dark-square); }
.board-square.is-highlighted::before,
.board-square.is-last-move::before,
.board-square.is-selected::before,
.board-square.is-check::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
}
.board-square.is-highlighted::before,
.board-square.is-last-move::before { background: rgba(246, 200, 95, .34); }
.board-square.is-selected::before { background: rgba(246, 200, 95, .56); box-shadow: inset 0 0 0 3px rgba(199, 144, 38, .72); }
.board-square.is-check::before { background: rgba(221, 58, 54, .62); box-shadow: inset 0 0 0 3px rgba(255, 91, 83, .92); }
.board-square.is-premove::before { background: rgba(88, 193, 164, .38); box-shadow: inset 0 0 0 3px rgba(54, 139, 119, .92); }
.board-square:focus-visible { z-index: 3; outline: 3px solid #f5d76e; outline-offset: -4px; }
.board-square:disabled { cursor: default; }
.board-square.is-drag-source .chess-piece { opacity: .25; }
.chess-piece {
  position: relative;
  z-index: 1;
  display: block;
  font-family: "DejaVu Sans", "Noto Sans Symbols 2", "Segoe UI Symbol", "Arial Unicode MS", serif;
  font-size: clamp(24px, 7.15cqw, 68px);
  line-height: 1;
  pointer-events: none;
  transform: translateY(-1%);
}
.piece-white {
  color: #fffdf2;
  -webkit-text-stroke: 1px rgba(43, 47, 37, .82);
  text-shadow: 0 2px 2px rgba(27, 31, 26, .6), 0 0 1px #202820;
}
.piece-black {
  color: #26372b;
  -webkit-text-stroke: 1px rgba(250, 246, 228, .88);
  text-shadow: 0 2px 1px rgba(255,255,255,.28), 0 0 2px rgba(22,34,26,.65);
}
.coordinate {
  position: absolute;
  z-index: 2;
  font: 700 clamp(8px, 1.55cqw, 12px)/1 system-ui, sans-serif;
  pointer-events: none;
}
.coordinate-rank { top: 3px; left: 4px; }
.coordinate-file { right: 4px; bottom: 3px; }
.square-light .coordinate { color: #66705e; }
.square-dark .coordinate { color: #f3ead7; }
.move-marker { position: absolute; z-index: 2; pointer-events: none; }
.move-dot { width: 27%; aspect-ratio: 1; border-radius: 50%; background: rgba(25, 45, 31, .34); }
.capture-ring { width: 88%; height: 88%; border: clamp(3px, .55cqw, 6px) solid rgba(33, 46, 34, .58); border-radius: 50%; }
.board-arrows { position: absolute; inset: 0; z-index: 4; width: 100%; height: 100%; overflow: visible; pointer-events: none; }
.board-arrows line { stroke: #f6c85f; stroke-width: .12; stroke-linecap: round; opacity: .88; }
.drag-piece { position: fixed; z-index: 1000; transform: translate(-50%, -50%); font-family: "DejaVu Sans", "Noto Sans Symbols 2", "Segoe UI Symbol", serif; font-size: clamp(42px, 9vw, 76px); line-height: 1; pointer-events: none; filter: drop-shadow(0 7px 5px rgba(0,0,0,.4)); }
@container (min-width: 0px) { .chess-board-2d { container-type: inline-size; } }
@media (max-width: 520px) {
  .chess-board-2d { border-radius: 6px; }
  .chess-piece { font-size: clamp(22px, 9.4cqw, 54px); }
}
@media (prefers-reduced-motion: reduce) {
  .board-square, .chess-piece { transition: none !important; }
}
</style>
