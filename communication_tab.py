import json
import re
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl
import tempfile
from galaxy_worker import load_ogame_session

def fetch_messages(profile_path="profile_data"):
    """
    Flujo de 3 pasos para obtener mensajes:
    1. Request mainTabs, buscar qué tabs tienen mensajes (id 1=Comunicación, 2=Flotas)
    2. Si Flotas/Comunicación, request getMessageWrapper para obtener subtabs con mensajes
    3. Request getMessagesList con activeSubTab para obtener los mensajes finales
    Retorna array de messages con {title, content, time}
    """
    try:
        session = load_ogame_session(profile_path)
        
        # PASO 1: Obtener tabs principales y sus contadores de mensajes
        print("[MESSAGES] Paso 1: Obteniendo tabs principales...")
        url_main = "https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame&component=messages"
        response_main = session.get(url_main, timeout=10)
        response_main.raise_for_status()
        
        soup_main = BeautifulSoup(response_main.text, 'html.parser')
        main_tabs = {}
        
        # Buscar todos los divs con clase "singleTab" que tengan data-category-id
        for tab_div in soup_main.find_all('div', class_='singleTab'):
            tab_id = tab_div.get('data-category-id')
            if not tab_id:
                continue
            
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
            print(f"  Tab {tab_id}: {msg_count} mensajes")
        
        # Buscar tabs con mensajes (1=Comunicación, 2=Flotas)
        tabs_with_messages = [tid for tid, count in main_tabs.items() if count > 0 and tid in ["1", "2"]]
        
        if not tabs_with_messages:
            print("[MESSAGES] ⚠️  No hay tabs con mensajes (Comunicación o Flotas)")
            return []
        
        print(f"[MESSAGES] Tabs con mensajes: {tabs_with_messages}")
        
        all_messages = []
        
        # PASO 2: Para cada tab con mensajes, obtener sus subtabs
        for active_tab in tabs_with_messages:
            print(f"[MESSAGES] Paso 2: Obteniendo subtabs para tab {active_tab}...")
            
            url_wrapper = "https://s163-ar.ogame.gameforge.com/game/index.php?page=componentOnly&component=messages&ajax=1&action=getMessageWrapper"
            response_wrapper = session.post(url_wrapper, data={"activeTab": active_tab}, timeout=10)
            response_wrapper.raise_for_status()
            
            soup_wrapper = BeautifulSoup(response_wrapper.text, 'html.parser')
            sub_tabs = {}
            
            # Buscar todos los divs con clase "innerTabItem" que tengan data-subtab-id
            for subtab_div in soup_wrapper.find_all('div', class_='innerTabItem'):
                subtab_id = subtab_div.get('data-subtab-id')
                if not subtab_id:
                    continue
                
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
                print(f"  Subtab {subtab_id}: {msg_count} mensajes")
            
            # Subtabs con mensajes
            subtabs_with_messages = [sid for sid, count in sub_tabs.items() if count > 0]
            
            if not subtabs_with_messages:
                print(f"[MESSAGES]   ⚠️  No hay subtabs con mensajes en tab {active_tab}")
                continue
            
            # PASO 3: Para cada subtab con mensajes, obtener los mensajes
            for active_subtab in subtabs_with_messages:
                print(f"[MESSAGES] Paso 3: Obteniendo mensajes para subtab {active_subtab}...")
                
                url_list = "https://s163-ar.ogame.gameforge.com/game/index.php?page=componentOnly&component=messages&asJson=1&action=getMessagesList"
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
                        all_messages.append(msg)
                        #all_messages.append({
                        #    "title": msg.get("title", "Sin título"),
                        #    "content": msg.get("text", ""),
                        #    "time": msg.get("time", "")
                        #})
                
                except json.JSONDecodeError:
                    print(f"  ⚠️  Respuesta no JSON para subtab {active_subtab}")
                    continue
        
        if not all_messages:
            return [{
                "title": "Sin mensajes",
                "content": "Se encontraron tabs pero no se obtuvieron mensajes.",
                "time": ""
            }]
        
        print(f"[MESSAGES] ✓ Total: {len(all_messages)} mensajes")
        return all_messages
        
    except Exception as e:
        print(f"[MESSAGES] ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return [{
            "title": "Error",
            "content": str(e),
            "time": ""
        }]

def display_messages(text_edit: QLabel, messages: list):
    """
    Muestra los mensajes en la UI
    """
    text_edit.clear()

    for msg in messages:
        text_edit.setText(
            text_edit.text() + msg +"\n"
        )
        #text_edit.append(
        #    f"<b>{msg['title']}</b><br>"
        #    f"<small>{msg['time']}</small><br>"
        #    f"{msg['content']}<br>"
        #    f"<hr>"
        #)


def create_comms_tab(socket_url: str, main_window=None):
    widget = QWidget()
    layout = QVBoxLayout(widget)

    messages_view = QLabel()
    
    messages = fetch_messages()
    display_messages(messages_view, messages)
    
    # Conectar sms_timer para actualizar mensajes automáticamente
    def refresh_messages():
        try:
            messages = fetch_messages()
            display_messages(messages_view, messages)
        except Exception as e:
            print(f"[SOCKET] Error refrescando mensajes: {e}")
    
    if main_window and hasattr(main_window, 'sms_timer'):
        main_window.sms_timer.timeout.connect(refresh_messages)
    layout.addWidget(messages_view)

    web = QWebEngineView()
    layout.addWidget(web)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Socket Control</title>
        <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
        <style>
            body {{
                background: #111;
                color: #eee;
                font-family: sans-serif;
                margin: 0;
                padding: 10px;
            }}
            button {{
                padding: 10px;
                background: #333;
                color: #eee;
                border: 1px solid #555;
                cursor: pointer;
            }}
            #log {{
                margin-top: 10px;
                font-size: 13px;
                white-space: pre-wrap;
            }}
        </style>
    </head>
    <body>

        <h3>Socket.IO Control</h3>
        <button onclick="sendPing()">Ping</button>
        <div id="log"></div>

        <script>
            const log = msg => {{
                document.getElementById("log").textContent += msg + "\\n";
            }};

            const socket = io("{socket_url}");

            socket.on("connect", () => {{
                log("✔ Conectado");
            }});

            socket.on("event", data => {{
                log("⬅ " + JSON.stringify(data));
            }});

            function sendPing() {{
                socket.emit("cmd", {{
                    type: "cmd",
                    cmd: "ping",
                    payload: {{}}
                }});
                log("➡ ping");
            }}
        </script>

    </body>
    </html>
    """

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    tmp.write(html.encode("utf-8"))
    tmp.close()

    web.setUrl(QUrl.fromLocalFile(tmp.name))

    return widget
