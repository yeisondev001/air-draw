<div align="center">

![Air Draw — dibuja en el aire con el dedo](docs/assets/banner.png)

# 🖐️ Air Draw

[![CI](https://github.com/yeisondev001/air-draw/actions/workflows/ci.yml/badge.svg)](https://github.com/yeisondev001/air-draw/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![JavaScript](https://img.shields.io/badge/javascript-ES%202022-F7DF1E?logo=javascript&logoColor=black)](https://developer.mozilla.org/es/docs/Web/JavaScript)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-4ade80.svg)](LICENSE)

**[🎮 Jugar en el navegador](https://air-draw-zeta.vercel.app)**

</div>

---

Un mini juego de **visión por computadora**: te muestra una figura y la dibujas **en el aire con el dedo**. El sistema detecta tu mano con la cámara, sigue la punta del índice y compara tu trazo contra la figura para darte un puntaje de **0 a 100**.

Hay **dos versiones del mismo juego**:

- 🖥️ **Escritorio** — `air_draw.py`, con **Python + OpenCV + MediaPipe**
- 🌐 **Navegador** — `web/`, con **JavaScript + Canvas + MediaPipe WASM** (la jugable en línea, arriba)

Lo interesante: **no hay ningún modelo entrenado para puntuar**. La flor es una curva matemática y la comparación es geometría pura.

Funciona desde el celular (Android e iOS) y desde la computadora. No hay que instalar nada, y **la cámara se procesa en tu dispositivo** — ningún frame se envía a ningún servidor.

![Demo](docs/assets/demo.gif)

---

## 🎯 Cómo se juega

Cinco figuras, siempre las mismas y en el mismo orden (para que los puntajes sean comparables):

⭕ Círculo → 🔺 Triángulo → ⬜ Cuadrado → 🌀 Espiral → 🌸 Flor

La figura objetivo aparece punteada en pantalla como guía. Dibujas encima, cierras el trazo, y te puntúa.

| Gesto | Acción |
|---|---|
| ☝️ **Solo índice** | Dibujar |
| **Dedo quieto 1 s** o ✌️ **índice + medio** | Cerrar el trazo y puntuar (el cierre es automático, con cuenta regresiva) |
| 🖐️ **Palma abierta** | Borrar y reintentar la figura |
| 👍 **Pulgar arriba** | Jugar de nuevo en la pantalla final |

**Teclas:** `R` reinicia la partida · `Q` sale.

---

## 🗺️ Flujo de la aplicación

```mermaid
flowchart TD
    A[👋 Abrir la app] --> B{¿Dónde?}
    B -->|Navegador| C[Escribir nick · entrar]
    B -->|Escritorio| C
    C --> D[Cámara activa · 21 landmarks por frame]
    D --> E{Clasificador de gesto}
    E -->|☝️ solo índice| F[✏️ Dibujar · punta filtrada]
    E -->|🖐️ palma abierta| G[🧹 Borrar trazo]
    E -->|✌️ índice + medio<br/>o dedo quieto 1 s| H[✔️ Cerrar trazo]
    F --> E
    G --> F
    H --> I[Puntuación: geometría contra la plantilla]
    I --> J[Puntaje 0-100 + sonido]
    J --> K{¿Quedan figuras?}
    K -->|sí · figura 2 a 5| E
    K -->|no| L[🏆 Pantalla final · ranking]
    L --> M[📸 Tarjeta con el puntaje para compartir]
    L -->|👍 pulgar arriba sostenido| E
```

---

## 🧠 Cómo funciona

```mermaid
flowchart TD
    A[cámara] --> B[MediaPipe Hands<br/>21 landmarks de la mano]
    B --> C[clasificador de gesto<br/>geometría entre landmarks · sin ML]
    C --> D[punta del índice]
    D --> E[One-Euro Filter<br/>trazo suave sin lag]
    E --> F[remuestrear → normalizar<br/>→ comparar con la plantilla]
    F --> G[puntaje 0-100]
```

El modelo entrega **21 landmarks por mano**: un punto `(x, y, z)` por cada articulación, en tiempo real.

![Los 21 landmarks de MediaPipe: numerados, con nombre y conexiones](docs/assets/hand-landmarks.png)

El juego vive de esos números: el cursor es la **punta del índice `8`**, los gestos son geometría entre puntos contra la **muñeca `0`** (invariante a la rotación), y MCP / PIP / DIP / TIP van del nudillo a la punta.

**Tres decisiones del diseño:**

| Decisión | Por qué |
|---|---|
| **One-Euro Filter** | los landmarks tiemblan: filtra fuerte al moverse lento, rápido al acelerar — suavidad sin lag |
| **Histéresis de gestos** | 3 frames seguidos antes de activar un gesto: sin esto la detección parpadea y corta el trazo |
| **Puntaje sin ML** | geometría tipo [$1 Unistroke](https://depts.washington.edu/acelab/proj/dollar/index.html): 64 puntos, normalización, distancia punto a punto + término de curvatura. Un círculo daba 77/100 como "triángulo"; con curvatura, ~51. Determinista, sin dataset |

---

## 🛠️ Tecnologías

Dos versiones del mismo juego, con el mismo motor de puntuación:

### 🖥️ Escritorio — `air_draw.py`

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-Hand_Landmarker-0068FF)
![OpenCV](https://img.shields.io/badge/OpenCV-captura_%26_render-5C3EE8?logo=opencv&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-comparaci%C3%B3n_vectorizada-013243?logo=numpy&logoColor=white)

- **MediaPipe Tasks (Vision)** — modelo Hand Landmarker: 21 puntos por mano
- **OpenCV** — captura de video y renderizado
- **NumPy** — remuestreo y comparación vectorizada

### 🌐 Web — `web/` · [▶ jugable en línea](https://air-draw-zeta.vercel.app)

![JavaScript](https://img.shields.io/badge/JavaScript-ES2022-F7DF1E?logo=javascript&logoColor=black)
![Canvas](https://img.shields.io/badge/Canvas-2D-222222)
![MediaPipe WASM](https://img.shields.io/badge/MediaPipe-Task_Vision_WASM-0068FF)
![Vercel](https://img.shields.io/badge/Vercel-hosting_%2B_serverless-000000?logo=vercel&logoColor=white)
![Upstash Redis](https://img.shields.io/badge/Upstash-Redis_ranking-00E291?logo=redis&logoColor=white)

- **JavaScript + Canvas** — sin framework: un solo HTML con el juego
- **MediaPipe Tasks Vision (WASM)** — el mismo modelo corriendo en el navegador
- **Vercel** — hosting + serverless function del ranking
- **Upstash Redis** — ranking global (el servidor recalcula el puntaje: editar el score en devtools no sirve)

**Motor compartido:** `web/scoring.js` es JavaScript puro, lo usa el cliente para mostrar el puntaje y el servidor para recalcularlo antes de guardar — y tiene tests (`node --test tests/`, corren en el CI).

![Node.js](https://img.shields.io/badge/Node.js-tests-en%20CI-339933?logo=nodedotjs&logoColor=white)

---

## 🏗️ Arquitectura

Dos versiones, el mismo motor de puntuación. La privacidad está en el diseño: la cámara vive en el cliente, **ningún frame de video viaja a ningún servidor** — lo único que viaja es el puntaje, y aun así el servidor lo recalcula para no fiarse del cliente.

```mermaid
flowchart LR
    subgraph WEB [🌐 Navegador — todo el vision corre local]
        CAM[Cámara] -->|frames| MP[MediaPipe Hand Landmarker<br/>WASM]
        MP -->|21 landmarks| JUEGO[index.html<br/>gestos · trazo · render Canvas]
        JUEGO --> MOTOR[scoring.js<br/>puntaje 0-100]
    end

    subgraph NUBE [☁️ Solo el ranking]
        MOTOR -->|POST /api/scores<br/>nick + puntos normalizados| API[api/scores.js<br/>Vercel serverless]
        API -->|re-puntúa con<br/>el mismo scoring.js| RDB[(Upstash Redis<br/>ranking global)]
        API -->|rank · récords| JUEGO
    end

    subgraph ESCRITORIO [🖥️ Python — sin servidores]
        CAM2[Cámara] --> CV[OpenCV · captura y render]
        CV --> MPY[MediaPipe Tasks Python]
        MPY --> PY[scoring NumPy · misma geometría]
    end
```

---

## 📦 Instalación

### Versión escritorio (Python)

**1. Entorno virtual**

```bash
python -m venv venv
```

Windows:
```bash
.\venv\Scripts\activate
```

macOS / Linux:
```bash
source venv/bin/activate
```

**2. Dependencias**

```bash
pip install -r requirements.txt
```

**3. Ejecutar**

```bash
python air_draw.py
```

El modelo de MediaPipe (~7.5 MB) se descarga solo la primera vez.

### Versión web (JavaScript)

No necesita instalación: [**juega en línea**](https://air-draw-zeta.vercel.app). Para correrla local:

```bash
cd web
python -m http.server 8000    # o cualquier servidor estático
```

y abrí `http://localhost:8000/index.html` (los módulos ES no cargan por `file://`). El ranking global necesita las credenciales de Vercel/Upstash; sin ellas, todo lo demás funciona.

---

## 💡 Notas

- Aléjate de la cámara lo suficiente para que quepa el brazo; los trazos muy pequeños no puntúan.
- Buena luz ayuda bastante a la detección.
- Requiere una cámara web. Se probó en Windows con Python 3.12.

---

## 📄 Licencia

MIT — ver [LICENSE](LICENSE).
