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
    """Ventana principal: contiene tabs (navegador, panel principal, subasta).
    No contiene toolbar ni sidebar; esos se muestran en popups.
    """
    def __init__(self, profile=None, url=None):
        super().__init__()
        self.setWindowTitle("OGame — Main")
        self.resize(1450, 900)

        profile = profile or QWebEngineProfile("ogame_profile", self)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        os.makedirs("profile_data", exist_ok=True)
        profile.setPersistentStoragePath(os.path.abspath("profile_data"))
        profile.setCachePath(os.path.abspath("profile_data/cache"))

        self.profile = profile

        # Web view inside a tab (no toolbar/sidebar here)
        self.web = QWebEngineView()
        self.page = CustomWebPage(profile, self.web, main_window=self)
        self.web.setPage(self.page)
        if url:
            self.web.load(QUrl(url))

        # Tabs
        self.tabs = QTabWidget()

        # Browser tab
        self.browser_tab = QWidget()
        browser_layout = QVBoxLayout()
        browser_layout.addWidget(self.web)
        self.browser_tab.setLayout(browser_layout)
        self.tabs.addTab(self.browser_tab, "🌐 Navegador")

        # Main panel tab
        main_layout = QVBoxLayout()
        self.main_panel = QWidget()
        self.main_panel.setStyleSheet("""
            background-color: #000;
            color: #EEE;
        """)
        self.main_panel.setLayout(main_layout)
        
        # Notification label (will be shown at the top of main panel)
        self._notif_label = QLabel("")
        self._notif_label.setStyleSheet("color: #0f0; font-weight: bold; padding: 8px;")
        main_layout.addWidget(self._notif_label)
        
        self.main_label = QLabel("🪐 Panel Principal de Planetas (en desarrollo)")
        main_layout.addWidget(self.main_label)
        self.tabs.addTab(self.main_panel, "📊 Panel Principal")

        # Auction tab (moved from sidebar)
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

        # Tray icon for notifications
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-games"))
        self.tray_icon.setVisible(True)

        # planet data storage
        self.planets_data = {}
        self.timer_global = QTimer(self)
        self.timer_global.setInterval(1000)
        self.timer_global.timeout.connect(self.increment_all_planets)
        self.timer_global.start()

        # Queue watcher: central notification for queues received from popups
        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(1000)
        self.queue_timer.timeout.connect(self.check_queues)
        self.queue_timer.start()

        # set to keep track of already-notified queue entries to avoid duplicates
        self.notified_queues = set()

        # Auction periodic refresh
        self.auction_timer = None

        # Keep track of popups
        self.popups = []

    # --- Panels and planets ---
    def refresh_main_panel(self):
        # Build HTML table: planets as columns, resources/queues as rows
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

        if not getattr(self, "planets_data", {}):
            html += "<p>No hay datos de planetas aún.</p>"
        else:
            # Helper functions
            def barra(cant, cap, color):
                try:
                    if cap <= 0:
                        return ""
                    ratio = min(1, cant / cap)
                    filled = int(15 * ratio)
                    empty = 15 - filled
                    block = '█' * filled
                    empty_block = '░' * empty
                    return f"<span style='color:{color};'>{block}</span><span style='color:#444;'>{empty_block}</span>"
                except Exception:
                    return ""

            def fmt(x):
                try:
                    return f"{int(x):,}".replace(",", ".")
                except Exception:
                    return str(x)

            def tiempo_lleno(cant, cap, prod):
                try:
                    if prod <= 0 or cant >= cap:
                        return "—"
                    horas = (cap - cant) / (prod * 3600)
                    if horas < 1:
                        minutos = horas * 60
                        return f"{minutos:.1f}m"
                    else:
                        return f"{horas:.1f}h"
                except Exception:
                    return "—"

            def format_queue_entry(entry, now):
                """Format a queue entry with progress bar."""
                label = entry.get('label', '')
                name = entry.get('name', '')
                start = entry.get('start', now)
                end = entry.get('end', now)
                remaining = max(0, end - now)
                minutes, seconds = divmod(remaining, 60)
                progress = 0
                if end > start:
                    progress = min(100, max(0, int(((now - start) / (end - start)) * 100)))
                color = "#0f0" if progress < 60 else "#ff0" if progress < 90 else "#f00"
                filled = int(12 * progress / 100)
                block = '█' * filled
                empty_block = '░' * (12 - filled)
                bar = f"<span style='color:{color};'>{block}</span><span style='color:#555;'>{empty_block}</span>"
                return f"{label} {name} ({minutes}m {seconds:02d}s) [{bar}] {progress}%"

            planets_list = list(self.planets_data.keys())
            now = int(time.time())

            # Collect research queues globally (they're shared across planets, show once)
            all_research_queues = {}
            for planet, data in self.planets_data.items():
                q = data.get("queues", [])
                for entry in q:
                    if "Investigación" in entry.get("label", ""):
                        key = f"{entry.get('label')}|{entry.get('name')}"
                        if key not in all_research_queues:
                            all_research_queues[key] = entry

            # Show research queues separate from table
            if all_research_queues:
                html += "<div class='research-section'><b>🧬 Investigaciones (Compartidas):</b><br>"
                for key, entry in all_research_queues.items():
                    html += format_queue_entry(entry, now) + "<br>"
                html += "</div>"

            # Start table with resources and per-planet queues
            html += "<table><tr><th>Recurso</th>"
            for planet in planets_list:
                html += f"<th>{planet}</th>"
            html += "</tr>"

            # Resource rows
            resource_names = ["Metal", "Cristal", "Deuterio", "Energía"]
            resource_keys = [("metal", "cap_metal", "prod_metal", "#0f0"),
                           ("crystal", "cap_crystal", "prod_crystal", "#0af"),
                           ("deuterium", "cap_deuterium", "prod_deuterium", "#ff0"),
                           ("energy", None, None, "#f0f")]

            for name, res_keys in zip(resource_names, resource_keys):
                html += f"<tr><td><b>{name}</b></td>"
                for planet in planets_list:
                    data = self.planets_data.get(planet, {})
                    r = data.get("resources", {})
                    if res_keys[0] == "energy":
                        html += f"<td>⚡ {fmt(r.get('energy', 0))}</td>"
                    else:
                        res_key, cap_key, prod_key, color = res_keys
                        cant = r.get(res_key, 0)
                        cap = r.get(cap_key, 1)
                        prod = r.get(prod_key, 0)
                        prod_h = prod * 3600
                        ttf = tiempo_lleno(cant, cap, prod)
                        bar_html = barra(cant, cap, color)
                        html += f"<td>{fmt(cant)} (+{fmt(prod_h)}/h) lleno en {ttf}<br>{bar_html}</td>"
                html += "</tr>"

            # Collect queue types once
            queue_types = {"🏗️ Construcciones": [], "🚀 Hangar": [], "🌿 Forma de Vida": []}
            for planet in planets_list:
                data = self.planets_data.get(planet, {})
                q = data.get("queues", [])
                for entry in q:
                    label = entry.get("label", "")
                    if "Investigación" in label:
                        continue  # Skip research (already shown above)
                    elif "Forma de Vida" in label:
                        queue_types["🌿 Forma de Vida"].append((planet, entry))
                    elif "Hangar" in label:
                        queue_types["🚀 Hangar"].append((planet, entry))
                    elif "Edificio" in label:
                        queue_types["🏗️ Construcciones"].append((planet, entry))

            # Add queue rows
            for queue_type, entries in queue_types.items():
                if entries:
                    html += f"<tr><td><b>{queue_type}</b></td>"
                    for planet in planets_list:
                        planet_queues = [e for p, e in entries if p == planet]
                        if planet_queues:
                            html += "<td>"
                            for entry in planet_queues:
                                html += format_queue_entry(entry, now) + "<br>"
                            html += "</td>"
                        else:
                            html += "<td>—</td>"
                    html += "</tr>"

            html += "</table>"

        self.main_label.setTextFormat(Qt.TextFormat.RichText)
        self.main_label.setText(html)

    def increment_all_planets(self):
        if not getattr(self, "planets_data", None):
            return
        now = time.time()
        for p, data in self.planets_data.items():
            r = data["resources"]
            elapsed = now - r.get("last_update", now)
            if elapsed <= 0:
                continue
            r["last_update"] = now
            r["metal"] += r["prod_metal"] * elapsed
            r["crystal"] += r["prod_crystal"] * elapsed
            r["deuterium"] += r["prod_deuterium"] * elapsed
        self.refresh_main_panel()

    def update_planet_data(self, planet, resources, queues):
        self.planets_data[planet] = {
            "resources": resources,
            "queues": queues,
            "last_update": time.strftime("%H:%M:%S")
        }
        self.refresh_main_panel()

    def check_queues(self):
        """Scan stored planets' queues and notify when any queue finishes.

        This runs centrally in the main window so notifications still happen
        even if the popup that reported the queue is closed.
        """
        now = int(time.time())
        active_keys = set()

        for planet, data in list(self.planets_data.items()):
            queues = data.get("queues") or []
            for entry in queues:
                label = entry.get("label")
                name = entry.get("name")
                start = int(entry.get("start", now))
                end = int(entry.get("end", now))
                key = f"{planet}|{label}|{name}|{start}|{end}"
                active_keys.add(key)

                if end <= now and key not in self.notified_queues:
                    # Queue finished -> notify and mark as notified
                    try:
                        self.show_notification("✅ Cola completada", f"{planet}: {label}: {name}")
                    except Exception as e:
                        print("[DEBUG] Error al enviar notificación desde MainWindow:", e)
                    self.notified_queues.add(key)

        # Prune notified_queues to keep memory bounded: remove keys no longer active
        to_remove = [k for k in self.notified_queues if k not in active_keys]
        for k in to_remove:
            try:
                self.notified_queues.remove(k)
            except KeyError:
                pass

    # --- Auction moved here ---
    def update_auction(self):
        # Create a hidden web view to fetch auction info using the shared profile
        profile = self.profile
        hidden_web = QWebEngineView()
        hidden_page = CustomWebPage(profile, hidden_web, main_window=self)
        hidden_web.setPage(hidden_page)

        def after_load():
            QTimer.singleShot(1500, lambda: hidden_web.page().runJavaScript(extract_auction_script, self.handle_auction_data))

        hidden_web.loadFinished.connect(after_load)

        current_url = self.web.url().toString()
        base_url = current_url.split("?")[0]
        auction_url = base_url + "?page=ingame&component=traderAuctioneer"
        hidden_web.load(QUrl(auction_url))

    def handle_auction_data(self, data):
        if not data:
            return
        self.last_auction_data = data
        status = data.get('status', '—')
        item = data.get('item', '—')
        bid = data.get('currentBid', '—')
        bidder = data.get('highestBidder', '—')
        time_left = data.get('timeLeft', '—')

        if isinstance(time_left, (int, float)) or str(time_left).isdigit():
            try:
                seconds = int(float(time_left))
                td = str(timedelta(seconds=seconds))
                h, m, s = td.split(":" )
                time_left = f"{int(h)}h {int(m)}m"
            except Exception:
                pass

        texto = f"{status}\nTiempo restante: {time_left}\nItem: {item}\nOferta: {bid}\nMejor postor: {bidder}"
        self.auction_text.setPlainText(texto)

    def show_notification(self, title, message):
        """Muestra notificación centralizada en la ventana principal.
        
        Notifica a través de:
        1. System tray (si disponible)
        2. Panel principal (etiqueta verde en la parte superior)
        
        Args:
            title: Título de la notificación
            message: Contenido del mensaje
        """
        print(f"[NOTIFY] {title}: {message}")

        # Mostrar en bandeja del sistema
        if hasattr(self, "tray_icon") and self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 5000)

        # Mostrar en etiqueta del panel principal
        try:
            if not hasattr(self, "_notif_label"):
                self._notif_label = QLabel()
                self._notif_label.setStyleSheet("color: #0f0; font-weight: bold;")
            self._notif_label.setText(f"🔔 {title}: {message}")
            # Auto-limpiar después de 8 segundos
            QTimer.singleShot(8000, lambda: self._notif_label.setText(""))
        except Exception as e:
            print("[DEBUG] Error al mostrar notificación en panel:", e)

