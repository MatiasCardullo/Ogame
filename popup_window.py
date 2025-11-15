from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
    QTextEdit, QToolBar, QPushButton, QFileDialog, QSystemTrayIcon
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon
import time
import os
from custom_page import CustomWebPage
from js_scripts import extract_meta_script, extract_resources_script, extract_queue_script


class PopupWindow(QMainWindow):
    """Ventana tipo popup: contiene toolbar y sidebar.
    Mantiene lógica de recursos, colas y notificaciones.
    """
    def __init__(self, profile=None, url=None, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("OGame Popup")
        self.resize(1000, 700)

        profile = profile or QWebEngineProfile("ogame_profile", self)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        os.makedirs("profile_data", exist_ok=True)
        profile.setPersistentStoragePath(os.path.abspath("profile_data"))
        profile.setCachePath(os.path.abspath("profile_data/cache"))

        self.web = QWebEngineView()
        self.page = CustomWebPage(profile, self.web, main_window=self.main_window)
        self.web.setPage(self.page)
        if url:
            self.web.load(QUrl(url))

        # Toolbar
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        for text, func in [("<", self.web.back), (">", self.web.forward), ("↻", self.web.reload)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            self.toolbar.addWidget(btn)

        # Layout
        self.container = QWidget()
        self.layout = QHBoxLayout()
        self.layout.addWidget(self.web)
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

        # Sidebar state
        self.has_sidebar = False

        # Timers
        self.timer_fast = QTimer(self)
        self.timer_fast.setInterval(1000)
        self.timer_fast.timeout.connect(self.update_queue_timers)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-games"))
        self.tray_icon.setVisible(True)

        self.web.loadFinished.connect(self.check_if_ingame)

    def check_if_ingame(self):
        script = """
            (function() {
                const metas = document.getElementsByTagName('meta');
                for (let m of metas) {
                    if (m.name && m.name.startsWith('ogame-player-name')) return true;
                }
                return false;
            })();
        """

        def after_check(is_ingame):
            self.toggle_sidebar(is_ingame)
            if is_ingame:
                self.update_meta_info()
                self.update_queues()

        self.web.page().runJavaScript(script, after_check)

    def toggle_sidebar(self, is_ingame):
        if is_ingame and not self.has_sidebar:
            self.add_sidebar()
        elif not is_ingame and self.has_sidebar:
            self.remove_sidebar()

    def add_sidebar(self):
        self.has_sidebar = True
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(320)
        self.sidebar.setStyleSheet("""
            QFrame { background-color: #111; color: #EEE; border-left: 2px solid #222; }
            QLabel { color: #EEE; font-size: 14px; padding: 2px; }
            QTextEdit { background-color: #181818; color: #CCC; border: 1px solid #333; font-family: Consolas; font-size: 13px; }
            QPushButton { background-color: #333; border-radius: 6px; padding: 6px; margin: 4px; }
            QPushButton:hover { background-color: #555; }
        """)

        sidebar_layout = QVBoxLayout()
        self.layout.addWidget(self.sidebar)
        self.sidebar.setLayout(sidebar_layout)

        # Basic info
        self.player_label = QLabel("👤 Jugador: —")
        self.universe_label = QLabel("🌌 Universo: —")
        self.coords_label = QLabel("📍 Coordenadas: —")
        self.planet_label = QLabel("🪐 Planeta: —")
        sidebar_layout.addWidget(self.player_label)
        sidebar_layout.addWidget(self.universe_label)
        sidebar_layout.addWidget(self.coords_label)
        sidebar_layout.addWidget(self.planet_label)
        sidebar_layout.addSpacing(10)

        # Resources
        self.metal_label = QLabel("⚙️ Metal: —")
        self.crystal_label = QLabel("💎 Cristal: —")
        self.deut_label = QLabel("🧪 Deuterio: —")
        self.energy_label = QLabel("⚡ Energía: —")
        sidebar_layout.addWidget(self.metal_label)
        sidebar_layout.addWidget(self.crystal_label)
        sidebar_layout.addWidget(self.deut_label)
        sidebar_layout.addWidget(self.energy_label)
        sidebar_layout.addSpacing(10)

        # Queues
        self.queue_text = QTextEdit()
        self.queue_text.setReadOnly(True)
        self.queue_text.setFixedHeight(180)
        sidebar_layout.addWidget(QLabel("📋 Colas activas:"))
        sidebar_layout.addWidget(self.queue_text)

        # Buttons
        self.refresh_btn = QPushButton("🔄 Actualizar recursos")
        self.refresh_btn.clicked.connect(self.update_resources)
        self.update_queue_btn = QPushButton("🏗️ Actualizar colas")
        self.update_queue_btn.clicked.connect(self.update_queues)
        self.save_btn = QPushButton("💾 Guardar HTML")
        self.save_btn.clicked.connect(self.save_html)
        sidebar_layout.addWidget(self.refresh_btn)
        sidebar_layout.addWidget(self.update_queue_btn)
        sidebar_layout.addWidget(self.save_btn)

        self.update_meta_info()
        self.update_queues()

    def remove_sidebar(self):
        self.has_sidebar = False
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if isinstance(widget, QFrame):
                self.layout.removeWidget(widget)
                widget.deleteLater()

    # --- Meta / resources ---
    def update_meta_info(self):
        self.web.page().runJavaScript(extract_meta_script, self.handle_meta_data)

    def handle_meta_data(self, data):
        if not data or not self.has_sidebar:
            return
        
        self.player_label.setText(f"👤 Jugador: {data.get('ogame-player-name', '—')}")
        self.universe_label.setText(f"🌌 Universo: {data.get('ogame-universe-name', '—')}")
        coords = f"📍 Coordenadas: {data.get('ogame-planet-coordinates', '—')}"
        if self.coords_label.text != coords:
            self.coords_label.setText(coords)
            self.update_resources()
        self.planet_label.setText(f"🪐 Planeta: {data.get('ogame-planet-name', '—')}")

    def update_resources(self):
        if not self.has_sidebar:
            return
        self.web.page().runJavaScript(extract_resources_script, self.handle_resource_data)

    def handle_resource_data(self, data):
        if not data or not self.has_sidebar:
            return

        self.current_resources = {
            "metal": data.get("metal", 0),
            "crystal": data.get("crystal", 0),
            "deuterium": data.get("deuterium", 0),
            "energy": data.get("energy", 0),
            "prod_metal": data.get("prod_metal", 0),
            "prod_crystal": data.get("prod_crystal", 0),
            "prod_deuterium": data.get("prod_deuterium", 0),
            "cap_metal": data.get("capacity_metal", 0),
            "cap_crystal": data.get("capacity_crystal", 0),
            "cap_deuterium": data.get("capacity_deuterium", 0),
            "last_update": time.time()
        }

        self.update_resource_labels()

        if hasattr(self, "timer_resources"):
            self.timer_resources.stop()
        else:
            self.timer_resources = QTimer(self)
            self.timer_resources.setInterval(1000)
            self.timer_resources.timeout.connect(self.increment_resources)
        self.timer_resources.start()

        # Notify main window if popup
        if self.main_window:
            planet = self.planet_label.text().replace("🪐 Planeta: ", "").strip()
            self.main_window.update_planet_data(
                planet=planet or "Desconocido",
                resources=self.current_resources,
                queues=getattr(self, "current_queues", [])
            )

    def update_resource_labels(self):
        r = getattr(self, "current_resources", None)
        if not r:
            return

        def fmt(x):
            return f"{int(x):,}".replace(",", ".")

        def tiempo_lleno(cant, cap, prod):
            if prod <= 0 or cant >= cap:
                return "—"
            horas = (cap - cant) / (prod * 3600)
            if horas < 1:
                minutos = horas * 60
                return f"{minutos:.1f}m"
            else:
                return f"{horas:.1f}h"

        def barra(cant, cap, color):
            if cap <= 0:
                return ""
            ratio = min(1, cant / cap)
            filled = int(20 * ratio)
            empty = 20 - filled
            return f"<span style='color:{color};'>{'█'*filled}</span><span style='color:#444;'>{'░'*empty}</span>"

        pm = r["prod_metal"] * 3600
        pc = r["prod_crystal"] * 3600
        pd = r["prod_deuterium"] * 3600

        tm = tiempo_lleno(r["metal"], r["cap_metal"], r["prod_metal"])
        tc = tiempo_lleno(r["crystal"], r["cap_crystal"], r["prod_crystal"])
        td = tiempo_lleno(r["deuterium"], r["cap_deuterium"], r["prod_deuterium"])

        self.metal_label.setText(
            f"⚙️ Metal: {fmt(r['metal'])} <span style='color:#0f0;'> (+{fmt(pm)}/h)</span> lleno en {tm}<br>"
            f"{barra(r['metal'], r['cap_metal'], '#0f0')}"
        )
        self.crystal_label.setText(
            f"💎 Cristal: {fmt(r['crystal'])} <span style='color:#0af;'> (+{fmt(pc)}/h)</span> lleno en {tc}<br>"
            f"{barra(r['crystal'], r['cap_crystal'], '#0af')}"
        )
        self.deut_label.setText(
            f"🧪 Deuterio: {fmt(r['deuterium'])} <span style='color:#ff0;'> (+{fmt(pd)}/h)</span> lleno en {td}<br>"
            f"{barra(r['deuterium'], r['cap_deuterium'], '#ff0')}"
        )
        self.energy_label.setText(f"⚡ Energía: {fmt(r['energy'])}")

    def increment_resources(self):
        r = getattr(self, "current_resources", None)
        if not r:
            return

        now = time.time()
        elapsed = now - r["last_update"]
        if elapsed <= 0:
            return
        r["last_update"] = now

        r["metal"] += r["prod_metal"] * elapsed
        r["crystal"] += r["prod_crystal"] * elapsed
        r["deuterium"] += r["prod_deuterium"] * elapsed

        self.update_resource_labels()

    # --- Queues ---
    def update_queues(self):
        if not self.has_sidebar:
            return

        check_script = """
            (function() {
                return !!document.querySelector('#productionboxbuildingcomponent, #productionboxresearchcomponent, #productionboxshipyardcomponent');
            })();
        """

        def after_check(has_sections):
            if has_sections:
                self.web.page().runJavaScript(extract_queue_script, self.handle_queue_data)
            else:
                print("[DEBUG] Página sin secciones de cola, se omite actualización.")

        self.web.page().runJavaScript(check_script, after_check)

    def handle_queue_data(self, data):
        if not data or not self.has_sidebar:
            self.current_queues = []
            self.queue_text.setText("— No hay construcciones activas —")
            self.timer_fast.stop()
            return

        if not hasattr(self, "queue_memory"):
            self.queue_memory = {}

        updated_queues = []
        now = int(time.time())

        for q in data:
            key = f"{q['label']}|{q['name']}"
            start = int(q.get("start", now))
            end = int(q.get("end", now))

            if q["label"] == "🚀 Hangar":
                if key in self.queue_memory:
                    start = self.queue_memory[key]["start"]
                    end = self.queue_memory[key]["end"]
                else:
                    if end - start < 10:
                        end = now + 30
                    self.queue_memory[key] = {"start": start, "end": end}
            else:
                self.queue_memory[key] = {"start": start, "end": end}

            updated_queues.append({
                "label": q["label"],
                "name": q["name"],
                "level": q.get("level", ""),
                "start": start,
                "end": end
            })

        for k in list(self.queue_memory.keys()):
            if all(k != f"{q['label']}|{q['name']}" for q in updated_queues):
                del self.queue_memory[k]

        self.current_queues = updated_queues
        self.timer_fast.start()
        self.update_queue_timers()

    def update_queue_timers(self):
        if not hasattr(self, "current_queues") or not self.current_queues:
            return

        now = int(time.time())
        lines = []
        finished_any = False

        if not hasattr(self, "finished_queue_names"):
            self.finished_queue_names = set()

        for entry in self.current_queues:
            label = entry["label"]
            name = entry["name"]
            level = entry["level"]
            start = entry["start"]
            end = entry["end"]

            remaining = max(0, end - now)
            minutes, seconds = divmod(remaining, 60)
            remaining_str = f"{minutes}m {seconds:02d}s" if remaining > 0 else "Completado"

            progress = 0
            if end > start:
                progress = max(0, min(100, int(((now - start) / (end - start)) * 100)))

            color = "#0f0" if progress < 60 else "#ff0" if progress < 90 else "#f00"
            filled = int(26 * progress / 100)
            bar = f"<span style='color:{color};'>{'█'*filled}</span><span style='color:#555;'>{'░'*(26-filled)}</span>"

            lines.append(f"{label}: {name} {level} ({remaining_str})<br>[{bar}] {progress}%")

            if remaining <= 0 and name not in self.finished_queue_names:
                self.finished_queue_names.add(name)
                finished_any = True

        self.queue_text.setHtml("<br><br>".join(lines))

        if finished_any:
            self.update_resources()
            self.update_queues()

    # --- Utilities ---
    def save_html(self):
        def handle_html(html):
            path, _ = QFileDialog.getSaveFileName(self, "Guardar HTML", "pagina.html", "Archivos HTML (*.html)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
        self.web.page().toHtml(handle_html)

    def closeEvent(self, event):
        if self.main_window and self in getattr(self.main_window, 'popups', []):
            try:
                self.main_window.popups.remove(self)
            except Exception:
                pass
        for popup in getattr(self, "popups", []):
            try:
                popup.close()
            except Exception:
                pass
        super().closeEvent(event)
