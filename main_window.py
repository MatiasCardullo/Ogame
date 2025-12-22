from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QLabel, QTextEdit, QPushButton, QSystemTrayIcon, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QFormLayout, QListWidget,
    QListWidgetItem, QDateTimeEdit, QScrollArea, QGridLayout
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl, QTimer, Qt, QDateTime
from PyQt6.QtGui import QIcon
from custom_page import CustomWebPage
from sprite_widget import SpriteWidget
from datetime import timedelta
import time, os, subprocess, json, sys
from js_scripts import (
    in_game, extract_meta_script, extract_resources_script,
    extract_queue_functions, extract_auction_script, extract_planet_array
)
from text import barra_html, cantidad, produccion, progress_color, tiempo_lleno, time_str
from worker import FleetWorker
from fleet_sender import send_fleet, send_scheduled_fleets

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
        self.base_url = "https://s163-ar.ogame.gameforge.com/game/index.php"

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
        
        # ----- Control de intervalo de actualización -----
        update_interval_layout = QHBoxLayout()
        update_interval_layout.addWidget(QLabel("⏱️ Intervalo de actualización:"))
        self.update_interval_combo = QComboBox()
        self.update_interval_combo.addItem("1 segundo", 1000)
        self.update_interval_combo.addItem("30 segundos", 30000)
        self.update_interval_combo.addItem("1 minuto", 60000)
        self.update_interval_combo.setCurrentIndex(1)  # Default: 30 segundos
        self.update_interval_combo.currentIndexChanged.connect(self.on_update_interval_changed)
        update_interval_layout.addWidget(self.update_interval_combo)
        update_interval_layout.addStretch()
        main_layout.addLayout(update_interval_layout)
        
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
        fleets_tab = QWidget()
        fleets_layout = QHBoxLayout()
        fleets_layout.setContentsMargins(5, 5, 5, 5)
        fleets_layout.setSpacing(10)
        
        # Panel izquierdo: Flotas en movimiento
        left_fleets = QWidget()
        left_fleets_layout = QVBoxLayout()
        self.fleets_label = QTextEdit()
        self.fleets_label.setReadOnly(True)
        left_fleets_layout.addWidget(QLabel("📊 Flotas en Movimiento"))
        left_fleets_layout.addWidget(self.fleets_label)
        left_fleets.setLayout(left_fleets_layout)
        fleets_layout.addWidget(left_fleets, 1)
        
        # Panel derecho: Programador de naves
        right_scheduler = self.create_fleet_scheduler_panel()
        fleets_layout.addWidget(right_scheduler, 1)
        
        fleets_tab.setLayout(fleets_layout)
        self.panel_tabs.addTab(fleets_tab, "🚀 Flotas en Movimiento")
        
        # Tab 3: Debris y Reciclaje
        debris_tab = self.create_debris_tab()
        self.panel_tabs.addTab(debris_tab, "♻️ Debris y Reciclaje")
        
        main_layout.addWidget(self.panel_tabs, 1)  # stretch factor = 1

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

        # Intervalo de actualización (en ms)
        self.current_update_interval = 30000  # Default: 30 segundos

        # Timers
        self.timer_global = QTimer(self)
        self.timer_global.setInterval(self.current_update_interval)
        self.timer_global.timeout.connect(self.increment_all_planets)
        self.timer_global.start()

        self.queue_timer = QTimer(self)
        self.queue_timer.setInterval(self.current_update_interval)
        self.queue_timer.timeout.connect(self.check_queues)
        self.queue_timer.start()

        # Panel refresh timer (usa el intervalo también)
        self.panel_timer = QTimer(self)
        self.panel_timer.setInterval(self.current_update_interval)
        self.panel_timer.timeout.connect(self.refresh_main_panel)
        self.panel_timer.start()

        # Fleet update timer
        self.fleet_timer = QTimer(self)
        self.fleet_timer.setInterval(60000)
        self.fleet_timer.timeout.connect(self.update_fleets)
        self.fleet_timer.start()

        # Fleet sender timer (ejecutar envíos cada 30 segundos)
        self.fleet_sender_timer = QTimer(self)
        self.fleet_sender_timer.setInterval(30000)  # 30 segundos
        self.fleet_sender_timer.timeout.connect(self.auto_send_scheduled_fleets)
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
    
    def closeEvent(self, event):
        """Guardar datos al cerrar la aplicación"""
        self.save_scheduled_fleets()
        super().closeEvent(event)
    
    def load_scheduled_fleets(self):
        """Carga las misiones programadas desde un archivo JSON"""
        try:
            if os.path.exists("scheduled_fleets.json"):
                with open("scheduled_fleets.json", "r", encoding="utf-8") as f:
                    self.scheduled_fleets = json.load(f)
                    print(f"✅ Cargadas {len(self.scheduled_fleets)} misiones programadas")
                    # Actualizar lista visual después de cargar
                    if hasattr(self, 'fleet_scheduled_list'):
                        self._refresh_scheduled_fleets_list()
        except Exception as e:
            print(f"⚠️ Error cargando misiones: {e}")
    
    def save_scheduled_fleets(self):
        """Guarda las misiones programadas en un archivo JSON"""
        try:
            with open("scheduled_fleets.json", "w", encoding="utf-8") as f:
                json.dump(self.scheduled_fleets, f, indent=2, ensure_ascii=False)
                print(f"✅ Guardadas {len(self.scheduled_fleets)} misiones programadas")
        except Exception as e:
            print(f"⚠️ Error guardando misiones: {e}")

    def web_engine(self, profile, url):
        web = QWebEngineView()
        page = CustomWebPage(profile, web, main_window=self)
        web.setPage(page)
        web.load(QUrl(url))
        return web

    def create_fleet_scheduler_panel(self):
        """Crea el panel para programar envío de naves"""
        scheduler_widget = QWidget()
        scheduler_layout = QVBoxLayout()
        scheduler_layout.setContentsMargins(5, 5, 5, 5)
        
        # Título
        title = QLabel("⏳ Programador de Misiones [WIP]")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title.setFont(title_font)
        scheduler_layout.addWidget(title)
        
        # Grupo: Configuración de misión
        mission_group = QGroupBox("🎯 Configuración de Misión")
        mission_form = QFormLayout()
        
        self.fleet_mission_combo = QComboBox()
        self.fleet_mission_combo.addItems([
            "Expedición",
            "Recolecta de escombros",
            "Ataque",
            "Transporte",
            "Estacionamiento",
            "Espía"
        ])
        self.fleet_mission_combo.currentTextChanged.connect(self.on_fleet_mission_changed)
        mission_form.addRow("Tipo de Misión:", self.fleet_mission_combo)
        
        self.fleet_planet_combo = QComboBox()
        self.fleet_planet_combo.addItem("Seleccionar planeta...")
        self.fleet_planet_combo.currentTextChanged.connect(self.on_fleet_origin_changed)
        mission_form.addRow("Origen:", self.fleet_planet_combo)
        
        # Grupo de coordenadas destino
        coords_layout = QHBoxLayout()
        self.fleet_dest_galaxy = QSpinBox()
        self.fleet_dest_galaxy.setRange(1, 9)
        self.fleet_dest_galaxy.setValue(1)
        self.fleet_dest_system = QSpinBox()
        self.fleet_dest_system.setRange(1, 499)
        self.fleet_dest_system.setValue(1)
        self.fleet_dest_position = QSpinBox()
        self.fleet_dest_position.setRange(1, 16)
        self.fleet_dest_position.setValue(1)
        coords_layout.addWidget(QLabel("G:"))
        coords_layout.addWidget(self.fleet_dest_galaxy)
        coords_layout.addWidget(QLabel("S:"))
        coords_layout.addWidget(self.fleet_dest_system)
        coords_layout.addWidget(QLabel("P:"))
        coords_layout.addWidget(self.fleet_dest_position)
        mission_form.addRow("Destino:", coords_layout)
        
        mission_group.setLayout(mission_form)
        scheduler_layout.addWidget(mission_group)
        
        # Grupo: Selección de naves (scrollable, 2 columnas)
        ships_group = QGroupBox("🚢 Naves a Enviar")
        ships_layout = QVBoxLayout()
        
        ships_scroll = QScrollArea()
        ships_scroll.setWidgetResizable(True)
        ships_container = QWidget()
        ships_grid = QGridLayout(ships_container)
        ships_grid.setSpacing(1)
        
        # Definir naves con sus IDs (basado en POST de expedición)
        # am### es el ID, nombre es la clave, spinbox es el control
        self.fleet_ships = {
            "Cazador Ligero": {"id": "am204", "spinbox": QSpinBox()},
            "Cazador Pesado": {"id": "am205", "spinbox": QSpinBox()},
            "Crucero": {"id": "am206", "spinbox": QSpinBox()},
            "Nave de Batalla": {"id": "am207", "spinbox": QSpinBox()},
            "Acorazado": {"id": "am215", "spinbox": QSpinBox()},
            "Bombardero": {"id": "am211", "spinbox": QSpinBox()},
            "Destructor": {"id": "am213", "spinbox": QSpinBox()},
            "Estrella de la Muerte": {"id": "am214", "spinbox": QSpinBox()},
            "Nave Pequeña de Carga": {"id": "am202", "spinbox": QSpinBox()},
            "Nave Grande de Carga": {"id": "am203", "spinbox": QSpinBox()},
            "Nave Colonizadora": {"id": "am208", "spinbox": QSpinBox()},
            "Reciclador": {"id": "am209", "spinbox": QSpinBox()},
            "Sonda de Espionaje": {"id": "am210", "spinbox": QSpinBox()},
            "Segador": {"id": "am218", "spinbox": QSpinBox()},
            "Explorador": {"id": "am219", "spinbox": QSpinBox()}
        }
        
        row = 0
        col = 0
        for ship_name, ship_info in self.fleet_ships.items():
            spinbox = ship_info["spinbox"]
            spinbox.setRange(0, 9999)
            spinbox.setValue(0)
            
            # Crear layout horizontal para label + spinbox
            ship_layout = QHBoxLayout()
            ship_layout.addWidget(QLabel(f"  {ship_name}:"))
            ship_layout.addWidget(spinbox)
            ship_layout.addStretch()
            
            # Agregar a la grilla (3 columnas)
            ships_grid.addLayout(ship_layout, row, col)
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        ships_scroll.setWidget(ships_container)
        ships_scroll.setMaximumHeight(500)
        ships_layout.addWidget(ships_scroll)
        ships_group.setLayout(ships_layout)
        scheduler_layout.addWidget(ships_group)
        
        # Grupo: Programación
        timing_group = QGroupBox("⏰ Programación")
        timing_form = QFormLayout()
        
        self.fleet_timing_combo = QComboBox()
        self.fleet_timing_combo.addItems([
            "Enviar ahora",
            "Programar hora específica",
            "Cuando esté disponible"
        ])
        self.fleet_timing_combo.currentTextChanged.connect(self.on_fleet_timing_changed)
        timing_form.addRow("Tipo de Envío:", self.fleet_timing_combo)
        
        self.fleet_send_time = QDateTimeEdit()
        self.fleet_send_time.setDateTime(QDateTime.currentDateTime())
        self.fleet_send_time.setEnabled(False)
        timing_form.addRow("Hora de Envío:", self.fleet_send_time)
        
        self.fleet_available_label = QLabel("Se enviará cuando no haya expediciones en movimiento")
        self.fleet_available_label.setStyleSheet("color: #aaa; font-style: italic;")
        self.fleet_available_label.setVisible(False)
        timing_form.addRow("", self.fleet_available_label)
        
        self.fleet_repeat_count = QSpinBox()
        self.fleet_repeat_count.setMinimum(1)
        self.fleet_repeat_count.setMaximum(100)
        self.fleet_repeat_count.setValue(1)
        timing_form.addRow("Repetir X veces:", self.fleet_repeat_count)
        
        timing_group.setLayout(timing_form)
        scheduler_layout.addWidget(timing_group)
        
        # Botones de acción
        buttons_layout = QHBoxLayout()
        
        send_btn = QPushButton("✅ Enviar Flotas")
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a4a0a;
                color: #0f0;
                border: 1px solid #0f0;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0f8a0f;
            }
        """)
        send_btn.clicked.connect(self.on_send_fleet_clicked)
        buttons_layout.addWidget(send_btn)
        
        clear_btn = QPushButton("🔄 Limpiar")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a4a0a;
                color: #ff0;
                border: 1px solid #ff0;
                padding: 8px;
                border-radius: 4px;
            }
        """)
        clear_btn.clicked.connect(self.on_clear_fleet_form)
        buttons_layout.addWidget(clear_btn)
        
        scheduler_layout.addLayout(buttons_layout)
        
        # Historial de misiones programadas
        history_label = QLabel("📜 Misiones Programadas:")
        history_label.setStyleSheet("font-weight: bold; margin-top: 15px;")
        scheduler_layout.addWidget(history_label)
        
        # Botón para ejecutar envíos
        execute_btn = QPushButton("🚀 Ejecutar Envíos Pendientes")
        execute_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a3a6a;
                color: #0ff;
                border: 1px solid #0ff;
                padding: 6px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0a5a9a;
            }
        """)
        execute_btn.clicked.connect(self.on_execute_scheduled_fleets)
        scheduler_layout.addWidget(execute_btn)
        
        self.fleet_scheduled_list = QListWidget()
        self.fleet_scheduled_list.setMaximumHeight(120)
        self.fleet_scheduled_list.itemSelectionChanged.connect(self.on_fleet_selection_changed)
        scheduler_layout.addWidget(self.fleet_scheduled_list)
        
        # Botones de editar y eliminar
        fleet_actions_layout = QHBoxLayout()
        
        edit_btn = QPushButton("✏️ Editar")
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6a0a;
                color: #ff0;
                border: 1px solid #ff0;
                padding: 4px;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #6a8a0f;
            }
        """)
        edit_btn.clicked.connect(self.on_edit_fleet)
        fleet_actions_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("🗑️ Eliminar")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #6a0a0a;
                color: #f00;
                border: 1px solid #f00;
                padding: 4px;
                border-radius: 3px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #8a0f0f;
            }
        """)
        delete_btn.clicked.connect(self.on_delete_fleet)
        fleet_actions_layout.addWidget(delete_btn)
        
        fleet_actions_layout.addStretch()
        scheduler_layout.addLayout(fleet_actions_layout)
        
        # Stretch para que el resto del espacio sea vacío
        scheduler_layout.addStretch()
        
        scheduler_widget.setLayout(scheduler_layout)
        return scheduler_widget

    def create_debris_tab(self):
        """Crea la pestaña para mostrar debris y programar reciclajes"""
        debris_widget = QWidget()
        debris_layout = QVBoxLayout()
        debris_layout.setContentsMargins(5, 5, 5, 5)
        
        # Título
        title = QLabel("♻️ Escombros Disponibles [WIP]")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(11)
        title.setFont(title_font)
        debris_layout.addWidget(title)
        
        # Botón para cargar debris desde archivos JSON
        load_btn = QPushButton("📂 Cargar Datos de Debris")
        load_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a3a6a;
                color: #0ff;
                border: 1px solid #0ff;
                padding: 6px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0a5a9a;
            }
        """)
        load_btn.clicked.connect(self.load_debris_data)
        debris_layout.addWidget(load_btn)
        
        # Tabla de debris
        self.debris_list = QListWidget()
        self.debris_list.setSelectionMode(self.debris_list.SelectionMode.MultiSelection)
        debris_layout.addWidget(QLabel("🎯 Debris Detectados:"))
        debris_layout.addWidget(self.debris_list)
        
        # Filtros
        filters_group = QGroupBox("🔍 Filtros")
        filters_form = QFormLayout()
        
        self.debris_min_metal = QSpinBox()
        self.debris_min_metal.setMinimum(0)
        self.debris_min_metal.setMaximum(999999999)
        self.debris_min_metal.setValue(0)
        filters_form.addRow("Metal mínimo:", self.debris_min_metal)
        
        self.debris_max_distance = QSpinBox()
        self.debris_max_distance.setMinimum(1)
        self.debris_max_distance.setMaximum(9)
        self.debris_max_distance.setValue(9)
        filters_form.addRow("Galaxia máxima:", self.debris_max_distance)
        
        filters_group.setLayout(filters_form)
        debris_layout.addWidget(filters_group)
        
        # Botones de acción
        actions_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Actualizar Lista")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a6a0a;
                color: #ff0;
                border: 1px solid #ff0;
                padding: 6px;
                border-radius: 4px;
            }
        """)
        refresh_btn.clicked.connect(self.refresh_debris_list)
        actions_layout.addWidget(refresh_btn)
        
        recycle_btn = QPushButton("♻️ Programar Reciclaje")
        recycle_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a4a0a;
                color: #0f0;
                border: 1px solid #0f0;
                padding: 6px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0f8a0f;
            }
        """)
        recycle_btn.clicked.connect(self.schedule_recycling_missions)
        actions_layout.addWidget(recycle_btn)
        
        actions_layout.addStretch()
        debris_layout.addLayout(actions_layout)
        
        # Stretch
        debris_layout.addStretch()
        
        debris_widget.setLayout(debris_layout)
        
        # Data
        self.debris_data = []
        
        return debris_widget

    def load_debris_data(self):
        """Carga datos de debris desde los archivos galaxy_data_g*.json"""
        try:
            combined_data = {}
            
            # Cargar datos de todas las galaxias
            for g in range(1, 6):
                galaxy_file = f"galaxy_data_g{g}.json"
                if os.path.isfile(galaxy_file):
                    with open(galaxy_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        combined_data.update(data)
            
            if not combined_data:
                self._notif_label.setText("⚠️ No se encontraron archivos de galaxia")
                return
            
            # Extraer lista de debris
            self.debris_data = extract_debris_list(combined_data)
            
            # Ordenar por cantidad de metal descendente
            self.debris_data.sort(key=lambda x: x.get("metal", 0), reverse=True)
            
            self._notif_label.setText(f"✅ Cargados {len(self.debris_data)} puntos de debris")
            self.refresh_debris_list()
            
        except Exception as e:
            self._notif_label.setText(f"❌ Error cargando debris: {str(e)}")
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

    def refresh_debris_list(self):
        """Actualiza la lista visual de debris aplicando filtros"""
        self.debris_list.clear()
        
        if not self.debris_data:
            self.debris_list.addItem("No hay datos de debris. Carga los archivos primero.")
            return
        
        min_metal = self.debris_min_metal.value()
        max_galaxy = self.debris_max_distance.value()
        
        # Filtrar debris
        filtered = [
            d for d in self.debris_data
            if d.get("metal", 0) >= min_metal and d.get("galaxy", 9) <= max_galaxy
        ]
        
        # Mostrar en la lista
        for debris in filtered:
            g = debris.get("galaxy", 0)
            s = debris.get("system", 0)
            p = debris.get("position", 0)
            metal = debris.get("metal", 0)
            crystal = debris.get("crystal", 0)
            deuterium = debris.get("deuterium", 0)
            ships_needed = debris.get("requiredShips", "?")
            
            total_resources = metal + crystal + deuterium
            
            item_text = f"📍 {g}:{s}:{p} | Metal: {cantidad(metal)} | Crystal: {cantidad(crystal)} | Deut: {cantidad(deuterium)} | Total: {cantidad(total_resources)} | Naves: {ships_needed}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, debris)  # Guardar el objeto debris
            self.debris_list.addItem(item)

    def schedule_recycling_missions(self):
        """Programa misiones de reciclaje para los debris seleccionados"""
        selected_items = self.debris_list.selectedItems()
        
        if not selected_items:
            self._notif_label.setText("⚠️ Selecciona al menos un punto de debris")
            return
        
        origin_text = self.fleet_planet_combo.currentText()
        if origin_text == "Seleccionar planeta...":
            self._notif_label.setText("⚠️ Selecciona un planeta de origen")
            return
        
        # Crear misión de reciclaje para cada debris seleccionado
        missions_created = 0
        
        for item in selected_items:
            debris = item.data(Qt.ItemDataRole.UserRole)
            if not debris:
                continue
            
            g = debris.get("galaxy", 0)
            s = debris.get("system", 0)
            p = debris.get("position", 0)
            coords = f"{g}:{s}:{p}"
            
            # Crear entry de misión
            fleet_entry = {
                "id": len(self.scheduled_fleets),
                "mission": "Recolecta de escombros",
                "origin": origin_text,
                "destination": coords,
                "ships": {"Reciclador": 1},  # Por defecto 1 reciclador
                "total_ships": 1,
                "timing_type": "Enviar ahora",
                "scheduled_time": time.time(),
                "repeat_count": 1,
                "repeat_remaining": 1,
                "status": "Pendiente",
                "created_at": time.time()
            }
            
            self.scheduled_fleets.append(fleet_entry)
            missions_created += 1
        
        if missions_created > 0:
            self._refresh_scheduled_fleets_list()
            self.save_scheduled_fleets()
            self._notif_label.setText(f"✅ {missions_created} misiones de reciclaje programadas")
        
        # Limpiar selección
        self.debris_list.clearSelection()

    def on_fleet_mission_changed(self, mission_text):
        """Actualiza opciones según la misión seleccionada"""
        if mission_text == "Expedición":
            # Bloquear posición en 16 para expediciones
            self.fleet_dest_position.setValue(16)
            self.fleet_dest_position.setEnabled(False)
            # Auto-seleccionar "Cuando esté disponible" para expediciones
            self.fleet_timing_combo.blockSignals(True)
            self.fleet_timing_combo.setCurrentText("Cuando esté disponible")
            self.fleet_timing_combo.blockSignals(False)
            self.on_fleet_timing_changed("Cuando esté disponible")
        else:
            # Permitir edición normal para otras misiones
            self.fleet_dest_position.setEnabled(True)

    def on_fleet_origin_changed(self, origin_text):
        """Completa automáticamente galaxia y sistema según el planeta seleccionado"""
        if origin_text == "Seleccionar planeta..." or not origin_text:
            return
        
        # Extraer coordenadas del texto (formato: "Nombre (G:S:P)")
        try:
            if "(" in origin_text and ")" in origin_text:
                coords_str = origin_text.split("(")[1].split(")")[0]
                parts = coords_str.split(":")
                if len(parts) >= 2:
                    galaxy = int(parts[0])
                    system = int(parts[1])
                    
                    # Establecer galaxia y sistema automáticamente
                    self.fleet_dest_galaxy.setValue(galaxy)
                    self.fleet_dest_system.setValue(system)
        except (ValueError, IndexError):
            pass

    def on_fleet_timing_changed(self, timing_text):
        """Actualiza la UI según el tipo de envío seleccionado"""
        self.fleet_send_time.setEnabled(timing_text == "Programar hora específica")
        self.fleet_available_label.setVisible(timing_text == "Cuando esté disponible")

    def on_fleet_send_now_changed(self, state):
        """Actualiza la disponibilidad del campo de hora según el checkbox"""
        self.fleet_send_time.setEnabled(state == 0)  # Deshabilitado si está marcado

    def on_send_fleet_clicked(self):
        """Procesa el envío de flotas programadas"""
        mission = self.fleet_mission_combo.currentText()
        origin_text = self.fleet_planet_combo.currentText()
        
        if origin_text == "Seleccionar planeta...":
            self._notif_label.setText("⚠️ Selecciona un planeta de origen")
            return
        
        # Construir coordenadas
        g = self.fleet_dest_galaxy.value()
        s = self.fleet_dest_system.value()
        p = self.fleet_dest_position.value()
        coords = f"{g}:{s}:{p}"
        
        # Verificar que hay al menos una nave seleccionada
        ships_dict = {}
        total_ships = 0
        for ship_name, ship_info in self.fleet_ships.items():
            count = ship_info["spinbox"].value()
            if count > 0:
                ships_dict[ship_name] = count
                total_ships += count
        
        if total_ships == 0:
            self._notif_label.setText("⚠️ Debes seleccionar al menos una nave")
            return
        
        # Obtener información de timing
        timing_type = self.fleet_timing_combo.currentText()
        repeat_count = self.fleet_repeat_count.value()
        
        if timing_type == "Enviar ahora":
            send_time_str = "Ahora"
            send_timestamp = time.time()
        elif timing_type == "Programar hora específica":
            send_time_str = self.fleet_send_time.dateTime().toString("dd/MM/yyyy HH:mm")
            send_timestamp = self.fleet_send_time.dateTime().toSecsSinceEpoch()
        else:  # "Cuando esté disponible"
            send_time_str = "Cuando esté disponible"
            send_timestamp = None
        
        # Almacenar envío programado
        fleet_entry = {
            "id": len(self.scheduled_fleets),
            "mission": mission,
            "origin": origin_text,
            "destination": coords,
            "ships": ships_dict,
            "total_ships": total_ships,
            "timing_type": timing_type,
            "scheduled_time": send_timestamp,
            "repeat_count": repeat_count,
            "repeat_remaining": repeat_count,
            "status": "Pendiente",
            "created_at": time.time()
        }
        
        self.scheduled_fleets.append(fleet_entry)
        
        self._notif_label.setText(f"✅ Envío programado: {mission} a {coords} (x{repeat_count})")
        
        # Actualizar lista visual
        self._refresh_scheduled_fleets_list()
        self.save_scheduled_fleets()
        
        # Limpiar formulario
        self.on_clear_fleet_form()

    def on_clear_fleet_form(self):
        """Limpia los campos del formulario de flotas"""
        self.fleet_mission_combo.setCurrentIndex(0)
        self.fleet_planet_combo.setCurrentIndex(0)
        self.fleet_dest_galaxy.setValue(1)
        self.fleet_dest_system.setValue(1)
        self.fleet_dest_position.setValue(1)
        # Limpiar todos los SpinBox de naves
        for ship_info in self.fleet_ships.values():
            ship_info["spinbox"].setValue(0)
        self.fleet_timing_combo.setCurrentIndex(0)
        self.fleet_send_time.setDateTime(QDateTime.currentDateTime())

    def on_execute_scheduled_fleets(self):
        """Ejecuta los envíos de flotas programadas"""
        if not self.scheduled_fleets:
            self._notif_label.setText("⚠️ No hay envíos programados")
            return
        
        try:
            # Pasar los datos de flotas actuales para "Cuando esté disponible"
            results = send_scheduled_fleets(
                self.scheduled_fleets, 
                profile_path="profile_data",
                fleets_data=self.fleets_data
            )
            
            # Contar envíos exitosos
            successful = sum(1 for r in results if r["success"])
            
            # Actualizar lista visual
            self._refresh_scheduled_fleets_list()
            self.save_scheduled_fleets()
            
            self._notif_label.setText(f"✅ {successful}/{len(results)} envíos ejecutados")
        
        except Exception as e:
            self._notif_label.setText(f"❌ Error ejecutando envíos: {str(e)}")
            print(f"Error en envío de flotas: {e}")
            import traceback
            traceback.print_exc()

    def auto_send_scheduled_fleets(self):
        """Envía automáticamente los envíos de flotas programadas (llamado por timer)"""
        if not self.scheduled_fleets:
            return
        
        try:
            # Verificar si hay envíos pendientes
            pending_fleets = [f for f in self.scheduled_fleets if f.get("status") in ["Pendiente", "Enviada"]]
            if not pending_fleets:
                return
            
            print(f"\n[AUTO-SEND] Revisando {len(pending_fleets)} envíos programados...")
            
            # Pasar los datos de flotas actuales para "Cuando esté disponible"
            results = send_scheduled_fleets(
                self.scheduled_fleets, 
                profile_path="profile_data",
                fleets_data=self.fleets_data
            )
            
            if results:
                successful = sum(1 for r in results if r["success"])
                print(f"[AUTO-SEND] {successful}/{len(results)} envíos ejecutados")
                
                # Actualizar lista visual y guardar
                self._refresh_scheduled_fleets_list()
                self.save_scheduled_fleets()
        
        except Exception as e:
            print(f"[AUTO-SEND] Error: {str(e)}")

    def on_fleet_selection_changed(self):
        """Se ejecuta cuando se selecciona un elemento de la lista de misiones"""
        pass

    def on_edit_fleet(self):
        """Edita la misión seleccionada"""
        current_row = self.fleet_scheduled_list.currentRow()
        if current_row < 0:
            self._notif_label.setText("⚠️ Selecciona una misión para editar")
            return
        
        fleet = self.scheduled_fleets[current_row]
        
        # Si ya fue enviada, no permitir editar
        if fleet.get("status") == "Enviada" or fleet.get("status") == "Completada":
            self._notif_label.setText("⚠️ No puedes editar una misión que ya fue enviada")
            return
        
        # Cargar datos en el formulario
        self.fleet_mission_combo.setCurrentText(fleet.get("mission", "Expedición"))
        self.fleet_planet_combo.setCurrentText(fleet.get("origin", ""))
        
        # Extraer coordenadas
        coords = fleet.get("destination", "1:1:1").split(":")
        self.fleet_dest_galaxy.setValue(int(coords[0]))
        self.fleet_dest_system.setValue(int(coords[1]))
        self.fleet_dest_position.setValue(int(coords[2]))
        
        # Cargar naves
        for ship_name, ship_info in self.fleet_ships.items():
            ship_info["spinbox"].setValue(fleet.get("ships", {}).get(ship_name, 0))
        
        # Cargar timing
        self.fleet_timing_combo.setCurrentText(fleet.get("timing_type", "Enviar ahora"))
        if fleet.get("scheduled_time"):
            dt = QDateTime.fromSecsSinceEpoch(int(fleet.get("scheduled_time", 0)))
            self.fleet_send_time.setDateTime(dt)
        self.fleet_repeat_count.setValue(fleet.get("repeat_count", 1))
        
        # Eliminar de la lista
        self.scheduled_fleets.pop(current_row)
        self._refresh_scheduled_fleets_list()
        
        self._notif_label.setText(f"✏️ Misión editada - Guarda los cambios con 'Enviar Flotas'")
    
    def on_delete_fleet(self):
        """Elimina la misión seleccionada"""
        current_row = self.fleet_scheduled_list.currentRow()
        if current_row < 0:
            self._notif_label.setText("⚠️ Selecciona una misión para eliminar")
            return
        
        fleet = self.scheduled_fleets[current_row]
        mission = fleet.get("mission", "Expedición")
        destination = fleet.get("destination", "?:?:?")
        
        self.scheduled_fleets.pop(current_row)
        self._refresh_scheduled_fleets_list()
        
        self._notif_label.setText(f"🗑️ Eliminada: {mission} → {destination}")
        self.save_scheduled_fleets()
    
    def _refresh_scheduled_fleets_list(self):
        """Actualiza la lista visual de misiones programadas"""
        self.fleet_scheduled_list.clear()
        for idx, fleet in enumerate(self.scheduled_fleets):
            status_icon = "⏳"
            if fleet.get("status") == "Enviada":
                status_icon = "🔄" if fleet.get("repeat_remaining", 0) > 0 else "✅"
            elif fleet.get("status") == "Completada":
                status_icon = "✅"
            
            repeat_text = f" (x{fleet.get('repeat_remaining', 1)})" if fleet.get("repeat_count", 1) > 1 else ""
            entry_text = f"{status_icon} {fleet.get('mission')} → {fleet.get('destination')}{repeat_text}"
            item = QListWidgetItem(entry_text)
            self.fleet_scheduled_list.addItem(item)

    def update_fleet_origin_combo(self):
        """Actualiza el combo de planetas disponibles basado en los datos cargados"""
        current_text = self.fleet_planet_combo.currentText()
        
        # Limpiar combo pero mantener la opción por defecto
        self.fleet_planet_combo.clear()
        self.fleet_planet_combo.addItem("Seleccionar planeta...")
        
        # Agregar todos los planetas disponibles
        for planet_key in sorted(self.planets_data.keys()):
            pdata = self.planets_data[planet_key]
            coords = pdata.get("coords", "0:0:0")
            
            # Obtener nombre del planeta desde la clave
            if '|' in planet_key:
                name = planet_key.split('|')[0]
            else:
                name = planet_key
            
            # Formato: "Nombre (Coordenadas)"
            display_text = f"{name} ({coords})"
            self.fleet_planet_combo.addItem(display_text, planet_key)
        
        # Restaurar selección anterior si existe
        if current_text and current_text != "Seleccionar planeta...":
            index = self.fleet_planet_combo.findText(current_text)
            if index >= 0:
                self.fleet_planet_combo.setCurrentIndex(index)

    def on_update_interval_changed(self):
        """Actualiza el intervalo de los timers cuando el usuario cambia la selección."""
        new_interval = self.update_interval_combo.currentData()
        if new_interval is not None:
            self.current_update_interval = new_interval
            
            # Actualizar timers
            if hasattr(self, 'timer_global'):
                self.timer_global.setInterval(new_interval)
            if hasattr(self, 'queue_timer'):
                self.queue_timer.setInterval(new_interval)
            if hasattr(self, 'panel_timer'):
                self.panel_timer.setInterval(new_interval)
            
            print(f"[DEBUG] Intervalo de actualización cambiado a {new_interval}ms")

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
        
        # Detectar si es luna (probablemente el nombre contenga "Moon" o similar)
        is_moon = 'moon' in planet.lower() if planet else False
        
        self.current_main_web_planet = planet
        self.current_main_web_coords = coords
        self.current_main_web_is_moon = is_moon
        
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
        
        self.update_planet_data(
            planet_name=planet_name,
            coords=coords,
            resources=resources,
            queues=queues_list,
            is_moon=is_moon,
            parent_planet_key=parent_planet_key
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
            # Actualizar flotas inicialmente
            QTimer.singleShot(2000, self.update_fleets)
            # Inicializar combo de planetas después que se carguen datos
            QTimer.singleShot(5000, self.update_fleet_origin_combo)
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
                QTimer.singleShot(1200, self.load_moon_for_current_planet)
            else:
                QTimer.singleShot(1200, finish_and_next)

        try:
            self.main_web.loadFinished.connect(on_planet_load_finished)
            self.main_web.load(QUrl(planet_url))
        except Exception as e:
            print('[DEBUG] Error cargando planeta en main_web:', e)
            QTimer.singleShot(1000, finish_and_next)

        # avanzar índice inmediatamente
        self.current_planet_index += 1

    def load_moon_for_current_planet(self):
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
        self.current_planet_parent_key = self._get_planet_key(
            self.current_main_web_planet,
            self.current_main_web_coords
        )
        
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

    # ====================================================================
    #  FLEETS
    # ====================================================================
    def update_fleets(self):
        """Actualiza el estado de flotas en movimiento"""
        try:
            # Usar FleetWorker para obtener datos de flotas
            fleet_worker = FleetWorker()  # Cargará la sesión automáticamente
            result = fleet_worker.get_fleet_status()
            
            if result.get("success"):
                self.fleets_data = result.get("fleets", [])
                self.last_fleet_update = result.get("timestamp", time.time())
                print(f"[FLEETS] Actualizadas {len(self.fleets_data)} flotas activas")
                self.refresh_main_panel()
            else:
                print(f"[FLEETS] Error: {result.get('error', 'Unknown')}")
        
        except Exception as e:
            print(f"[FLEETS] Error en update_fleets: {e}")
            import traceback
            traceback.print_exc()

    # ====================================================================
    #  PANEL PRINCIPAL
    # ====================================================================
    def refresh_main_panel(self):
        """Actualiza ambas secciones del panel (recursos y flotas)"""
        self.refresh_resources_panel()
        self.refresh_fleets_panel()

    def refresh_resources_panel(self):
        """Actualiza la pestaña de Recursos y Colas"""
        html = """
        <style>
            body { background-color: #000; color: #EEE; font-family: Consolas; }
            table { border-collapse: collapse; margin-top: 10px; width: 100%; }
            th { background-color: #222; color: #0f0; border: 1px solid #333; padding: 8px; text-align: center; }
            td { background-color: #111; color: #EEE; border: 1px solid #333; padding: 6px; font-size: 12px; }
            .bar { font-family: monospace; }
            .research-section { background-color: #1a1a2e; padding: 8px; margin-top: 10px; border: 1px solid #0af; }
            .moon-section { background-color: #0a1a1a; padding: 4px 6px; margin-top: 4px; border-left: 2px solid #0af; font-size: 11px; }
        </style>
        <h2>🌌 Recursos y Colas</h2>
        """

        if not self.planets_data:
            html += "<p>No hay datos de planetas aún.</p>"
            self.resources_label.setText(html)
            return

        def queue_entry(entry, now):
            name = entry.get('name', '')
            start = entry.get('start', now)
            end = entry.get('end', now)

            remaining = max(0, end - now)
            time = time_str(remaining, True)

            progress = 0
            if end > start:
                progress = min(100, max(0, ((now - start) / (end - start)) * 100))

            return name, time, progress

        def format_queue_entry(entry, now):
            """Formato amigable para mostrar una queue"""
            name, time, progress = queue_entry(entry, now)
            color = progress_color(progress)
            barra = barra_html(progress, 100, color)
            aux = f"{name} [{int(progress)}%] ({time})"
            if len(aux) > 40:
                return f"{name}<br>[{int(progress)}%] ({time})<br>{barra}"
            else:
                return f"{aux}<br>{barra}"
        
        def format_research_queue_entry(entry, now):
            """Formato amigable para mostrar una queue de Investigacion"""
            name, time, progress = queue_entry(entry, now)
            color = progress_color(progress, 89)
            color = "#0f0" if progress < 89 else "#ff0" if progress < 95 else "#f00"
            barra = barra_html(progress, 100, color, 50)
            return f"{barra} {name} [{progress:.2f}%] ({time})"
        
        # Extraer solo planetas (no lunas) para las columnas
        planet_info = []
        for key in self.planets_data.keys():
            parts = key.rsplit('|', 1)
            if len(parts) == 2:
                name, coords = parts
                planet_info.append((name, coords, key))
            else:
                planet_info.append((key, "0:0:0", key))
        
        now = int(time.time())

        # ----- Investigaciones (global, deduplicadas por label+name)
        unique_research = {}
        for planet_key, pdata in self.planets_data.items():
            queues = pdata.get("queues", [])
            for q in queues:
                label = (q.get("label", "") or "")
                name = (q.get("name", "") or "")
                is_research = (
                    "Investigación" in label or "🧬" in label or
                    "investig" in label.lower() or "research" in label.lower()
                )
                if is_research:
                    key = f"{label}|{name}".strip().lower()
                    if key not in unique_research:
                        unique_research[key] = q

        # Incluir investigaciones globales (desde popups) también
        for q in getattr(self, 'global_queues', {}).values():
            label = (q.get("label", "") or "")
            name = (q.get("name", "") or "")
            key = f"{label}|{name}".strip().lower()
            if key not in unique_research:
                unique_research[key] = q

        if unique_research:
            html += "<div class='research-section'><b>🧬 Investigaciones:</b><br>"
            for entry in unique_research.values():
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
                    if prodInt > 0:
                        full = f"({produccion(prodInt)}) lleno en {tiempo_lleno(cant, cap, prodInt)}"
                    else:
                        full = f"({produccion(prodInt)}) vacio en {tiempo_lleno(cant, cap, -prodInt)}"
                else:
                    full = f" - almacenes llenos!!!"
                char = progress_color((cant / cap) * 100)
                barra = barra_html(cant, cap, color, 19) + f"<span style='color:{char};'>{'█'}</span>"
                html += f"<td>{cantidad(cant)} {full}<br>{barra}"
                
                # Mostrar lunas si existen
                moons = pdata.get("moons", {})
                if moons:
                    html += "<div class='moon-section'>"
                    for moon_key, moon_data in moons.items():
                        moon_name = moon_data.get("name", "Moon")
                        moon_resources = moon_data.get("resources", {})
                        moon_cant = moon_resources.get(rkey, 0)
                        html += f"🌙 {moon_name}: {cantidad(moon_cant)}"
                    html += "</div>"
                
                html += "</td>"

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
            
            # Agregar colas de lunas también
            moons = self.planets_data[key].get("moons", {})
            for moon_key, moon_data in moons.items():
                for q in moon_data.get("queues", []):
                    label = q.get("label", "")
                    end = int(q.get("end", now))
                    if end <= now:
                        continue
                    # Para lunas, solo mostrar construcciones
                    queue_types["🏗️ Construcciones"].append((name, coords, q, moon_data.get("name", "Moon")))

        for qtype, entries in queue_types.items():
            if not entries:
                continue

            html += f"<tr><td><b>{qtype}</b></td>"

            for name, coords, key in planet_info:
                # Colas del planeta: filtrar y extraer solo el dict q
                planet_entries = [e[2] for e in entries if len(e) == 3 and e[0] == name and e[1] == coords]
                # Colas de lunas del planeta: extraer (q_dict, moon_name)
                moon_entries = [(e[2], e[3]) for e in entries if len(e) == 4 and e[0] == name and e[1] == coords]
                
                if not planet_entries and not moon_entries:
                    html += "<td>—</td>"
                    continue

                html += "<td>"
                
                # Mostrar colas del planeta
                for idx, q in enumerate(planet_entries):
                    html += format_queue_entry(q, now)
                    if idx < len(planet_entries) - 1 or moon_entries:
                        html += "<br>"
                
                # Mostrar colas de lunas
                for midx, (q, moon_name) in enumerate(moon_entries):
                    html += f"<div class='moon-section'>🌙 {moon_name}<br>"
                    html += format_queue_entry(q, now)
                    html += "</div>"
                    if midx < len(moon_entries) - 1:
                        html += "<br>"
                
                html += "</td>"

            html += "</tr>"
        html += "</table>"

        self.resources_label.setHtml(html)

    def refresh_fleets_panel(self):
        """Actualiza la pestaña de Flotas en Movimiento"""
        html = """
        <style>
            body { background-color: #000; color: #EEE; font-family: Consolas; }
            table { border-collapse: collapse; margin-top: 10px; width: 100%; }
            th { background-color: #222; color: #0f0; border: 1px solid #333; padding: 8px; text-align: center; }
            td { background-color: #111; color: #EEE; border: 1px solid #333; padding: 6px; font-size: 12px; }
            .bar { font-family: monospace; }
        </style>
        <h2>🚀 Flotas en Movimiento</h2>
        """

        if not self.fleets_data:
            html += "<p style='color: #666;'>📭 Sin flotas en movimiento</p>"
            self.fleets_label.setHtml(html)
            return

        html += "<table><tr><th>Misión</th><th>Origen</th><th>Destino</th><th>Naves</th><th>Llegada</th><th>Estado</th></tr>"
        
        now = int(time.time())
        
        for fleet in self.fleets_data:
            mission = fleet.get('mission_name', '—')
            origin = f"{fleet['origin']['name']}<br>{fleet['origin']['coords']}"
            dest = f"{fleet['destination']['name']}<br>{fleet['destination']['coords']}"
            ships_count = fleet.get('ships_count', 0)
            arrival_clock = fleet.get('arrival_clock', '—')
            arrival_time = fleet.get('arrival_time', 0)
            
            # Calcular tiempo faltante
            remaining = max(0, arrival_time - now)
            time_remaining = time_str(remaining, True) if remaining > 0 else "Llegó"
            
            # Color según estado
            if remaining <= 0:
                color = "#f00"  # Rojo - llegó
            elif remaining <= 300:  # 5 minutos
                color = "#f80"  # Naranja - pronto
            else:
                color = "#0f0"  # Verde - en camino
            
            # Indicador de regreso
            return_indicator = " (R)" if fleet.get('return_flight', False) else ""
            
            html += f"<tr><td>{mission}{return_indicator}</td>"
            html += f"<td><small>{origin}</small></td>"
            html += f"<td><small>{dest}</small></td>"
            html += f"<td>{ships_count}</td>"
            html += f"<td><small>{arrival_clock}</small></td>"
            html += f"<td><span style='color: {color}; font-weight: bold;'>{time_remaining}</span></td>"
            html += "</tr>"
        
        html += "</table>"
        
        self.fleets_label.setHtml(html)


    # ====================================================================
    #  UPDATE PLANET DATA (API nueva con queues que incluyen id)
    # ====================================================================
    def update_planet_data(self, planet_name, coords, resources, queues, is_moon=False, parent_planet_key=None):
        """
        Recibe:
          - planet_name (str)
          - coords (str)
          - resources (dict)
          - queues (list of queue dicts, cada uno con 'id','label','name','start','end','planet_name','coords',...)
          - is_moon (bool): indica si es una luna
          - parent_planet_key (str): ID del planeta padre (si es luna)
        """
        # Normalizar recursos: asegurar last_update timestamp
        resources = resources or {}
        if "last_update" not in resources:
            resources["last_update"] = time.time()

        # Usar el ID del planeta como clave única para evitar duplicados
        planet_id = getattr(self, 'current_main_web_planet_id', None)
        
        # Si no tenemos ID, generar uno basado en coords (fallback)
        if not planet_id:
            planet_id = self._get_planet_key(planet_name, coords)
        
        # Filtrar las queues: solo edificios para lunas
        qlist = []
        for q in queues or []:
            qid = q.get("id")
            if not qid:
                continue
            q_planet = q.get("planet_name", planet_name)
            q_coords = q.get("coords", coords)

            # Para lunas, ignorar investigaciones (que son globales)
            if is_moon:
                label = q.get("label", "")
                is_research = (
                    "investig" in label.lower() or "research" in label.lower() or "🧬" in label
                )
                if is_research:
                    continue  # Ignorar investigaciones en lunas

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
                continue

            # Si la cola pertenece a este planeta, verificar nombre Y coordenadas
            # Esto es importante cuando hay múltiples planetas con el mismo nombre
            if q_planet == planet_name and q_coords == coords:
                qlist.append(entry)

        if is_moon and parent_planet_key:
            # Guardar luna de forma anidada dentro del planeta usando el ID del planeta padre
            if parent_planet_key not in self.planets_data:
                # Si el planeta padre no existe aún, crear un placeholder
                self.planets_data[parent_planet_key] = {
                    "planet_id": parent_planet_key,
                    "coords": "",
                    "resources": {},
                    "queues": [],
                    "moons": {}
                }
            
            # Inicializar estructura de moons si no existe
            if "moons" not in self.planets_data[parent_planet_key]:
                self.planets_data[parent_planet_key]["moons"] = {}
            
            # Guardar luna dentro del planeta usando su ID como clave
            self.planets_data[parent_planet_key]["moons"][planet_id] = {
                "name": planet_name,
                "coords": coords,
                "resources": resources,
                "queues": qlist,
                "last_update": time.time(),
                "planet_id": planet_id
            }
        else:
            # Guardar planeta normalmente
            pdata = self.planets_data.get(planet_id, {})
            pdata["planet_id"] = planet_id
            pdata["coords"] = coords
            pdata["resources"] = resources
            pdata["queues"] = qlist
            pdata["last_update"] = time.time()
            
            # Asegurar que existe la estructura de moons
            if "moons" not in pdata:
                pdata["moons"] = {}
            
            self.planets_data[planet_id] = pdata

        # Refrescar UI
        try:
            self.refresh_main_panel()
            self.update_fleet_origin_combo()  # Actualizar combo de planetas
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
