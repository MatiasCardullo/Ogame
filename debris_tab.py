import json, os, time, traceback, threading, subprocess, sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QGroupBox, QFormLayout, 
    QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt
from fleet_tab import _refresh_scheduled_fleets_list, save_scheduled_fleets
from text import cantidad

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
    
    # Botones de carga
    load_buttons_layout = QHBoxLayout()
    
    load_all_btn = QPushButton("📂 Escanear Todas las Galaxias")
    load_all_btn.setStyleSheet("""
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
    load_all_btn.clicked.connect(lambda: run_galaxy_worker_and_refresh(self, galaxy_only=None))
    load_buttons_layout.addWidget(load_all_btn)
    
    self.load_single_galaxy_btn = QPushButton("🌍 Escanear Galaxia Seleccionada")
    self.load_single_galaxy_btn.setStyleSheet("""
        QPushButton {
            background-color: #3a5a0a;
            color: #ff0;
            border: 1px solid #ff0;
            padding: 6px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #5a7a0f;
        }
    """)
    self.load_single_galaxy_btn.clicked.connect(lambda: load_selected_galaxy(self))
    load_buttons_layout.addWidget(self.load_single_galaxy_btn)
    
    load_buttons_layout.addStretch()
    debris_layout.addLayout(load_buttons_layout)
    
    # Botones para cargar desde JSONs (sin GalaxyWorker)
    json_buttons_layout = QHBoxLayout()
    
    load_all_json_btn = QPushButton("📄 Cargar desde JSONs (Todas)")
    load_all_json_btn.setStyleSheet("""
        QPushButton {
            background-color: #3a3a0a;
            color: #ff0;
            border: 1px solid #ff0;
            padding: 6px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #5a5a0f;
        }
    """)
    load_all_json_btn.clicked.connect(lambda: load_debris_data(self))
    json_buttons_layout.addWidget(load_all_json_btn)
    
    self.load_single_json_btn = QPushButton("📄 Recargar desde JSON")
    self.load_single_json_btn.setStyleSheet("""
        QPushButton {
            background-color: #2a3a0a;
            color: #ff0;
            border: 1px solid #ff0;
            padding: 6px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #4a5a0f;
        }
    """)
    self.load_single_json_btn.clicked.connect(lambda: load_debris_data(self))
    json_buttons_layout.addWidget(self.load_single_json_btn)
    
    json_buttons_layout.addStretch()
    debris_layout.addLayout(json_buttons_layout)
    
    # Tabla de debris
    self.debris_table = QTableWidget()
    self.debris_table.setColumnCount(7)
    self.debris_table.setHorizontalHeaderLabels(["Coordenadas", "Metal", "Crystal", "Deuterium", "Total", "Naves", ""])
    self.debris_table.setSelectionBehavior(self.debris_table.SelectionBehavior.SelectRows)
    self.debris_table.setSelectionMode(self.debris_table.SelectionMode.MultiSelection)
    self.debris_table.horizontalHeader().setStretchLastSection(False)
    self.debris_table.setColumnWidth(0, 100)
    self.debris_table.setColumnWidth(1, 120)
    self.debris_table.setColumnWidth(2, 120)
    self.debris_table.setColumnWidth(3, 120)
    self.debris_table.setColumnWidth(4, 120)
    self.debris_table.setColumnWidth(5, 70)
    self.debris_table.setColumnWidth(6, 30)
    debris_layout.addWidget(QLabel("🎯 Debris Detectados:"))
    debris_layout.addWidget(self.debris_table)
    
    # Filtros
    filters_group = QGroupBox("🔍 Filtros")
    filters_form = QFormLayout()
    
    self.debris_resource_type = QComboBox()
    self.debris_resource_type.addItems(["Todos", "Metal", "Crystal", "Deuterium"])
    self.debris_resource_type.setCurrentIndex(0)
    filters_form.addRow("Filtrar por:", self.debris_resource_type)
    
    self.debris_galaxy = QSpinBox()
    self.debris_galaxy.setMinimum(1)
    self.debris_galaxy.setMaximum(5)
    self.debris_galaxy.setValue(5)
    filters_form.addRow("Galaxia:", self.debris_galaxy)
    
    filters_group.setLayout(filters_form)
    debris_layout.addWidget(filters_group)
    
    # Botones de acción
    actions_layout = QHBoxLayout()
    
    refresh_btn = QPushButton("🔄 Actualizar Filtros")
    refresh_btn.setStyleSheet("""
        QPushButton {
            background-color: #4a6a0a;
            color: #ff0;
            border: 1px solid #ff0;
            padding: 6px;
            border-radius: 4px;
        }
    """)
    refresh_btn.clicked.connect(lambda: refresh_debris_list(self))
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
    recycle_btn.clicked.connect(lambda: schedule_recycling_missions(self))
    actions_layout.addWidget(recycle_btn)
    
    actions_layout.addStretch()
    debris_layout.addLayout(actions_layout)
    
    # Stretch
    debris_layout.addStretch()
    
    debris_widget.setLayout(debris_layout)
    
    # Data
    self.debris_data = []
    
    return debris_widget

def extract_debris_list(galaxy_data: dict):
    debris_list = []

    for g, systems in galaxy_data.items():
        # Verificar que systems es un diccionario
        if not isinstance(systems, dict):
            continue
            
        for s, positions in systems.items():
            # Verificar que positions es un diccionario
            if not isinstance(positions, dict):
                continue
                
            for pos, entry in positions.items():
                # Verificar que entry es un diccionario
                if not isinstance(entry, dict):
                    continue
                    
                debris = entry.get("debris")
                if not debris:
                    continue

                try:
                    debris_list.append({
                        "galaxy": int(g),
                        "system": int(s),
                        "position": int(pos),
                        "metal": int(debris.get("metal", 0)) if isinstance(debris, dict) else 0,
                        "crystal": int(debris.get("crystal", 0)) if isinstance(debris, dict) else 0,
                        "deuterium": int(debris.get("deuterium", 0)) if isinstance(debris, dict) else 0,
                        "requiredShips": debris.get("requiredShips") if isinstance(debris, dict) else None
                    })
                except (ValueError, TypeError, AttributeError):
                    # Ignorar entries con datos malformados
                    continue

    return debris_list

def load_debris_data(self):
    """Carga datos de debris desde los archivos galaxy_data_g*.json"""
    try:
        combined_data = {}
        files_loaded = 0
        
        # Cargar datos de todas las galaxias
        for g in range(1, 6):
            galaxy_file = f"galaxy_data_g{g}.json"
            if os.path.isfile(galaxy_file):
                try:
                    with open(galaxy_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            combined_data.update(data)
                            files_loaded += 1
                            print(f"✅ Cargado {galaxy_file} ({len(data)} entradas)")
                except Exception as e:
                    print(f"⚠️ Error cargando {galaxy_file}: {e}")
        
        if not combined_data:
            self._notif_label.setText("⚠️ No se encontraron archivos de galaxia o están vacíos")
            return
        
        print(f"📊 Total de archivos cargados: {files_loaded}")
        print(f"📊 Total de entradas: {len(combined_data)}")
        
        # Extraer lista de debris
        self.debris_data = extract_debris_list(combined_data)
        
        # Ordenar por cantidad de metal descendente
        self.debris_data.sort(key=lambda x: x.get("metal", 0), reverse=True)
        
        self._notif_label.setText(f"✅ Cargados {len(self.debris_data)} puntos de debris de {files_loaded} archivo(s)")
        print(f"✅ Debris extraído: {len(self.debris_data)} puntos")
        refresh_debris_list(self)
        
    except Exception as e:
        self._notif_label.setText(f"❌ Error cargando debris: {str(e)}")
        print(f"❌ Error: {e}")
        traceback.print_exc()

def run_galaxy_worker_and_refresh(self, galaxy_only=None):
    """Ejecuta galaxy_worker.py en una consola separada para obtener datos de galaxia
    
    Args:
        galaxy_only: Si es None, escanea todas las galaxias (1-5). Si es un número, escanea solo esa galaxia.
    """
    try:
        self._notif_label.setText("🔄 Abriendo consola para explorar galaxias...")        
        
        def run_galaxy_workers_subprocess():
            try:
                galaxies_to_scan = [galaxy_only] if galaxy_only else range(1, 6)
                
                for galaxy_num in galaxies_to_scan:
                    try:
                        # Ejecutar galaxy_worker.py con argumento del número de galaxia
                        if sys.platform == "win32":
                            subprocess.Popen(
                                [sys.executable, "galaxy_worker.py", str(galaxy_num)],
                                creationflags=subprocess.CREATE_NEW_CONSOLE
                            )
                        else:
                            # Para otros sistemas operativos
                            subprocess.Popen([sys.executable, "galaxy_worker.py", str(galaxy_num)])
                        
                        print(f"[DEBUG] Galaxia {galaxy_num} lanzada en consola separada")
                        
                    except Exception as e:
                        self._notif_label.setText(f"❌ Error lanzando galaxia {galaxy_num}: {str(e)}")
                        print(f"[GalaxyWorker] Error en galaxia {galaxy_num}: {e}")
                        traceback.print_exc()
                
                self._notif_label.setText("✅ Procesos GalaxyWorker lanzados en consolas separadas")
                print("[GalaxyWorker] Todos los procesos han sido lanzados")
                
            except Exception as e:
                self._notif_label.setText(f"❌ Error ejecutando GalaxyWorker: {str(e)}")
                print(f"❌ Error: {e}")
                traceback.print_exc()
        
        # Ejecutar en thread para no bloquear UI
        thread = threading.Thread(target=run_galaxy_workers_subprocess, daemon=True)
        thread.start()
        
    except Exception as e:
        self._notif_label.setText(f"❌ Error ejecutando GalaxyWorker: {str(e)}")
        print(f"❌ Error: {e}")
        traceback.print_exc()

def load_selected_galaxy(self):
    """Carga solo la galaxia seleccionada en el filtro"""
    selected_galaxy = self.debris_galaxy.value()
    run_galaxy_worker_and_refresh(self, galaxy_only=selected_galaxy)

def refresh_debris_list(self):
    """Actualiza la tabla visual de debris aplicando filtros"""
    self.debris_table.setRowCount(0)
    
    if not self.debris_data:
        row = self.debris_table.rowCount()
        self.debris_table.insertRow(row)
        item = QTableWidgetItem("No hay datos de debris. Carga los archivos primero.")
        self.debris_table.setItem(row, 0, item)
        return
    
    resource_type = self.debris_resource_type.currentText()
    target_galaxy = self.debris_galaxy.value()
    
    # Filtrar debris por galaxia y recurso
    filtered = [
        d for d in self.debris_data
        if d.get("galaxy", 0) == target_galaxy
    ]
    
    # Si no es "Todos", filtrar por tipo de recurso
    if resource_type != "Todos":
        if resource_type == "Metal":
            filtered = [d for d in filtered if d.get("metal", 0) > 0]
        elif resource_type == "Crystal":
            filtered = [d for d in filtered if d.get("crystal", 0) > 0]
        elif resource_type == "Deuterium":
            filtered = [d for d in filtered if d.get("deuterium", 0) > 0]
    
    # Mostrar en la tabla
    for debris in filtered:
        g = debris.get("galaxy", 0)
        s = debris.get("system", 0)
        p = debris.get("position", 0)
        metal = debris.get("metal", 0)
        crystal = debris.get("crystal", 0)
        deuterium = debris.get("deuterium", 0)
        ships_needed = debris.get("requiredShips", "?")
        
        total_resources = metal + crystal + deuterium
        
        row = self.debris_table.rowCount()
        self.debris_table.insertRow(row)
        
        # Columna 0: Coordenadas
        coords_item = QTableWidgetItem(f"{g}:{s}:{p}")
        self.debris_table.setItem(row, 0, coords_item)
        
        # Columna 1: Metal
        metal_item = QTableWidgetItem(cantidad(metal))
        metal_item.setData(Qt.ItemDataRole.UserRole, debris)  # Guardar el objeto debris
        self.debris_table.setItem(row, 1, metal_item)
        
        # Columna 2: Crystal
        crystal_item = QTableWidgetItem(cantidad(crystal))
        self.debris_table.setItem(row, 2, crystal_item)
        
        # Columna 3: Deuterium
        deut_item = QTableWidgetItem(cantidad(deuterium))
        self.debris_table.setItem(row, 3, deut_item)
        
        # Columna 4: Total
        total_item = QTableWidgetItem(cantidad(total_resources))
        self.debris_table.setItem(row, 4, total_item)
        
        # Columna 5: Ships
        ships_item = QTableWidgetItem(str(ships_needed))
        self.debris_table.setItem(row, 5, ships_item)
        
        # Columna 6: Empty (para checkbox si lo necesitamos luego)
        empty_item = QTableWidgetItem("")
        self.debris_table.setItem(row, 6, empty_item)

def schedule_recycling_missions(self):
    """Programa misiones de reciclaje para los debris seleccionados"""
    selected_rows = self.debris_table.selectionModel().selectedRows()
    
    if not selected_rows:
        self._notif_label.setText("⚠️ Selecciona al menos un punto de debris")
        return
    
    origin_text = self.fleet_planet_combo.currentText()
    if origin_text == "Seleccionar planeta...":
        self._notif_label.setText("⚠️ Selecciona un planeta de origen")
        return
    
    # Crear misión de reciclaje para cada debris seleccionado
    missions_created = 0
    
    for row in selected_rows:
        # Obtener el debris desde la columna 1 (Metal) donde está guardado
        item = self.debris_table.item(row, 1)
        debris = item.data(Qt.ItemDataRole.UserRole) if item else None
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
        _refresh_scheduled_fleets_list(self)
        save_scheduled_fleets(self.scheduled_fleets)
        self._notif_label.setText(f"✅ {missions_created} misiones de reciclaje programadas")
    
    # Limpiar selección
    self.debris_table.selectionModel().clearSelection()