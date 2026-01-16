from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtCore import QUrl


class CustomWebPage(QWebEnginePage):
    """Maneja popups del navegador (Google login, universo, etc.)"""
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        pass  # No hacer nada = no imprimir mensajes

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
                except Exception as e:
                    print(f"[DEBUG] Error agregando popup a lista: {e}")
            
            print(f"[DEBUG] Popup creado para: {current_url}")
            return popup.web.page()
        else:
            # Cargar en main_web si es OGame
            if self.main_window and hasattr(self.main_window, 'main_web') and self.main_window.main_web:
                print(f"[DEBUG] Cargando en main_web: {current_url}")
                return self.main_window.pages_views[0]['web'].page()
            else:
                # Fallback: crear popup
                popup = PopupWindow(profile=self.profile(), main_window=self.main_window)
                popup.show()
                
                if self.main_window is not None:
                    try:
                        self.main_window.popups.append(popup)
                    except Exception:
                        pass
                
                print(f"[DEBUG] Popup creado (fallback): {current_url}")
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
            if "/accounts" in url_lower or "/hub" in url_lower:
                return False  # Usar main_web para login estándar
            else:
                return True
        else:
            return True  # Popup para servicios externos
