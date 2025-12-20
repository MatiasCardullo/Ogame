from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import QUrl


class CustomWebPage(QWebEnginePage):
    """Maneja popups del navegador (Google login, universo, etc.)"""

    def __init__(self, profile, parent=None, main_window=None):
        super().__init__(profile, parent)
        self.main_window = main_window
        self.is_login_page = False  # Flag para detectar si es página de login

    def createWindow(self, _type):
        """
        Decide si crear popup o cargar en main_web.
        
        Crea popup si:
        1. Es login con URL no estándar (?language=ar, etc)
        2. Es ventana emergente desde main_web
        
        Carga en main_web si:
        - Es navegación normal dentro del juego
        """
        from popup_window import PopupWindow

        # Obtener URL actual de quién solicita el popup
        current_url = self.requestedUrl().toString() if hasattr(self, 'requestedUrl') else ""

        # Detectar si es login no estándar o emergente window.open() desde main_web
        should_use_popup = self._should_create_popup(current_url)

        if should_use_popup:
            # Crear popup para login/emergente
            popup = PopupWindow(profile=self.profile(), main_window=self.main_window)
            popup.show()

            if self.main_window is not None:
                try:
                    self.main_window.popups.append(popup)
                except Exception:
                    pass

            return popup.web.page()
        
        # Por defecto, cargar en main_web si existe
        if self.main_window and hasattr(self.main_window, 'main_web'):
            return self.main_window.main_web.page()
        
        # Fallback: crear popup si no existe main_web
        popup = PopupWindow(profile=self.profile(), main_window=self.main_window)
        popup.show()

        if self.main_window is not None:
            try:
                self.main_window.popups.append(popup)
            except Exception:
                pass

        return popup.web.page()

    def _should_create_popup(self, url: str) -> bool:
        """
        Detecta si debemos crear popup basado en la URL y contexto.
        
        Retorna True si:
        - Es URL de login no estándar (con ?language=ar, etc)
        - Es window.open() desde dentro del juego (main_web)
        """
        if not url:
            return False
        
        url_lower = url.lower()
        
        # ========== CASOS DE LOGIN ==========
        if "lobby.ogame.gameforge.com" in url_lower:
            # URL estándar de login = cargar en main_web
            if "/accounts" or "/hub" in url_lower:
                return False  # Usar main_web para login estándar
            else:
                return True
        
        # ========== VENTANAS EMERGENTES EXTERNAS ==========
        # Si no es OGame ni Gameforge, probablemente sea servicio externo (Google, etc)
        if "ogame" not in url_lower and "gameforge" not in url_lower:
            return True  # Popup para servicios externos
        
        # Por defecto, usar main_web (navegación normal dentro del juego)
        return False
