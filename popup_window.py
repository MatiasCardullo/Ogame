from PyQt6.QtWidgets import (
    QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QFrame,
    QTextEdit, QToolBar, QPushButton, QFileDialog, QSystemTrayIcon
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon
import time
import os
import hashlib

from custom_page import CustomWebPage
from js_scripts import extract_meta_script, extract_resources_script, extract_queue_functions


def make_queue_id(label, name, planet_name, coords, start, end):
    """Genera un id SHA1 único para una cola."""
    base = f"{label}|{name}|{planet_name}|{coords}|{int(start)}|{int(end)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


class PopupWindow(QMainWindow):
    """Ventana popup OGame: sidebar + navegador + colas + recursos"""

    def __init__(self, profile=None, url=None, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.setWindowTitle("OGame Popup")
        self.resize(1000, 700)

        # Profile persistente (para mantener sesión)
        profile = profile or QWebEngineProfile("ogame_profile", self)
        profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        os.makedirs("profile_data", exist_ok=True)
        profile.setPersistentStoragePath(os.path.abspath("profile_data"))
        profile.setCachePath(os.path.abspath("profile_data/cache"))

        # WebEngineView
        self.web = QWebEngineView()
        self.page = CustomWebPage(profile, self.web, main_window=self.main_window)
        self.web.setPage(self.page)
        if url:
            self.web.load(QUrl(url))

        # Toolbar simple
        self.toolbar = QToolBar()
        self.addToolBar(self.toolbar)
        for text, func in [("<", self.web.back), (">", self.web.forward), ("↻", self.web.reload)]:
            btn = QPushButton(text)
            btn.clicked.connect(func)
            self.toolbar.addWidget(btn)

        # Layout principal
        self.container = QWidget()
        self.layout = QHBoxLayout()
        self.layout.addWidget(self.web)
        self.container.setLayout(self.layout)
        self.setCentralWidget(self.container)

        # Estado del sidebar
        self.has_sidebar = False

        # Timers
        self.timer_fast = QTimer(self)
        self.timer_fast.setInterval(1000)
        self.timer_fast.timeout.connect(self.update_queue_timers)

        self.web.loadFinished.connect(self.check_if_ingame)

        # Notificaciones
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("applications-games"))
        self.tray_icon.setVisible(True)

        # Memoria de colas: dict[id] = queue_dict
        self.queue_memory = {}

    # -------------------------------------------------------------
    # Detectar si estamos dentro del juego (ogame-player-name meta)
    # -------------------------------------------------------------
    def check_if_ingame(self):
        script = """
            (function() {
                const metas = document.getElementsByTagName('meta');
                for (let m of metas) {
                    if (m.name && m.name.startsWith('ogame-player-name')) 
                        return true;
                }
                return false;
            })();
        """

        def after_check(is_ingame):
            self.toggle_sidebar(is_ingame)
            if is_ingame:
                self.update_meta_info()
                self.update_queues()

        self.web.page().runJavaScript(script, after_check)

    # -------------------------------------------------------------
    # Sidebar ON/OFF
    # -------------------------------------------------------------
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
            QFrame { background-color: #111; color: #EEE; border-left: 2px solid #222; }
            QLabel { color: #EEE; font-size: 14px; padding: 2px; }
            QTextEdit { background-color: #181818; color: #CCC; border: 1px solid #333; font-family: Consolas; font-size: 13px; }
            QPushButton { background-color: #333; border-radius: 6px; padding: 6px; margin: 4px; }
            QPushButton:hover { background-color: #555; }
        """)

        sidebar_layout = QVBoxLayout()
        self.layout.addWidget(self.sidebar)
        self.sidebar.setLayout(sidebar_layout)

        # Meta info
        self.player_label = QLabel("👤 Jugador: —")
        self.universe_label = QLabel("🌌 Universo: —")
        self.coords_label = QLabel("📍 Coordenadas: —")
        self.planet_label = QLabel("🪐 Planeta: —")

        sidebar_layout.addWidget(self.player_label)
        sidebar_layout.addWidget(self.universe_label)
        sidebar_layout.addWidget(self.coords_label)
        sidebar_layout.addWidget(self.planet_label)
        sidebar_layout.addSpacing(10)

        # Recursos
        self.metal_label = QLabel("⚙️ Metal: —")
        self.crystal_label = QLabel("💎 Cristal: —")
        self.deut_label = QLabel("🧪 Deuterio: —")
        self.energy_label = QLabel("⚡ Energía: —")

        sidebar_layout.addWidget(self.metal_label)
        sidebar_layout.addWidget(self.crystal_label)
        sidebar_layout.addWidget(self.deut_label)
        sidebar_layout.addWidget(self.energy_label)
        sidebar_layout.addSpacing(10)

        # Colas
        self.queue_text = QTextEdit()
        self.queue_text.setReadOnly(True)
        self.queue_text.setFixedHeight(220)
        sidebar_layout.addWidget(QLabel("📋 Colas activas:"))
        sidebar_layout.addWidget(self.queue_text)

        # Botones
        self.refresh_btn = QPushButton("🔄 Actualizar recursos")
        self.refresh_btn.clicked.connect(self.update_resources)

        self.update_queue_btn = QPushButton("🏗️ Actualizar colas")
        self.update_queue_btn.clicked.connect(self.update_queues)

        self.save_btn = QPushButton("💾 Guardar HTML")
        self.save_btn.clicked.connect(self.save_html)

        sidebar_layout.addWidget(self.refresh_btn)
        sidebar_layout.addWidget(self.update_queue_btn)
        sidebar_layout.addWidget(self.save_btn)

        self.update_meta_info()
        self.update_queues()

    def remove_sidebar(self):
        self.has_sidebar = False
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if isinstance(widget, QFrame):
                self.layout.removeWidget(widget)
                widget.deleteLater()

    # -------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------
    def update_meta_info(self):
        self.web.page().runJavaScript(extract_meta_script, self.handle_meta_data)

    def handle_meta_data(self, data):
        if not data or not self.has_sidebar:
            return

        player = data.get('ogame-player-name', '—')
        universe = data.get('ogame-universe-name', '—')
        coords = data.get('ogame-planet-coordinates', '—')
        planet = data.get('ogame-planet-name', '—')

        self.current_planet_coords = coords
        self.current_planet_name = planet

        self.player_label.setText(f"👤 Jugador: {player}")
        self.universe_label.setText(f"🌌 Universo: {universe}")
        self.coords_label.setText(f"📍 Coordenadas: {coords}")
        self.planet_label.setText(f"🪐 Planeta: {planet}")

        # Update UI and send current data to MainWindow
        self.update_queue_timers()
        self.update_resources()

    # -------------------------------------------------------------
    # RECURSOS
    # -------------------------------------------------------------
    def update_resources(self):
        if not self.has_sidebar:
            return
        self.web.page().runJavaScript(extract_resources_script, self.handle_resource_data)

    def handle_resource_data(self, data):
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

        # Timer para incrementar recursos
        if hasattr(self, "timer_resources"):
            self.timer_resources.stop()
        else:
            self.timer_resources = QTimer(self)
            self.timer_resources.setInterval(1000)
            self.timer_resources.timeout.connect(self.increment_resources)
        self.timer_resources.start()

        # 🔥 Enviar datos al MainWindow con la nueva API (incluye queues desde memoria)
        if self.main_window:
            # pasar las queues actuales como lista ordenada (descartando claves internas)
            queues_list = list(self.queue_memory.values())
            # ordenar por end asc
            queues_list.sort(key=lambda q: q.get("end", time.time()))
            self.main_window.update_planet_data(
                planet_name=self.current_planet_name,
                coords=self.current_planet_coords,
                resources=self.current_resources,
                queues=queues_list
            )

    def update_resource_labels(self):
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
                return f"{horas*60:.1f}m"
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
        self.energy_label.setText(
            f"⚡ Energía: {fmt(r['energy'])}"
        )

    def increment_resources(self):
        r = getattr(self, "current_resources", None)
        if not r:
            return

        now = time.time()
        elapsed = now - r["last_update"]
        if elapsed <= 0:
            return
        r["last_update"] = now

        r["metal"] += r["prod_metal"] * elapsed
        r["crystal"] += r["prod_crystal"] * elapsed
        r["deuterium"] += r["prod_deuterium"] * elapsed

        self.update_resource_labels()

    # -------------------------------------------------------------
    # COLAS
    # -------------------------------------------------------------
    def update_queues(self):
        if not self.has_sidebar:
            return

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
                # No cambio en el DOM, mantenemos memoria
                self.update_queue_timers()
                return

            present_flags = (
                det.get('building_present')
                or det.get('research_present')
                or det.get('lf_building_present')
                or det.get('lf_research_present')
                or det.get('shipyard_present')
            )

            if not present_flags:
                # página sin cajas: no tocar memoria
                self.update_queue_timers()
                return

            active_flags = (
                det.get('building')
                or det.get('research')
                or det.get('lf_building')
                or det.get('lf_research')
                or det.get('shipyard')
            )

            if not active_flags:
                # no hay colas activas en DOM -> no sobrescribir memoria
                self.update_queue_timers()
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
                self.update_queue_timers()
                return

            present_js = (
                f"let present = {{building: {str(det.get('building_present')).lower()}, "
                f"research: {str(det.get('research_present')).lower()}, "
                f"lf_building: {str(det.get('lf_building_present')).lower()}, "
                f"lf_research: {str(det.get('lf_research_present')).lower()}, "
                f"shipyard: {str(det.get('shipyard_present')).lower()}}};"
            )

            dynamic_script = f"""
                (function() {{
                    {present_js}
                    let final = [];
                    {extract_queue_functions}
                    return {{ present: present, queues: final.concat({",".join(parts)}) }};
                }})();
            """

            self.web.page().runJavaScript(dynamic_script, self.handle_queue_data)

        self.web.page().runJavaScript(detect_script, after_detect)

    def handle_queue_data(self, data):
        """
        Normaliza y procesa las colas extraídas del DOM.
        Memoria: self.queue_memory keyed by id (sha1).
        """
        # Si no tenemos sidebar visible, limpiar y parar timer (legacy)
        if not data or not self.has_sidebar:
            self.current_queues = []
            self.queue_text.setText("— No hay construcciones activas —")
            try:
                self.timer_fast.stop()
            except Exception:
                pass
            return

        # Normalizar entrada (legacy support)
        present_map = None
        queues = None
        if isinstance(data, dict) and 'queues' in data:
            present_map = data.get('present', {}) or {}
            queues = data.get('queues', []) or []
        elif isinstance(data, list):
            queues = data
        else:
            queues = []

        now = int(time.time())
        planet_name = getattr(self, "current_planet_name", "—")
        coords = getattr(self, "current_planet_coords", "—")

        # Si recibimos datos del DOM -> actualizamos memoria
        if queues:
            for q in queues:
                label = q.get("label", "")
                name = q.get("name", "")
                level = q.get("level", "")
                start = int(q.get("start", now))
                end = int(q.get("end", now))

                # Detectar si es investigación (principal o lifeform)
                is_research = (
                    "investig" in label.lower()
                    or "research" in label.lower()
                    or "🧬" in label.lower()
                )

                if is_research:
                    # Investigación -> almacenar como GLOBAL para evitar ids por planeta
                    planet_for_store = 'GLOBAL'
                    coords_for_store = 'GLOBAL'
                    key_raw = f"{label}|{name}|GLOBAL|{start}|{end}"
                else:
                    # Construcciones normales -> sí dependen del planeta
                    planet_for_store = planet_name
                    coords_for_store = coords
                    key_raw = f"{label}|{name}|{planet_name}|{coords}|{start}|{end}"

                # ID único estable SHA1
                qid = hashlib.sha1(key_raw.encode("utf-8")).hexdigest()

                # Recuperar memoria previa (si existe)
                mem = self.queue_memory.get(qid)
                if mem:
                    if end - start < 5:
                        start = mem.get("start", start)
                        end = mem.get("end", end)

                # Guardar en memoria
                self.queue_memory[qid] = {
                    "id": qid,
                    "label": label,
                    "name": name,
                    "level": level,
                    "start": start,
                    "end": end,
                    "planet_name": planet_for_store,
                    "coords": coords_for_store
                }

        # Reconstruir current_queues desde memoria y ordenar por end
        updated = list(self.queue_memory.values())
        updated.sort(key=lambda e: e.get("end", now))
        self.current_queues = updated

        # Asegurar timer corriendo si hay colas
        if self.current_queues:
            try:
                self.timer_fast.start()
            except Exception:
                pass
        else:
            try:
                self.timer_fast.stop()
            except Exception:
                pass

        # Actualizar UI inmediatamente
        self.update_queue_timers()

        # Enviar recursos + colas actualizados al MainWindow (si existe)
        if self.main_window and hasattr(self, "current_resources"):
            # Pasar una copia ordenada de las colas
            queues_list = list(self.queue_memory.values())
            queues_list.sort(key=lambda q: q.get("end", time.time()))
            self.main_window.update_planet_data(
                planet_name=planet_name,
                coords=coords,
                resources=getattr(self, "current_resources", {}),
                queues=queues_list
            )

    # -------------------------------------------------------------
    # TIMER DE COLAS
    # -------------------------------------------------------------
    def update_queue_timers(self):
        """
        Muestra las colas en el sidebar usando memoria (queue_memory).
        """
        # Reconstruir desde memoria si current_queues vacío
        queues = getattr(self, "current_queues", None)
        if not queues or len(queues) == 0:
            if self.queue_memory:
                now = int(time.time())
                queues = list(self.queue_memory.values())
                queues.sort(key=lambda e: e.get("end", now))
            else:
                try:
                    self.queue_text.setHtml("— No hay construcciones activas —")
                except Exception:
                    self.queue_text.setPlainText("— No hay construcciones activas —")
                try:
                    self.timer_fast.stop()
                except Exception:
                    pass
                return

        now = time.time()
        lines = []
        planet_now = getattr(self, "current_planet_name", "—")

        if not hasattr(self, "finished_queue_ids"):
            self.finished_queue_ids = {}  # dict: qid -> finish_time

        finished_any = False
        queues_to_remove = []
        
        TIMER_QUEUE_REMOVAL = 5.0

        for entry in queues:
            label = entry.get("label", "")
            name = entry.get("name", "")
            level = entry.get("level", "")
            start = int(entry.get("start", now))
            end = int(entry.get("end", now))
            planet_name = entry.get("planet_name", "—")
            coords = entry.get("coords", "—")
            qid = entry.get("id")

            remaining = max(0, end - now)
            m, s = divmod(int(remaining), 60)
            remaining_str = f"{m}m {s:02d}s" if remaining > 0 else "Completado"

            progress = 0
            if end > start:
                progress = min(100, max(0, int(((now - start) / (end - start)) * 100)))

            # Si la cola está al 100% (remaining <= 0), marcarla para eliminar después del timer
            if remaining <= 0 and qid:
                if qid not in self.finished_queue_ids:
                    # Primera vez que se completa: registrar timestamp
                    self.finished_queue_ids[qid] = now
                    finished_any = True
                
                # Verificar si ha pasado el tiempo de espera
                time_since_finish = now - self.finished_queue_ids[qid]
                if time_since_finish >= TIMER_QUEUE_REMOVAL:
                    queues_to_remove.append(qid)
                else:
                    # Aún dentro del timer: mostrar como completada
                    color = "#0f0"
                    filled = 26
                    bar = f"<span style='color:{color};'>{'█'*filled}</span>"
                    is_research = (
                        "investig" in label.lower()
                        or "research" in label.lower()
                        or "🧬" in label.lower()
                    )
                    if is_research:
                        header = f"[GLOBAL] {label}: {name} {level}"
                    else:
                        header = f"[{planet_name} ({coords})] {label}: {name} {level}"
                    lines.append(f"✅ {header} ({remaining_str}) [{bar}]")
                
                continue  # No mostrar en la lista normal

            color = "#0f0" if progress < 60 else "#ff0" if progress < 90 else "#f00"
            filled = int(26 * progress / 100)
            bar = f"<span style='color:{color};'>{'█'*filled}</span><span style='color:#555;'>{'░'*(26-filled)}</span>"

            is_research = (
                "investig" in label.lower()
                or "research" in label.lower()
                or "🧬" in label.lower()
            )
            if is_research:
                header = f"[GLOBAL] {label}: {name} {level}"
            else:
                header = f"[{planet_name} ({coords})] {label}: {name} {level}"
            lines.append(f"{header} ({remaining_str})<br>[{bar}] {progress}%")

        # Render
        try:
            self.queue_text.setHtml("<br><br>".join(lines))
        except Exception:
            try:
                self.queue_text.setPlainText("\n\n".join(lines))
            except Exception:
                pass

        # Eliminar queues completadas del memory (después del timer)
        for qid in queues_to_remove:
            if qid in self.queue_memory:
                del self.queue_memory[qid]
            if qid in self.finished_queue_ids:
                del self.finished_queue_ids[qid]

        if finished_any:
            # refrescar recursos y colas (esto actualizará memoria y panel)
            try:
                self.update_resources()
                self.update_queues()
            except Exception:
                pass

    # -------------------------------------------------------------
    # GUARDAR HTML
    # -------------------------------------------------------------
    def save_html(self):
        def handle_html(html):
            path, _ = QFileDialog.getSaveFileName(self, "Guardar HTML", "pagina.html", "Archivos HTML (*.html)")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)
        self.web.page().toHtml(handle_html)

    # -------------------------------------------------------------
    # Cierre
    # -------------------------------------------------------------
    def closeEvent(self, event):
        if self.main_window and self in getattr(self.main_window, "popups", []):
            try:
                self.main_window.popups.remove(self)
            except:
                pass
        super().closeEvent(event)
