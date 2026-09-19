/* Tests del motor de puntuación — corren con `node --test tests/`
   y forman parte del CI. El motor es puro y determinista: si un cambio
   rompe la calibración del puntaje, esto lo grita antes del deploy. */
import test from "node:test";
import assert from "node:assert/strict";
import { SHAPES, scoreStroke, verifyRun, MAX_SCORE, resample } from "../web/scoring.js";

/** Trazo sintético a escala de juego: la plantilla de la figura
    re-muestreada a 64 puntos y llevada a píxeles (~628 px de largo). */
const trazo = s => resample(s.pts, 64, s.closed)
  .map(p => ({ x: 320 + p.x * 200, y: 240 + p.y * 200 }));

test("la plantilla perfecta de cada figura puntúa 100 en su propia figura", () => {
  for (const s of SHAPES) {
    const r = scoreStroke(trazo(s), s);
    assert.ok(r, `no se pudo puntuar ${s.name}`);
    assert.equal(r.score, 100, `${s.name} debía dar 100`);
  }
});

test("un círculo no puntúa alto como triángulo (el término de curvatura funciona)", () => {
  const r = scoreStroke(trazo(SHAPES[0]), SHAPES[1]);   // círculo vs triángulo
  // Sin el término de curvatura daba 77; con él queda en ~51. El test
  // fija el comportamiento: si alguien desactiva `turning`, grita.
  assert.ok(r.score < 60, `dio ${r.score}, esperábamos < 60`);
});

test("los trazos demasiado cortos no se puntúan", () => {
  // 64 puntos pero con perímetro mínimo: no llega a la longitud mínima.
  const corto = resample(SHAPES[0].pts, 64, true)
    .map(p => ({ x: 320 + p.x, y: 240 + p.y }));
  assert.equal(scoreStroke(corto, SHAPES[0]), null);
});

test("menos de 18 puntos no se puntúan", () => {
  const pocos = trazo(SHAPES[0]).slice(0, 10);
  assert.equal(scoreStroke(pocos, SHAPES[0]), null);
});

test("verifyRun recalcula una partida perfecta como 5x100", () => {
  const run = SHAPES.map(s => ({
    shapeId: s.id,
    points: scoreStroke(trazo(s), s).normalized.map(p => [p.x, p.y]),
  }));
  assert.equal(verifyRun(run), MAX_SCORE);
});

test("verifyRun rechaza partidas manipuladas", () => {
  const s = SHAPES[0];
  const puntos = scoreStroke(trazo(s), s).normalized.map(p => [p.x, p.y]);
  // figura en orden equivocado
  assert.equal(verifyRun(SHAPES.map((x, i) => ({
    shapeId: i === 0 ? "flor" : x.id, points: puntos,
  }))), null);
  // partida incompleta
  assert.equal(verifyRun([{ shapeId: s.id, points: puntos }]), null);
  // NaN injection
  assert.equal(verifyRun(SHAPES.map(x => ({
    shapeId: x.id, points: [[NaN, NaN], ...Array(63).fill([0, 0])],
  }))), null);
});
