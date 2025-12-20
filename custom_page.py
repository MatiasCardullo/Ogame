from PyQt6.QtWebEngineCore import QWebEnginePage


class CustomWebPage(QWebEnginePage):
    """Maneja popups del navegador (Google login, universo, etc.)"""

    def __init__(self, profile, parent=None, main_window=None):
        super().__init__(profile, parent)
        self.main_window = main_window

    def createWindow(self, _type):
        """Carga en main_web en lugar de crear una ventana emergente."""
        # En lugar de abrir un popup, cargar en main_web si existe
        if self.main_window and hasattr(self.main_window, 'main_web'):
            return self.main_window.main_web.page()
        
        # Fallback: crear un popup si no existe main_web
        from popup_window import PopupWindow

        popup = PopupWindow(profile=self.profile(), main_window=self.main_window)
        popup.show()

        if self.main_window is not None:
            try:
                self.main_window.popups.append(popup)
            except Exception:
                pass

        return popup.web.page()
