from datetime import timedelta
import os
os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = "9222"
import time
from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QMessageBox,
    QToolBar, QPushButton, QLabel, QFrame, QFileDialog, QTextEdit, QSystemTrayIcon
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtGui import QIcon
from custom_page import CustomWebPage
from sidebar_updater import extract_meta_script, extract_resources_script, extract_queue_script, extract_auction_script

class BrowserWindow(QMainWindow):
    def __init__(self, profile=None, url=None, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.popups = []
        self.has_sidebar = False
        self.setWindowTitle("OGame Browser")
        self.resize(1450, 900)

        # --- Perfil persistente ---
        profile = profile or QWebEngineProfile("ogame_profile", self)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        os.makedirs("profile_data", exist_ok=True)
        profile.setPersistentStoragePath(os.path.abspath("profile_data"))
        profile.setCachePath(os.path.abspath("profile_data/cache"))

        # --- WebEngine ---
        self.web = QWebEngineView()
        self.page = CustomWebPage(profile, self.web, main_window=self)
        self.web.setPage(self.page)
        if url:
            self.web.load(QUrl(url))

        # --- Toolbar ---
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        for text, func in [("<", self.web.back), (">", self.web.forward), ("↻", self.web.reload)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            self.toolbar.addWidget(btn)

        # --- Layout principal ---
        self.container = QWidget()
        self.layout = QHBoxLayout()
        self.layout.addWidget(self.web)
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

        # --- Timer de actualización visual rápida (cada 1 s) ---
        self.timer_fast = QTimer(self)
        self.timer_fast.setInterval(1000)
        self.timer_fast.timeout.connect(self.update_queue_timers)

        # --- Icono de notificaciones del sistema ---
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-games"))
        self.tray_icon.setVisible(True)

        # Detectar entorno ingame
        self.web.loadFinished.connect(self.check_if_ingame)

    # ================================
    #   Lógica principal
    # ================================
    def check_if_ingame(self):
        script = """
            (function() {
                const metas = document.getElementsByTagName('meta');
                for (let m of metas) {
                    if (m.name && m.name.startsWith('ogame-player-name')) return true;
                }
                return false;
            })();
        """
        def after_check(is_ingame):
            self.toggle_sidebar(is_ingame)
            if is_ingame:
                self.update_queues()
        self.web.page().runJavaScript(script, after_check)

    def toggle_sidebar(self, is_ingame):
        if is_ingame and not self.has_sidebar:
            self.add_sidebar()
        elif not is_ingame and self.has_sidebar:
            self.remove_sidebar()

    def add_sidebar(self):
        self.has_sidebar = True
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(320)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #111;
                color: #EEE;
                border-left: 2px solid #222;
            }
            QLabel {
                color: #EEE;
                font-size: 14px;
                padding: 2px;
            }
            QTextEdit {
                background-color: #181818;
                color: #CCC;
                border: 1px solid #333;
                font-family: Consolas;
                font-size: 13px;
            }
            QPushButton {
                background-color: #333;
                border-radius: 6px;
                padding: 6px;
                margin: 4px;
            }
            QPushButton:hover {
                background-color: #555;
            }
        """)

        sidebar_layout = QVBoxLayout()
        self.layout.addWidget(self.sidebar)
        self.sidebar.setLayout(sidebar_layout)
        # --- Info básica ---
        self.player_label = QLabel("👤 Jugador: —")
        self.planet_label = QLabel("🪐 Planeta: —")
        self.coords_label = QLabel("📍 Coordenadas: —")
        self.universe_label = QLabel("🌌 Universo: —")
        sidebar_layout.addWidget(self.player_label)
        sidebar_layout.addWidget(self.planet_label)
        sidebar_layout.addWidget(self.coords_label)
        sidebar_layout.addWidget(self.universe_label)
        sidebar_layout.addSpacing(10)
        # --- Recursos ---
        self.metal_label = QLabel("⚙️ Metal: —")
        self.crystal_label = QLabel("💎 Cristal: —")
        self.deut_label = QLabel("🧪 Deuterio: —")
        self.energy_label = QLabel("⚡ Energía: —")
        sidebar_layout.addWidget(self.metal_label)
        sidebar_layout.addWidget(self.crystal_label)
        sidebar_layout.addWidget(self.deut_label)
        sidebar_layout.addWidget(self.energy_label)
        sidebar_layout.addSpacing(10)
        # --- Colas ---
        self.queue_text = QTextEdit()
        self.queue_text.setReadOnly(True)
        self.queue_text.setFixedHeight(180)
        sidebar_layout.addWidget(QLabel("📋 Colas activas:"))
        sidebar_layout.addWidget(self.queue_text)
        self.auction_text = QTextEdit()
        self.auction_text.setReadOnly(True)
        self.auction_text.setFixedHeight(50)
        sidebar_layout.addWidget(QLabel("🏆 Subasta actual:"))
        sidebar_layout.addWidget(self.auction_text)
        # --- Botones ---
        self.refresh_btn = QPushButton("🔄 Actualizar recursos")
        self.refresh_btn.clicked.connect(self.update_resources)
        self.update_queue_btn = QPushButton("🏗️ Actualizar colas")
        self.update_queue_btn.clicked.connect(self.update_queues)
        self.save_btn = QPushButton("💾 Guardar HTML")
        self.save_btn.clicked.connect(self.save_html)
        self.auction_btn = QPushButton("🏆 Actualizar subasta")
        self.auction_btn.clicked.connect(self.update_auction)
        sidebar_layout.addWidget(self.refresh_btn)
        sidebar_layout.addWidget(self.update_queue_btn)
        sidebar_layout.addWidget(self.save_btn)
        sidebar_layout.addWidget(self.auction_btn)

        self.update_meta_info()
        self.update_resources()
        self.update_queues()

    def remove_sidebar(self):
        self.has_sidebar = False
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if isinstance(widget, QFrame):
                self.layout.removeWidget(widget)
                widget.deleteLater()

    # ================================
    #   Actualizaciones manuales
    # ================================
    def update_meta_info(self):
        self.web.page().runJavaScript(extract_meta_script, self.handle_meta_data)

    def handle_meta_data(self, data):
        if not data or not self.has_sidebar:
            return
        self.player_label.setText(f"👤 Jugador: {data.get('ogame-player-name', '—')}")
        self.planet_label.setText(f"🪐 Planeta: {data.get('ogame-planet-name', '—')}")
        self.coords_label.setText(f"📍 Coordenadas: {data.get('ogame-planet-coordinates', '—')}")
        self.universe_label.setText(f"🌌 Universo: {data.get('ogame-universe-name', '—')}")

    # ================================
    #   Actualizar recursos
    # ================================
    def update_resources(self):
        """Obtiene los recursos directamente desde la página actual (sin abrir ventana oculta)."""
        if not self.has_sidebar:
            return

        print("[DEBUG] Ejecutando extract_resources_script directamente en la página actual...")
        self.web.page().runJavaScript(extract_resources_script, self.handle_resource_data)

    def handle_resource_data(self, data):
        # print("[DEBUG] Datos recibidos de extract_resources_script:", data)
        if not data or not self.has_sidebar:
            return

        self.current_resources = {
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

        self.update_resource_labels()

        if hasattr(self, "timer_resources"):
            self.timer_resources.stop()
        else:
            self.timer_resources = QTimer(self)
            self.timer_resources.setInterval(1000)
            self.timer_resources.timeout.connect(self.increment_resources)
        self.timer_resources.start()

    def update_resource_labels(self):
        """Actualiza los labels con valores actuales, barra de llenado y tiempo estimado."""
        r = getattr(self, "current_resources", None)
        if not r:
            return

        def fmt(x):
            return f"{int(x):,}".replace(",", ".")

        def tiempo_lleno(cant, cap, prod):
            if prod <= 0 or cant >= cap:
                return "—"
            horas = (cap - cant) / (prod * 3600)
            if horas < 1:
                minutos = horas * 60
                return f"{minutos:.1f}m"
            else:
                return f"{horas:.1f}h"

        def barra(cant, cap, color):
            if cap <= 0:
                return ""
            ratio = min(1, cant / cap)
            filled = int(20 * ratio)
            empty = 20 - filled
            return f"<span style='color:{color};'>{'█'*filled}</span><span style='color:#444;'>{'░'*empty}</span>"

        pm = r["prod_metal"] * 3600
        pc = r["prod_crystal"] * 3600
        pd = r["prod_deuterium"] * 3600

        tm = tiempo_lleno(r["metal"], r["cap_metal"], r["prod_metal"])
        tc = tiempo_lleno(r["crystal"], r["cap_crystal"], r["prod_crystal"])
        td = tiempo_lleno(r["deuterium"], r["cap_deuterium"], r["prod_deuterium"])

        self.metal_label.setText(
            f"⚙️ Metal: {fmt(r['metal'])} <span style='color:#0f0;'> (+{fmt(pm)}/h)</span> lleno en {tm}<br>"
            f"{barra(r['metal'], r['cap_metal'], '#0f0')}"
        )
        self.crystal_label.setText(
            f"💎 Cristal: {fmt(r['crystal'])} <span style='color:#0af;'> (+{fmt(pc)}/h)</span> lleno en {tc}<br>"
            f"{barra(r['crystal'], r['cap_crystal'], '#0af')}"
        )
        self.deut_label.setText(
            f"🧪 Deuterio: {fmt(r['deuterium'])} <span style='color:#ff0;'> (+{fmt(pd)}/h)</span> lleno en {td}<br>"
            f"{barra(r['deuterium'], r['cap_deuterium'], '#ff0')}"
        )
        self.energy_label.setText(f"⚡ Energía: {fmt(r['energy'])}")

    def increment_resources(self):
        r = getattr(self, "current_resources", None)
        if not r:
            return

        now = time.time()
        elapsed = now - r["last_update"]
        if elapsed <= 0:
            return
        r["last_update"] = now

        # 🚀 Usar directamente producción/segundo (sin dividir por 3600)
        metal_incr = r["prod_metal"] * elapsed
        crystal_incr = r["prod_crystal"] * elapsed
        deuterium_incr = r["prod_deuterium"] * elapsed

        r["metal"] += metal_incr
        r["crystal"] += crystal_incr
        r["deuterium"] += deuterium_incr

        # Debug opcional
        #if not hasattr(self, "_res_debug_counter"):
        #    self._res_debug_counter = 0
        #self._res_debug_counter += 1
        #if self._res_debug_counter % 5 == 0:
        #    print(f"[RES_DEBUG] +{metal_incr:.2f} / +{crystal_incr:.2f} / +{deuterium_incr:.2f}  (prod_s: {r['prod_metal']}, {r['prod_crystal']}, {r['prod_deuterium']})")

        self.update_resource_labels()

    # ================================
    #   Colas de construcción
    # ================================
    def update_queues(self):
        if not self.has_sidebar:
            return

        check_script = """
            (function() {
                return !!document.querySelector('#productionboxbuildingcomponent, #productionboxresearchcomponent, #productionboxshipyardcomponent');
            })();
        """

        def after_check(has_sections):
            if has_sections:
                self.web.page().runJavaScript(extract_queue_script, self.handle_queue_data)
            else:
                print("[DEBUG] Página sin secciones de cola, se omite actualización.")

        self.web.page().runJavaScript(check_script, after_check)

    def handle_queue_data(self, data):
        if not data or not self.has_sidebar:
            self.current_queues = []
            self.queue_text.setText("— No hay construcciones activas —")
            self.timer_fast.stop()
            return

        if not hasattr(self, "queue_memory"):
            self.queue_memory = {}

        updated_queues = []
        now = int(time.time())

        for q in data:
            key = f"{q['label']}|{q['name']}"
            start = int(q.get("start", now))
            end = int(q.get("end", now))

            # ✅ Solo persistir tiempos para Hangar
            if q["label"] == "🚀 Hangar":
                if key in self.queue_memory:
                    start = self.queue_memory[key]["start"]
                    end = self.queue_memory[key]["end"]
                else:
                    if end - start < 10:
                        end = now + 30
                    self.queue_memory[key] = {"start": start, "end": end}
            else:
                # Edificios e investigaciones: tiempos absolutos
                self.queue_memory[key] = {"start": start, "end": end}

            updated_queues.append({
                "label": q["label"],
                "name": q["name"],
                "level": q.get("level", ""),
                "start": start,
                "end": end
            })

        # Limpiar colas terminadas
        for k in list(self.queue_memory.keys()):
            if all(k != f"{q['label']}|{q['name']}" for q in updated_queues):
                del self.queue_memory[k]

        self.current_queues = updated_queues
        self.timer_fast.start()
        self.update_queue_timers()

    def update_queue_timers(self):
        if not hasattr(self, "current_queues") or not self.current_queues:
            return

        now = int(time.time())
        lines = []
        finished_any = False

        # 🔹 Crear set para registrar colas terminadas (si no existe)
        if not hasattr(self, "finished_queue_names"):
            self.finished_queue_names = set()

        for entry in self.current_queues:
            label = entry["label"]
            name = entry["name"]
            level = entry["level"]
            start = entry["start"]
            end = entry["end"]

            remaining = max(0, end - now)
            minutes, seconds = divmod(remaining, 60)
            remaining_str = f"{minutes}m {seconds:02d}s" if remaining > 0 else "Completado"

            progress = 0
            if end > start:
                progress = max(0, min(100, int(((now - start) / (end - start)) * 100)))

            color = "#0f0" if progress < 60 else "#ff0" if progress < 90 else "#f00"
            filled = int(26 * progress / 100)
            bar = f"<span style='color:{color};'>{'█'*filled}</span><span style='color:#555;'>{'░'*(26-filled)}</span>"

            lines.append(f"{label}: {name} {level} ({remaining_str})<br>[{bar}] {progress}%")

            # ✅ Detectar finalización nueva
            if remaining <= 0 and name not in self.finished_queue_names:
                self.finished_queue_names.add(name)
                finished_any = True
                self.show_notification("✅ Cola completada", f"{label}: {name} {level}")

        self.queue_text.setHtml("<br><br>".join(lines))

        # ⚙️ Si terminó alguna, actualizar colas y recursos
        if finished_any:
            self.update_resources()
            self.update_queues()

    def show_notification(self, title, message):
        """Muestra una notificación de sistema y una alternativa en la sidebar."""
        print(f"[NOTIFY] {title}: {message}")

        # ✅ Mostrar notificación del sistema si está disponible
        if hasattr(self, "tray_icon") and self.tray_icon.isSystemTrayAvailable():
            self.tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                5000
            )

        # 🧭 También mostrar un texto temporal en la sidebar (por si Windows no muestra nada)
        if hasattr(self, "sidebar"):
            try:
                if not hasattr(self, "_notif_label"):
                    from PyQt6.QtCore import QTimer
                    self._notif_label = QLabel()
                    self._notif_label.setStyleSheet("color: #0f0; font-weight: bold;")
                    self.sidebar.layout().insertWidget(0, self._notif_label)
                self._notif_label.setText(f"🔔 {title}: {message}")
                QTimer.singleShot(8000, lambda: self._notif_label.setText(""))
            except Exception as e:
                print("[DEBUG] Error al mostrar notificación en sidebar:", e)

    # ================================
    #   Subasta
    # ================================
    def update_auction(self):
        """Abre una ventana secundaria con la página de subastas, obtiene datos y la cierra."""
        if not self.has_sidebar:
            return

        profile = self.web.page().profile()
        self.hidden_window = QMainWindow()
        self.hidden_window.setWindowTitle("OGame Auction Fetcher")
        self.hidden_window.resize(800, 600)
        self.hidden_window.showMinimized()

        self.hidden_web = QWebEngineView()
        self.hidden_page = CustomWebPage(profile, self.hidden_web, main_window=self)
        self.hidden_web.setPage(self.hidden_page)
        self.hidden_window.setCentralWidget(self.hidden_web)

        def after_load():
            print("[DEBUG] Página de subasta cargada, ejecutando script...")
            QTimer.singleShot(2000, lambda: self.hidden_web.page().runJavaScript(
                extract_auction_script, self.handle_auction_data
            ))
            QTimer.singleShot(6000, self.hidden_window.close)

        self.hidden_web.loadFinished.connect(after_load)

        current_url = self.web.url().toString()
        base_url = current_url.split("?")[0]
        auction_url = base_url + "?page=ingame&component=traderAuctioneer"
        print(f"[DEBUG] Cargando página de subastas: {auction_url}")
        self.hidden_web.load(QUrl(auction_url))

    def handle_auction_data(self, data):
        print("[DEBUG] Datos de subasta:", data)
        if not data or not self.has_sidebar:
            return

        self.last_auction_data = data
        self.refresh_auction_text(data)

        # Reiniciar temporizador de actualización automática
        if hasattr(self, "auction_timer") and self.auction_timer.isActive():
            self.auction_timer.stop()

        self.auction_timer = QTimer(self)
        self.auction_timer.setInterval(60000)  # cada 1m
        self.auction_timer.timeout.connect(self.refresh_auction_timer)
        self.auction_timer.start()

    def refresh_auction_text(self, data):
        """Actualiza el cuadro de texto con formato bonito."""
        status = data.get('status', '—')
        item = data.get('item', '—')
        bid = data.get('currentBid', '—')
        bidder = data.get('highestBidder', '—')
        time_left = data.get('timeLeft', '—')

        # Si el tiempo es un número (ej. "20792"), formatear
        if isinstance(time_left, (int, float)) or str(time_left).isdigit():
            try:
                seconds = int(float(time_left))
                td = str(timedelta(seconds=seconds))
                # Convertir "HH:MM:SS" → "6h 24m 51s"
                h, m, s = td.split(":")
                time_left = f"{int(h)}h {int(m)}m"
            except Exception:
                pass

        texto = f"🏆 {status}\n⏳ Tiempo restante: {time_left}"

        # Mostrar detalles solo si la subasta está activa
        if "activa" in status.lower():
            self.auction_text.setFixedHeight(100)
            texto += (
                f"\n🧩 Ítem: {item}"
                f"\n💰 Oferta actual: {bid}"
                f"\n👤 Mejor postor: {bidder}"
            )

        self.auction_text.setPlainText(texto)

    def refresh_auction_timer(self):
        """Reejecuta la lectura desde la página oculta para mantener datos frescos."""
        if not self.has_sidebar:
            return

        profile = self.web.page().profile()
        hidden_web = QWebEngineView()
        hidden_page = CustomWebPage(profile, hidden_web, main_window=self)
        hidden_web.setPage(hidden_page)

        def after_load():
            QTimer.singleShot(1500, lambda: hidden_web.page().runJavaScript(
                extract_auction_script, self.handle_auction_data
            ))

        current_url = self.web.url().toString()
        base_url = current_url.split("?")[0]
        auction_url = base_url + "?page=ingame&component=traderAuctioneer"
        hidden_web.loadFinished.connect(after_load)
        hidden_web.load(QUrl(auction_url))
    # ================================
    #   Guardar HTML y exit
    # ================================
    def save_html(self):
        def handle_html(html):
            path, _ = QFileDialog.getSaveFileName(
                self, "Guardar HTML", "pagina.html", "Archivos HTML (*.html)"
            )
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
        self.web.page().toHtml(handle_html)

    def closeEvent(self, event):
        # 🔹 Si esta ventana pertenece a un main_window, limpiarla de su lista
        if self.main_window and self in self.main_window.popups:
            self.main_window.popups.remove(self)
        # 🔹 Cerrar también cualquier popup abierto desde esta misma
        for popup in getattr(self, "popups", []):
            try:
                popup.close()
            except Exception:
                pass
        super().closeEvent(event)
