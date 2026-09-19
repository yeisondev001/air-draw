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

export const SHAPES = [
  { id: "circulo",   name: "Círculo",   emoji: "⭕",
    pts: gen(t => ({ x: Math.cos(t), y: Math.sin(t) }), 96, 0, TAU), closed: true },
  { id: "triangulo", name: "Triángulo", emoji: "🔺", pts: poly(3, -Math.PI / 2), closed: true },
  { id: "estrella",  name: "Estrella",  emoji: "⭐", pts: star5(), closed: true },
  { id: "corazon",   name: "Corazón",   emoji: "❤️",
    pts: gen(t => ({
      x: 16 * Math.pow(Math.sin(t), 3),
      y: -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t))
    }), 140, 0, TAU), closed: true },
  // Curva rosa: r = cos(2.5·θ) sobre [0, 4π] da exactamente 5 pétalos.
  { id: "flor",      name: "Flor",      emoji: "🌸",
    pts: gen(t => { const r = Math.cos(2.5 * t); return { x: r * Math.cos(t), y: r * Math.sin(t) }; },
             220, 0, 4 * Math.PI), closed: true },
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

/** Distancia media probando todos los inicios (figura cerrada) y ambos sentidos. */
export function meanDistance(A, B, closed) {
  const n = A.length;
  const shifts = closed ? n : 1;
  let best = Infinity;
  for (let dir = 0; dir < 2; dir++) {
    for (let s = 0; s < shifts; s++) {
      let sum = 0;
      for (let i = 0; i < n; i++) {
        const j = dir === 0 ? (i + s) % n : (((s - i) % n) + n) % n;
        sum += (A[i].x - B[j].x) ** 2 + (A[i].y - B[j].y) ** 2;
      }
      if (sum < best) best = sum;
    }
  }
  return Math.sqrt(best / n);
}

const TEMPLATES = new Map(
  SHAPES.map(s => [s.id, normalize(resample(s.pts, N, s.closed))])
);

/** Puntaje 0-100 de un trazo YA normalizado (N puntos) contra una figura. */
export function scoreNormalized(A, shapeId) {
  const B = TEMPLATES.get(shapeId);
  if (!B || !Array.isArray(A) || A.length !== N) return null;
  const d = meanDistance(A, B, true);
  return Math.round(100 * clamp(1 - (d - 0.12) / 0.62, 0, 1));
}

/** Puntaje de un trazo crudo en píxeles. Devuelve {score, normalized} o null. */
export function scoreStroke(stroke, shape) {
  if (stroke.length < 18) return null;
  let len = 0;
  for (let i = 1; i < stroke.length; i++) len += dist(stroke[i - 1], stroke[i]);
  if (len < 220) return null;                    // trazo demasiado corto
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
