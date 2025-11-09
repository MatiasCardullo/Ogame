import os
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QToolBar, QPushButton, QLabel, QFrame, QFileDialog, QTextEdit, QCheckBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl, QTimer

from custom_page import CustomWebPage
from sidebar_updater import extract_meta_script, extract_resources_script, extract_queue_script


class BrowserWindow(QMainWindow):
    def __init__(self, profile=None, url=None, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.popups = []
        self.has_sidebar = False
        self.setWindowTitle("OGame Browser")
        self.resize(1450, 900)

        # --- Perfil persistente ---
        profile = profile or QWebEngineProfile("ogame_profile", self)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        os.makedirs("profile_data", exist_ok=True)
        profile.setPersistentStoragePath(os.path.abspath("profile_data"))
        profile.setCachePath(os.path.abspath("profile_data/cache"))

        # --- WebEngine ---
        self.web = QWebEngineView()
        self.page = CustomWebPage(profile, self.web, main_window=self)
        self.web.setPage(self.page)
        if url:
            self.web.load(QUrl(url))

        # --- Toolbar ---
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        for text, func in [("⬅", self.web.back), ("➡", self.web.forward), ("↻", self.web.reload)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            self.toolbar.addWidget(btn)

        # --- Layout principal ---
        self.container = QWidget()
        self.layout = QHBoxLayout()
        self.layout.addWidget(self.web)
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

        # --- Timer de auto-refresh general (cada 5 s) ---
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.auto_update)

        # --- Timer de actualización visual rápida (cada 1 s) ---
        self.timer_fast = QTimer(self)
        self.timer_fast.setInterval(1000)
        self.timer_fast.timeout.connect(self.update_queue_timers)

        # Detectar entorno ingame
        self.web.loadFinished.connect(self.check_if_ingame)

    # ================================
    #   Lógica principal
    # ================================
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
        self.web.page().runJavaScript(script, self.toggle_sidebar)

    def toggle_sidebar(self, is_ingame):
        if is_ingame and not self.has_sidebar:
            self.add_sidebar()
        elif not is_ingame and self.has_sidebar:
            self.remove_sidebar()

    def add_sidebar(self):
        self.has_sidebar = True
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(280)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #111;
                color: #EEE;
                border-left: 2px solid #222;
            }
            QLabel {
                color: #EEE;
                font-size: 14px;
                padding: 2px;
            }
            QTextEdit {
                background-color: #181818;
                color: #CCC;
                border: 1px solid #333;
                font-family: Consolas;
                font-size: 13px;
            }
            QPushButton {
                background-color: #333;
                border-radius: 6px;
                padding: 6px;
                margin: 4px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)

        # --- Info básica ---
        self.player_label = QLabel("👤 Jugador: —")
        self.planet_label = QLabel("🪐 Planeta: —")
        self.coords_label = QLabel("📍 Coordenadas: —")
        self.universe_label = QLabel("🌌 Universo: —")

        # --- Recursos ---
        self.metal_label = QLabel("⚙️ Metal: —")
        self.crystal_label = QLabel("💎 Cristal: —")
        self.deut_label = QLabel("🧪 Deuterio: —")
        self.energy_label = QLabel("⚡ Energía: —")

        # --- Colas ---
        self.queue_text = QTextEdit()
        self.queue_text.setReadOnly(True)
        self.queue_text.setFixedHeight(180)

        # --- Botones ---
        self.refresh_btn = QPushButton("🔄 Actualizar recursos")
        self.refresh_btn.clicked.connect(self.update_resources)
        self.update_queue_btn = QPushButton("🏗️ Actualizar colas")
        self.update_queue_btn.clicked.connect(self.update_queues)
        self.save_btn = QPushButton("💾 Guardar HTML")
        self.save_btn.clicked.connect(self.save_html)

        # --- Auto-refresh toggle ---
        self.auto_refresh = QCheckBox("⏱️ Auto-actualizar cada 5 s")
        self.auto_refresh.stateChanged.connect(self.toggle_auto_refresh)

        sidebar_layout = QVBoxLayout()
        sidebar_layout.addWidget(self.player_label)
        sidebar_layout.addWidget(self.planet_label)
        sidebar_layout.addWidget(self.coords_label)
        sidebar_layout.addWidget(self.universe_label)
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(self.metal_label)
        sidebar_layout.addWidget(self.crystal_label)
        sidebar_layout.addWidget(self.deut_label)
        sidebar_layout.addWidget(self.energy_label)
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(QLabel("📋 Colas activas:"))
        sidebar_layout.addWidget(self.queue_text)
        sidebar_layout.addWidget(self.refresh_btn)
        sidebar_layout.addWidget(self.update_queue_btn)
        sidebar_layout.addWidget(self.save_btn)
        sidebar_layout.addWidget(self.auto_refresh)
        self.sidebar.setLayout(sidebar_layout)

        self.layout.addWidget(self.sidebar)
        self.web.loadFinished.connect(self.update_meta_info)

    def remove_sidebar(self):
        self.has_sidebar = False
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if isinstance(widget, QFrame):
                self.layout.removeWidget(widget)
                widget.deleteLater()

    # ================================
    #   Actualizaciones manuales
    # ================================
    def update_meta_info(self):
        self.web.page().runJavaScript(extract_meta_script, self.handle_meta_data)

    def handle_meta_data(self, data):
        if not data or not self.has_sidebar:
            return
        self.player_label.setText(f"👤 Jugador: {data.get('ogame-player-name', '—')}")
        self.planet_label.setText(f"🪐 Planeta: {data.get('ogame-planet-name', '—')}")
        self.coords_label.setText(f"📍 Coordenadas: {data.get('ogame-planet-coordinates', '—')}")
        self.universe_label.setText(f"🌌 Universo: {data.get('ogame-universe-name', '—')}")

    def update_resources(self):
        if self.has_sidebar:
            self.web.page().runJavaScript(extract_resources_script, self.handle_resource_data)

    def handle_resource_data(self, data):
        if not data or not self.has_sidebar:
            return
        self.metal_label.setText(f"⚙️ Metal: {data.get('metal_box', '—')}")
        self.crystal_label.setText(f"💎 Cristal: {data.get('crystal_box', '—')}")
        self.deut_label.setText(f"🧪 Deuterio: {data.get('deuterium_box', '—')}")
        self.energy_label.setText(f"⚡ Energía: {data.get('energy_box', '—')}")

    def update_queues(self):
        if self.has_sidebar:
            self.web.page().runJavaScript(extract_queue_script, self.handle_queue_data)

    def update_queue_timers(self):
        import time
        if not hasattr(self, "current_queues") or not self.current_queues:
            return

        now = int(time.time())
        lines = []
        finished_any = False

        for entry in self.current_queues:
            label = entry["label"]
            name = entry["name"]
            level = entry["level"]
            start = entry["start"]
            end = entry["end"]

            remaining = max(0, end - now)
            minutes, seconds = divmod(remaining, 60)
            remaining_str = f"{minutes}m {seconds:02d}s" if remaining > 0 else "Completado"

            # Progreso visual
            progress = 0
            if end > start:
                progress = max(0, min(100, int(((now - start) / (end - start)) * 100)))

            bar_length = 26
            filled = int(bar_length * progress / 100)
            if progress < 60:
                bar = f"<span style='color:#0f0;'>{'█'*filled}</span><span style='color:#555;'>{'░'*(bar_length-filled)}</span>"
            elif progress < 90:
                bar = f"<span style='color:#ff0;'>{'█'*filled}</span><span style='color:#555;'>{'░'*(bar_length-filled)}</span>"
            else:
                bar = f"<span style='color:#f00;'>{'█'*filled}</span><span style='color:#555;'>{'░'*(bar_length-filled)}</span>"

            lines.append(f"{label}: {name} {level} ({remaining_str})<br>[{bar}] {progress}%")

            if remaining <= 0:
                finished_any = True

        self.queue_text.setHtml("<br><br>".join(lines))

        # Si terminó una cola, volver a ejecutar JS para refrescar
        if finished_any:
            self.update_queues()

    def handle_queue_data(self, data):
        import time
        if not data or not self.has_sidebar:
            self.current_queues = []
            self.queue_text.setText("— No hay construcciones activas —")
            return

        # Guardar en memoria las colas actuales para update visual cada 1 s
        self.current_queues = data
        self.update_queue_timers()

    # ================================
    #   Auto-refresh cada 5 segundos
    # ================================
    def toggle_auto_refresh(self, state):
        if state:
            self.timer.start()
            self.timer_fast.start()
        else:
            self.timer.stop()
            self.timer_fast.stop()

    def auto_update(self):
        # Si no hay colas, intentar buscarlas
        if not getattr(self, "current_queues", None):
            self.update_queues()
        self.update_resources()

    # ================================
    #   Guardar HTML
    # ================================
    def save_html(self):
        def handle_html(html):
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar HTML", "pagina.html", "Archivos HTML (*.html)"
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
        self.web.page().toHtml(handle_html)
