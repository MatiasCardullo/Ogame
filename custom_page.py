from PyQt6.QtWebEngineCore import QWebEnginePage


class CustomWebPage(QWebEnginePage):
    """Maneja popups del navegador (Google login, universo, etc.)"""

    def __init__(self, profile, parent=None, main_window=None):
        super().__init__(profile, parent)
        self.main_window = main_window

    def createWindow(self, _type):
        """Crea una nueva ventana emergente usando la clase del main_window."""
        # Importar localmente (solo cuando se necesita) para evitar import circular
        from browser_window import BrowserWindow

        popup = BrowserWindow(profile=self.profile(), main_window=self.main_window, is_popup=True)
        popup.setWindowTitle("OGame Popup")
        popup.show()

        if self.main_window:
            self.main_window.popups.append(popup)
        return popup.web.page()
