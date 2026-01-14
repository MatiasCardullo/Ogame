import json, re, os
from datetime import datetime
from bs4 import BeautifulSoup
from PyQt6.QtCore import pyqtSignal, QObject
from workers.new_galaxy_worker import load_ogame_session

def clean_message_html(html_content: str, base_url: str = "https://s163-ar.ogame.gameforge.com") -> str:
    """
    Limpia el HTML de los mensajes:
    1. Remueve scripts <script type="text/javascript">initOverlays();</script>
    2. Agrega base_url a las imágenes con src que comienzan con '/'
    """
    if not html_content:
        return html_content
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Remover scripts
    for script in soup.find_all('script', {'type': 'text/javascript'}):
        script.decompose()
    
    # 2. Actualizar URLs de imágenes
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src and src.startswith('/'):
            img['src'] = base_url + src
    
    return str(soup)

def fetch_messages(base_url, profile_path="profile_data"):
    """
    Flujo de 3 pasos para obtener mensajes:
    1. Request mainTabs, buscar qué tabs tienen mensajes (id 1=Comunicación, 2=Flotas)
    2. Si Flotas/Comunicación, request getMessageWrapper para obtener subtabs con mensajes
    3. Request getMessagesList con activeSubTab para obtener los mensajes finales
    Retorna array de messages con {title, content, time, tab_id, subtab_id, tab_name, subtab_name}
    """
    try:
        session = load_ogame_session(profile_path)
        
        # PASO 1: Obtener tabs principales y sus contadores de mensajes
        #print("[MESSAGES] Paso 1: Obteniendo tabs principales...")
        url_main = base_url + "/game/index.php?page=ingame&component=messages"
        response_main = session.get(url_main, timeout=10)
        response_main.raise_for_status()
        
        soup_main = BeautifulSoup(response_main.text, 'html.parser')
        main_tabs = {}
        tab_names = {}
        
        # Buscar todos los divs con clase "singleTab" que tengan data-category-id
        for tab_div in soup_main.find_all('div', class_='singleTab'):
            tab_id = tab_div.get('data-category-id')
            if not tab_id:
                continue
            
            # Obtener nombre del tab
            tab_label = tab_div.find('div', class_='tabLabel')
            tab_name = tab_label.get_text(strip=True) if tab_label else f"Tab {tab_id}"
            tab_names[tab_id] = tab_name
            
            # Buscar el div con newMessagesCount dentro de este tab
            msg_count_div = tab_div.find('div', class_='newMessagesCount')
            if msg_count_div:
                count_text = msg_count_div.get_text(strip=True)
                try:
                    msg_count = int(count_text) if count_text else 0
                except ValueError:
                    msg_count = 0
            else:
                msg_count = 0
            
            main_tabs[tab_id] = msg_count
            #print(f"  Tab {tab_id} ({tab_name}): {msg_count} mensajes")
        
        # Buscar tabs con mensajes (cualquier tab que tenga mensajes)
        tabs_with_messages = [tid for tid, count in main_tabs.items() if count > 0]
        
        if not tabs_with_messages:
            #print("[MESSAGES] ⚠️  No hay tabs con mensajes")
            return []
        #print(f"[MESSAGES] Tabs con mensajes: {tabs_with_messages}")
        all_messages = []
        
        # PASO 2: Para cada tab con mensajes, obtener sus subtabs
        for active_tab in tabs_with_messages:
            tab_name = tab_names.get(active_tab, f"Tab {active_tab}")
            #print(f"[MESSAGES] Paso 2: Obteniendo subtabs para tab {active_tab} ({tab_name})...")
            
            url_wrapper = base_url + "/game/index.php?page=componentOnly&component=messages&ajax=1&action=getMessageWrapper"
            response_wrapper = session.post(url_wrapper, data={"activeTab": active_tab}, timeout=10)
            response_wrapper.raise_for_status()
            
            soup_wrapper = BeautifulSoup(response_wrapper.text, 'html.parser')
            sub_tabs = {}
            subtab_names = {}
            
            # Buscar todos los divs con clase "innerTabItem" que tengan data-subtab-id
            for subtab_div in soup_wrapper.find_all('div', class_='innerTabItem'):
                subtab_id = subtab_div.get('data-subtab-id')
                if not subtab_id:
                    continue
                
                # Obtener nombre del subtab
                subtab_name_elem = subtab_div.find('span', class_='subTabName')
                subtab_name = subtab_name_elem.get_text(strip=True) if subtab_name_elem else f"Subtab {subtab_id}"
                subtab_names[subtab_id] = subtab_name
                
                # Buscar el span con newMessagesCount dentro de este subtab
                msg_count_span = subtab_div.find('span', class_='newMessagesCount')
                msg_count = 0
                if msg_count_span:
                    count_text = msg_count_span.get_text(strip=True)
                    # Extraer número de "(21)" -> 21
                    if count_text:
                        numbers = re.findall(r'\d+', count_text)
                        msg_count = int(numbers[0]) if numbers else 0
                
                sub_tabs[subtab_id] = msg_count
                #print(f"  Subtab {subtab_id} ({subtab_name}): {msg_count} mensajes")
            
            # Subtabs con mensajes
            subtabs_with_messages = [sid for sid, count in sub_tabs.items() if count > 0]
            
            if not subtabs_with_messages:
                #print(f"[MESSAGES]   ⚠️  No hay subtabs con mensajes en tab {active_tab}")
                continue
            
            # PASO 3: Para cada subtab con mensajes, obtener los mensajes
            for active_subtab in subtabs_with_messages:
                subtab_name = subtab_names.get(active_subtab, f"Subtab {active_subtab}")
                #print(f"[MESSAGES] Paso 3: Obteniendo mensajes para subtab {active_subtab} ({subtab_name})...")
                
                url_list = base_url + "/game/index.php?page=componentOnly&component=messages&asJson=1&action=getMessagesList"
                response_list = session.post(
                    url_list,
                    data={
                        "showTrash": "false",
                        "activeSubTab": active_subtab
                    },
                    timeout=10
                )
                response_list.raise_for_status()
                
                try:
                    data = response_list.json()
                    messages_list = data.get("messages", [])
                    print(f"  ✓ Obtenidos {len(messages_list)} mensajes")
                    
                    for msg in messages_list:
                        # Agregar información de tab/subtab al mensaje
                        if isinstance(msg, str):
                            # Si es HTML, limpiarlo (remover scripts, agregar base_url a imágenes)
                            cleaned_html = clean_message_html(msg, base_url)
                            msg_obj = {
                                "html": cleaned_html,
                                "tab_id": active_tab,
                                "tab_name": tab_name,
                                "subtab_id": active_subtab,
                                "subtab_name": subtab_name
                            }
                        else:
                            # Si es dict, limpiar el campo html si existe
                            if "html" in msg and isinstance(msg["html"], str):
                                msg["html"] = clean_message_html(msg["html"], base_url)
                            msg["tab_id"] = active_tab
                            msg["tab_name"] = tab_name
                            msg["subtab_id"] = active_subtab
                            msg["subtab_name"] = subtab_name
                            msg_obj = msg
                        
                        all_messages.append(msg_obj)
                
                except json.JSONDecodeError:
                    print(f"  ⚠️  Respuesta no JSON para subtab {active_subtab}")
                    continue
        
        if not all_messages:
            return []
        save_messages_to_file(all_messages, "messages_log")
        return all_messages
        
    except Exception as e:
        print(f"[MESSAGES] ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def save_messages_to_file(messages, messages_dir="messages_log"):
    """
    Guarda los mensajes como HTML en carpetas organizadas por tab/subtab.
    Estructura: messages_log/tab_id_name/subtab_id_name/messages_*.html
    No sobrescribe, crea nuevos archivos para cada actualización.
    """
    try:
        # Rastrear carpetas creadas para actualizar sus latest.html
        created_folders = {}
        
        # Agrupar mensajes por tab/subtab
        messages_by_location = {}
        
        for msg in messages:
            if isinstance(msg, dict) and "tab_id" in msg:
                tab_id = msg.get("tab_id", "unknown")
                tab_name = msg.get("tab_name", f"Tab_{tab_id}")
                subtab_id = msg.get("subtab_id", "unknown")
                subtab_name = msg.get("subtab_name", f"Subtab_{subtab_id}")
                
                # Sanitizar nombres para rutas
                tab_folder = f"{tab_id}_{tab_name}".replace(" ", "_").replace("/", "_")
                subtab_folder = f"{subtab_id}_{subtab_name}".replace(" ", "_").replace("/", "_")
                
                location_key = (tab_folder, subtab_folder)
                if location_key not in messages_by_location:
                    messages_by_location[location_key] = []
                
                messages_by_location[location_key].append(msg)
        
        # Guardar mensajes en sus carpetas correspondientes
        for (tab_folder, subtab_folder), folder_messages in messages_by_location.items():
            # Si el tab y subtab son iguales, no crear carpeta extra de subtab
            if tab_folder == subtab_folder:
                full_path = os.path.join(messages_dir, tab_folder)
            else:
                full_path = os.path.join(messages_dir, tab_folder, subtab_folder)
            
            os.makedirs(full_path, exist_ok=True)
            
            created_folders[full_path] = folder_messages
            
            # Generar timestamp para el nombre del archivo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(full_path, f"messages_{timestamp}.html")
            
            # Crear HTML con estructura completa
            html_content = f"""<!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Mensajes OGame - {tab_folder} / {subtab_folder}</title>
                    <style>
                        body {{
                            background-color: #000;
                            color: #EEE;
                            font-family: Arial, sans-serif;
                            margin: 0;
                            padding: 10px;
                        }}
                        h1 {{
                            color: #0f0;
                            border-bottom: 2px solid #0f0;
                            padding-bottom: 10px;
                        }}
                        .msg {{
                            background-color: #111;
                            border: 1px solid #333;
                            margin: 10px 0;
                            padding: 10px;
                            border-radius: 4px;
                        }}
                        .msg_new {{
                            border-left: 4px solid #0f0;
                        }}
                        .msgHead {{
                            display: flex;
                            justify-content: space-between;
                            margin-bottom: 10px;
                            padding-bottom: 10px;
                            border-bottom: 1px solid #333;
                        }}
                        .msgHeadItem {{
                            flex: 1;
                        }}
                        .msgTitle {{
                            font-weight: bold;
                            color: #0f0;
                            font-size: 14px;
                        }}
                        .msgDate {{
                            color: #999;
                            font-size: 12px;
                            text-align: right;
                        }}
                        .msgContent {{
                            color: #CCC;
                            line-height: 1.6;
                            font-size: 13px;
                        }}
                        .txt_link {{
                            color: #0af;
                            text-decoration: none;
                        }}
                        .txt_link:hover {{
                            text-decoration: underline;
                        }}
                        hr {{
                            border: none;
                            border-top: 1px solid #333;
                            margin: 10px 0;
                        }}
                        img[sq16] {{
                            width: 16px;
                            height: 16px;
                            margin-right: 5px;
                            vertical-align: middle;
                        }}
                        .lifeformbox {{
                            background-color: #0a2a0a;
                            border: 1px solid #0f0;
                            border-radius: 4px;
                            padding: 10px;
                            margin: 10px 0;
                            font-size: 12px;
                        }}
                        .msg_actions {{
                            margin-top: 10px;
                            padding-top: 10px;
                            border-top: 1px solid #333;
                            font-size: 12px;
                        }}
                    </style>
                </head>
                <body>
                    <h1>📜 Mensajes OGame</h1>
                    <p><strong>{tab_folder} / {subtab_folder}</strong></p>
                    <p>Guardado: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}</p>
                    <p>Total: {len(folder_messages)} mensajes</p>
                    <hr>
            """
            
            # Agregar mensajes
            for msg in folder_messages:
                if isinstance(msg, dict):
                    if "html" in msg:
                        # HTML directo
                        html_content += msg["html"]
                    else:
                        # Formatear como dict
                        title = msg.get("title", "Sin título")
                        time = msg.get("time", "")
                        content = msg.get("text", msg.get("content", ""))
                        html_content += f"<div class='msg'><div class='msgTitle'>{title}</div><div class='msgDate'>{time}</div><div class='msgContent'>{content}</div></div><hr>"
            
            html_content += """
                </body>
                </html>
            """
            
            # Guardar archivo
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            #print(f"[MESSAGES] ✓ Guardados {len(folder_messages)} mensajes en {filename}")
            
            # Actualizar archivo latest
            latest_file = os.path.join(full_path, "messages_latest.html")
            with open(latest_file, "w", encoding="utf-8") as f:
                f.write(html_content)
        
        return created_folders
        
    except Exception as e:
        print(f"[MESSAGES] ⚠️  Error guardando mensajes: {e}")
        return {}

class FetchMessagesWorker(QObject):
    """Worker para obtener mensajes en thread separado sin bloquear la UI"""
    finished = pyqtSignal()
    success = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
    
    def run(self):
        """Obtiene mensajes en thread separado"""
        try:
            messages = fetch_messages(self.base_url)
            if messages:
                self.success.emit(messages)
            else:
                self.success.emit([])
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()

