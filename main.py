from PyQt6.QtWidgets import QApplication
from main_window import MainWindow
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    url = "https://lobby.ogame.gameforge.com/ar_AR/"
    window = MainWindow(url=url)
    window.show()
    sys.exit(app.exec())
