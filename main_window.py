from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QSystemTrayIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl, QTimer, Qt
from PyQt6.QtGui import QIcon
from js_scripts import extract_auction_script
from custom_page import CustomWebPage
from sprite_widget import SpriteWidget
from datetime import timedelta
import time, os
from text import barra_html, cantidad, produccion, tiempo_lleno, time_str

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

        # Web view
        self.web = QWebEngineView()
        self.page = CustomWebPage(profile, self.web, main_window=self)
        self.web.setPage(self.page)
        self.web.load(QUrl(url))
        self.web.loadFinished.connect(self.open_popup)

        # Tabs
        self.tabs = QTabWidget()

        # ----- Tab navegador -----
        self.browser_tab = QWidget()
        browser_layout = QVBoxLayout()
        browser_layout.addWidget(self.web)
        self.browser_tab.setLayout(browser_layout)
        self.tabs.addTab(self.browser_tab, "🌐 Navegador")

        # ----- Panel principal -----
        main_layout = QVBoxLayout()
        self.main_panel = QWidget()
        self.main_panel.setStyleSheet("""
            background-color: #000;
            color: #EEE;
        """)
        self.main_panel.setLayout(main_layout)

        # Notificaciones
        self._notif_label = QLabel("")
        self._notif_label.setStyleSheet("color: #0f0; font-weight: bold; padding: 8px;")
        main_layout.addWidget(self._notif_label)

        # Sprite Viewer
        self.sprite_widget = SpriteWidget()
        main_layout.addWidget(self.sprite_widget)

        self.main_label = QLabel("🪐 Panel Principal de Planetas (en desarrollo)")
        main_layout.addWidget(self.main_label)
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

    def _get_planet_key(self, planet_name, coords):
        """Genera una clave única para un planeta basada en nombre y coordenadas.
        Esto evita que planetas con el mismo nombre pero diferentes coordenadas se sobrescriban.
        """
        if not coords:
            coords = "0:0:0"
        return f"{planet_name}|{coords}"

    def open_popup(self):
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
            QTimer.singleShot(1000, self.load_other_planets)
        QTimer.singleShot(3000, lambda: self.web.page().runJavaScript(js, done))

    # ====================================================================
    #  CARGAR OTROS PLANETAS
    # ====================================================================
    def load_other_planets(self):
        """Busca los enlaces de otros planetas en el sidebar y los carga secuencialmente."""
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
        
        # Ejecutar el script en el popup si existe (el sidebar está ahí),
        # si no, caer back al web principal.
        target_page = None
        popup = None
        if hasattr(self, 'popups') and self.popups:
            try:
                popup = self.popups[-1]
                print("[DEBUG] Hay popup(s) abierto(s). Esperando sidebar en popup si es necesario...")
            except Exception as e:
                print("[DEBUG] Error accediendo popup list:", e)

        def run_detection_on(page, description):
            try:
                print(f"[DEBUG] Ejecutando búsqueda de planetList en: {description}")
                page.runJavaScript(script, handle_planets)
            except Exception as e:
                print("[DEBUG] Error ejecutando script de planetList:", e)

        # Si tenemos popup, esperar a que tenga sidebar visible (has_sidebar)
        if popup is not None:
            def wait_for_sidebar(attempts=0):
                try:
                    if getattr(popup, 'has_sidebar', False):
                        run_detection_on(popup.web.page(), 'popup')
                        return
                except Exception as e:
                    print("[DEBUG] Error leyendo popup.has_sidebar:", e)

                if attempts >= 20:  # ~10s timeout (20 * 500ms)
                    print("[DEBUG] Timeout esperando sidebar en popup, fallback a web principal")
                    run_detection_on(self.web.page(), 'web principal (fallback)')
                    return

                # volver a intentar en 500ms
                QTimer.singleShot(500, lambda: wait_for_sidebar(attempts + 1))

            wait_for_sidebar(0)
        else:
            run_detection_on(self.web.page(), 'web principal')

    def load_next_planet(self):
        """Carga el siguiente planeta de la lista."""
        if not hasattr(self, 'planets_to_load') or self.current_planet_index >= len(self.planets_to_load):
            print("[DEBUG] ✓ Todos los planetas cargados")
            return
        
        planet = self.planets_to_load[self.current_planet_index]
        print(f"[DEBUG] Cargando planeta {self.current_planet_index + 1}/{len(self.planets_to_load)}: {planet['name']}")
        # Crear un PopupWindow (que contiene la lógica para extraer recursos/colas)
        # Reutilizar el popup existente (el sidebar) en lugar de abrir nuevas ventanas
        popup = None
        if hasattr(self, 'popups') and self.popups:
            popup = self.popups[-1]

        if not popup:
            # Si no hay popup disponible, avanzar para no bloquear
            print('[DEBUG] No hay popup disponible para recargar, saltando...')
            self.current_planet_index += 1
            QTimer.singleShot(500, self.load_next_planet)
            return

        def finish_and_next():
            try:
                # Forzar extracción final desde el popup
                try:
                    popup.update_resources()
                except Exception:
                    pass
                try:
                    popup.update_queues()
                except Exception:
                    pass
            finally:
                QTimer.singleShot(500, self.load_next_planet)

        def on_load_finished(ok=True):
            try:
                # desconectar este handler para evitar llamadas múltiples
                popup.web.loadFinished.disconnect(on_load_finished)
            except Exception:
                pass
            print(f"[DEBUG] Página de {planet['name']} recargada en popup, esperando datos...")
            QTimer.singleShot(1200, finish_and_next)

        try:
            popup.web.loadFinished.connect(on_load_finished)
            popup.web.load(QUrl(planet['url']))
        except Exception as e:
            print('[DEBUG] Error recargando popup:', e)
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
            color = "#0f0" if progress < 75 else "#ff0" if progress < 95 else "#f00"
            barra = barra_html(progress, 100, color, 25)
            return f"{name} [{progress:.2f}%] ({time})<br>{barra}"
        
        def format_research_queue_entry(entry,now):
            """Formato amigable para mostrar una queue de Investigacion"""
            name, time, progress = queue_entry(entry,now)
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
                prod = produccion(prodInt)
                full = tiempo_lleno(cant, cap, prodInt)
                char = "#0f0" if (cant / cap) < 0.9 else "#ff0" if cant < cap else "#f00"
                barra = barra_html(cant, cap, color, 24) + f"<span style='color:{char};'>{'█'}</span>"
                html += f"<td>{cantidad(cant)} ({prod}) lleno en {full}<br>{barra}</td>"

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

        self.main_label.setTextFormat(Qt.TextFormat.RichText)
        self.main_label.setText(html)

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
        self.refresh_main_panel()

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

        self.refresh_main_panel()

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
            QTimer.singleShot(8000, lambda: self._notif_label.setText(""))
        except Exception as e:
            print("[DEBUG] Error al mostrar notificación:", e)
