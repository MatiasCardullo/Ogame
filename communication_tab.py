import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QPushButton, QGridLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer, QThread
from js_scripts import check_msg
from workers.messages import FetchMessagesWorker

def display_messages(button_layout: QGridLayout, web_view: QWebEngineView, messages_dir: str = "messages_log"):
    """
    Busca carpetas reales en messages_log y crea botones PyQt6
    Cada botón carga el messages_latest.html correspondiente en el QWebEngineView
    """
    # Limpiar layout anterior
    while button_layout.count():
        item = button_layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    
    # Verificar si el directorio existe
    if not os.path.exists(messages_dir):
        os.makedirs(messages_dir, exist_ok=True)
        label = QLabel("No hay mensajes aún")
        label.setStyleSheet("color: #999; padding: 10px;")
        button_layout.addWidget(label)
        return
    
    # Buscar estructura: messages_log/tab_folder/ o messages_log/tab_folder/subtab_folder/
    locations = []
    
    for tab_folder in os.listdir(messages_dir):
        tab_path = os.path.join(messages_dir, tab_folder)
        
        if not os.path.isdir(tab_path):
            continue
        
        # Extraer tab_name del nombre de carpeta (formato: "id_name")
        try:
            tab_id, tab_name = tab_folder.split("_", 1)
            tab_name = tab_name.replace("_", " ")
        except:
            tab_name = tab_folder
        
        # Verificar si hay messages_latest.html directamente en la carpeta del tab
        latest_file_direct = os.path.join(tab_path, "messages_latest.html")
        if os.path.exists(latest_file_direct):
            locations.append({
                "tab_name": tab_name,
                "subtab_name": tab_name,  # Si no hay subtab, usar el mismo nombre del tab
                "latest_file": latest_file_direct
            })
            continue  # No buscar subcarpetas si ya encontró el archivo directo
        
        # Buscar subcarpetas
        for subtab_folder in os.listdir(tab_path):
            subtab_path = os.path.join(tab_path, subtab_folder)
            
            if not os.path.isdir(subtab_path):
                continue
            
            # Verificar que exista messages_latest.html
            latest_file = os.path.join(subtab_path, "messages_latest.html")
            if not os.path.exists(latest_file):
                continue
            
            # Extraer subtab_name del nombre de carpeta
            try:
                subtab_id, subtab_name = subtab_folder.split("_", 1)
                subtab_name = subtab_name.replace("_", " ")
            except:
                subtab_name = subtab_folder
            
            locations.append({
                "tab_name": tab_name,
                "subtab_name": subtab_name,
                "latest_file": latest_file
            })
    
    if not locations:
        label = QLabel("No hay mensajes guardados aún")
        label.setStyleSheet("color: #999; padding: 10px;")
        button_layout.addWidget(label)
        return
    
    # Crear botones para cada ubicación
    row = 0
    col = 0
    max_cols = 3
    
    for location in locations:
        if location['subtab_name'] == location['tab_name']:
            text = f"📁 {location['tab_name']}"
        else:
            text = f"📁 {location['tab_name']}\n→ {location['subtab_name']}"
        btn = QPushButton(text)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #111;
                color: #0af;
                border: 2px solid #0af;
                padding: 15px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #0af;
                color: #000;
            }
            QPushButton:pressed {
                background-color: #0f0;
                border-color: #0f0;
                color: #000;
            }
        """)
        btn.setMinimumHeight(80)
        
        # Conectar click a función que carga el archivo
        latest_path = location["latest_file"]
        btn.clicked.connect(lambda checked, path=latest_path, web=web_view: load_message_file(web, path))
        
        button_layout.addWidget(btn, row, col)
        
        col += 1
        if col >= max_cols:
            col = 0
            row += 1
    
    # Llenar espacios vacíos
    while col > 0 and col < max_cols:
        button_layout.addWidget(QWidget(), row, col)
        col += 1

def load_message_file(web_view: QWebEngineView, file_path: str):
    """
    Carga un archivo HTML en el QWebEngineView
    """
    try:
        if os.path.exists(file_path):
            # Convertir ruta de archivo a URL
            file_url = QUrl.fromLocalFile(os.path.abspath(file_path))
            web_view.load(file_url)
            #print(f"[MESSAGES] ✓ Cargado: {file_path}")
        else:
            web_view.setHtml(f"<p style='color: red;'>Archivo no encontrado: {file_path}</p>")
    except Exception as e:
        web_view.setHtml(f"<p style='color: red;'>Error: {str(e)}</p>")

def create_comms_tab(socket_url: str, main_window=None):
    """
    Crea la pestaña de comunicaciones con:
    - Panel de botones para mensajes (generados desde carpetas) - scrollable
    - Visor de mensajes (QWebEngineView)
    - Timer para detectar nuevos mensajes cada 1 segundo
    """

    comms_tab = QWidget()
    layout = QVBoxLayout()
    layout.setContentsMargins(5, 5, 5, 5)
    comms_tab.setStyleSheet("""
        background-color: #000;
        color: #EEE;
    """)
    
    # ----- Título -----
    title = QLabel("📨 Centro de Mensajes OGame")
    title.setStyleSheet("""
        color: #0f0;
        font-weight: bold;
        font-size: 14px;
        padding: 5px;
        border-bottom: 2px solid #0f0;
    """)
    layout.addWidget(title)
    
    # ----- Panel de botones (scrollable) -----
    buttons_container = QWidget()
    button_grid = QGridLayout()
    button_grid.setSpacing(5)
    buttons_container.setLayout(button_grid)
    
    # Scroll area para botones
    buttons_scroll = QScrollArea()
    buttons_scroll.setWidget(buttons_container)
    buttons_scroll.setWidgetResizable(True)
    buttons_scroll.setMaximumHeight(200)
    buttons_scroll.setStyleSheet("""
        QScrollArea {
            background-color: #000;
            border: 1px solid #333;
        }
        QScrollBar:vertical {
            background-color: #111;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #0af;
            border-radius: 6px;
        }
    """)
    
    layout.addWidget(buttons_scroll)
    
    # ----- Visor de mensajes -----
    web_view = QWebEngineView()
    web_view.setStyleSheet("""
        QWebEngineView {
            background-color: #000;
            border: 1px solid #333;
        }
    """)
    layout.addWidget(web_view)
    
    # ----- Panel de información -----
    info_layout = QHBoxLayout()
    status_label = QLabel("⏳ Esperando mensajes...")
    status_label.setStyleSheet("color: #999; font-style: italic;")
    info_layout.addWidget(status_label)
    info_layout.addStretch()
    layout.addLayout(info_layout)
    
    # ----- Timer para detectar nuevos mensajes -----
    def check_for_new_messages():
        """Ejecuta check_msg JavaScript cada 1 segundo"""
        def handle_msg_check(data):
            """Callback después de ejecutar check_msg"""
            if data and isinstance(data, dict):
                msg_count = data.get('msg', 0)
                if msg_count > 0:
                    status_label.setText(f"🔔 {msg_count} nuevo(s) mensaje(s) - Actualizando...")
                    QTimer.singleShot(500, refresh_messages)
                else:
                    status_label.setText("✓ Sin mensajes nuevos")
        
        # Ejecutar check_msg script
        try:
            main_window.pages_views[3]['web'].page().runJavaScript(check_msg, handle_msg_check)
        except Exception as e:
            print(f"[COMMS] Error en check_msg: {e}")
    
    def refresh_messages():
        """Obtiene mensajes en thread separado y actualiza la UI
        Maneja casos donde el objeto QThread/worker fue destruido por Qt
        para evitar 'wrapped C/C++ object of type QThread has been deleted'."""
        try:
            # Si hay un thread vivo, no iniciar otro
            existing_thread = getattr(comms_tab, 'fetch_thread', None)
            if existing_thread is not None:
                try:
                    if existing_thread.isRunning():
                        #print("[COMMS] ⏳ Ya hay una búsqueda en progreso, omitiendo...")
                        return
                except RuntimeError:
                    # El objeto C++ fue eliminado; limpiar referencias para recrear
                    comms_tab.fetch_thread = None
                    comms_tab.fetch_worker = None

            #print("[COMMS] 🔄 Actualizando mensajes (en thread separado)...")
            status_label.setText("⏳ Obteniendo mensajes...")
            
            # Crear worker y thread
            comms_tab.fetch_thread = QThread()
            comms_tab.fetch_worker = FetchMessagesWorker(main_window.base_url)
            comms_tab.fetch_worker.moveToThread(comms_tab.fetch_thread)
            
            # Conectar señales
            comms_tab.fetch_thread.started.connect(comms_tab.fetch_worker.run)
            comms_tab.fetch_worker.finished.connect(comms_tab.fetch_thread.quit)
            comms_tab.fetch_worker.finished.connect(comms_tab.fetch_worker.deleteLater)
            comms_tab.fetch_thread.finished.connect(comms_tab.fetch_thread.deleteLater)
            comms_tab.fetch_worker.success.connect(_on_messages_loaded)
            comms_tab.fetch_worker.error.connect(_on_messages_error)

            # Iniciar thread
            comms_tab.fetch_thread.start()
        except Exception as e:
            print(f"[COMMS] ❌ Error iniciando worker: {e}")
            status_label.setText(f"❌ Error: {str(e)[:50]}")
    
    def _on_messages_loaded(messages):
        """Callback cuando se obtienen los mensajes exitosamente"""
        try:
            if messages:
                comms_tab.msg_timer.setInterval(10000)
                print(f"[COMMS] ✅ {len(messages)} mensaje(s) obtenido(s)")
                display_messages(button_grid, web_view, "messages_log")
                status_label.setText(f"✓ {len(messages)} mensaje(s) cargado(s)")
            else:
                comms_tab.msg_timer.setInterval(1000)
                status_label.setText("✓ No hay mensajes nuevos")
        except Exception as e:
            print(f"[COMMS] ❌ Error procesando mensajes: {e}")
            status_label.setText(f"❌ Error: {str(e)[:50]}")
    
    def _on_messages_error(error_msg):
        """Callback cuando hay error obteniendo mensajes"""
        print(f"[COMMS] ❌ Error: {error_msg}")
        status_label.setText(f"❌ Error: {error_msg[:50]}")
        comms_tab.msg_timer.setInterval(1000)  # Reintentar pronto
    
    # ----- Timer de 1 segundo -----
    comms_tab.msg_timer = QTimer()
    comms_tab.msg_timer.setInterval(1000)
    comms_tab.msg_timer.timeout.connect(check_for_new_messages)
    comms_tab.msg_timer.start()
    
    comms_tab.setLayout(layout)
    return comms_tab
