import os
os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"
import time
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QToolBar, QPushButton, QLabel, QFrame, QFileDialog, QTextEdit
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
        for text, func in [("<", self.web.back), (">", self.web.forward), ("↻", self.web.reload)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            self.toolbar.addWidget(btn)

        # --- Layout principal ---
        self.container = QWidget()
        self.layout = QHBoxLayout()
        self.layout.addWidget(self.web)
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

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
        def after_check(is_ingame):
            self.toggle_sidebar(is_ingame)
            if is_ingame:
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

    # ================================
    #   Actualizar recursos
    # ================================
    def update_resources(self):
        """Abre una ventana minimizada con la misma sesión para extraer recursos."""
        if not self.has_sidebar:
            return

        # 🔹 Usar el mismo perfil de sesión que el navegador principal
        profile = self.web.page().profile()

        # Crear ventana secundaria (minimizada)
        self.hidden_window = QMainWindow()
        self.hidden_window.setWindowTitle("OGame Resource Fetcher")
        self.hidden_window.resize(800, 600)
        self.hidden_window.showMinimized()

        self.hidden_web = QWebEngineView()
        self.hidden_page = CustomWebPage(profile, self.hidden_web, main_window=self)
        self.hidden_web.setPage(self.hidden_page)
        self.hidden_window.setCentralWidget(self.hidden_web)

        def after_load():
            print("[DEBUG] Página de recursos cargada, ejecutando script...")
            QTimer.singleShot(2000, lambda: self.hidden_web.page().runJavaScript(
                extract_resources_script, self.handle_resource_data
            ))
            QTimer.singleShot(6000, self.hidden_window.close)

        self.hidden_web.loadFinished.connect(after_load)

        current_url = self.web.url().toString()
        base_url = current_url.split("?")[0]
        prod_url = base_url + "?page=ingame&component=resourcesettings"
        print(f"[DEBUG] Cargando página de recursos: {prod_url}")
        self.hidden_web.load(QUrl(prod_url))

    def handle_resource_data(self, data):
        print("[DEBUG] Datos recibidos de extract_resources_script:", data)
        if not data or not self.has_sidebar:
            return

        self.metal_label.setText(f"⚙️ Metal: {data.get('metal', '—')}")
        self.crystal_label.setText(f"💎 Cristal: {data.get('crystal', '—')}")
        self.deut_label.setText(f"🧪 Deuterio: {data.get('deuterium', '—')}")
        self.energy_label.setText(f"⚡ Energía: {data.get('energy', '—')}")


    # ================================
    #   Colas de construcción
    # ================================
    def update_queues(self):
        if self.has_sidebar:
            self.web.page().runJavaScript(extract_queue_script, self.handle_queue_data)

    def handle_queue_data(self, data):
        if not data or not self.has_sidebar:
            self.current_queues = []
            self.queue_text.setText("— No hay construcciones activas —")
            self.timer_fast.stop()
            return

        self.current_queues = data
        self.timer_fast.start()
        self.update_queue_timers()

    def update_queue_timers(self):
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

            progress = 0
            if end > start:
                progress = max(0, min(100, int(((now - start) / (end - start)) * 100)))

            color = "#0f0" if progress < 60 else "#ff0" if progress < 90 else "#f00"
            filled = int(26 * progress / 100)
            bar = f"<span style='color:{color};'>{'█'*filled}</span><span style='color:#555;'>{'░'*(26-filled)}</span>"

            lines.append(f"{label}: {name} {level} ({remaining_str})<br>[{bar}] {progress}%")

            if remaining <= 0:
                finished_any = True

        self.queue_text.setHtml("<br><br>".join(lines))

        # ⚙️ Cuando una cola termina, actualizar colas y recursos
        if finished_any:
            self.update_queues()
            QTimer.singleShot(2000, self.update_resources)

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
