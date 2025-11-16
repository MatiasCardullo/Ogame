from PyQt6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QSystemTrayIcon
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl, QTimer, Qt
from PyQt6.QtGui import QIcon
from js_scripts import extract_auction_script
from custom_page import CustomWebPage
from datetime import timedelta
import time
import os


class MainWindow(QMainWindow):
    """Ventana principal de OGame."""

    def __init__(self, profile=None, url=None):
        super().__init__()
        self.setWindowTitle("OGame — Main")
        self.resize(1450, 900)

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
        if url:
            self.web.load(QUrl(url))

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
        # planets_data keyed by planet_name -> dict(coords, resources, queues(list), last_update)
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

        # Helpers
        def barra(cant, cap, color):
            try:
                if cap <= 0:
                    return ""
                ratio = min(1, cant / cap)
                filled = int(15 * ratio)
                empty = 15 - filled
                return f"<span style='color:{color};'>{'█'*filled}</span>" \
                       f"<span style='color:#444;'>{'░'*empty}</span>"
            except:
                return ""

        def fmt(x):
            try:
                return f"{int(x):,}".replace(",", ".")
            except:
                return str(x)

        def tiempo_lleno(cant, cap, prod):
            try:
                if prod <= 0 or cant >= cap:
                    return "—"
                horas = (cap - cant) / (prod * 3600)
                if horas < 1:
                    return f"{horas*60:.1f}m"
                return f"{horas:.1f}h"
            except:
                return "—"

        def format_queue_entry(entry, now):
            """Formato amigable para mostrar una queue en la tabla principal."""
            label = entry.get('label', '')
            name = entry.get('name', '')
            start = int(entry.get('start', now))
            end = int(entry.get('end', now))
            planet_name = entry.get('planet_name', '—')
            coords = entry.get('coords', '—')

            remaining = max(0, end - now)
            d, r = divmod(remaining, 86400)
            h, r = divmod(r, 3600)
            m, s = divmod(r, 60)

            if d > 0:
                parts = [f"{d}d"]
                if h > 0: parts.append(f"{h}h")
                if m > 0: parts.append(f"{m}m")
                time_text = " ".join(parts)
            else:
                time_text = f"{h}:{m:02d}:{s:02d}"

            progress = 0
            if end > start:
                progress = min(100, max(0, int(((now - start) / (end - start)) * 100)))

            color = "#0f0" if progress < 60 else "#ff0" if progress < 90 else "#f00"
            filled = int(12 * progress / 100)
            bar = f"<span style='color:{color};'>{'█'*filled}</span>" \
                  f"<span style='color:#555;'>{'░'*(12-filled)}</span>"
            return f"{name} ({time_text}) [{bar}] {progress}%"

        planet_names = list(self.planets_data.keys())
        now = int(time.time())

        # ----- Investigaciones (global, deduplicadas por label+name)
        unique_research = {}
        #print(f"[DEBUG] Planetas en datos: {list(self.planets_data.keys())}")
        for pname, pdata in self.planets_data.items():
            queues = pdata.get("queues", [])
            #print(f"[DEBUG] {pname}: {len(queues)} colas")
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
                html += format_queue_entry(entry, now) + "<br>"
            html += "</div>"

        # ----- Tabla recursos + colas por planeta
        html += "<table><tr><th>Recurso</th>"
        for p in planet_names:
            coords = self.planets_data[p].get("coords", "—")
            html += f"<th>{p}<br><small>{coords}</small></th>"
        html += "</tr>"

        resource_names = ["Metal", "Cristal", "Deuterio", "Energía"]
        resource_specs = [
            ("metal", "cap_metal", "prod_metal", "#0f0"),
            ("crystal", "cap_crystal", "prod_crystal", "#0af"),
            ("deuterium", "cap_deuterium", "prod_deuterium", "#ff0"),
            ("energy", None, None, "#f0f")
        ]

        for rname, spec in zip(resource_names, resource_specs):
            rkey, capkey, prodkey, color = spec
            html += f"<tr><td><b>{rname}</b></td>"

            for planet_name in planet_names:
                pdata = self.planets_data[planet_name]
                r = pdata["resources"]

                if rkey == "energy":
                    html += f"<td>⚡ {fmt(r.get('energy', 0))}</td>"
                    continue

                cant = r.get(rkey, 0)
                cap = r.get(capkey, 1)
                prod = r.get(prodkey, 0)
                prod_h = prod * 3600
                ttf = tiempo_lleno(cant, cap, prod)
                bar_html = barra(cant, cap, color)

                html += f"<td>{fmt(cant)} (+{fmt(prod_h)}/h) lleno en {ttf}<br>{bar_html}</td>"

            html += "</tr>"

        # ----- Colas (no investigación) — agrupar por tipo y mostrar por planeta
        queue_types = {
            "🏗️ Construcciones": [],
            "🚀 Hangar": [],
            "🌿 Forma de Vida": []
        }

        for planet_name in planet_names:
            for q in self.planets_data[planet_name].get("queues", []):
                label = q.get("label", "")
                end = int(q.get("end", now))
                # Filtrar colas completadas (end <= now)
                if end <= now:
                    continue
                if "Investigación" in label or "🧬" in label:
                    continue
                elif "Forma de Vida" in label or "lf" in label.lower():
                    queue_types["🌿 Forma de Vida"].append((planet_name, q))
                elif "Hangar" in label or "🚀" in label:
                    queue_types["🚀 Hangar"].append((planet_name, q))
                else:
                    queue_types["🏗️ Construcciones"].append((planet_name, q))

        for qtype, entries in queue_types.items():
            if not entries:
                continue

            html += f"<tr><td><b>{qtype}</b></td>"

            for planet_name in planet_names:
                planet_entries = [e for p, e in entries if p == planet_name]
                if not planet_entries:
                    html += "<td>—</td>"
                    continue

                html += "<td>"
                for e in planet_entries:
                    html += format_queue_entry(e, now) + "<br>"
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

        # Asegurarse que planet_name exista
        pdata = self.planets_data.get(planet_name, {})
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

            # Si la cola pertenece a este planeta, añadirla
            if q_planet == planet_name:
                qlist.append(entry)

        pdata["queues"] = qlist
        pdata["last_update"] = time.time()
        self.planets_data[planet_name] = pdata

        # Refrescar UI
        self.refresh_main_panel()

    # ====================================================================
    #  Incremento pasivo
    # ====================================================================
    def increment_all_planets(self):
        if not self.planets_data:
            return
        now = time.time()

        for p, pdata in self.planets_data.items():
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

        for pname, pdata in self.planets_data.items():
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
                            f"{pname}: {q.get('label','')} {q.get('name','')}"
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
