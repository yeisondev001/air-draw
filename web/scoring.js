/* ============================================================
   Motor de puntuación — compartido entre el navegador y el servidor.

   El mismo archivo se importa desde index.html (para mostrarte el puntaje
   al instante) y desde api/scores.js (para RECALCULARLO en el servidor
   antes de guardarlo). Así el ranking no depende de lo que diga el cliente.

   Sin machine learning: las figuras son curvas paramétricas y la
   comparación es geometría (enfoque tipo $1 Unistroke Recognizer).
   ============================================================ */

const TAU = Math.PI * 2;
export const N = 64;                       // puntos tras remuestrear

const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

/* ---------------------- Plantillas ---------------------- */
function gen(fn, n, t0, t1) {
  const o = [];
  for (let i = 0; i < n; i++) o.push(fn(t0 + (t1 - t0) * i / (n - 1)));
  return o;
}
function poly(sides, phase) {
  const o = [];
  for (let i = 0; i < sides; i++) {
    const a = phase + TAU * i / sides;
    o.push({ x: Math.cos(a), y: Math.sin(a) });
  }
  return o;
}
function star5() {
  const v = [];
  for (let i = 0; i < 5; i++) {
    const a = -Math.PI / 2 + TAU * i / 5;
    v.push({ x: Math.cos(a), y: Math.sin(a) });
  }
  return [0, 2, 4, 1, 3].map(i => v[i]);
}

/* Las figuras van de fácil a difícil. Criterio: que se puedan dibujar de un
   trazo, en el aire y sin perder la cuenta. La estrella (5 líneas que se
   cruzan) y la flor de 5 pétalos (dos vueltas completas) quedaron afuera:
   son dibujables con un mouse, no con el dedo en el aire. */
export const SHAPES = [
  { id: "circulo",   name: "Círculo",   emoji: "⭕",
    pts: gen(t => ({ x: Math.cos(t), y: Math.sin(t) }), 96, 0, TAU), closed: true },
  { id: "triangulo", name: "Triángulo", emoji: "🔺", pts: poly(3, -Math.PI / 2), closed: true },
  { id: "cuadrado",  name: "Cuadrado",  emoji: "⬜", pts: poly(4, -Math.PI / 4), closed: true },
  // Espiral: figura abierta, sale natural con el brazo.
  { id: "espiral",   name: "Espiral",   emoji: "🌀",
    pts: gen(t => { const r = t / (3 * Math.PI); return { x: r * Math.cos(t), y: r * Math.sin(t) }; },
             160, 0.6, 3 * Math.PI), closed: false },
  // Curva rosa con 4 pétalos: r = cos(2·θ). Una sola vuelta, no dos.
  { id: "flor",      name: "Flor",      emoji: "🌸",
    pts: gen(t => { const r = Math.cos(2 * t); return { x: r * Math.cos(t), y: r * Math.sin(t) }; },
             180, 0, TAU), closed: true },
];

export const MAX_SCORE = SHAPES.length * 100;

/* ---------------------- Algoritmo ---------------------- */

/** Reparte n puntos equidistantes a lo largo del trazo. */
export function resample(pts, n, closed) {
  const p = pts.map(q => ({ x: q.x, y: q.y }));
  if (closed) p.push({ x: p[0].x, y: p[0].y });
  let total = 0;
  for (let i = 1; i < p.length; i++) total += dist(p[i - 1], p[i]);
  if (!(total > 0)) return null;

  const I = total / (n - 1);
  const out = [{ x: p[0].x, y: p[0].y }];
  let D = 0;
  for (let i = 1; i < p.length && out.length < n; i++) {
    let a = p[i - 1];
    const b = p[i];
    let d = dist(a, b);
    while (D + d >= I && out.length < n) {
      const t = (I - D) / d;
      const q = { x: a.x + t * (b.x - a.x), y: a.y + t * (b.y - a.y) };
      out.push(q);
      a = q; d = dist(a, b); D = 0;
    }
    D += d;
  }
  const last = p[p.length - 1];
  while (out.length < n) out.push({ x: last.x, y: last.y });
  return out;
}

/** Centra en el origen y escala a desviación RMS = 1. */
export function normalize(pts) {
  const n = pts.length;
  const cx = pts.reduce((s, p) => s + p.x, 0) / n;
  const cy = pts.reduce((s, p) => s + p.y, 0) / n;
  let ss = 0;
  for (const p of pts) ss += (p.x - cx) ** 2 + (p.y - cy) ** 2;
  const s = Math.sqrt(ss / n) || 1;
  return pts.map(p => ({ x: (p.x - cx) / s, y: (p.y - cy) / s }));
}

/** Ángulo de giro en cada punto: la "firma de esquinas" de la figura.
    Un círculo da valores chicos y uniformes; un triángulo, tres picos grandes.
    Esto es lo que impide que un círculo puntúe alto como triángulo. */
const K = 4;   // ventana: mide el giro entre puntos separados, no adyacentes.
               // Con K=1 el temblor de la mano domina la señal; con K=4 se
               // suaviza el ruido y las esquinas reales se siguen viendo.
export function turning(pts, closed = true) {
  const n = pts.length, out = new Array(n);
  for (let i = 0; i < n; i++) {
    if (!closed && (i < K || i >= n - K)) { out[i] = 0; continue; }
    const a = pts[(i - K + n) % n], b = pts[i], c = pts[(i + K) % n];
    let d = Math.atan2(c.y - b.y, c.x - b.x) - Math.atan2(b.y - a.y, b.x - a.x);
    while (d > Math.PI) d -= TAU;
    while (d < -Math.PI) d += TAU;
    out[i] = d;
  }
  return out;
}

const TURN_W = 0.55;   // cuánto pesa la curvatura frente a la posición

// En el aire un trazo real siempre tiene un tramo flojo (el arranque, la
// esquina donde el filtro va más atrás). Promediar ese tramo con el resto
// hundía el puntaje a 0 aunque el resto fuera perfecto: la media recortada
// descarta el peor 12% de los errores de posición. El error de curvatura se
// promedia completo: ahi vive la firma de esquinas y no conviene perderla.
const TRIM = 0.12;

/** Distancia combinada (posición + curvatura), probando todos los puntos de
    inicio si la figura es cerrada, y ambos sentidos de giro. */
export function meanDistance(A, B, closed, TA, TB) {
  const n = A.length;
  const shifts = closed ? n : 1;
  TA = TA || turning(A);
  TB = TB || turning(B);
  let best = Infinity;
  for (let dir = 0; dir < 2; dir++) {
    for (let s = 0; s < shifts; s++) {
      const posE = new Array(n), turnE = new Array(n);
      for (let i = 0; i < n; i++) {
        const j = dir === 0 ? (i + s) % n : (((s - i) % n) + n) % n;
        posE[i] = (A[i].x - B[j].x) ** 2 + (A[i].y - B[j].y) ** 2;
        // Al invertir el sentido, los ángulos de giro cambian de signo.
        const tb = dir === 0 ? TB[j] : -TB[j];
        turnE[i] = (TA[i] - tb) ** 2;
      }
      posE.sort((a, b) => a - b);
      const k = Math.floor(n * TRIM);
      let pos = 0, turn = 0;
      for (let i = 0; i < n - k; i++) pos += posE[i];
      for (let i = 0; i < n; i++) turn += turnE[i];
      const d = Math.sqrt(pos / (n - k)) + TURN_W * Math.sqrt(turn / n);
      if (d < best) best = d;
    }
  }
  return best;
}

const TEMPLATES = new Map(SHAPES.map(s => {
  const pts = normalize(resample(s.pts, N, s.closed));
  return [s.id, { pts, turn: turning(pts, s.closed), closed: s.closed }];
}));

/* Curva de puntaje, calibrada contra trazos simulados con distorsión de mano
   (ruido, lag del filtro, inclinación, arco incompleto):
   d≈0.25 (pulso normal) → ~95 · d≈0.45 → ~78 · d≈0.70 → ~52 · d≈1.0 → ~26 */
const D_PERFECT = 0.25;
const D_ZERO = 1.15;

/** Puntaje 0-100 de un trazo YA normalizado (N puntos) contra una figura. */
export function scoreNormalized(A, shapeId) {
  const tpl = TEMPLATES.get(shapeId);
  if (!tpl || !Array.isArray(A) || A.length !== N) return null;
  const d = meanDistance(A, tpl.pts, tpl.closed, turning(A, tpl.closed), tpl.turn);
  return Math.round(100 * clamp(1 - (d - D_PERFECT) / (D_ZERO - D_PERFECT), 0, 1));
}

/** Puntaje de un trazo crudo en píxeles. Devuelve {score, normalized} o null. */
export function scoreStroke(stroke, shape) {
  if (stroke.length < 18) return null;
  let len = 0;
  for (let i = 1; i < stroke.length; i++) len += dist(stroke[i - 1], stroke[i]);
  if (len < 170) return null;                    // trazo demasiado corto
  const r = resample(stroke, N, shape.closed);
  if (!r) return null;
  const A = normalize(r);
  return { score: scoreNormalized(A, shape.id), normalized: A };
}

/** Recalcula el total desde los trazos enviados. Usado por el servidor. */
export function verifyRun(rounds) {
  if (!Array.isArray(rounds) || rounds.length !== SHAPES.length) return null;
  let total = 0;
  for (let i = 0; i < SHAPES.length; i++) {
    const r = rounds[i];
    if (!r || r.shapeId !== SHAPES[i].id) return null;
    if (!Array.isArray(r.points) || r.points.length !== N) return null;
    const A = r.points.map(p => ({ x: +p[0], y: +p[1] }));
    if (A.some(p => !Number.isFinite(p.x) || !Number.isFinite(p.y))) return null;
    const s = scoreNormalized(A, r.shapeId);
    if (s === null) return null;
    total += s;
  }
  return total;
}
