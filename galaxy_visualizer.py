import json
import numpy as np
import plotly.graph_objects as go

# ---------------------------
# Configuración
# ---------------------------
NUM_G = "5"
JSON_PATH = f"galaxy_data_g{NUM_G}.json"

R_DONUT = 10
PLANET_LINEAR_SPEED = 0.12
DONUT_SPEED = 0.015
FRAMES = 120

STAR_SIZE = 10
PLANET_SIZE = 5

# ---------------------------
# Helpers
# ---------------------------
def slot_to_radius(slot):
    return 0.5 + slot * 0.15


def load_systems(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    systems = []
    data = data.get(NUM_G)
    system_ids = sorted(data.keys(), key=int)

    for sid in system_ids:
        system_data = data[sid]
        planets = []

        for key, value in system_data.items():
            if not key.isdigit():
                continue

            if "planet" in value:
                slot = int(key)
                planets.append({
                    "r": slot_to_radius(slot),
                    "phase": np.random.uniform(0, 2*np.pi)
                })

        if planets:
            systems.append(planets)

    return systems


# ---------------------------
# Carga de datos
# ---------------------------
systems = load_systems(JSON_PATH)
NUM_SYSTEMS = len(systems)

system_angles = np.linspace(0, 2*np.pi, NUM_SYSTEMS, endpoint=False)

# ---------------------------
# Frames
# ---------------------------
frames = []

for t in range(FRAMES):
    x_stars, y_stars = [], []
    x_planets, y_planets = [], []

    donut_offset = DONUT_SPEED * t

    for i, planets in enumerate(systems):
        angle = system_angles[i] + donut_offset
        cx = R_DONUT * np.cos(angle)
        cy = R_DONUT * np.sin(angle)

        x_stars.append(cx)
        y_stars.append(cy)

        for p in planets:
            omega = PLANET_LINEAR_SPEED / p["r"]
            phi = omega * t + p["phase"]

            x_planets.append(cx + p["r"] * np.cos(phi))
            y_planets.append(cy + p["r"] * np.sin(phi))

    frames.append(go.Frame(data=[
        go.Scatter(
            x=x_stars,
            y=y_stars,
            mode="markers",
            marker=dict(size=STAR_SIZE, color="yellow")
        ),
        go.Scatter(
            x=x_planets,
            y=y_planets,
            mode="markers",
            marker=dict(size=PLANET_SIZE, color="white")
        )
    ]))

# ---------------------------
# Figura base
# ---------------------------
fig = go.Figure(
    data=frames[0].data,
    frames=frames
)

fig.update_layout(
    title="Donut de sistemas planetarios (datos reales)",
    xaxis=dict(visible=False, range=[-14, 14]),
    yaxis=dict(visible=False, range=[-14, 14]),
    width=800,
    height=800,
    plot_bgcolor="black",
    paper_bgcolor="black",
    updatemenus=[{
        "type": "buttons",
        "showactive": False,
        "buttons": [{
            "label": "▶ Play",
            "method": "animate",
            "args": [None, {
                "frame": {"duration": 50, "redraw": True},
                "transition": {"duration": 0},
                "mode": "immediate"
            }]
        }]
    }]
)

fig.show()
