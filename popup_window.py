from PyQt6.QtWidgets import (
    QMainWindow, QHBoxLayout, QWidget, QToolBar, QPushButton, QFileDialog
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl
import os

from custom_page import CustomWebPage

class PopupWindow(QMainWindow):
    """Ventana popup OGame"""

    def __init__(self, profile=None, url=None, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("OGame Popup")

        # Profile persistente (para mantener sesión)
        profile = profile or QWebEngineProfile("ogame_profile", self)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        os.makedirs("profile_data", exist_ok=True)
        profile.setPersistentStoragePath(os.path.abspath("profile_data"))
        profile.setCachePath(os.path.abspath("profile_data/cache"))

        # WebEngineView
        self.web = QWebEngineView()
        self.page = CustomWebPage(profile, self.web, main_window=self.main_window)
        self.web.setPage(self.page)
        if url:
            self.web.load(QUrl(url))

        # Toolbar simple
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        for text, func in [("<", self.web.back), (">", self.web.forward), ("↻", self.web.reload), ("💾", self.save_html)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            self.toolbar.addWidget(btn)

        # Layout principal
        self.container = QWidget()
        self.layout = QHBoxLayout()
        self.layout.addWidget(self.web)
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

    # -------------------------------------------------------------
    # GUARDAR HTML
    # -------------------------------------------------------------
    def save_html(self):
        def handle_html(html):
            path, _ = QFileDialog.getSaveFileName(self, "Guardar HTML", "pagina.html", "Archivos HTML (*.html)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
        self.web.page().toHtml(handle_html)

    # -------------------------------------------------------------
    # Cierre
    # -------------------------------------------------------------
    def closeEvent(self, event):
        if self.main_window and self in getattr(self.main_window, "popups", []):
            try:
                self.main_window.popups.remove(self)
            except:
                pass
        super().closeEvent(event)
