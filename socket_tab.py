from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl
import tempfile
import os

def create_socket_tab(socket_url: str) -> QWidget:
    """
    Crea un QWidget con una UI web conectada por Socket.IO
    listo para enchufar en una QTabWidget
    """

    widget = QWidget()
    layout = QVBoxLayout(widget)

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
