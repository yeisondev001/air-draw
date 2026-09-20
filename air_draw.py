"""
Air Draw — dibuja figuras en el aire con el dedo.

Visión artificial con MediaPipe Hands: detecta 21 puntos de la mano, sigue la
punta del índice, suaviza el trazo con un One-Euro Filter y lo compara contra
una plantilla geométrica para darte un puntaje de 0 a 100.

No hay ningún modelo entrenado para puntuar: la flor es una curva rosa
(r = cos(2·θ)) y la comparación es geometría pura (algoritmo tipo $1 Recognizer,
más un término de curvatura que distingue esquinas de curvas suaves).

Uso:  python air_draw.py
Gestos:  ☝️ índice = dibujar · ✌️ índice+medio = cerrar trazo · 🖐️ palma = reintentar
Teclas:  Q = salir · R = reiniciar partida
"""

import math
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Callable

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

MODEL = Path(__file__).with_name("hand_landmarker.task")
MODEL_URL = ("https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
             "hand_landmarker/float16/1/hand_landmarker.task")


def ensure_model() -> str:
    """Descarga el modelo de MediaPipe la primera vez (7.5 MB)."""
    if not MODEL.exists():
        print(f"Descargando modelo ({MODEL_URL.rsplit('/', 1)[-1]}, ~7.5 MB)...")
        urllib.request.urlretrieve(MODEL_URL, MODEL)
        print("Listo.")
    return str(MODEL)
W, H = 640, 480   # 960x720 demoraba el landmarker: 10 fps en el equipo de prueba
TAU = math.tau

# Paleta BGR (OpenCV usa BGR, no RGB)
FG     = (248, 239, 233)
MUTED  = (190, 163, 142)
GREEN  = (128, 222,  74)
BLUE   = (250, 165,  96)
GOLD   = ( 36, 191, 251)
RED    = (113, 113, 248)
PANEL  = ( 20,  14,   9)


# ============================ PLANTILLAS DE FIGURAS ============================
# Todas se dibujan de UN SOLO TRAZO, sin levantar el dedo.

def gen(fn: Callable[[float], tuple], n: int, t0: float, t1: float) -> np.ndarray:
    return np.array([fn(t0 + (t1 - t0) * i / (n - 1)) for i in range(n)], dtype=np.float64)


def poly(sides: int, phase: float) -> np.ndarray:
    return np.array([(math.cos(phase + TAU * i / sides),
                      math.sin(phase + TAU * i / sides)) for i in range(sides)])


def star5() -> np.ndarray:
    v = [(math.cos(-math.pi / 2 + TAU * i / 5),
          math.sin(-math.pi / 2 + TAU * i / 5)) for i in range(5)]
    return np.array([v[i] for i in (0, 2, 4, 1, 3)])


def spiral(t: float) -> tuple:
    r = t / (3 * math.pi)
    return (r * math.cos(t), r * math.sin(t))


def flower(t: float) -> tuple:
    r = math.cos(2 * t)            # curva rosa: 4 pétalos en una sola vuelta
    return (r * math.cos(t), r * math.sin(t))


@dataclass
class Shape:
    name: str
    pts: np.ndarray
    closed: bool = True


# De fácil a difícil. Criterio: que se pueda dibujar de un trazo, en el aire y
# sin perder la cuenta. La estrella (5 líneas cruzadas) y la flor de 5 pétalos
# (dos vueltas completas) quedaron afuera: se dibujan con mouse, no con el dedo.
SHAPES = [
    Shape("Circulo",   gen(lambda t: (math.cos(t), math.sin(t)), 96, 0, TAU)),
    Shape("Triangulo", poly(3, -math.pi / 2)),
    Shape("Cuadrado",  poly(4, -math.pi / 4)),
    Shape("Espiral",   gen(spiral, 160, 0.6, 3 * math.pi), closed=False),
    Shape("Flor",      gen(flower, 180, 0, TAU)),
]

N = 64   # puntos tras remuestrear
K = 4    # ventana para medir el giro (con K=1 domina el temblor de la mano)
TURN_W = 0.55      # cuánto pesa la curvatura frente a la posición
D_PERFECT = 0.20   # distancia que vale 100 puntos
D_ZERO = 1.10      # distancia que vale 0


# ========================== COMPARACIÓN DE TRAZOS ==========================
# Remuestrear -> normalizar -> comparar. Determinista, sin machine learning.

def resample(pts: np.ndarray, n: int, closed: bool) -> Optional[np.ndarray]:
    p = np.vstack([pts, pts[0]]) if closed else np.asarray(pts, dtype=np.float64)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    total = seg.sum()
    if total <= 0:
        return None
    # Interpolación lineal a lo largo del camino, a intervalos iguales.
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    targets = np.linspace(0.0, total, n)
    x = np.interp(targets, cum, p[:, 0])
    y = np.interp(targets, cum, p[:, 1])
    return np.stack([x, y], axis=1)


def normalize(pts: np.ndarray) -> np.ndarray:
    c = pts.mean(axis=0)
    d = pts - c
    scale = math.sqrt((d ** 2).sum() / len(d)) or 1.0
    return d / scale


def turning(pts: np.ndarray, closed: bool = True) -> np.ndarray:
    """Ángulo de giro en cada punto: la 'firma de esquinas' de la figura.

    Un círculo da valores chicos y uniformes; un triángulo, tres picos grandes.
    Esto es lo que impide que un círculo puntúe alto como triángulo.
    """
    n = len(pts)
    idx = np.arange(n)
    a, b, c = pts[(idx - K) % n], pts, pts[(idx + K) % n]
    d = np.arctan2(c[:, 1] - b[:, 1], c[:, 0] - b[:, 0]) - \
        np.arctan2(b[:, 1] - a[:, 1], b[:, 0] - a[:, 0])
    d = (d + math.pi) % TAU - math.pi          # normalizar a [-π, π)
    if not closed:
        d[:K] = 0.0
        d[-K:] = 0.0
    return d


def mean_distance(a: np.ndarray, b: np.ndarray, closed: bool,
                  ta: np.ndarray = None, tb: np.ndarray = None) -> float:
    """Distancia combinada (posición + curvatura).

    Prueba todos los puntos de inicio si la figura es cerrada, y ambos sentidos.
    """
    n = len(a)
    ta = turning(a, closed) if ta is None else ta
    tb = turning(b, closed) if tb is None else tb
    shifts = range(n) if closed else range(1)
    best = math.inf
    idx = np.arange(n)
    for reverse in (False, True):
        for s in shifts:
            j = (s - idx) % n if reverse else (idx + s) % n
            # Al invertir el sentido, los ángulos de giro cambian de signo.
            tbj = -tb[j] if reverse else tb[j]
            d = (math.sqrt(float(((a - b[j]) ** 2).sum()) / n)
                 + TURN_W * math.sqrt(float(((ta - tbj) ** 2).sum()) / n))
            if d < best:
                best = d
    return best


# Plantillas ya remuestreadas y normalizadas (se calculan una sola vez).
TEMPLATES = {}
for _s in SHAPES:
    _p = normalize(resample(_s.pts, N, _s.closed))
    TEMPLATES[_s.name] = (_p, turning(_p, _s.closed))


def score_stroke(stroke: List[tuple], shape: Shape) -> Optional[int]:
    if len(stroke) < 18:
        return None
    pts = np.array(stroke, dtype=np.float64)
    length = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    if length < 0.24 * W:                  # trazo demasiado corto para contar
        return None
    a = resample(pts, N, shape.closed)
    if a is None:
        return None
    A = normalize(a)
    B, tb = TEMPLATES[shape.name]
    d = mean_distance(A, B, shape.closed, turning(A, shape.closed), tb)
    return int(round(100 * max(0.0, min(1.0, 1 - (d - D_PERFECT) / (D_ZERO - D_PERFECT)))))


# ============================== ONE-EURO FILTER ==============================
# Sin esto el dedo tiembla y el trazo parece un electrocardiograma.

class LowPass:
    def __init__(self):
        self.s = None

    def filter(self, x: float, a: float) -> float:
        self.s = x if self.s is None else a * x + (1 - a) * self.s
        return self.s

    def reset(self):
        self.s = None


class OneEuro:
    def __init__(self, min_cutoff=1.2, beta=0.02, d_cutoff=1.0):
        self.min_cutoff, self.beta, self.d_cutoff = min_cutoff, beta, d_cutoff
        self.xf, self.df = LowPass(), LowPass()
        self.prev = None
        self.t_prev = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1 / (TAU * cutoff)
        return 1 / (1 + tau / dt)

    def filter(self, x: float, t: float) -> float:
        if self.t_prev is None:
            self.t_prev, self.prev = t, x
            self.xf.filter(x, 1.0)
            return x
        dt = max(t - self.t_prev, 1e-3)
        self.t_prev = t
        d_raw = (x - self.prev) / dt
        self.prev = x
        d_hat = self.df.filter(d_raw, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(d_hat)
        return self.xf.filter(x, self._alpha(cutoff, dt))

    def reset(self):
        self.xf.reset()
        self.df.reset()
        self.prev = None
        self.t_prev = None


# ================================ ESTADO ================================
@dataclass
class Game:
    round: int = 0
    total: int = 0
    stroke: List[tuple] = field(default_factory=list)
    last_stroke: List[tuple] = field(default_factory=list)
    mode: str = "idle"
    pending: str = "idle"
    hold: int = 0
    flash: float = 0.0
    flash_score: int = 0
    flash_hold: int = 0   # el puntaje queda fijo un instante antes de desvanecerse
    lock_until: float = 0.0
    done: bool = False
    thumb_hold: int = 0
    last_draw_t: float = 0.0    # cierre automatico: dedo quieto = trazo listo
AUTO_MS = 1.0   # pausa (en segundos) que activa el cierre automatico


BONES = [(0, 5), (5, 8), (0, 9), (9, 12), (0, 13), (13, 16), (0, 17), (17, 20), (0, 1), (1, 4)]


def finger_up(lm, tip: int, pip: int) -> bool:
    """Dedo extendido: distancia de la punta a la muñeca mayor que la del PIP.

    La versión vieja (tip.y < pip.y) falla con la mano inclinada: este test
    es invariante a la rotación, así que no confunde una mano de canto con
    los dedos abiertos.
    """
    dx, dy = lm[tip].x - lm[0].x, lm[tip].y - lm[0].y
    px, py = lm[pip].x - lm[0].x, lm[pip].y - lm[0].y
    return dx * dx + dy * dy > (px * px + py * py) * 1.25


def thumbs_up(lm) -> bool:
    """👍: los otros cuatro dedos doblados y el pulgar sobre la muñeca.

    Es la pose más robusta para distinguir de las del dibujo: nada en
    común con ☝️ ni ✌️, y no requiere precisión entre dedos.
    """
    otros = (finger_up(lm, 8, 6), finger_up(lm, 12, 10),
             finger_up(lm, 16, 14), finger_up(lm, 20, 18))
    return not any(otros) and lm[4].y < lm[0].y - 0.06


def draw_ghost(img, shape: Shape):
    """Figura objetivo punteada, como guía."""
    p = normalize(resample(shape.pts, 200, shape.closed))
    r = H * 0.26
    pts = np.stack([W / 2 + p[:, 0] * r, H / 2 + p[:, 1] * r], axis=1).astype(np.int32)
    for i in range(0, len(pts) - 1, 2):           # saltear puntos = línea punteada
        cv2.line(img, tuple(pts[i]), tuple(pts[i + 1]), (110, 80, 55), 3, cv2.LINE_AA)


def draw_path(img, pts, color, thickness):
    if len(pts) < 2:
        return
    arr = np.array(pts, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(img, [arr], False, color, thickness, cv2.LINE_AA)


def text(img, s, org, scale, color, thick=2, center=False):
    font = cv2.FONT_HERSHEY_SIMPLEX
    if center:
        (tw, _), _ = cv2.getTextSize(s, font, scale, thick)
        org = (org[0] - tw // 2, org[1])
    cv2.putText(img, s, org, font, scale, color, thick, cv2.LINE_AA)


def main():
    # MSMF: el backend DSHOW limitaba la cámara a ~10 fps; MSMF da ~21.
    cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    if not cap.isOpened():
        raise SystemExit("No se pudo abrir la camara.")

    def make_landmarker(delegate):
        """GPU acelera el inferencia ~3x; si el driver no banca, cae a CPU."""
        return vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(
                    model_asset_path=ensure_model(), delegate=delegate),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                # Confianza mas baja que el default (0.5): el tracking
                # aguanta mejor la luz floja y los movimientos rapidos.
                min_hand_detection_confidence=0.35,
                min_hand_presence_confidence=0.35,
                min_tracking_confidence=0.35,
            ))

    try:
        landmarker = make_landmarker(mp_python.BaseOptions.Delegate.GPU)
    except Exception:
        landmarker = make_landmarker(mp_python.BaseOptions.Delegate.CPU)

    fx, fy = OneEuro(), OneEuro()
    g = Game()
    g.round = 1
    fps_t, fps_n, fps = time.time(), 0, 0.0
    t0 = time.time()

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame = cv2.flip(frame, 1)                       # espejo
        frame = cv2.resize(frame, (W, H))
        now = time.time()

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Tira negra arriba para que el detector no confunda la cara con la mano
        # cuando están cerca. El landmarker deja de "ver" esa region.
        rgb[:int(H * 0.38), :] = 0
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        res = landmarker.detect_for_video(mp_img, int((now - t0) * 1000))

        canvas = cv2.addWeighted(frame, 0.45, np.full_like(frame, PANEL, np.uint8), 0.55, 0)

        shape = SHAPES[g.round - 1] if not g.done else None
        if shape:
            draw_ghost(canvas, shape)

        tip = None
        if res.hand_landmarks:
            lm = res.hand_landmarks[0]
            # Muñeca en la zona enmascarada (top 38%) = landmarks basura,
            # no clasificamos para no inventar gestos en una mano recortada.
            if lm[0].y > 0.40:
                idx = finger_up(lm, 8, 6)
                mid = finger_up(lm, 12, 10)
                n_up = sum((idx, mid, finger_up(lm, 16, 14), finger_up(lm, 20, 18)))

                if n_up >= 4:
                    gesture = "clear"
                elif idx and mid:
                    gesture = "done"
                elif idx and not mid:
                    gesture = "draw"
                else:
                    gesture = "idle"
            else:
                gesture = "idle"

            # Histéresis: 3 frames seguidos antes de cambiar de gesto.
            if gesture == g.pending:
                g.hold += 1
                if g.hold >= 3:
                    g.mode = gesture
            else:
                g.pending, g.hold = gesture, 0

            tip = (fx.filter(lm[8].x * W, now), fy.filter(lm[8].y * H, now))

            for a, b in BONES:
                cv2.line(canvas,
                         (int(lm[a].x * W), int(lm[a].y * H)),
                         (int(lm[b].x * W), int(lm[b].y * H)),
                         (150, 110, 70), 2, cv2.LINE_AA)
        else:
            g.mode = "idle"
            fx.reset()
            fy.reset()

        # 👍 sostenido ~0.4 s en la pantalla final: jugar de nuevo sin teclado.
        if res.hand_landmarks and g.done and thumbs_up(res.hand_landmarks[0]):
            g.thumb_hold += 1
            if g.thumb_hold >= 12:
                g = Game(round=1)
                fx.reset()
                fy.reset()
        else:
            g.thumb_hold = 0

        # ---- lógica de la ronda ----
        if not g.done and now >= g.lock_until:
            if g.mode == "draw" and tip:
                if not g.stroke or math.dist(tip, g.stroke[-1]) > 2.5:
                    g.stroke.append(tip)
                    g.last_draw_t = now

                # Cierre automático: dedo quieto ~1 s con un trazo que ya
                # sirve, sin que nadie tenga que saber el gesto de ✌️.
                largo = sum(math.dist(a, b) for a, b in zip(g.stroke, g.stroke[1:]))
                if (len(g.stroke) >= 18 and largo >= 0.24 * W
                        and now - g.last_draw_t >= AUTO_MS):
                    g.mode = "done"
            elif g.mode == "done" and g.stroke:
                s = score_stroke(g.stroke, shape)
                if s is not None:
                    g.total += s
                    g.flash, g.flash_score, g.flash_hold = 1.0, s, 50   # ~1.6 s a tamaño completo
                    g.last_stroke, g.stroke = g.stroke, []
                    g.lock_until = now + 1.7
                    if g.round >= len(SHAPES):
                        g.done = True
                    else:
                        g.round += 1
                else:
                    g.stroke = []
            if g.mode == "clear":
                g.stroke, g.last_stroke = [], []

        draw_path(canvas, g.last_stroke, (180, 160, 148), 5)
        draw_path(canvas, g.stroke, GREEN, 6)

        if tip:
            col = GREEN if g.mode == "draw" else (RED if g.mode == "clear" else BLUE)
            cv2.circle(canvas, (int(tip[0]), int(tip[1])), 9 if g.mode == "draw" else 6, col, -1, cv2.LINE_AA)

            # Cuenta regresiva del cierre automático: arco dorado alrededor
            # de la punta, para que el cierre no sorprenda.
            if g.mode == "draw" and len(g.stroke) >= 18:
                pausa = min(1.0, (now - g.last_draw_t) / AUTO_MS)
                if pausa > 0.05:
                    cv2.ellipse(canvas, (int(tip[0]), int(tip[1])), (16, 16), 0,
                                -90, -90 + int(360 * pausa), GOLD, 3, cv2.LINE_AA)

        # ---- HUD ----
        if shape and g.flash <= 0:
            text(canvas, f"Dibuja: {shape.name}", (W // 2, 44), 0.95, FG, 2, center=True)
        text(canvas, f"Puntos {g.total}", (18, 40), 0.8, GREEN, 2)
        text(canvas, f"{min(g.round, len(SHAPES))}/{len(SHAPES)}", (18, 72), 0.65, MUTED, 2)
        text(canvas, f"{fps:.0f} fps", (W - 110, 40), 0.6, GOLD, 2)
        text(canvas, g.mode, (W - 110, 68), 0.55, MUTED, 1)

        if g.flash > 0:
            col = GREEN if g.flash_score >= 70 else (GOLD if g.flash_score >= 40 else RED)
            text(canvas, str(g.flash_score), (W // 2, H // 2 + 30), 3.4, col, 6, center=True)
            if g.flash_hold > 0:
                g.flash_hold -= 1
            else:
                g.flash -= 0.008

        if g.done and g.flash <= 0:
            cv2.rectangle(canvas, (0, H // 2 - 110), (W, H // 2 + 90), PANEL, -1)
            text(canvas, "FINAL", (W // 2, H // 2 - 50), 0.9, MUTED, 2, center=True)
            text(canvas, f"{g.total} / {len(SHAPES) * 100}", (W // 2, H // 2 + 20), 2.4, GREEN, 5, center=True)
            text(canvas, "Pulgar arriba o R = jugar de nuevo   Q = salir", (W // 2, H // 2 + 65), 0.6, MUTED, 1, center=True)

        fps_n += 1
        if fps_n >= 15:
            fps = fps_n / (now - fps_t)
            fps_t, fps_n = now, 0

        cv2.imshow("Air Draw", canvas)
        k = cv2.waitKey(1) & 0xFF
        if k in (ord("q"), 27):
            break
        if k == ord("r"):
            g = Game(round=1)
            fx.reset()
            fy.reset()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
