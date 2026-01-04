import json
import numpy as np
import plotly.graph_objects as go

# ---------------------------
# Configuración
# ---------------------------
STAR_LOCK = True
MOON_LOCK = False
NUM_G = "5"
JSON_PATH = f"galaxy_data_g{NUM_G}.json"

FRAMES = 120

STAR_SIZE = 10
PLANET_SIZE = 5

DONUT_RADIUS = 8
MOON_RADIUS = 0.25
DEBRIS_RADIUS = 0.30

DONUT_SPEED = 0.015
PLANET_SPEED = 0.12
MOON_SPEED = 0.35

# ---------------------------
# Helpers
# ---------------------------
def slot_to_radius(slot):
    return 0.5 + slot * 0.15

def load_systems(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)[NUM_G]

    systems = []

    for sid in sorted(data.keys(), key=int):
        system_data = data[sid]
        planets = []

        for key, value in system_data.items():
            if not key.isdigit():
                continue

            slot = int(key)
            r = slot_to_radius(slot)

            if not isinstance(value, dict):
                continue

            has_planet = "planet" in value
            has_moon = "moon" in value
            has_debris = "debris" in value

            if has_planet:
                planets.append({
                    "r": r,
                    "name": value["planet"]["name"],
                    "coords": f"{NUM_G}:{sid}:{key}",
                    "phase": np.random.uniform(0, 2*np.pi),
                    "has_moon": has_moon,
                    "has_debris": has_debris,
                    "moon_phase": np.random.uniform(0, 2*np.pi)
                })

            elif has_debris:
                # debris sin planeta → orbita estrella
                planets.append({
                    "r": r,
                    "name": "Space",
                    "coords": f"{NUM_G}:{sid}:{key}",
                    "phase": np.random.uniform(0, 2*np.pi),
                    "has_moon": False,
                    "has_debris": True,
                    "moon_phase": np.random.uniform(0, 2*np.pi)
                })

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
    x_moons, y_moons = [], []
    x_debris, y_debris = [], []
    star_hover = []
    planet_hover = []
    moon_hover = []
    debris_hover = []


    donut_offset = DONUT_SPEED * t

    for i, planets in enumerate(systems):
        angle = system_angles[i] + donut_offset
        cx = DONUT_RADIUS * np.cos(angle)
        cy = DONUT_RADIUS * np.sin(angle)

        # ⭐ estrella
        x_stars.append(cx)
        y_stars.append(cy)
        star_hover.append(f"System: {i}")

        for p in planets:
            # 🪐 planeta

            if(STAR_LOCK):
                px = (DONUT_RADIUS + p["phase"] + 1) * np.cos(angle)
                py = (DONUT_RADIUS + p["phase"] + 1) * np.sin(angle)
            else:
                omega_p = PLANET_SPEED / p["r"]
                phi_p = omega_p * t + p["phase"]
                px = cx + p["r"] * np.cos(phi_p)
                py = cy + p["r"] * np.sin(phi_p)

            x_planets.append(px)
            y_planets.append(py)
            planet_hover.append(
                f"Planet: {p['name']}<br>Coords: {p['coords']}"
            )

            # 🌙 luna
            if p.get("has_moon"):
                phi_m = MOON_SPEED * t + p["moon_phase"]
                if(MOON_LOCK):
                    mx = (DONUT_RADIUS + p["phase"]) * np.cos(angle) 
                    my = (DONUT_RADIUS + p["phase"]) * np.sin(angle)
                else:
                    phi_m = MOON_SPEED * t + p["moon_phase"]
                    mx = px + MOON_RADIUS * np.cos(phi_m)
                    my = py + MOON_RADIUS * np.sin(phi_m)

                x_moons.append(mx)
                y_moons.append(my)
                moon_hover.append(
                    f"Moon: {p['name']}<br>Coords: {p['coords']}"
                )

            # ☄ debris del planeta
            if p.get("has_debris"):
                if p.get("has_moon"):
                    phi_d = phi_m + np.pi
                    r_d = MOON_RADIUS
                else:
                    phi_d = MOON_SPEED * t + p["moon_phase"]
                    r_d = DEBRIS_RADIUS

                dx = px + r_d * np.cos(phi_d)
                dy = py + r_d * np.sin(phi_d)

                x_debris.append(dx)
                y_debris.append(dy)

    frames.append(go.Frame(data=[
        go.Scatter(
            x=x_stars,
            y=y_stars,
            mode="markers",
            marker=dict(size=STAR_SIZE, color="yellow"),
            hovertext=star_hover,
            hoverinfo="text"
        ),
        go.Scatter(
            x=x_planets,
            y=y_planets,
            mode="markers",
            marker=dict(size=PLANET_SIZE, color="white"),
            hovertext=planet_hover,
            hoverinfo="text"
        ),
        go.Scatter(
            x=x_moons,
            y=y_moons,
            mode="markers",
            marker=dict(size=3, color="blue"),
            hovertext=moon_hover,
            hoverinfo="text"
        ),
        go.Scatter(
            x=x_debris,
            y=y_debris,
            mode="markers",
            marker=dict(size=3, color="red")
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
