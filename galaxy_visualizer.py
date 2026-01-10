import json, sys, traceback
import numpy as np
import plotly.graph_objects as go
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl
from pathlib import Path

def galaxy_loader(NUM_G):
    # ---------------------------
    # Configuración
    # ---------------------------
    NUM_G = str(NUM_G)
    STAR_LOCK = False
    MOON_LOCK = False
    JSON_PATH = f"galaxy_data_g{NUM_G}.json"

    FRAMES = 120

    STAR_SIZE = 14
    PLANET_SIZE = 7

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

    def map_moon_size(size):
        if MOON_MAX == MOON_MIN:
            return 3
        t = (size - MOON_MIN) / (MOON_MAX - MOON_MIN)
        return 2 + 2 * t   # 2 → 4

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

                obj={
                    "r": r,
                    "coords": f"{NUM_G}:{sid}:{key}",
                    "phase": np.random.uniform(0, 2*np.pi),
                    "has_moon": has_moon,
                    "has_debris": has_debris,
                    "moon_phase": np.random.uniform(0, 2*np.pi)
                }
                if has_debris:
                    obj["name"] = "DEEP_SPACE"
                    obj["metal"] = value["debris"]["metal"]
                    obj["crystal"] = value["debris"]["crystal"]
                    obj["deuterium"] = value["debris"]["deuterium"]
                if has_planet:
                    obj["name"] = value["planet"]["name"]
                    if has_moon:
                        obj["moon_name"] = value["moon"]["name"]
                        obj["moon_size"] = int(value["moon"]["size"])
                planets.append(obj)
            systems.append(planets)
        return systems

    JS_CLICK = """
    <script>
    document.addEventListener("DOMContentLoaded", function () {
        const plot = document.getElementById("galaxy_plot");

        // 🔥 asegurar foco
        plot.setAttribute("tabindex", "0");
        plot.focus();

        // click → aislar sistema
        plot.on('plotly_click', function (data) {
            const systemId = data.points[0].customdata;

            const update = plot.data.map(trace => {
                if (!trace.customdata) return trace.marker.opacity;

                return trace.customdata.map(sid =>
                    sid === systemId ? 1.0 : 0.05
                );
            });

            Plotly.restyle(plot, {
                'marker.opacity': update
            });

            plot.focus(); // volver a enfocar después del click
        });

        // ⎋ ESC → reset
        window.addEventListener("keydown", function (e) {
            if (e.key === "Escape") {
                Plotly.restyle(plot, {
                    'marker.opacity': 1.0
                });
                plot.focus();
            }
        });
    });
    </script>

    """


    # ---------------------------
    # Carga de datos
    # ---------------------------
    systems = load_systems(JSON_PATH)
    moon_sizes = []
    for system in systems:
        for p in system:
            if p.get("has_moon") and "moon_size" in p:
                moon_sizes.append(p["moon_size"])
    MOON_MIN = min(moon_sizes) if moon_sizes else 1
    MOON_MAX = max(moon_sizes) if moon_sizes else 1

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
        star_custom = []
        planet_custom = []
        moon_custom = []
        debris_custom = []
        star_color = []
        planet_color = []
        debris_colors = []
        moon_sizes_frame = []

        donut_offset = DONUT_SPEED * t

        for i, planets in enumerate(systems):
            angle = system_angles[i] + donut_offset
            cx = DONUT_RADIUS * np.cos(angle)
            cy = DONUT_RADIUS * np.sin(angle)

            # ⭐ estrella
            x_stars.append(cx)
            y_stars.append(cy)
            if planets:
                star_hover.append(f"System: {i}")
                star_color.append("yellow")
            else:
                star_hover.append(None)
                star_color.append("rgba(255,255,0,0.1)")
            star_custom.append(i)

            for p in planets:
                # 🪐 planeta
                has_real_planet = "name" in p and p["name"] != "DEEP_SPACE"
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
                if has_real_planet:
                    planet_hover.append(None)
                    planet_color.append("rgba(0,0,0,0)")
                else:
                    planet_hover.append(f"Planet: {p['name']}<br>Coords: {p['coords']}")
                    planet_color.append("white")
                planet_custom.append(i)


                # 🌙 luna
                if p.get("has_moon"):
                    moon_sizes_frame.append(map_moon_size(p["moon_size"]))
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
                        f"Moon: {p['moon_name']}<br>Coords: {p['coords']}"
                    )
                    moon_custom.append(i)


                # ☄ debris
                if p.get("has_debris"):
                    phi_d = MOON_SPEED * t + p["moon_phase"]

                    # decidir centro de órbita
                    if has_real_planet:
                        if p.get("has_moon"):
                            phi_d += np.pi
                            r_d = MOON_RADIUS
                        else:
                            r_d = DEBRIS_RADIUS

                        cx_d = px
                        cy_d = py
                    else:
                        # debris orbitando la estrella
                        r_d = p["r"]
                        cx_d = cx
                        cy_d = cy

                    # posición base
                    dx = cx_d + r_d * np.cos(phi_d)
                    dy = cy_d + r_d * np.sin(phi_d)

                    # recursos → color
                    resources = [
                        ("metal", "#555"),
                        ("crystal", "#aff"),
                        ("deuterium", "#0f8")
                    ]

                    active = [(name, col) for name, col in resources if p.get(name, 0) > 0]
                    count = max(1, len(active))

                    for k, (name, color) in enumerate(active):
                        offset = k * (2 * np.pi / count)

                        dx_k = dx + 0.05 * np.cos(offset)
                        dy_k = dy + 0.05 * np.sin(offset)

                        x_debris.append(dx_k)
                        y_debris.append(dy_k)
                        debris_colors.append(color)

                        debris_hover.append(
                            f"Debris ({name})<br>"
                            f"Coords: {p['coords']}<br>"
                            f"Metal: {p.get('metal', 0)}<br>"
                            f"Crystal: {p.get('crystal', 0)}<br>"
                            f"Deuterium: {p.get('deuterium', 0)}"
                        )

                        debris_custom.append(i)


        frames.append(go.Frame(data=[
            go.Scatter(
                x=x_stars,
                y=y_stars,
                mode="markers",
                marker=dict(size=STAR_SIZE, color=star_color),
                hovertext=star_hover,
                hoverinfo="text",
                customdata=star_custom
            ),
            go.Scatter(
                x=x_planets,
                y=y_planets,
                mode="markers",
                marker=dict(size=PLANET_SIZE, color="white"),
                hovertext=planet_hover,
                hoverinfo="text",
                customdata=planet_custom
            ),
            go.Scatter(
                x=x_moons,
                y=y_moons,
                mode="markers",
                marker=dict(size=moon_sizes_frame, color="blue"),
                hovertext=moon_hover,
                hoverinfo="text",
                customdata=moon_custom
            ),
            go.Scatter(
                x=x_debris,
                y=y_debris,
                mode="markers",
                marker=dict(
                    size=3,
                    color=debris_colors
                ),
                hoverinfo="text",
                hovertext=debris_hover,
                customdata=debris_custom
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

    html = fig.to_html(
        full_html=True,
        include_plotlyjs="inline",
        div_id="galaxy_plot"
    )

    html = html.replace("</body>", JS_CLICK + "</body>")

    with open(f"galaxy_{NUM_G}.html", "w", encoding="utf-8") as f:
        f.write(html)

class GalaxyViewer(QMainWindow):
    def __init__(self,galaxy):
        super().__init__()
        self.setWindowTitle("Galaxy Visualizer")
        self.resize(900, 900)

        view = QWebEngineView()
        html_path = Path(f"galaxy_{galaxy}.html").absolute()

        view.load(QUrl.fromLocalFile(str(html_path)))
        self.setCentralWidget(view)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python galaxy_visualizer.py <galaxia>")
        sys.exit(1)

    try:
        galaxy_num = int(sys.argv[1])
        if not (1 <= galaxy_num <= 5):
            raise ValueError("La galaxia debe estar entre 1 y 5")
        galaxy_loader(galaxy_num)
        app = QApplication(sys.argv)
        win = GalaxyViewer(galaxy_num)
        win.show()
        sys.exit(app.exec())
            
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"[GalaxyVisualizer] Error en galaxia: {e}")
        traceback.print_exc()