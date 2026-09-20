# Genera docs/assets/hand-landmarks.png: los 21 landmarks de MediaPipe
# con sus conexiones, numerados y con nombres (recurso del README).
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Posiciones esquemáticas de cada landmark (x, y) — una mano abierta.
PTS = {
    0: (0.55, 0.00),
    1: (0.38, 0.10), 2: (0.29, 0.28), 3: (0.21, 0.44), 4: (0.13, 0.58),
    5: (0.42, 0.50), 6: (0.40, 0.70), 7: (0.38, 0.86), 8: (0.37, 1.02),
    9: (0.55, 0.52), 10: (0.55, 0.74), 11: (0.55, 0.92), 12: (0.55, 1.10),
    13: (0.67, 0.50), 14: (0.71, 0.69), 15: (0.74, 0.86), 16: (0.77, 1.02),
    17: (0.76, 0.48), 18: (0.84, 0.63), 19: (0.90, 0.77), 20: (0.96, 0.90),
}
BONES = [[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],
         [9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],
         [13,17],[17,18],[18,19],[19,20],[0,17]]
NAMES = ["WRIST", "THUMB_CMC", "THUMB_MCP", "THUMB_IP", "THUMB_TIP",
         "INDEX_FINGER_MCP", "INDEX_FINGER_PIP", "INDEX_FINGER_DIP",
         "INDEX_FINGER_TIP", "MIDDLE_FINGER_MCP", "MIDDLE_FINGER_PIP",
         "MIDDLE_FINGER_DIP", "MIDDLE_FINGER_TIP", "RING_FINGER_MCP",
         "RING_FINGER_PIP", "RING_FINGER_DIP", "RING_FINGER_TIP",
         "PINKY_MCP", "PINKY_PIP", "PINKY_DIP", "PINKY_TIP"]

fig = plt.figure(figsize=(9.6, 5.4), dpi=160)
ax = fig.add_axes([0.02, 0.06, 0.52, 0.86])
ax.set_xlim(-0.05, 1.15); ax.set_ylim(-0.15, 1.28)
ax.axis("off"); fig.patch.set_facecolor("#ffffff")

for a, b in BONES:
    ax.plot([PTS[a][0], PTS[b][0]], [PTS[a][1], PTS[b][1]],
            color="#2ecc40", lw=3.5, zorder=1, solid_capstyle="round")
xs = [p[0] for p in PTS.values()]; ys = [p[1] for p in PTS.values()]
ax.scatter(xs, ys, s=130, color="#e02020", zorder=2, edgecolors="white", lw=1.2)
for i, (x, y) in PTS.items():
    ax.annotate(str(i), (x, y), xytext=(10, 10), textcoords="offset points",
                fontsize=13, fontweight="bold", color="#111111")

# Listado de nombres en dos columnas a la derecha.
ax2 = fig.add_axes([0.54, 0.04, 0.45, 0.90]); ax2.axis("off")
ax2.set_xlim(0, 2); ax2.set_ylim(0, 11)
for i, name in enumerate(NAMES):
    col, row = divmod(i, 11)
    ax2.text(col + 0.05, 10.6 - row, f"{i}. {name}", fontsize=10.5,
             family="monospace", va="top", color="#111111")

fig.savefig("docs/assets/hand-landmarks.png", facecolor="#ffffff")
print("ok docs/assets/hand-landmarks.png")
