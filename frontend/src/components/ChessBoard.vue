<script setup>
import { computed } from "vue";

const props = defineProps({
  fen: { type: String, required: true },
  highlights: { type: Array, default: () => [] },
  arrows: { type: Array, default: () => [] },
});

const pieces = {
  K: "♔", Q: "♕", R: "♖",
  B: "♗", N: "♘", P: "♙",
  k: "♚", q: "♛", r: "♜",
  b: "♝", n: "♞", p: "♟",
};

const squares = computed(() => {
  const rows = props.fen.split(" ")[0].split("/");
  const result = [];

  rows.forEach((row, rowIndex) => {
    let column = 0;

    for (const token of row) {
      const count = /\d/.test(token) ? Number(token) : 1;

      for (let i = 0; i < count; i++) {
        result.push({
          name: `${"abcdefgh"[column]}${8 - rowIndex}`,
          piece: /\d/.test(token) ? "" : token,
          dark: (rowIndex + column) % 2 === 1,
        });
        column++;
      }
    }
  });

  return result;
});

function center(square) {
  return {
    x: "abcdefgh".indexOf(square[0]) * 100 + 50,
    y: (8 - Number(square[1])) * 100 + 50,
  };
}
</script>

<template>
  <div class="board" role="img" aria-label="Chess demonstration board">
    <div
      v-for="square in squares"
      :key="square.name"
      class="square"
      :class="{
        dark: square.dark,
        highlighted: highlights.includes(square.name),
      }"
      :title="square.name"
    >
      <span
        class="piece"
        :class="{ white: square.piece && square.piece === square.piece.toUpperCase() }"
      >
        {{ pieces[square.piece] || "" }}
      </span>
      <small>{{ square.name }}</small>
    </div>

    <svg class="arrows" viewBox="0 0 800 800" aria-hidden="true">
      <g v-for="(arrow, index) in arrows" :key="index">
        <line
          :x1="center(arrow[0]).x"
          :y1="center(arrow[0]).y"
          :x2="center(arrow[1]).x"
          :y2="center(arrow[1]).y"
        />
        <circle :cx="center(arrow[1]).x" :cy="center(arrow[1]).y" r="13" />
      </g>
    </svg>
  </div>
</template>

<style scoped>
.board {
  position: relative;
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  width: 100%;
  max-width: 480px;
  aspect-ratio: 1;
  border: 3px solid #26392d;
  border-radius: 8px;
  overflow: hidden;
}

.square {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #eeeed2;
  min-width: 0;
}

.square.dark {
  background: #769656;
}

.square.highlighted {
  box-shadow: inset 0 0 0 4px #efb735;
}

.piece {
  font-family: "Segoe UI Symbol", "DejaVu Sans", serif;
  font-size: clamp(20px, 7vw, 48px);
  line-height: 1;
  color: #17221b;
}

.piece.white {
  color: #fff;
  text-shadow: 1px 1px 2px #17221b, -1px -1px 1px #17221b;
}

small {
  position: absolute;
  bottom: 2px;
  left: 3px;
  font: 10px sans-serif;
  color: #17221b;
}

.arrows {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.arrows line {
  stroke: #d45b18;
  stroke-width: 12;
  stroke-linecap: round;
  opacity: 0.8;
}

.arrows circle {
  fill: #d45b18;
}
</style>