import json
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox,
    QSpinBox, QGroupBox, QFormLayout, QListWidget,
    QListWidgetItem, QDateTimeEdit, QGridLayout
)
from PyQt6.QtCore import QDateTime, QThread, pyqtSignal, QObject

from fleet_sender import send_scheduled_fleets

class FleetSendWorker(QObject):
    """Worker para enviar flotas programadas sin bloquear la UI"""
    finished = pyqtSignal()
    success = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, scheduled_fleets, profile_path, fleet_slots=None, exp_slots=None):
        super().__init__()
        self.scheduled_fleets = scheduled_fleets
        self.profile_path = profile_path
        self.fleet_slots = fleet_slots or {"current": 0, "max": 0}
        self.exp_slots = exp_slots or {"current": 0, "max": 0}
    
    def run(self):
        """Envía flotas programadas en hilo separado"""
        try:
            results = send_scheduled_fleets(
                self.scheduled_fleets,
                profile_path=self.profile_path,
                fleet_slots=self.fleet_slots,
                exp_slots=self.exp_slots
            )
            
            if results:
                self.success.emit(results)
            else:
                self.error.emit('No results from send_scheduled_fleets')
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

def create_fleets_tab(self):
    fleets_tab = QWidget()
    fleets_layout = QVBoxLayout()
    fleets_layout.setContentsMargins(5, 5, 5, 5)
    fleets_layout.setSpacing(10)

    # Programador de naves
    scheduler = create_fleet_scheduler_panel(self)
    fleets_layout.addWidget(scheduler)
    
    fleets_tab.setLayout(fleets_layout)
    return fleets_tab

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
        "Transporte",
        "Desplegar",
        "Expedición",
        "Recolecta de escombros",
        "Ataque",
        "Espía"
    ])
    self.fleet_mission_combo.currentTextChanged.connect(lambda text: on_fleet_mission_changed(self, text))
    mission_form.addRow("Tipo de Misión:", self.fleet_mission_combo)
    
    self.fleet_planet_combo = QComboBox()
    self.fleet_planet_combo.addItem("Seleccionar planeta...")
    self.fleet_planet_combo.currentTextChanged.connect(lambda text: on_fleet_origin_changed(self, text))
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
        ship_layout.addWidget(spinbox)
        ship_layout.addWidget(QLabel(f" {ship_name}"))
        ship_layout.addStretch()
        
        # Agregar a la grilla (4 columnas)
        ships_grid.addLayout(ship_layout, row, col)
        
        col += 1
        if col >= 4:
            col = 0
            row += 1
    
    ships_layout.addWidget(ships_container)
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
    self.fleet_timing_combo.currentTextChanged.connect(lambda text: on_fleet_timing_changed(self, text))
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
    send_btn.clicked.connect(lambda: on_send_fleet_clicked(self))
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
    clear_btn.clicked.connect(lambda: on_clear_fleet_form(self))
    buttons_layout.addWidget(clear_btn)
    
    scheduler_layout.addLayout(buttons_layout)
    
    # Historial de misiones programadas
    history_label = QLabel("📜 Misiones Programadas:")
    history_label.setStyleSheet("font-weight: bold; margin-top: 15px;")
    scheduler_layout.addWidget(history_label)
    
    self.fleet_scheduled_list = QListWidget()
    self.fleet_scheduled_list.setMaximumHeight(120)
    self.fleet_scheduled_list.itemSelectionChanged.connect(on_fleet_selection_changed)
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
    edit_btn.clicked.connect(lambda: on_edit_fleet(self))
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
    delete_btn.clicked.connect(lambda: on_delete_fleet(self))
    fleet_actions_layout.addWidget(delete_btn)
    
    fleet_actions_layout.addStretch()
    scheduler_layout.addLayout(fleet_actions_layout)
    
    # Stretch para que el resto del espacio sea vacío
    scheduler_layout.addStretch()
    
    scheduler_widget.setLayout(scheduler_layout)
    return scheduler_widget

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
        on_fleet_timing_changed(self,"Cuando esté disponible")
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
    _refresh_scheduled_fleets_list(self)
    save_scheduled_fleets(self.scheduled_fleets)
    
    # Limpiar formulario
    on_clear_fleet_form(self)

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

def auto_send_scheduled_fleets(self):
    """Envía automáticamente los envíos de flotas programadas (llamado por timer, en hilo separado)"""
    if not self.scheduled_fleets:
        return
    
    # Verificar si hay envíos pendientes
    pending_fleets = [f for f in self.scheduled_fleets if f.get("status") in ["Pendiente"]]
    if not pending_fleets:
        return
    
    # Crear worker y thread para envío
    self.fleet_send_thread = QThread()
    self.fleet_send_worker = FleetSendWorker(
        self.scheduled_fleets,
        profile_path="profile_data",
        fleet_slots=self.fleet_slots,
        exp_slots=self.exp_slots
    )
    self.fleet_send_worker.moveToThread(self.fleet_send_thread)
    
    # Conectar señales
    self.fleet_send_thread.started.connect(self.fleet_send_worker.run)
    self.fleet_send_worker.finished.connect(self.fleet_send_thread.quit)
    self.fleet_send_worker.success.connect(lambda msg: _on_fleet_send_success(self, msg))
    self.fleet_send_worker.error.connect(lambda msg: _on_fleet_send_error(self, msg))
    
    # Iniciar thread
    self.fleet_send_thread.start()

def _on_fleet_send_success(self, results):
    """Callback cuando el envío de flotas es exitoso"""
    successful = sum(1 for r in results if r["success"])
    print(f"[AUTO-SEND] {successful}/{len(results)} envíos ejecutados")
    self.main_web.reload()
    # Actualizar lista visual y guardar
    _refresh_scheduled_fleets_list(self)
    save_scheduled_fleets(self.scheduled_fleets)

def _on_fleet_send_error(self, error_msg):
    """Callback cuando hay error en el envío de flotas"""
    print(f"[AUTO-SEND] Error: {error_msg}")

def on_fleet_selection_changed():
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
    self.fleet_mission_combo.setCurrentText(fleet.get("mission", ""))
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
    _refresh_scheduled_fleets_list(self)
    
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
    _refresh_scheduled_fleets_list(self)
    
    self._notif_label.setText(f"🗑️ Eliminada: {mission} → {destination}")
    save_scheduled_fleets(self.scheduled_fleets)

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
    
    # Crear lista de planetas ordenada por coordenadas
    planet_list = []
    for planet_id, pdata in self.planets_data.items():
        name = pdata.get("name", "Unknown")
        coords = pdata.get("coords", "0:0:0")
        planet_list.append((name, coords, planet_id))
    
    # Ordenar por coordenadas
    def coords_sort_key(item):
        name, coords, pid = item
        try:
            parts = coords.split(":")
            g = int(parts[0]) if len(parts) > 0 else 0
            s = int(parts[1]) if len(parts) > 1 else 0
            p = int(parts[2]) if len(parts) > 2 else 0
            return (g, s, p)
        except (ValueError, IndexError):
            return (0, 0, 0)
    
    planet_list.sort(key=coords_sort_key)
    
    # Agregar todos los planetas disponibles
    for name, coords, planet_id in planet_list:
        # Formato: "Nombre (Coordenadas)"
        display_text = f"{name} ({coords})"
        self.fleet_planet_combo.addItem(display_text, planet_id)
    
    # Restaurar selección anterior si existe
    if current_text and current_text != "Seleccionar planeta...":
        index = self.fleet_planet_combo.findText(current_text)
        if index >= 0:
            self.fleet_planet_combo.setCurrentIndex(index)

def save_scheduled_fleets(scheduled_fleets):
    """Guarda las misiones programadas en un archivo JSON"""
    try:
        with open("scheduled_fleets.json", "w", encoding="utf-8") as f:
            json.dump(scheduled_fleets, f, indent=2, ensure_ascii=False)
            print(f"✅ Guardadas {len(scheduled_fleets)} misiones programadas")
    except Exception as e:
        print(f"⚠️ Error guardando misiones: {e}")