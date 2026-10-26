<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

const props = defineProps({
  fen: { type: String, required: true },
  highlights: { type: Array, default: () => [] },
  arrows: { type: Array, default: () => [] },
  flipped: { type: Boolean, default: false },
  interactive: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  checkSquare: { type: String, default: "" },
});
const emit = defineEmits(["square-click"]);

const host = ref(null);
const FILES = "abcdefgh";
const sqPos = (name) => ({
  x: FILES.indexOf(name[0]) - 3.5,
  z: 8 - Number(name[1]) - 3.5,
});

let renderer, scene, camera, controls, ro, raf;
let boardGroup, piecesGroup, fxGroup;
const raycaster = new THREE.Raycaster();
const pointerNdc = new THREE.Vector2();
const boardPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const hitPoint = new THREE.Vector3();
let pointerStart = null;
let rebuild = () => {};

function onBoardPointerDown(event) {
  if (!event.isPrimary || event.button !== 0) return;
  pointerStart = { x: event.clientX, y: event.clientY, moved: false };
}

function onBoardPointerMove(event) {
  if (!pointerStart || !event.isPrimary) return;
  if (Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 7) {
    pointerStart.moved = true;
  }
}

function onBoardClick(event) {
  const gesture = pointerStart;
  pointerStart = null;
  if (!props.interactive || props.disabled || (gesture && gesture.moved)) return;
  const rect = renderer?.domElement.getBoundingClientRect();
  if (!rect?.width || !rect?.height || !camera || !boardGroup) return;
  pointerNdc.set(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1,
  );
  raycaster.setFromCamera(pointerNdc, camera);
  boardGroup.updateMatrixWorld(true);
  const worldPoint = raycaster.ray.intersectPlane(boardPlane, hitPoint);
  if (!worldPoint) return;
  const local = boardGroup.worldToLocal(worldPoint.clone());
  const file = Math.floor(local.x + 4);
  const row = Math.floor(local.z + 4);
  if (file < 0 || file > 7 || row < 0 || row > 7) return;
  emit("square-click", `${FILES[file]}${8 - row}`);
}

/* ---------- procedural textures ---------- */
function marble(light, dark, vein) {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const x = c.getContext("2d");
  const g = x.createLinearGradient(0, 0, 256, 256);
  g.addColorStop(0, light);
  g.addColorStop(1, dark);
  x.fillStyle = g;
  x.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 9; i++) {
    let px = Math.random() * 256, py = Math.random() * 256;
    x.beginPath();
    x.moveTo(px, py);
    for (let j = 0; j < 5; j++) {
      const nx = px + (Math.random() - 0.3) * 90;
      const ny = py + (Math.random() - 0.3) * 90;
      x.quadraticCurveTo(px + (Math.random() - 0.5) * 60, py + (Math.random() - 0.5) * 60, nx, ny);
      px = nx; py = ny;
    }
    x.strokeStyle = vein;
    x.globalAlpha = 0.08 + Math.random() * 0.3;
    x.lineWidth = 0.6 + Math.random() * 2.2;
    x.stroke();
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

function labelTexture(text) {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const x = c.getContext("2d");
  x.font = "bold 84px Georgia, serif";
  x.textAlign = "center";
  x.textBaseline = "middle";
  x.fillStyle = "#f0c46a";
  x.shadowColor = "rgba(0,0,0,.8)";
  x.shadowBlur = 6;
  x.fillText(text, 64, 70);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function glowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const x = c.getContext("2d");
  const g = x.createRadialGradient(64, 64, 8, 64, 64, 80);
  g.addColorStop(0, "rgba(255,176,46,.18)");
  g.addColorStop(1, "rgba(255,150,30,.75)");
  x.fillStyle = g;
  x.fillRect(0, 0, 128, 128);
  x.strokeStyle = "#ffd26a";
  x.lineWidth = 9;
  x.strokeRect(4, 4, 120, 120);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/* ---------- piece geometry ---------- */
const cache = {};
const geo = (k, f) => (cache[k] ??= f());
const lathe = (pts) =>
  new THREE.LatheGeometry(pts.map(([r, y]) => new THREE.Vector2(r, y)), 56);
const BASE = [[0, 0], [.37, 0], [.39, .03], [.39, .08], [.33, .13], [.28, .17], [.3, .2], [.24, .24]];

function knightHead() {
  const p = [[-.22, .2], [.22, .2], [.16, .42], [.34, .6], [.36, .7], [.22, .78],
    [.14, .98], [.04, .84], [-.06, .96], [-.12, .8], [-.3, .45]];
  const s = new THREE.Shape();
  s.moveTo(...p[0]);
  p.slice(1).forEach((q) => s.lineTo(...q));
  const g = new THREE.ExtrudeGeometry(s, {
    depth: 0.18, bevelEnabled: true, bevelSize: 0.045, bevelThickness: 0.05, bevelSegments: 5,
  });
  g.translate(0, 0, -0.09);
  g.computeVertexNormals();
  return g;
}

function build(type, mat) {
  const g = new THREE.Group();
  const add = (geom, x = 0, y = 0, z = 0) => {
    const m = new THREE.Mesh(geom, mat);
    m.position.set(x, y, z);
    m.castShadow = m.receiveShadow = true;
    g.add(m);
    return m;
  };
  const sph = (r, sy = 1) => geo(`s${r}_${sy}`, () => {
    const s = new THREE.SphereGeometry(r, 32, 24);
    s.scale(1, sy, 1);
    return s;
  });
  const box = (w, h, d) => geo(`b${w}_${h}_${d}`, () => new THREE.BoxGeometry(w, h, d));
  const body = (pts) => add(geo(type, () => lathe([...BASE, ...pts])));

  switch (type) {
    case "p":
      body([[.15, .34], [.11, .46], [.2, .5], [.2, .53], [.11, .56], [0, .56]]);
      add(sph(0.17), 0, 0.7, 0);
      break;
    case "r":
      body([[.22, .34], [.19, .62], [.27, .7], [.27, .8], [0, .8]]);
      for (let i = 0; i < 8; i++) {
        const a = (i / 8) * Math.PI * 2;
        add(box(0.1, 0.14, 0.1), Math.cos(a) * 0.2, 0.87, Math.sin(a) * 0.2).rotation.y = -a;
      }
      break;
    case "n":
      body([[0, .24]]);
      add(geo("knight", knightHead));
      break;
    case "b":
      body([[.2, .34], [.11, .5], [.2, .56], [.2, .6], [.1, .64], [0, .64]]);
      add(sph(0.16, 1.45), 0, 0.84, 0);
      add(sph(0.055), 0, 1.08, 0);
      break;
    case "q":
      body([[.22, .34], [.13, .62], [.25, .8], [.22, .86], [0, .86]]);
      for (let i = 0; i < 9; i++) {
        const a = (i / 9) * Math.PI * 2;
        add(sph(0.045), Math.cos(a) * 0.19, 0.9, Math.sin(a) * 0.19);
      }
      add(sph(0.075), 0, 1.0, 0);
      break;
    case "k":
      body([[.23, .34], [.14, .7], [.26, .86], [.2, .92], [0, .92]]);
      add(box(0.09, 0.34, 0.09), 0, 1.1, 0);
      add(box(0.24, 0.09, 0.09), 0, 1.15, 0);
      break;
  }
  return g;
}

/* ---------- scene ---------- */
function init() {
  const el = host.value;
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  el.appendChild(renderer.domElement);
  renderer.domElement.addEventListener("pointerdown", onBoardPointerDown);
  renderer.domElement.addEventListener("pointermove", onBoardPointerMove);
  renderer.domElement.addEventListener("click", onBoardClick);

  scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.75;

  camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100);
  camera.position.set(0, 10.5, 11.5);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0.2, 0);
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.minDistance = 9;
  controls.maxDistance = 24;
  controls.minPolarAngle = 0.2;
  controls.maxPolarAngle = 1.38;

  const key = new THREE.DirectionalLight(0xfff1dc, 2.4);
  key.position.set(6, 12, 7);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -7, right: 7, top: 7, bottom: -7, near: 1, far: 40 });
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.02;
  const teal = new THREE.DirectionalLight(0x22e6c8, 1.3);
  teal.position.set(-8, 5, -7);
  const amber = new THREE.DirectionalLight(0xffa83a, 0.9);
  amber.position.set(8, 4, -6);
  scene.add(key, teal, amber);

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(60, 60),
    new THREE.ShadowMaterial({ opacity: 0.5 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.65;
  ground.receiveShadow = true;
  scene.add(ground);

  boardGroup = new THREE.Group();
  piecesGroup = new THREE.Group();
  fxGroup = new THREE.Group();
  boardGroup.add(piecesGroup, fxGroup);
  scene.add(boardGroup);

  /* squares */
  const lightMats = [0, 1, 2].map(() => new THREE.MeshPhysicalMaterial({
    map: marble("#f1f8ef", "#bcd5c6", "#4f8a80"), roughness: 0.2, clearcoat: 1, clearcoatRoughness: 0.08,
  }));
  const darkMats = [0, 1, 2].map(() => new THREE.MeshPhysicalMaterial({
    map: marble("#0e5a58", "#031d1e", "#5df0d4"), roughness: 0.12, clearcoat: 1, clearcoatRoughness: 0.05,
  }));
  const sqGeo = new THREE.BoxGeometry(1, 0.3, 1);
  for (let r = 0; r < 8; r++) {
    for (let c = 0; c < 8; c++) {
      const dark = (r + c) % 2 === 1;
      const pool = dark ? darkMats : lightMats;
      const m = new THREE.Mesh(sqGeo, pool[(Math.random() * 3) | 0]);
      m.position.set(c - 3.5, -0.15, r - 3.5);
      m.receiveShadow = true;
      boardGroup.add(m);
    }
  }

  /* frame, base and inlay */
  const bronze = new THREE.MeshStandardMaterial({ color: 0x8a5424, metalness: 0.9, roughness: 0.32 });
  const brass = new THREE.MeshStandardMaterial({ color: 0xe8b658, metalness: 1, roughness: 0.22 });
  const part = (mat, w, h, d, x, y, z, shadow = true) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
    m.position.set(x, y, z);
    m.castShadow = shadow;
    m.receiveShadow = true;
    boardGroup.add(m);
  };
  part(bronze, 9.2, 0.3, 0.6, 0, 0, 4.3);
  part(bronze, 9.2, 0.3, 0.6, 0, 0, -4.3);
  part(bronze, 0.6, 0.3, 8, 4.3, 0, 0);
  part(bronze, 0.6, 0.3, 8, -4.3, 0, 0);
  part(bronze, 9.8, 0.5, 9.8, 0, -0.4, 0);
  part(brass, 8.34, 0.03, 0.05, 0, 0.15, 4.12, false);
  part(brass, 8.34, 0.03, 0.05, 0, 0.15, -4.12, false);
  part(brass, 0.05, 0.03, 8.34, 4.12, 0.15, 0, false);
  part(brass, 0.05, 0.03, 8.34, -4.12, 0.15, 0, false);

  /* coordinates */
  const plane = new THREE.PlaneGeometry(0.38, 0.38);
  const addLabel = (text, x, z) => {
    const m = new THREE.Mesh(plane, new THREE.MeshBasicMaterial({ map: labelTexture(text), transparent: true }));
    m.rotation.x = -Math.PI / 2;
    m.position.set(x, 0.158, z);
    boardGroup.add(m);
  };
  for (let i = 0; i < 8; i++) {
    addLabel(FILES[i], i - 3.5, 4.38);
    addLabel(String(8 - i), -4.38, i - 3.5);
  }

  /* pieces */
  const matWhite = new THREE.MeshPhysicalMaterial({
    color: 0xf5e8c6, roughness: 0.22, metalness: 0.1, clearcoat: 1, clearcoatRoughness: 0.08,
    emissive: 0x2a2010, envMapIntensity: 1.2,
  });
  const matBlack = new THREE.MeshPhysicalMaterial({
    color: 0x0b2c2d, roughness: 0.14, metalness: 0.65, clearcoat: 1, clearcoatRoughness: 0.05,
    emissive: 0x022b27, envMapIntensity: 1.5,
  });
  const glowTex = glowTexture();
  const glowGeo = new THREE.PlaneGeometry(0.96, 0.96);

  rebuild = () => {
    piecesGroup.clear();
    fxGroup.children.forEach((o) => o.geometry && !o.userData.shared && o.geometry.dispose());
    fxGroup.clear();
    boardGroup.rotation.y = props.flipped ? Math.PI : 0;

    props.fen.split(" ")[0].split("/").forEach((row, r) => {
      let c = 0;
      for (const ch of row) {
        if (/\d/.test(ch)) { c += Number(ch); continue; }
        const white = ch === ch.toUpperCase();
        const p = build(ch.toLowerCase(), white ? matWhite : matBlack);
        p.position.set(c - 3.5, 0, r - 3.5);
        if (ch.toLowerCase() === "n") p.rotation.y = white ? Math.PI / 2 : -Math.PI / 2;
        piecesGroup.add(p);
        c++;
      }
    });

    props.highlights.forEach((name) => {
      const { x, z } = sqPos(name);
      const m = new THREE.Mesh(glowGeo, new THREE.MeshBasicMaterial({
        map: glowTex, transparent: true, depthWrite: false, toneMapped: false,
      }));
      m.userData.shared = true;
      m.userData.pulse = true;
      m.rotation.x = -Math.PI / 2;
      m.position.set(x, 0.012, z);
      fxGroup.add(m);
    });

    if (/^[a-h][1-8]$/.test(props.checkSquare)) {
      const { x, z } = sqPos(props.checkSquare);
      const check = new THREE.Mesh(
        new THREE.PlaneGeometry(0.96, 0.96),
        new THREE.MeshBasicMaterial({
          color: 0xe34242,
          transparent: true,
          opacity: 0.64,
          depthWrite: false,
          side: THREE.DoubleSide,
        }),
      );
      check.rotation.x = -Math.PI / 2;
      check.position.set(x, 0.025, z);
      fxGroup.add(check);
    }

    props.arrows.forEach(([from, to]) => {
      const a = sqPos(from), b = sqPos(to);
      const dx = b.x - a.x, dz = b.z - a.z;
      const len = Math.hypot(dx, dz) || 1;
      const s = new THREE.Shape();
      const L = len - 0.25, hd = 0.4, sw = 0.09, hw = 0.26;
      s.moveTo(0.2, -sw); s.lineTo(L - hd, -sw); s.lineTo(L - hd, -hw); s.lineTo(L, 0);
      s.lineTo(L - hd, hw); s.lineTo(L - hd, sw); s.lineTo(0.2, sw); s.closePath();
      const m = new THREE.Mesh(
        new THREE.ExtrudeGeometry(s, { depth: 0.04, bevelEnabled: true, bevelSize: 0.02, bevelThickness: 0.02, bevelSegments: 2 }),
        new THREE.MeshStandardMaterial({
          color: 0xffb02e, emissive: 0xff7a00, emissiveIntensity: 0.8,
          roughness: 0.3, transparent: true, opacity: 0.93,
        })
      );
      m.rotation.x = -Math.PI / 2;
      const holder = new THREE.Group();
      holder.add(m);
      holder.position.set(a.x, 0.03, a.z);
      holder.rotation.y = Math.atan2(-dz, dx);
      holder.geometry = m.geometry;
      fxGroup.add(holder);
    });
  };

  const resize = () => {
    const w = el.clientWidth, h = el.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  ro = new ResizeObserver(resize);
  ro.observe(el);
  resize();
  rebuild();

  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const tick = (t) => {
    raf = requestAnimationFrame(tick);
    controls.update();
    if (!reduce) {
      const o = 0.7 + 0.3 * Math.sin(t / 420);
      fxGroup.children.forEach((m) => m.userData.pulse && (m.material.opacity = o));
    }
    renderer.render(scene, camera);
  };
  raf = requestAnimationFrame(tick);
}

onMounted(init);
watch(() => [props.fen, props.highlights, props.arrows, props.flipped, props.checkSquare], () => rebuild(), { deep: true });

onBeforeUnmount(() => {
  cancelAnimationFrame(raf);
  ro?.disconnect();
  controls?.dispose();
  scene?.traverse((o) => {
    o.geometry?.dispose();
    [].concat(o.material || []).forEach((m) => { m.map?.dispose(); m.dispose(); });
  });
  renderer?.dispose();
  renderer?.domElement.removeEventListener("pointerdown", onBoardPointerDown);
  renderer?.domElement.removeEventListener("pointermove", onBoardPointerMove);
  renderer?.domElement.removeEventListener("click", onBoardClick);
  renderer?.domElement.remove();
});
</script>

<template>
  <div
    ref="host"
    class="board3d"
    role="img"
    aria-label="3D chess board. Drag to rotate, scroll to zoom."
  />
</template>

<style scoped>
.board3d {
  width: 100%;
  max-width: 760px;
  aspect-ratio: 10 / 9;
  cursor: grab;
  touch-action: none;
}
.board3d:active { cursor: grabbing; }
.board3d :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
