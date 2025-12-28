from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QLabel, QTextEdit, QPushButton, QSystemTrayIcon, QComboBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtGui import QIcon
from custom_page import CustomWebPage
from debris_tab import create_debris_tab
from fleet_tab import _refresh_scheduled_fleets_list, auto_send_scheduled_fleets, create_fleets_tab, save_scheduled_fleets, update_fleet_origin_combo, update_fleets
from panel import refresh_fleets_panel, refresh_resources_panel, update_planet_data
from sprite_widget import SpriteWidget
from datetime import timedelta
import time, os, json
from js_scripts import (
    in_game, extract_meta_script, extract_resources_script,
    extract_queue_functions, extract_auction_script, extract_planet_array
)
from worker import FleetWorker

logged = True
#os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"

class MainWindow(QMainWindow):
    """Ventana principal de OGame."""

    def __init__(self, profile=None, url=None):
        super().__init__()
        self.setWindowTitle("OGame — Main")

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
        self.base_url = "https://s163-ar.ogame.gameforge.com/game/index.php"

        # Login
        self.login = self.web_engine(profile, url)
        if logged :
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
        self.main_panel.setLayout(main_layout)

        # Panel Principal
        
        # Contenedor horizontal para sprite_widget + QWebEngineView
        top_container = QWidget()
        top_layout = QHBoxLayout()
        #top_layout.setContentsMargins(0, 0, 0, 0)
        #top_layout.setSpacing(1)
        
        self.sprite_widget = SpriteWidget()
        top_layout.addWidget(self.sprite_widget, 1)  # stretch factor = 1 para que ocupe espacio disponible
        
        # QWebEngineView integrado (el navegador del planeta actual)
        self.web_layout = QVBoxLayout()
        self.main_web = self.web_engine(self.profile, self.base_url)
        self.main_web.setZoomFactor(0.7)
        self.main_web.setMinimumWidth(1000)
        self.toolbar = QHBoxLayout()
        for text, func in [("<", self.main_web.back), (">", self.main_web.forward), ("↻", self.main_web.reload), ("💾", self.save_html)]:
            btn = QPushButton(text)
            btn.setBaseSize(20, 20)
            btn.clicked.connect(func)
            self.toolbar.addWidget(btn)
        self.web_layout.addLayout(self.toolbar)
        self.web_layout.addWidget(self.main_web)
        top_layout.addLayout(self.web_layout)
                
        # Configurar extracción de datos en main_web
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
        
        self.tabs.addTab(self.main_panel, "📊 Panel Principal")

        # ----- Subasta -----
        self.auction_tab = QWidget()
        auction_layout = QVBoxLayout()
        self.auction_text = QTextEdit()
        self.auction_text.setReadOnly(True)
        auction_layout.addWidget(QLabel("🏆 Subasta"))
        auction_layout.addWidget(self.auction_text)
        self.auction_refresh_btn = QPushButton("Actualizar subasta")
        self.auction_refresh_btn.clicked.connect(self.update_auction)
        auction_layout.addWidget(self.auction_refresh_btn)
        self.auction_tab.setLayout(auction_layout)
        self.tabs.addTab(self.auction_tab, "🏆 Subasta")

        self.setCentralWidget(self.tabs)

        # Tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-games"))
        self.tray_icon.setVisible(True)

        # DATA
        # planets_data keyed by planet_key (name|coords) -> dict(coords, resources, queues(list), last_update)
        # Esto permite tener múltiples planetas con el mismo nombre pero diferentes coordenadas
        self.planets_data = {}
        # global queues (research, etc.) keyed by queue id
        self.research_data = {}

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
        # Fleet update timer
        self.fleet_timer = QTimer(self)
        self.fleet_timer.setInterval(60000)
        self.fleet_timer.timeout.connect(lambda: update_fleets(self))
        self.fleet_timer.start()

        self.fleet_sender_timer = QTimer(self)
        self.fleet_sender_timer.setInterval(5000)
        self.fleet_sender_timer.timeout.connect(lambda: auto_send_scheduled_fleets(self))
        self.fleet_sender_timer.start()

        self.notified_queues = set()
        self.popups = []
        
        self.main_web_queue_memory = {}
        
        # Fleet data storage
        self.fleets_data = []
        self.last_fleet_update = 0
        
        # Envíos programados de naves
        self.scheduled_fleets = []
        self.load_scheduled_fleets()
        
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
        
        self.main_web.loadFinished.connect(self.on_main_web_loaded)

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
    
    def handle_main_web_meta(self, data):
        """Maneja metadata del planeta en main_web."""
        if not data:
            return
                
        player = data.get('ogame-player-name', '—')
        universe = data.get('ogame-universe-name', '—')
        coords = data.get('ogame-planet-coordinates', '—')
        planet = data.get('ogame-planet-name', '—')
        planet_id = data.get('ogame-planet-id', None)  # Debe venir del JS

        # Detectar si es luna (probablemente el nombre contenga "Moon" o similar)
        is_moon = 'moon' in planet.lower() if planet else False

        self.current_main_web_planet = planet
        self.current_main_web_coords = coords
        self.current_main_web_is_moon = is_moon
        self.current_main_web_planet_id = planet_id

        # Extraer recursos
        self.main_web.page().runJavaScript(extract_resources_script, self.handle_main_web_resources)

    def handle_main_web_resources(self, data):
        """Maneja recursos del planeta en main_web."""
        if not data:
            return
        
        resources = {
            "metal": data.get("metal", 0),
            "crystal": data.get("crystal", 0),
            "deuterium": data.get("deuterium", 0),
            "energy": data.get("energy", 0),
            "prod_metal": data.get("prod_metal", 0),
            "prod_crystal": data.get("prod_crystal", 0),
            "prod_deuterium": data.get("prod_deuterium", 0),
            "cap_metal": data.get("capacity_metal", 0),
            "cap_crystal": data.get("capacity_crystal", 0),
            "cap_deuterium": data.get("capacity_deuterium", 0),
            "last_update": time.time()
        }
        
        # Extraer colas
        detect_script = """
            (function() {
                return {
                    building_present: !!document.querySelector('#productionboxbuildingcomponent'),
                    building: !!document.querySelector('#productionboxbuildingcomponent .construction.active'),
                    research_present: !!document.querySelector('#productionboxresearchcomponent'),
                    research: !!document.querySelector('#productionboxresearchcomponent .construction.active'),
                    lf_building_present: !!document.querySelector('#productionboxlfbuildingcomponent'),
                    lf_building: !!document.querySelector('#productionboxlfbuildingcomponent .construction.active'),
                    lf_research_present: !!document.querySelector('#productionboxlfresearchcomponent'),
                    lf_research: !!document.querySelector('#productionboxlfresearchcomponent .construction.active'),
                    shipyard_present: !!document.querySelector('#productionboxshipyardcomponent'),
                    shipyard: !!document.querySelector('#productionboxshipyardcomponent .construction.active')
                };
            })();
        """
        
        def after_detect(det):
            if not det:
                update_planet_data(self,
                    planet_name=getattr(self, 'current_main_web_planet', 'Unknown'),
                    coords=getattr(self, 'current_main_web_coords', '0:0:0'),
                    resources=resources,
                    queues=[]
                )
                return
            
            present_flags = (
                det.get('building_present') or det.get('research_present') or 
                det.get('lf_building_present') or det.get('lf_research_present') or 
                det.get('shipyard_present')
            )
            
            if not present_flags:
                update_planet_data(self,
                    planet_name=getattr(self, 'current_main_web_planet', 'Unknown'),
                    coords=getattr(self, 'current_main_web_coords', '0:0:0'),
                    resources=resources,
                    queues=[]
                )
                return
            
            active_flags = (
                det.get('building') or det.get('research') or 
                det.get('lf_building') or det.get('lf_research') or 
                det.get('shipyard')
            )
            
            if not active_flags:
                update_planet_data(self,
                    planet_name=getattr(self, 'current_main_web_planet', 'Unknown'),
                    coords=getattr(self, 'current_main_web_coords', '0:0:0'),
                    resources=resources,
                    queues=[]
                )
                return
            
            parts = []
            if det.get('building'):
                parts.append("extract_building()")
            if det.get('research'):
                parts.append("extract_research()")
            if det.get('lf_building'):
                parts.append("extract_lf_building()")
            if det.get('lf_research'):
                parts.append("extract_lf_research()")
            if det.get('shipyard'):
                parts.append("extract_shipyard()")
            
            if not parts:
                update_planet_data(self,
                    planet_name=getattr(self, 'current_main_web_planet', 'Unknown'),
                    coords=getattr(self, 'current_main_web_coords', '0:0:0'),
                    resources=resources,
                    queues=[]
                )
                return
            
            present_js = (
                f"""let present = {{
                    building: {str(det.get('building_present')).lower()},
                    research: {str(det.get('research_present')).lower()},
                    lf_building: {str(det.get('lf_building_present')).lower()},
                    lf_research: {str(det.get('lf_research_present')).lower()},
                    shipyard: {str(det.get('shipyard_present')).lower()}
                }};"""
            )
            
            dynamic_script = f"""
                (function() {{
                    {present_js}
                    let final = [];
                    {extract_queue_functions}
                    return {{ present: present, queues: final.concat({",".join(parts)}) }};
                }})();"""
            
            self.main_web.page().runJavaScript(dynamic_script, lambda queues_data: self.handle_main_web_queues(queues_data, resources))
        
        self.main_web.page().runJavaScript(detect_script, after_detect)

    def handle_main_web_queues(self, data, resources):
        """Maneja colas del planeta en main_web."""
        import hashlib
        
        now = int(time.time())
        planet_name = getattr(self, 'current_main_web_planet', 'Unknown')
        coords = getattr(self, 'current_main_web_coords', '0:0:0')
        is_moon = getattr(self, 'current_main_web_is_moon', False)
        parent_planet_key = getattr(self, 'current_planet_parent_key', None)
        
        # Procesar colas del DOM actual
        if data and isinstance(data, dict):
            queues_data = data.get('queues', []) or []
            
            for q in queues_data:
                label = q.get("label", "")
                name = q.get("name", "")
                level = q.get("level", "")
                start = int(q.get("start", now))
                end = int(q.get("end", now))
                
                is_research = (
                    "investig" in label.lower() or "research" in label.lower() or "🧬" in label
                )
                
                if is_research:
                    key_raw = f"{label}|{name}|GLOBAL|{start}|{end}"
                    planet_for_store = 'GLOBAL'
                    coords_for_store = 'GLOBAL'
                else:
                    key_raw = f"{label}|{name}|{planet_name}|{coords}|{start}|{end}"
                    planet_for_store = planet_name
                    coords_for_store = coords
                
                qid = hashlib.sha1(key_raw.encode("utf-8")).hexdigest()
                
                # Guardar en memory
                self.main_web_queue_memory[qid] = {
                    "id": qid,
                    "label": label,
                    "name": name,
                    "level": level,
                    "start": start,
                    "end": end,
                    "planet_name": planet_for_store,
                    "coords": coords_for_store
                }
        
        # Filtrar colas de memory para este planeta (incluyendo GLOBAL)
        queues_list = [
            q for q in self.main_web_queue_memory.values()
            if (q.get("planet_name") == planet_name and q.get("coords") == coords) or 
               q.get("planet_name") == "GLOBAL"
        ]
        queues_list.sort(key=lambda q: q.get("end", now))
        
        update_planet_data(self,
            planet_name=planet_name,
            coords=coords,
            resources=resources,
            queues=queues_list,
            is_moon=is_moon,
            parent_planet_key=parent_planet_key
        )

    def on_open(self):
        self.showMaximized()
        js = """
        (async function() {
            try {
                function sleep(ms) {
                    return new Promise(resolve => setTimeout(resolve, ms));
                }
                let targetBtn = null;
                let intentos = 0;
                while (!targetBtn && intentos < 50) { // 50 intentos = 50 * 200ms = 10s
                    const buttons = document.querySelectorAll('button.button.button-default.button-md');
                    for (const btn of buttons) {
                        if (btn.textContent.includes("Jugado por última vez")) {
                            targetBtn = btn;
                            break;
                        }
                    }
                    if (!targetBtn) {
                        console.log('[AUTOCLICK] Esperando botón... intento ', intentos);
                        await sleep(200);
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
            print("[DEBUG] Primer planeta cargado, comprobando cache de planetas...")
            self.tabs.setCurrentWidget(self.main_panel)
            self.login.hide()
            #try:
            #    self.create_secondary_views()
            #except Exception as e:
                #print("[DEBUG] Error creando vistas secundarias:", e)

            # Intentar cargar datos de planetas desde cache
            cache_loaded = self.load_data()
            
            if not cache_loaded:
                # Si no hay cache, cargar planetas desde el navegador
                print("[DEBUG] Cache no encontrado, cargando planetas desde navegador...")
                QTimer.singleShot(1000, self.load_other_planets)
            else:
                print("[DEBUG] ✅ Datos de planetas cargados desde cache")

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
        planet_url = f"{self.base_url}?page=ingame&component=overview&cp={planet_id}"
        
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
            moon_url = f"{self.base_url}?page=ingame&component=overview&cp={moon_id}"
            
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

    # ====================================================================
    #  PANEL PRINCIPAL
    # ====================================================================
    def refresh_main_panel(self):
        """Actualiza ambas secciones del panel (recursos y flotas)"""
        refresh_resources_panel(self)
        refresh_fleets_panel(self)

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
    #  SUBASTA
    # ====================================================================
    def update_auction(self):
        hidden_web = QWebEngineView()
        hidden_page = CustomWebPage(self.profile, hidden_web, main_window=self)
        hidden_web.setPage(hidden_page)

        def after_load():
            QTimer.singleShot(1500, lambda:
                hidden_web.page().runJavaScript(
                    extract_auction_script,
                    self.handle_auction_data
                )
            )

        hidden_web.loadFinished.connect(after_load)

        current_url = self.web.url().toString()
        base_url = current_url.split("?")[0]
        auction_url = base_url + "?page=ingame&component=traderAuctioneer"

        hidden_web.load(QUrl(auction_url))

        def handle_auction_data(data):
            if not data:
                return

            status = data.get('status', '—')
            item = data.get('item', '—')
            bid = data.get('currentBid', '—')
            bidder = data.get('highestBidder', '—')
            time_left = data.get('timeLeft', '—')

            if str(time_left).isdigit():
                try:
                    seconds = int(time_left)
                    td = str(timedelta(seconds=seconds))
                    h, m, s = td.split(":")
                    time_left = f"{int(h)}h {int(m)}m"
                except:
                    pass

            texto = (
                f"{status}\n"
                f"Tiempo restante: {time_left}\n"
                f"Item: {item}\n"
                f"Oferta: {bid}\n"
                f"Mejor postor: {bidder}"
            )

            self.auction_text.setPlainText(texto)

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
        save_scheduled_fleets(self.scheduled_fleets)
        self.save_research_data()
        self.save_planets_data()
        super().closeEvent(event)