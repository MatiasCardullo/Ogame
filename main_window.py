from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QLabel, QTextEdit, QPushButton, QSystemTrayIcon, QComboBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEngineScript
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtGui import QIcon
from custom_page import CustomWebPage
from debris_tab import create_debris_tab
from fleet_tab import _refresh_scheduled_fleets_list, auto_send_scheduled_fleets, create_fleets_tab, save_scheduled_fleets, update_fleet_origin_combo
from panel import handle_main_web_resources, refresh_resources_panel
from communication_tab import create_comms_tab
from sprite_widget import SpriteWidget
import time, os, json
from js_scripts import (
    in_game, extract_meta_script, extract_resources_script, auction_listener,
    extract_planet_array, extract_fleets_script
)
from text import time_str_to_ms

logged = True
os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"

class MainWindow(QMainWindow):
    """Ventana principal de OGame."""

    def __init__(self, profile=None, url=None):
        super().__init__()
        self.setWindowTitle("OGame")

        # Profile
        profile = profile or QWebEngineProfile("ogame_profile", self)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        os.makedirs("profile_data", exist_ok=True)
        profile.setPersistentStoragePath(os.path.abspath("profile_data"))
        profile.setCachePath(os.path.abspath("profile_data/cache"))
        self.profile = profile

        # Tabs
        self.tabs = QTabWidget()

        # ----- Tab navegador -----
        self.browser_tab = QWidget()
        self.browser_box = QHBoxLayout()
        self.base_url = "https://s163-ar.ogame.gameforge.com"
        self.url_ingame = self.base_url + "/game/index.php?page=ingame"
        # Login
        self.login = self.web_engine(profile, url)
        if not logged :
            self.login.loadFinished.connect(self.on_open)
        self.browser_box.addWidget(self.login)
        self.browser_tab.setLayout(self.browser_box)
        self.tabs.addTab(self.browser_tab, "🌐 Navegador")

        # ----- Panel principal -----
        main_layout = QVBoxLayout()
        self.main_panel = QWidget()
        self.main_panel.setStyleSheet("""
            background-color: #000;
            color: #EEE;
        """)
        
        # Contenedor horizontal para sprite_widget + QWebEngineView
        top_container = QWidget()
        top_layout = QHBoxLayout()
        #top_layout.setContentsMargins(0, 0, 0, 0)
        #top_layout.setSpacing(1)
        
        self.sprite_widget = SpriteWidget()
        top_layout.addWidget(self.sprite_widget, 1)  # stretch factor = 1 para que ocupe espacio disponible
        
        # QWebEngineView integrado (el navegador del planeta actual)
        self.main_web_layout = QVBoxLayout()
        
        # Define pages with their URLs
        self.pages_config = [
            ("Main", f"{self.url_ingame}&component=overview"),
            ("Flotas", f"{self.url_ingame}&component=movement"),
            ("Imperio", f"{self.base_url}/game/index.php?page=standalone&component=empire"),
            ("Subasta", f"{self.url_ingame}&component=traderOverview#animation=false&page=traderAuctioneer")
        ]
        
        # Create web views for all pages
        # self.pages_views[i] = {'title': ..., 'url': ..., 'web': ..., 'container': ...}
        self.pages_views = []
        for i, (title, url) in enumerate(self.pages_config):
            web = self.web_engine(self.profile, url)
            container = QWidget()
            c_layout = QVBoxLayout()
            c_layout.setContentsMargins(0, 0, 0, 0)
            c_layout.addWidget(web)
            container.setLayout(c_layout)
            
            # Conectar extracción de flotas si es la página de Flotas (index 1)
            if i == 1:
                web.loadFinished.connect(lambda: self.on_fleets_page_loaded())
            # Conectar extracción de subasta
            if i == 3:
                web.loadFinished.connect(lambda: self.on_auction_page_loaded())
            
            # Monitorear cambios de URL para detectar desconexión
            web.urlChanged.connect(lambda url, page_idx=i: self.check_disconnection(url, page_idx))
            
            self.pages_views.append({
                'index': i,
                'title': title,
                'url': url,
                'web': web,
                'container': container
            })
        
        # Page 0 (Main) starts large in the main area
        self.main_web = self.pages_views[0]['web']
        self.main_web.setZoomFactor(0.75)
        self.main_web.setMinimumWidth(800)
        self.active_page_index = 0

        # Navbar uses wrapper actions so it always targets the active `self.main_web`
        self.navbar = QHBoxLayout()
        for text, action in [("💾", "save"), ("🏠", "home"), ("<", "back"), (">", "forward"), ("↻", "reload")]:
            btn = QPushButton(text)
            btn.setBaseSize(20, 20)
            if action == "save":
                btn.clicked.connect(self.save_html)
            elif action == "home":
                btn.clicked.connect(self.reload_default_url)
            else:
                btn.clicked.connect(lambda _, act=action: self.nav_action(act))
            self.navbar.addWidget(btn)

        self.main_web_layout.addLayout(self.navbar)
        self.main_web_layout.addWidget(self.main_web)

        # Side bar with custom tabs (VBoxLayout)
        side_bar = QWidget()
        side_bar_layout = QVBoxLayout()
        side_bar_layout.setContentsMargins(0, 0, 0, 0)
        side_bar_layout.setSpacing(0)
        
        self.tab_buttons = []
        for page_info in self.pages_views:
            idx = page_info['index']
            title = page_info['title']
            web = page_info['web']
            
            # Tab button (clickable header)
            tab_btn = QPushButton(title)
            tab_btn.setStyleSheet("text-align: left; padding: 5px;")
            tab_btn.clicked.connect(lambda checked, i=idx: self.on_tab_clicked(i))
            
            # Container for small preview
            preview_container = QWidget()
            preview_layout = QVBoxLayout()
            preview_layout.setContentsMargins(0, 0, 0, 0)
            preview_layout.setSpacing(0)
            preview_layout.addWidget(web)
            preview_container.setLayout(preview_layout)
            
            # Set zoom for all pages except the active one
            if idx != 0:
                web.setZoomFactor(0.25)
                web.setMinimumHeight(110)
                web.setMinimumWidth(220)
            
            side_bar_layout.addWidget(tab_btn)
            side_bar_layout.addWidget(preview_container)
            
            self.tab_buttons.append(tab_btn)
            page_info['preview_container'] = preview_container
        
        side_bar_layout.addStretch()
        side_bar.setLayout(side_bar_layout)
        side_bar.setFixedWidth(240)

        top_layout.addLayout(self.main_web_layout, 1)
        top_layout.addWidget(side_bar)

        # Configurar extracción de datos en main_web (only for Main tab)
        self.setup_main_web_extraction()
        
        top_container.setLayout(top_layout)
        main_layout.addWidget(top_container)
        
        # ----- Tabs internos para recursos/flotas -----
        self.panel_tabs = QTabWidget()
        
        # Tab 1: Recursos y Colas
        resources_tab = QWidget()
        resources_layout = QVBoxLayout()
        self.resources_label = QTextEdit()
        self.resources_label.setReadOnly(True)
        resources_layout.addWidget(self.resources_label)
        resources_tab.setLayout(resources_layout)
        self.panel_tabs.addTab(resources_tab, "📦 Recursos y Colas")
        
        # Tab 2: Flotas en Movimiento + Programador de Naves
        fleets_tab = create_fleets_tab(self)
        self.panel_tabs.addTab(fleets_tab, "🚀 Flotas en Movimiento")
        
        # Tab 3: Debris y Reciclaje
        debris_tab = create_debris_tab(self)
        self.panel_tabs.addTab(debris_tab, "♻️ Debris y Reciclaje")
        
        main_layout.addWidget(self.panel_tabs, 1)  # stretch factor = 1

        # ----- Control de intervalo de actualización -----
        footer_layout = QHBoxLayout()
        update_interval_layout = QHBoxLayout()
        update_interval_layout.addWidget(QLabel("⏱️ Intervalo de actualización:"))
        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItem("1 segundo", 1000)
        self.update_interval_combo.addItem("10 segundo", 10000)
        self.update_interval_combo.addItem("30 segundos", 30000)
        self.update_interval_combo.addItem("1 minuto", 60000)
        self.update_interval_combo.setCurrentIndex(0)  # Default: 1 segundos
        self.update_interval_combo.currentIndexChanged.connect(self.on_update_interval_changed)
        update_interval_layout.addWidget(self.update_interval_combo)
        update_interval_layout.addStretch()
        
        self._notif_label = QLabel("")
        self._notif_label.setStyleSheet("color: #0f0; font-weight: bold; padding: 8px;")
        footer_layout.addLayout(update_interval_layout)
        footer_layout.addWidget(self._notif_label)
        main_layout.addLayout(footer_layout)

        self.main_panel.setLayout(main_layout)
        self.tabs.addTab(self.main_panel, "📊 Panel Principal")
        self.tabs.setCurrentWidget(self.main_panel)

        # ----- Tab Comunicaciones -----
        comunication_tab = create_comms_tab("https://TU-DOMINIO-O-NGROK:3000",self)
        self.tabs.addTab(comunication_tab, "Comunicaciones")

        self.setCentralWidget(self.tabs)

        # Tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-games"))
        self.tray_icon.setVisible(True)

        # Intervalo de actualización (en ms)
        self.current_update_interval = 1000  # Default: 1 segundos
        self.panel_timer = QTimer(self)
        self.panel_timer.setInterval(self.current_update_interval)
        self.panel_timer.timeout.connect(self.refresh_main_panel)
        self.panel_timer.start()

        # Timers
        self.timer_global = QTimer(self)
        self.timer_global.setInterval(1000)
        self.timer_global.timeout.connect(self.increment_all_planets)
        self.timer_global.start()
        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(1000)
        self.queue_timer.timeout.connect(self.check_queues)
        self.queue_timer.start()

        self.fleet_sender_timer = QTimer(self)
        self.fleet_sender_timer.setInterval(60000)
        self.fleet_sender_timer.timeout.connect(lambda: auto_send_scheduled_fleets(self))
        self.fleet_sender_timer.start()

        # Timer para actualizar flotas desde pages_views[1]
        self.fleets_update_timer = QTimer(self)
        self.fleets_update_timer.setInterval(60000)  # Cada 1 minuto
        self.fleets_update_timer.timeout.connect(self.update_fleets_from_page)
        self.fleets_update_timer.start()

        self.notified_queues = set()
        self.popups = []
        
        self.main_web_queue_memory = {}

        # DATA
        # planets_data keyed by planet_key (name|coords) -> dict(coords, resources, queues(list), last_update)
        # Esto permite tener múltiples planetas con el mismo nombre pero diferentes coordenadas
        self.planets_data = {}
        # global queues (research, etc.) keyed by queue id
        self.research_data = {}
        # Intentar cargar datos de planetas desde cache
        self.cache_loaded = self.load_data()
        
        # Fleet data storage
        self.fleets_data = []
        self.last_fleet_update = 0
        self.fleet_slots = {"current": 0, "max": 0}
        self.exp_slots = {"current": 0, "max": 0}
        
        # Envíos programados de naves
        self.scheduled_fleets = []
        self.load_scheduled_fleets()
        
        self.showMaximized()
        
    def load_scheduled_fleets(self):
        """Carga las misiones programadas desde un archivo JSON"""
        try:
            if os.path.exists("scheduled_fleets.json"):
                with open("scheduled_fleets.json", "r", encoding="utf-8") as f:
                    self.scheduled_fleets = json.load(f)
                    print(f"✅ Cargadas {len(self.scheduled_fleets)} misiones programadas")
                    # Actualizar lista visual después de cargar
                    if hasattr(self, 'fleet_scheduled_list'):
                        _refresh_scheduled_fleets_list(self)
        except Exception as e:
            print(f"⚠️ Error cargando misiones: {e}")
    
    def load_data(self):
        """Carga los datos de planetas e investigaciones desde JSON"""
        try:
            if os.path.exists("research_data.json"):
                with open("research_data.json", "r", encoding="utf-8") as f:
                    self.research_data = json.load(f)
                    print(f"✅ Cargados datos de {len(self.research_data)} investigaciones desde cache")
            if os.path.exists("planets_data.json"):
                with open("planets_data.json", "r", encoding="utf-8") as f:
                    self.planets_data = json.load(f)
                    print(f"✅ Cargados datos de {len(self.planets_data)} planetas desde cache")
                    # Actualizar el combo de planetas y panel
                    if hasattr(self, 'fleet_planet_combo'):
                        update_fleet_origin_combo(self)
                    if hasattr(self, 'main_panel'):
                        self.refresh_main_panel()
                    return True
            return False
        except Exception as e:
            print(f"⚠️ Error cargando datos: {e}")
            return False
    
    def save_planets_data(self):
        """Guarda los datos de planetas en un archivo JSON"""
        try:
            if self.planets_data:
                with open("planets_data.json", "w", encoding="utf-8") as f:
                    json.dump(self.planets_data, f, indent=2, ensure_ascii=False)
                    print(f"✅ Guardados datos de {len(self.planets_data)} planetas en cache")
        except Exception as e:
            print(f"⚠️ Error guardando datos de planetas: {e}")

    def save_research_data(self):
        """Guarda los datos de investigaciones en un archivo JSON"""
        self.research_data = {k: v for k, v in self.research_data.items() if v.get("end", 0) > time.time()}
        try:
            with open("research_data.json", "w", encoding="utf-8") as f:
                json.dump(self.research_data, f, indent=2, ensure_ascii=False)
                print(f"✅ Guardados datos de {len(self.research_data)} investigaciones en cache")
        except Exception as e:
            print(f"⚠️ Error guardando datos de investigaciones: {e}")

    def web_engine(self, profile, url):
        web = QWebEngineView()
        page = CustomWebPage(profile, web, main_window=self)
        web.setPage(page)
        web.load(QUrl(url))
        return web

    def nav_action(self, action):
        """Wrapper to call navigation on the active main web view."""
        try:
            if not hasattr(self, 'main_web') or self.main_web is None:
                return
            if action == 'back':
                self.main_web.back()
            elif action == 'forward':
                self.main_web.forward()
            elif action == 'reload':
                self.main_web.reload()
        except Exception as e:
            print('[DEBUG] nav_action error:', e)

    def check_disconnection(self, url, page_idx):
        """Detecta si la URL cambió a la página de lobby (desconexión)."""
        try:
            url_str = url.toString() if hasattr(url, 'toString') else str(url)
            # print(f"[DEBUG] pages_views[{page_idx}] URL cambió a: {url_str}")
            
            # Detectar si es la URL de lobby (desconexión)
            if "lobby.ogame.gameforge.com" in url_str and "hub" in url_str:
                print(f"[DEBUG] ⚠️  Desconexión detectada en página {page_idx}! Ejecutando on_open()...")
                QTimer.singleShot(500, self.on_open)
        except Exception as e:
            print(f'[DEBUG] check_disconnection error: {e}')

    def reload_default_url(self):
        """Recarga la URL preestablecida de la página actualmente seleccionada."""
        try:
            if not hasattr(self, 'active_page_index') or not hasattr(self, 'pages_views'):
                return
            
            # Obtener la página activa
            active_page = self.pages_views[self.active_page_index]
            url = active_page['url']
            web = active_page['web']
            
            print(f"[DEBUG] Recargando página activa {self.active_page_index}: {url}")
            web.load(QUrl(url))
        except Exception as e:
            print(f'[DEBUG] reload_default_urls error: {e}')

    def reload_other_pages_urls(self):
        """Recarga las URLs preestablecidas de todas las páginas excepto Main (index 0), solo si están en una URL diferente."""
        try:
            if not hasattr(self, 'pages_views'):
                return
            
            print("[DEBUG] Recargando URLs de páginas secundarias...")
            for i, page_info in enumerate(self.pages_views):
                # Saltar la página Main (index 0)
                if i == 0:
                    continue
                url = page_info['url']
                web = page_info['web']
                current_url = web.url().toString()
                # Solo recargar si la URL actual es diferente a la preestablecida
                if current_url != url:
                    print(f"[DEBUG] Cargando página {i}: {url}")
                    web.load(QUrl(url))
                else:
                    print(f"[DEBUG] Página {i} ya está en la URL correcta, omitiendo recarga")
        except Exception as e:
            print(f'[DEBUG] reload_other_pages_urls error: {e}')

    def on_update_interval_changed(self):
        """Actualiza el intervalo de los timers cuando el usuario cambia la selección."""
        new_interval = self.update_interval_combo.currentData()
        if new_interval is not None:
            self.current_update_interval = new_interval
            self.panel_timer.setInterval(new_interval)
            self.panel_timer
            print(f"[DEBUG] Intervalo de actualización cambiado a {new_interval}ms")
            self.refresh_main_panel()

    def setup_main_web_extraction(self):
        """Configura main_web para extraer datos automáticamente cuando carga una página."""
        if not hasattr(self, 'main_web'):
            return

        # Ensure we don't attach multiple times
        try:
            self.main_web.loadFinished.disconnect(self.on_main_web_loaded)
        except Exception:
            pass

        self.main_web.loadFinished.connect(self.on_main_web_loaded)

        # Keep navbar and other controls in sync (they call self.main_web dynamically)

    def on_main_web_loaded(self):
        """Cuando main_web carga una página, extrae datos si estamos en el juego."""
        def check_ingame(is_ingame):
            if is_ingame:
                # Extraer metadata
                self.main_web.page().runJavaScript(extract_meta_script, self.handle_main_web_meta)
        
        self.main_web.page().runJavaScript(in_game, check_ingame)

    def save_html(self):
            def handle_html(html):
                path, _ = QFileDialog.getSaveFileName(self, "Guardar HTML", "pagina.html", "Archivos HTML (*.html)")
                if path:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(html)
            self.main_web.page().toHtml(handle_html)

    def on_tab_clicked(self, clicked_index):
        """Swap the clicked page into the main area, move current main to its tab."""
        try:
            if clicked_index == self.active_page_index:
                return  # Same page, no swap needed

            # Get the current large view and the clicked small view
            current_large = self.main_web
            current_page_idx = self.active_page_index

            clicked_page = self.pages_views[clicked_index]
            clicked_web = clicked_page['web']
            clicked_container = clicked_page['preview_container']

            # Get the preview container for the current large page
            current_page = self.pages_views[current_page_idx]
            current_container = current_page['preview_container']

            # Remove current large from main layout
            try:
                self.main_web_layout.removeWidget(current_large)
            except Exception:
                pass
            current_large.setParent(None)

            # Remove clicked small from its preview container
            try:
                clicked_container.layout().removeWidget(clicked_web)
            except Exception:
                pass
            clicked_web.setParent(None)

            # Move current large to its preview container (shrink to 0.25)
            current_large.setZoomFactor(0.25)
            current_large.setMinimumHeight(110)
            current_large.setMinimumWidth(220)
            current_container.layout().addWidget(current_large)

            # Move clicked small to main area (enlarge to 0.75)
            clicked_web.setZoomFactor(0.75)
            clicked_web.setMinimumWidth(800)
            self.main_web_layout.addWidget(clicked_web)

            # Update references
            self.main_web = clicked_web
            self.active_page_index = clicked_index

            # Only attach extraction if switching to Main tab (index 0)
            if clicked_index == 0:
                self.setup_main_web_extraction()
            else:
                # Disconnect extraction from non-Main tabs
                try:
                    self.main_web.loadFinished.disconnect(self.on_main_web_loaded)
                except Exception:
                    pass

        except Exception as e:
            print('[DEBUG] on_tab_clicked error:', e)
    
    def handle_main_web_meta(self, data):
        """Maneja metadata del planeta en main_web."""
        if not data:
            print("main web - no data")
            return

        language = data.get('ogame-language', 'en')
        player = data.get('ogame-player-name', '—')
        universe_url = data.get('ogame-universe', '—')
        universe = data.get('ogame-universe-name', '—')
        coords = data.get('ogame-planet-coordinates', '0:0:0')
        planet = data.get('ogame-planet-name', '—')
        planet_id = data.get('ogame-planet-id', None)
        planet_type = data.get('ogame-planet-type', None)
        speed = data.get('ogame-universe-speed', '0')
        speed_fleet_holding = data.get('ogame-universe-speed-fleet-holding', '0')
        speed_fleet_peaceful = data.get('ogame-universe-speed-fleet-peaceful', '0')
        speed_fleet_war = data.get('ogame-universe-speed-fleet-war', '0')

        self.current_main_web_planet = planet
        self.current_main_web_coords = coords
        self.current_main_web_is_moon = planet_type == 'moon'
        self.current_main_web_planet_id = planet_id

        # Extraer recursos
        self.main_web.page().runJavaScript(extract_resources_script, lambda data: handle_main_web_resources(self, data))

    def on_open(self):
        js = """
        (async function() {
            try {
                function sleep(ms) {
                    return new Promise(resolve => setTimeout(resolve, ms));
                }
                let targetBtn = null;
                let intentos = 0;
                while (!targetBtn && intentos < 50) {
                    const buttons = document.querySelectorAll('button.button.button-default.button-md');
                    for (const btn of buttons) {
                        if (btn.textContent.includes("Jugado por última vez")) {
                            targetBtn = btn;
                            break;
                        }
                    }
                    if (!targetBtn) {
                        console.log('[AUTOCLICK] Esperando botón... intento ', intentos);
                        await sleep(5000);
                        intentos++;
                    }
                }
                if (!targetBtn) {
                    console.log('[AUTOCLICK] No se encontró el botón después de esperar.');
                    return false;
                }
                console.log('[AUTOCLICK] Click en:', targetBtn.textContent.trim());
                targetBtn.click();
                return true;
            } catch(e) {
                console.log('[AUTOCLICK ERROR]', e);
                return false;
            }
        })();
        """
        def done(result):            
            if not self.cache_loaded:
                # Si no hay cache, cargar planetas desde el navegador
                print("[DEBUG] Cache no encontrado, cargando planetas desde navegador...")
                QTimer.singleShot(1000, self.load_other_planets)
            else:
                print("[DEBUG] ✅ Datos de planetas cargados desde cache")
            
            # Timer para recargar las páginas secundarias después de on_open
            QTimer.singleShot(3000, self.reload_other_pages_urls)
        
        url = self.pages_views[0]['web'].url().toString() 
        if "loading" in url or self.pages_views[0]['url'] in url:
            QTimer.singleShot(3000, self.reload_other_pages_urls)
        else:
            QTimer.singleShot(3000, lambda: self.login.page().runJavaScript(js, done))

    def load_other_planets(self):
        """Busca los enlaces de otros planetas en main_web y los carga secuencialmente."""
        
        def retry_load_other_planets(attempt):
            """Reintentar búsqueda de planetas con delay."""
            max_attempts = 10
            delay_ms = 5000
            
            if attempt > max_attempts:
                print(f"[DEBUG] ⚠️  No se encontraron planetas después de {max_attempts} intentos")
                return
            
            print(f"[DEBUG] Reintentando búsqueda de planetList (intento {attempt}/{max_attempts})...")
            
            def handle_retry(planets):
                if planets and isinstance(planets, list):
                    print(f"[DEBUG] ✓ Encontrados {len(planets)} planetas en intento {attempt}: {[p['name'] for p in planets]}")
                    self.planets_to_load = planets
                    self.current_planet_index = 0
                    self.load_next_planet()
                else:
                    # Reintentar
                    QTimer.singleShot(delay_ms, lambda: retry_load_other_planets(attempt + 1))
            
            try:
                self.main_web.page().runJavaScript(extract_planet_array, handle_retry)
            except Exception as e:
                print(f"[DEBUG] Error ejecutando script (intento {attempt}):", e)
                QTimer.singleShot(delay_ms, lambda: retry_load_other_planets(attempt + 1))
        
        def handle_planets(planets):
            print(f"[DEBUG] Resultado del script: {planets}")
            if planets and isinstance(planets, list):
                print(f"[DEBUG] ✓ Encontrados {len(planets)} planetas: {[p['name'] for p in planets]}")
                # Almacenar la lista y empezar a cargar
                self.planets_to_load = planets
                self.current_planet_index = 0
                self.load_next_planet()
                return
            
            # Si no encontramos, reintentar
            retry_load_other_planets(1)
        
        # Ejecutar el script en main_web
        try:
            print("[DEBUG] Ejecutando búsqueda de planetList en main_web (intento 1)...")
            self.main_web.page().runJavaScript(extract_planet_array, handle_planets)
        except Exception as e:
            print("[DEBUG] Error ejecutando script de planetList:", e)
            retry_load_other_planets(2)

    def load_next_planet(self):
        """Carga el siguiente planeta de la lista usando main_web."""
        if not hasattr(self, 'planets_to_load') or self.current_planet_index >= len(self.planets_to_load):
            print("[DEBUG] ✓ Todos los planetas cargados")
            return
        
        planet = self.planets_to_load[self.current_planet_index]
        planet_name = planet.get('name', 'Unknown')
        planet_id = planet.get('id', '')
        moon = planet.get('moon')  # Puede ser None o dict con {id, name}
        
        # Construir URL usando planet_id (cp = current planet)
        planet_url = f"{self.url_ingame}&component=overview&cp={planet_id}"
        
        print(f"[DEBUG] Cargando planeta {self.current_planet_index + 1}/{len(self.planets_to_load)}: {planet_name} (ID: {planet_id}) en main_web")

        def finish_and_next():
            """Termina la extracción actual y pasa al siguiente planeta."""
            QTimer.singleShot(500, self.load_next_planet)

        def on_planet_load_finished(ok=True):
            """Callback cuando termina de cargar la página del planeta."""
            try:
                self.main_web.loadFinished.disconnect(on_planet_load_finished)
            except Exception:
                pass
            print(f"[DEBUG] Página de {planet_name} cargada en main_web, esperando datos...")
            # Los datos se extraerán automáticamente vía on_main_web_loaded y los handlers
            
            # Si hay luna, cargarla después
            if moon and moon.get('id'):
                QTimer.singleShot(1200, load_moon_for_current_planet)
            else:
                QTimer.singleShot(1200, finish_and_next)

        def load_moon_for_current_planet():
            """Carga la luna del planeta actual si existe."""
            if not hasattr(self, 'planets_to_load') or self.current_planet_index == 0:
                return
            
            # El índice ya fue incrementado, así que usamos current_planet_index - 1
            planet = self.planets_to_load[self.current_planet_index - 1]
            moon = planet.get('moon')
            
            if not moon or not moon.get('id'):
                return
            
            moon_id = moon.get('id')
            moon_name = moon.get('name', 'Moon')
            
            # Guardar la referencia al planeta padre antes de cargar la luna
            # Usar el mismo sistema de ID que en update_planet_data
            import hashlib
            parent_coords = self.current_main_web_coords
            parent_id = hashlib.sha1(parent_coords.encode("utf-8")).hexdigest()[:16]
            self.current_planet_parent_key = parent_id
            
            # Construir URL usando moon_id
            moon_url = f"{self.url_ingame}&component=overview&cp={moon_id}"
            
            print(f"[DEBUG] Cargando luna {moon_name} (ID: {moon_id}) en main_web")

            def finish_and_next():
                """Termina la extracción de luna y pasa al siguiente planeta."""
                QTimer.singleShot(500, self.load_next_planet)

            def on_moon_load_finished(ok=True):
                """Callback cuando termina de cargar la página de la luna."""
                try:
                    self.main_web.loadFinished.disconnect(on_moon_load_finished)
                except Exception:
                    pass
                print(f"[DEBUG] Página de {moon_name} cargada en main_web, esperando datos...")
                # Los datos se extraerán automáticamente vía on_main_web_loaded y los handlers
                QTimer.singleShot(1200, finish_and_next)

            try:
                self.main_web.loadFinished.connect(on_moon_load_finished)
                self.main_web.load(QUrl(moon_url))
            except Exception as e:
                print('[DEBUG] Error cargando luna en main_web:', e)
                QTimer.singleShot(1000, finish_and_next)
        
        try:
            self.main_web.loadFinished.connect(on_planet_load_finished)
            self.main_web.load(QUrl(planet_url))
        except Exception as e:
            print('[DEBUG] Error cargando planeta en main_web:', e)
            QTimer.singleShot(1000, finish_and_next)

        # avanzar índice inmediatamente
        self.current_planet_index += 1

    def on_fleets_page_loaded(self):
        """Extrae información de flotas cuando carga pages_views[1]"""
        fleets_web = self.pages_views[1]['web']
        fleets_web.page().runJavaScript(extract_fleets_script, self.handle_fleets_data)

    def on_auction_page_loaded(self):
        """Extrae información de la subasta cuando carga pages_views[3]"""
        auction_web = self.pages_views[3]['web']

        def handle_auction_data(data):
            print(data)
            if data:
                wait = data.get('nextAuction', None)
                if wait:
                    print(f"Next auction in {wait}")
                    QTimer.singleShot(time_str_to_ms(wait), auction_web.reload)
                else:
                    wait = data.get('endAuction', "approx. 5m")
                    print(f"End of auction in {wait}")
                    wait = wait.split()[1]
                    QTimer.singleShot((time_str_to_ms(wait) - 300001), auction_web.reload)
                

        auction_web.page().runJavaScript(auction_listener, handle_auction_data)

    def update_fleets_from_page(self):
        """Actualiza fleets_data extrayendo datos de pages_views[1]"""
        if not hasattr(self, 'pages_views') or len(self.pages_views) < 2:
            return
        
        fleets_web = self.pages_views[1]['web']
        fleets_web.page().runJavaScript(extract_fleets_script, self.handle_fleets_data)

    def handle_fleets_data(self, data):
        """Procesa y almacena los datos de flotas extraídos del HTML"""
        if not data:
            self.fleets_data = []
            self.fleet_slots = {"current": 0, "max": 0}
            self.exp_slots = {"current": 0, "max": 0}
            return
        
        if isinstance(data, dict) and "fleets" in data:
            self.fleets_data = data.get("fleets", [])
            self.fleet_slots = data.get("fleetSlots", {"current": 0, "max": 0})
            self.exp_slots = data.get("expSlots", {"current": 0, "max": 0})
            #print(f"[FLEETS] ✅ Cargadas {len(self.fleets_data)} flotas desde pages_views[1]")
            #print(f"[FLEETS] Slots - Flotas: {self.fleet_slots}, Expediciones: {self.exp_slots}")
            # Actualizar timestamp
            self.last_fleet_update = time.time()
            try:
                with open("fleets_data.json", "w", encoding="utf-8") as f:
                    json.dump(self.fleets_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"⚠️ Error guardando misiones: {e}")
        else:
            print("[FLEETS] ⚠️  Formato de datos de flotas inválido")
            self.fleets_data = []
            self.fleet_slots = {"current": 0, "max": 0}
            self.exp_slots = {"current": 0, "max": 0}

    # ====================================================================
    #  PANEL PRINCIPAL
    # ====================================================================
    def refresh_main_panel(self):
        """Actualiza la sección del panel de recursos"""
        refresh_resources_panel(self)

    # ====================================================================
    #  Incremento pasivo
    # ====================================================================
    def increment_all_planets(self):
        if not self.planets_data:
            return
        now = time.time()

        for planet_key, pdata in self.planets_data.items():
            r = pdata["resources"]
            elapsed = now - r.get("last_update", now)
            if elapsed <= 0:
                continue

            r["last_update"] = now
            r["metal"] += r.get("prod_metal", 0) * elapsed
            r["crystal"] += r.get("prod_crystal", 0) * elapsed
            r["deuterium"] += r.get("prod_deuterium", 0) * elapsed

    # ====================================================================
    #  CHECK QUEUES
    # ====================================================================
    def check_queues(self):
        now = int(time.time())
        active_ids = set()

        for planet_key, pdata in self.planets_data.items():
            coords = pdata.get("coords", "0:0:0")
            planet_name = pdata.get("name", "")
            for q in pdata.get("queues", []):
                qid = q.get("id")
                if not qid:
                    continue
                active_ids.add(qid)
                end = int(q.get("end", now))
                if end <= now and qid not in self.notified_queues:
                    try:
                        self.show_notification(
                            "✅ Cola completada",
                            f"{planet_name} ({coords}): {q.get('label','')} {q.get('name','')}"
                        )
                    except Exception as e:
                        print("[DEBUG] Error al enviar notificación:", e)
                    self.notified_queues.add(qid)

        # Also consider global queues (researches)
        for q in getattr(self, 'research_data', {}).values():
            qid = q.get("id")
            if not qid:
                continue
            active_ids.add(qid)
            end = int(q.get("end", now))
            if end <= now and qid not in self.notified_queues:
                try:
                    self.show_notification(
                        "✅ Cola completada",
                        f"{q.get('label','')} {q.get('name','')}"
                    )
                except Exception as e:
                    print("[DEBUG] Error al enviar notificación:", e)
                self.notified_queues.add(qid)

        # Prune notified set
        to_remove = [qid for qid in list(self.notified_queues) if qid not in active_ids]
        for qid in to_remove:
            try:
                self.notified_queues.remove(qid)
            except KeyError:
                pass

    # ====================================================================
    #  NOTIFICACIONES
    # ====================================================================
    def show_notification(self, title, message):
        print(f"[NOTIFY] {title}: {message}")

        if hasattr(self, "tray_icon") and self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 5000)

        try:
            self._notif_label.setText(f"🔔 {title}: {message}")
            #QTimer.singleShot(8000, lambda: self._notif_label.setText(""))
        except Exception as e:
            print("[DEBUG] Error al mostrar notificación:", e)

    def closeEvent(self, event):
        """Guardar datos al cerrar la aplicación"""
        self.login.page().deleteLater()
        for page in self.pages_views:
            web = page['web']
            web.page().deleteLater()
        save_scheduled_fleets(self.scheduled_fleets)
        self.save_research_data()
        self.save_planets_data()
        event.accept()