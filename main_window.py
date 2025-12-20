from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QLabel, QTextEdit, QPushButton, QSystemTrayIcon
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl, QTimer, Qt
from PyQt6.QtGui import QIcon
from custom_page import CustomWebPage
from sprite_widget import SpriteWidget
from datetime import timedelta
import time, os, subprocess, json, sys
from js_scripts import (
    in_game, extract_meta_script, extract_resources_script,
    extract_queue_functions, extract_auction_script
)
from text import barra_html, cantidad, produccion, progress_color, tiempo_lleno, time_str

logged = True
#os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"

def extract_debris_list(galaxy_data: dict):
    debris_list = []

    for g, systems in galaxy_data.items():
        for s, positions in systems.items():
            for pos, entry in positions.items():
                debris = entry.get("debris")
                if not debris:
                    continue

                debris_list.append({
                    "galaxy": int(g),
                    "system": int(s),
                    "position": int(pos),
                    "metal": debris.get("metal", 0),
                    "crystal": debris.get("crystal", 0),
                    "deuterium": debris.get("deuterium", 0),
                    "requiredShips": debris.get("requiredShips")
                })

    return debris_list

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
        self.base_url = "https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame"

        # Login: se muestra inicialmente, pero lo ocultaremos automáticamente
        # después de que open_popup termine. El login se coloca dentro de
        # un contenedor junto a un botón para mostrar/ocultar.
        self.login = self.web_engine(profile, url)
        if logged :
            self.login.loadFinished.connect(self.on_open)
        self.left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.toggle_login_btn = QPushButton("Ocultar Login")
        self.toggle_login_btn.clicked.connect(self.toggle_login_visibility)
        left_layout.addWidget(self.toggle_login_btn)
        left_layout.addWidget(self.login)
        self.left_widget.setLayout(left_layout)
        self.browser_box.addWidget(self.left_widget)

        # Las vistas secundarias (galaxy, fleet, etc.) se crearán después de
        # que open_popup haya terminado para evitar carga prematura.
        self.secondary_views_created = False
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
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(5)
        
        self.sprite_widget = SpriteWidget()
        top_layout.addWidget(self.sprite_widget, 1)  # stretch factor = 1 para que ocupe espacio disponible
        
        # QWebEngineView integrado (el navegador del planeta actual)
        self.web_layout = QVBoxLayout()
        self.main_web = self.web_engine(self.profile, self.base_url)
        self.main_web.setZoomFactor(0.7)
        self.main_web.setMinimumWidth(800)
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
        
        self.main_label = QTextEdit()
        self.main_label.setReadOnly(True)
        main_layout.addWidget(self.main_label, 1)  # stretch factor = 1

        self._notif_label = QLabel("")
        self._notif_label.setStyleSheet("color: #0f0; font-weight: bold; padding: 8px;")
        main_layout.addWidget(self._notif_label)
        
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
        self.global_queues = {}

        # Timers
        self.timer_global = QTimer(self)
        self.timer_global.setInterval(1000)
        self.timer_global.timeout.connect(self.increment_all_planets)
        self.timer_global.start()

        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(1000)
        self.queue_timer.timeout.connect(self.check_queues)
        self.queue_timer.start()

        self.notified_queues = set()
        self.popups = []
        
        self.main_web_queue_memory = {}

    def web_engine(self, profile, url):
        web = QWebEngineView()
        page = CustomWebPage(profile, web, main_window=self)
        web.setPage(page)
        web.load(QUrl(url))
        return web

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
        
        self.current_main_web_planet = planet
        self.current_main_web_coords = coords
        
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
                self.update_planet_data(
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
                self.update_planet_data(
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
                self.update_planet_data(
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
                self.update_planet_data(
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
        
        self.update_planet_data(
            planet_name=planet_name,
            coords=coords,
            resources=resources,
            queues=queues_list
        )

    def _get_planet_key(self, planet_name, coords):
        """Genera una clave única para un planeta basada en nombre y coordenadas.
        Esto evita que planetas con el mismo nombre pero diferentes coordenadas se sobrescriban.
        """
        if not coords:
            coords = "0:0:0"
        return f"{planet_name}|{coords}"

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
            print("[DEBUG] Primer planeta cargado, iniciando carga de otros planetas...")
            self.tabs.setCurrentWidget(self.main_panel)
            self.login.hide()
            self.left_widget.setFixedWidth(55)
            self.toggle_login_btn.setText("Mostrar\nLogin")
            #try:
            self.create_secondary_views()
            #except Exception as e:
                #print("[DEBUG] Error creando vistas secundarias:", e)

            QTimer.singleShot(1000, self.load_other_planets)
        QTimer.singleShot(3000, lambda: self.login.page().runJavaScript(js, done))

    def create_secondary_views(self):
        """Crea y añade `galaxy` y `fleet` al layout si no existen todavía."""
        if getattr(self, 'secondary_views_created', False):
            return

        self.galaxy_box = QVBoxLayout()
        self.galaxy_debug = QTextEdit()
        
        # Iniciar 5 instancias de worker.py (una para cada galaxia)
        for galaxy_num in range(1, 6):
            subprocess.Popen([sys.executable, "worker.py", str(galaxy_num)])
            self.galaxy_debug.append(f"[Galaxy {galaxy_num}] Proceso iniciado")
        
        self.galaxy_box.addWidget(self.galaxy_debug)
        self.browser_box.addLayout(self.galaxy_box)
        
        # Intentar cargar datos si existen
        try:
            # Combinar datos de todas las galaxias
            combined_data = {}
            for g in range(1, 6):
                galaxy_file = f"galaxy_data_g{g}.json"
                if os.path.isfile(galaxy_file):
                    with open(galaxy_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        combined_data.update(data)
            
            if combined_data:
                debris = extract_debris_list(combined_data)
                debris.sort("requiredShips")
                print(debris[:5])
        except Exception as e:
            print(f"[DEBUG] No se pudieron cargar datos de galaxias: {e}")

        self.fleet = self.web_engine(self.profile, f"{self.base_url}&component=movement")
        self.fleet.loadFinished.connect(lambda: self.div_middle(self.fleet))
        self.browser_box.addWidget(self.fleet)

        self.secondary_views_created = True
        print("[DEBUG] Vistas secundarias creadas: galaxy, fleet")

    def toggle_login_visibility(self):
        """Muestra/oculta la vista de login y actualiza el texto del botón."""
        try:
            if getattr(self, 'login', None) and self.login.isVisible():
                self.login.hide()
                self.left_widget.setFixedWidth(55)
                self.toggle_login_btn.setText("Mostrar\nLogin")
            else:
                if getattr(self, 'login', None):
                    self.login.show()
                self.left_widget.setFixedWidth(150)
                self.toggle_login_btn.setText("Ocultar Login")
        except Exception as e:
            print("[DEBUG] Error toggling login visibility:", e)

    def div_middle(self, webview):
        """Muestra solo el div middle en el QWebEngineView dado"""
        js = """
        const middle = document.getElementById("middle");
        if (middle) {
            document.body.innerHTML = "";
            document.body.appendChild(middle.cloneNode(true));
        }
        """
        webview.page().runJavaScript(js)
    
    # ====================================================================
    #  CARGAR OTROS PLANETAS
    # ====================================================================
    def load_other_planets(self):
        """Busca los enlaces de otros planetas en main_web y los carga secuencialmente."""
        script = """
        (function() {
            console.log("[DEBUG JS] Buscando planetList...");
            
            // Intentar encontrar planetList en el documento
            let planetList = document.getElementById('planetList');
            console.log("[DEBUG JS] planetList encontrado:", !!planetList);
            
            if (!planetList) {
                console.log("[DEBUG JS] Intentando buscar en iframe...");
                const iframes = document.querySelectorAll('iframe');
                console.log("[DEBUG JS] Iframes encontrados:", iframes.length);
                for (let iframe of iframes) {
                    try {
                        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                        if (iframeDoc) {
                            planetList = iframeDoc.getElementById('planetList');
                            if (planetList) {
                                console.log("[DEBUG JS] planetList encontrado en iframe");
                                break;
                            }
                        }
                    } catch(e) {
                        console.log("[DEBUG JS] Error accediendo iframe:", e.message);
                    }
                }
            }
            
            if (!planetList) {
                console.log("[DEBUG JS] No se encontró planetList en ningún lugar");
                return null;
            }
            
            console.log("[DEBUG JS] Buscando enlaces de planetas...");
            const links = [];
            
            // Buscar todos los enlaces con clase planetlink
            const planetLinks = planetList.querySelectorAll('a.planetlink');
            console.log("[DEBUG JS] Links encontrados:", planetLinks.length);
            
            for (let link of planetLinks) {
                const dataLink = link.getAttribute('data-link');
                const planetNameEl = link.querySelector('.planet-name');
                const planetName = planetNameEl ? planetNameEl.textContent.trim() : 'Unknown';
                
                console.log("[DEBUG JS] Planeta:", planetName, "Link:", dataLink);
                
                if (dataLink) {
                    links.push({
                        url: dataLink,
                        name: planetName
                    });
                }
            }
            
            console.log("[DEBUG JS] Total links retornados:", links.length);
            return links.length > 0 ? links : null;
        })();
        """
        
        def handle_planets(planets):
            print(f"[DEBUG] Resultado del script: {planets}")
            if not planets or not isinstance(planets, list):
                print("[DEBUG] ⚠️  No se encontraron planetas adicionales")
                return
            
            print(f"[DEBUG] ✓ Encontrados {len(planets)} planetas: {[p['name'] for p in planets]}")
            # Almacenar la lista y empezar a cargar
            self.planets_to_load = planets
            self.current_planet_index = 0
            self.load_next_planet()
        
        # Ejecutar el script en main_web
        try:
            print("[DEBUG] Ejecutando búsqueda de planetList en main_web")
            self.main_web.page().runJavaScript(script, handle_planets)
        except Exception as e:
            print("[DEBUG] Error ejecutando script de planetList:", e)

    def load_next_planet(self):
        """Carga el siguiente planeta de la lista usando main_web."""
        if not hasattr(self, 'planets_to_load') or self.current_planet_index >= len(self.planets_to_load):
            print("[DEBUG] ✓ Todos los planetas cargados")
            return
        
        planet = self.planets_to_load[self.current_planet_index]
        print(f"[DEBUG] Cargando planeta {self.current_planet_index + 1}/{len(self.planets_to_load)}: {planet['name']} en main_web")

        def finish_and_next():
            """Termina la extracción actual y pasa al siguiente planeta."""
            QTimer.singleShot(500, self.load_next_planet)

        def on_load_finished(ok=True):
            """Callback cuando termina de cargar la página del planeta."""
            try:
                # desconectar este handler para evitar llamadas múltiples
                self.main_web.loadFinished.disconnect(on_load_finished)
            except Exception:
                pass
            print(f"[DEBUG] Página de {planet['name']} cargada en main_web, esperando datos...")
            # Los datos se extraerán automáticamente vía on_main_web_loaded y los handlers
            QTimer.singleShot(1200, finish_and_next)

        try:
            self.main_web.loadFinished.connect(on_load_finished)
            self.main_web.load(QUrl(planet['url']))
        except Exception as e:
            print('[DEBUG] Error cargando planeta en main_web:', e)
            QTimer.singleShot(1000, finish_and_next)

        # avanzar índice inmediatamente
        self.current_planet_index += 1

    # ====================================================================
    #  PANEL PRINCIPAL
    # ====================================================================

    def refresh_main_panel(self):
        html = """
        <style>
            body { background-color: #000; color: #EEE; font-family: Consolas; }
            table { border-collapse: collapse; margin-top: 10px; width: 100%; }
            th { background-color: #222; color: #0f0; border: 1px solid #333; padding: 8px; text-align: center; }
            td { background-color: #111; color: #EEE; border: 1px solid #333; padding: 6px; font-size: 12px; }
            .bar { font-family: monospace; }
            .research-section { background-color: #1a1a2e; padding: 8px; margin-top: 10px; border: 1px solid #0af; }
        </style>
        <h2>🌌 Panel Principal — Recursos y Colas</h2>
        """

        if not self.planets_data:
            html += "<p>No hay datos de planetas aún.</p>"
            self.main_label.setText(html)
            return

        def queue_entry(entry, now):
            name = entry.get('name', '')
            start = entry.get('start', now)
            end = entry.get('end', now)

            remaining = max(0, end - now)
            time = time_str(remaining)

            progress = 0
            if end > start:
                progress = min(100, max(0, ((now - start) / (end - start)) * 100))

            return name, time, progress

        def format_queue_entry(entry,now):
            """Formato amigable para mostrar una queue"""
            name, time, progress = queue_entry(entry,now)
            color = progress_color(progress)
            barra = barra_html(progress, 100, color)
            aux = f"{name} [{int(progress)}%] ({time})"
            if len(aux) > 40:
                return f"{name}<br>[{int(progress)}%] ({time})<br>{barra}"
            else:
                return f"{aux}<br>{barra}"
        
        def format_research_queue_entry(entry,now):
            """Formato amigable para mostrar una queue de Investigacion"""
            name, time, progress = queue_entry(entry,now)
            color = progress_color(progress, 89)
            color = "#0f0" if progress < 89 else "#ff0" if progress < 95 else "#f00"
            barra = barra_html(progress, 100, color, 50)
            return f"{barra} {name} [{progress:.2f}%] ({time})"
        
        # Extraer nombres únicos y coordenadas de las claves
        planet_info = []
        for key in self.planets_data.keys():
            parts = key.rsplit('|', 1)  # Separar por el último |
            if len(parts) == 2:
                name, coords = parts
                planet_info.append((name, coords, key))
            else:
                planet_info.append((key, "0:0:0", key))
        
        now = int(time.time())

        # ----- Investigaciones (global, deduplicadas por label+name)
        unique_research = {}
        #print(f"[DEBUG] Planetas en datos: {list(self.planets_data.keys())}")
        for planet_key, pdata in self.planets_data.items():
            queues = pdata.get("queues", [])
            #print(f"[DEBUG] {planet_key}: {len(queues)} colas")
            for q in queues:
                label = (q.get("label", "") or "")
                name = (q.get("name", "") or "")
                #print(f"[DEBUG]   Queue label: '{label}' (type: {type(label).__name__})")
                is_research = (
                    "Investigación" in label or "🧬" in label or
                    "investig" in label.lower() or "research" in label.lower()
                )
                if is_research:
                    key = f"{label}|{name}".strip().lower()
                    if key not in unique_research:
                        qid = q.get("id")
                        #print(f"[DEBUG] ✓ Encontré investigación! ID: {qid}, label: {label}")
                        unique_research[key] = q

        # Incluir investigaciones globales (desde popups) también
        for q in getattr(self, 'global_queues', {}).values():
            label = (q.get("label", "") or "")
            name = (q.get("name", "") or "")
            key = f"{label}|{name}".strip().lower()
            if key not in unique_research:
                #print(f"[DEBUG] (global) Añadiendo investigación: {label} / {name}")
                unique_research[key] = q

        #print(f"[DEBUG] Total investigaciones encontradas: {len(unique_research)}")
        if unique_research:
            html += "<div class='research-section'><b>🧬 Investigaciones:</b><br>"
            for entry in unique_research.values():
                # Filtrar investigaciones completadas
                end = int(entry.get("end", now))
                if end <= now:
                    continue
                html += format_research_queue_entry(entry, now) + "<br>"
            html += "</div>"

        # ----- Tabla recursos + colas por planeta
        html += "<table><tr><th>Recurso</th>"
        for name, coords, key in planet_info:
            html += f"<th>{name}<br><small>{coords}</small></th>"
        html += "</tr>"

        resource_names = ["Metal", "Cristal", "Deuterio", "Energía"]
        resource_specs = [
            ("metal", "cap_metal", "prod_metal", "#555"),
            ("crystal", "cap_crystal", "prod_crystal", "#aff"),
            ("deuterium", "cap_deuterium", "prod_deuterium", "#0f8"),
            ("energy", None, None, "#f0f")
        ]

        for rname, spec in zip(resource_names, resource_specs):
            rkey, capkey, prodkey, color = spec
            html += f"<tr><td><b>{rname}</b></td>"

            for name, coords, key in planet_info:
                pdata = self.planets_data[key]
                r = pdata["resources"]

                if rkey == "energy":
                    html += f"<td>⚡ {r.get('energy', 0)}</td>"
                    continue

                cant = r.get(rkey, 0)
                cap = r.get(capkey, 1)
                prodInt = r.get(prodkey, 0)
                if cant < cap:
                    full = f"({produccion(prodInt)}) lleno en {tiempo_lleno(cant, cap, prodInt)}"
                else:
                    full = f" - almacenes llenos!!!"
                char = progress_color((cant / cap) * 100)
                barra = barra_html(cant, cap, color, 19) + f"<span style='color:{char};'>{'█'}</span>"
                html += f"<td>{cantidad(cant)} {full}<br>{barra}</td>"

            html += "</tr>"

        # ----- Colas (no investigación) — agrupar por tipo y mostrar por planeta
        queue_types = {
            "🏗️ Construcciones": [],
            "🚀 Hangar": [],
            "🌿 Forma de Vida": []
        }

        for name, coords, key in planet_info:
            for q in self.planets_data[key].get("queues", []):
                label = q.get("label", "")
                end = int(q.get("end", now))
                # Filtrar colas completadas (end <= now)
                if end <= now:
                    continue
                if "Investigación" in label or "🧬" in label:
                    continue
                elif "Forma de Vida" in label or "lf" in label.lower():
                    queue_types["🌿 Forma de Vida"].append((name, coords, q))
                elif "Hangar" in label or "🚀" in label:
                    queue_types["🚀 Hangar"].append((name, coords, q))
                else:
                    queue_types["🏗️ Construcciones"].append((name, coords, q))

        for qtype, entries in queue_types.items():
            if not entries:
                continue

            html += f"<tr><td><b>{qtype}</b></td>"

            for name, coords, key in planet_info:
                planet_entries = [e for pname, pcoords, e in entries if pname == name and pcoords == coords]
                if not planet_entries:
                    html += "<td>—</td>"
                    continue

                html += "<td>"
                for idx, e in enumerate(planet_entries):
                    html += format_queue_entry(e, now)
                    if idx < len(planet_entries) - 1:
                        html += "<br>"
                html += "</td>"

            html += "</tr>"
        html += "</table>"

        self.main_label.setHtml(html)

    # ====================================================================
    #  UPDATE PLANET DATA (API nueva con queues que incluyen id)
    # ====================================================================
    def update_planet_data(self, planet_name, coords, resources, queues):
        """
        Recibe:
          - planet_name (str)
          - coords (str)
          - resources (dict)
          - queues (list of queue dicts, cada uno con 'id','label','name','start','end','planet_name','coords',...)
        """
        # Normalizar recursos: asegurar last_update timestamp
        resources = resources or {}
        if "last_update" not in resources:
            resources["last_update"] = time.time()

        # Generar clave única basada en nombre + coordenadas
        planet_key = self._get_planet_key(planet_name, coords)
        
        # Asegurarse que planet_name exista
        pdata = self.planets_data.get(planet_key, {})
        pdata["coords"] = coords
        pdata["resources"] = resources

        # Filtrar las queues recibidas: las queues con planet_name GLOBAL se guardan
        # en self.global_queues; las demás se asignan al planeta correspondiente.
        qlist = []
        for q in queues or []:
            qid = q.get("id")
            if not qid:
                continue
            q_planet = q.get("planet_name", planet_name)
            q_coords = q.get("coords", coords)

            entry = {
                "id": qid,
                "label": q.get("label", ""),
                "name": q.get("name", ""),
                "level": q.get("level", ""),
                "start": int(q.get("start", time.time())),
                "end": int(q.get("end", time.time())),
                "planet_name": q_planet,
                "coords": q_coords
            }

            # Si es global (research), almacenarla en global_queues
            if q_planet is None or str(q_planet).upper() == "GLOBAL":
                self.global_queues[qid] = entry
                # don't include in planet-specific list
                continue

            # Si la cola pertenece a este planeta, verificar nombre Y coordenadas
            # Esto es importante cuando hay múltiples planetas con el mismo nombre
            if q_planet == planet_name and q_coords == coords:
                qlist.append(entry)

        pdata["queues"] = qlist
        pdata["last_update"] = time.time()
        self.planets_data[planet_key] = pdata

        # Refrescar UI
        try:
            self.refresh_main_panel()
        except Exception as e:
            print("[DEBUG] Error updated_planet_data:", e)
    
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

        try:
            self.refresh_main_panel()
        except Exception as e:
            print(e)

    # ====================================================================
    #  CHECK QUEUES GLOBALES (notificaciones)
    # ====================================================================
    def check_queues(self):
        now = int(time.time())
        active_ids = set()

        for planet_key, pdata in self.planets_data.items():
            coords = pdata.get("coords", "0:0:0")
            planet_name = planet_key.rsplit('|', 1)[0] if '|' in planet_key else planet_key
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
        for q in getattr(self, 'global_queues', {}).values():
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

    def handle_auction_data(self, data):
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
