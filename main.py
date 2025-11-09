from PyQt6.QtWidgets import QApplication
from browser_window import BrowserWindow
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    url = "https://lobby.ogame.gameforge.com/es_ES/"
    window = BrowserWindow(url=url)
    window.show()
    sys.exit(app.exec())
