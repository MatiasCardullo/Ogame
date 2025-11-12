from PyQt6.QtWebEngineCore import QWebEnginePage


class CustomWebPage(QWebEnginePage):
    """Maneja popups del navegador (Google login, universo, etc.)"""

    def __init__(self, profile, parent=None, main_window=None):
        super().__init__(profile, parent)
        self.main_window = main_window

    def createWindow(self, _type):
        """Crea una nueva ventana emergente usando la clase del main_window."""
        # Importar localmente (solo cuando se necesita) para evitar import circular
        from popup_window import PopupWindow

        popup = PopupWindow(profile=self.profile(), main_window=self.main_window)
        popup.show()

        if self.main_window is not None:
            try:
                self.main_window.popups.append(popup)
            except Exception:
                pass

        return popup.web.page()
