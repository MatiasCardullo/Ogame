from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QToolBar, QPushButton, QLabel, QFrame, QFileDialog, QTextEdit
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PyQt6.QtCore import QUrl, Qt
import os


class BrowserWindow(QMainWindow):
    def __init__(self, profile=None, url=None, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.popups = []
        self.has_sidebar = False
        self.setWindowTitle("OGame Browser")
        self.resize(1450, 900)

        # --- Perfil persistente (cookies guardadas) ---
        profile = profile or QWebEngineProfile("ogame_profile", self)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        os.makedirs("profile_data", exist_ok=True)
        profile.setPersistentStoragePath(os.path.abspath("profile_data"))
        profile.setCachePath(os.path.abspath("profile_data/cache"))

        # --- WebEngine principal ---
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

        # Detectar cuándo hay una página "ingame"
        self.web.loadFinished.connect(self.check_if_ingame)

    # --- Detección del entorno de juego ---
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

    # --- Crear sidebar ---
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

        self.player_label = QLabel("👤 Jugador: —")
        self.planet_label = QLabel("🪐 Planeta: —")
        self.coords_label = QLabel("📍 Coordenadas: —")
        self.universe_label = QLabel("🌌 Universo: —")

        self.metal_label = QLabel("⚙️ Metal: —")
        self.crystal_label = QLabel("💎 Cristal: —")
        self.deut_label = QLabel("🧪 Deuterio: —")
        self.energy_label = QLabel("⚡ Energía: —")

        self.queue_text = QTextEdit()
        self.queue_text.setReadOnly(True)
        self.queue_text.setFixedHeight(180)

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

    # --- Extraer <meta> ---
    def update_meta_info(self):
        script = """
            (function() {
                const metas = document.getElementsByTagName('meta');
                let data = {};
                for (let m of metas) if (m.name && m.content) data[m.name] = m.content;
                return data;
            })();
        """
        self.web.page().runJavaScript(script, self.handle_meta_data)

    def handle_meta_data(self, data):
        if not data or not self.has_sidebar:
            return
        self.player_label.setText(f"👤 Jugador: {data.get('ogame-player-name', '—')}")
        self.planet_label.setText(f"🪐 Planeta: {data.get('ogame-planet-name', '—')}")
        self.coords_label.setText(f"📍 Coordenadas: {data.get('ogame-planet-coordinates', '—')}")
        self.universe_label.setText(f"🌌 Universo: {data.get('ogame-universe-name', '—')}")

    # --- Recursos ---
    def update_resources(self):
        if not self.has_sidebar:
            return
        script = """
            (function() {
                let ids = ['metal_box', 'crystal_box', 'deuterium_box', 'energy_box'];
                let data = {};
                for (let id of ids) {
                    let el = document.getElementById(id);
                    if (el) {
                        let valueEl = el.querySelector('.value');
                        data[id] = valueEl ? valueEl.textContent.trim() : '—';
                    }
                }
                return data;
            })();
        """
        self.web.page().runJavaScript(script, self.handle_resource_data)

    def handle_resource_data(self, data):
        if not data or not self.has_sidebar:
            return
        self.metal_label.setText(f"⚙️ Metal: {data.get('metal_box', '—')}")
        self.crystal_label.setText(f"💎 Cristal: {data.get('crystal_box', '—')}")
        self.deut_label.setText(f"🧪 Deuterio: {data.get('deuterium_box', '—')}")
        self.energy_label.setText(f"⚡ Energía: {data.get('energy_box', '—')}")

    # --- Colas activas ---
    def update_queues(self):
        if not self.has_sidebar:
            return
        script = """
            (function() {
                let selectors = ['#productionboxBuilding', '#productionboxResearch', '#productionboxShipyard'];
                let result = [];
                for (let sel of selectors) {
                    let box = document.querySelector(sel);
                    if (box) {
                        let desc = box.querySelector('.desc')?.textContent?.trim();
                        let time = box.querySelector('.time')?.textContent?.trim();
                        if (desc && time) result.push(`${desc} (${time})`);
                    }
                }
                return result;
            })();
        """
        self.web.page().runJavaScript(script, self.handle_queue_data)

    def handle_queue_data(self, data):
        if not data or not self.has_sidebar:
            self.queue_text.setText("— No hay construcciones activas —")
            return
        text = "\n".join("🛠️ " + line for line in data)
        self.queue_text.setText(text)

    # --- Guardar HTML ---
    def save_html(self):
        def handle_html(html):
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar HTML", "pagina.html", "Archivos HTML (*.html)"
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
        self.web.page().toHtml(handle_html)


class CustomWebPage(QWebEnginePage):
    def __init__(self, profile, parent=None, main_window=None):
        super().__init__(profile, parent)
        self.main_window = main_window

    def createWindow(self, _type):
        popup = BrowserWindow(profile=self.profile(), main_window=self.main_window)
        popup.setWindowTitle("OGame Popup")
        popup.show()
        if self.main_window:
            self.main_window.popups.append(popup)
        return popup.web.page()


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    url = "https://lobby.ogame.gameforge.com/es_ES/"
    window = BrowserWindow(url=url)
    window.show()
    sys.exit(app.exec())
