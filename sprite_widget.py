import os
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QLineEdit,
    QVBoxLayout, QGridLayout, QScrollArea
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt


class IconWidget(QWidget):
    def __init__(self, sprite, icon_data, size=100, parent=None):
        super().__init__(parent)
        cut = sprite.copy(icon_data["x"], icon_data["y"], 200, 200)
        cut = cut.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.label = QLabel(self)
        self.label.setPixmap(cut)
        self.setFixedSize(size, size)
        self.label.setGeometry(0, 0, size, size)
        self.label.setToolTip(icon_data.get("name", ""))

        # Control según estado
        state = icon_data["state"]
        if state == 0:
            control = QLineEdit(self)
            control.setPlaceholderText("0")
            control.setFixedSize(40, 22)
        else:
            control = QPushButton(self)
            control.setStyleSheet("""
                background-color: #00c853;
                border: none;
                border-radius: 4px;
            """)
            control.setFixedSize(22, 22)
        control.move(4, 4)
        control.raise_()


class SpriteWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # ===========================================================
        # 1) Datos integrados por defecto
        # ===========================================================

        self.iconData = {
            "Recursos": [
                { "x": 0, "y": 0, "state": 50, "name": "Mina de Metal" },
                { "x": 200, "y": 0, "state": 50, "name": "Mina de Cristal" },
                { "x": 400, "y": 0, "state": 50, "name": "Sintetizador de Deuterio" },
                { "x": 600, "y": 0, "state": 50, "name": "Planta de Energía Solar" },
                { "x": 800, "y": 0, "state": 50, "name": "Planta de Fusión" },
                { "x": 1000, "y": 0, "state": 0, "name": "Satélite Solar" },
                { "x": 1200, "y": 0, "state": 50, "name": "Almacén de Metal" },
                { "x": 1400, "y": 0, "state": 50, "name": "Almacén de Cristal" },
                { "x": 1600, "y": 0, "state": 50, "name": "Depósito de Deuterio" },
                { "x": 3200, "y": 3000, "state": 0, "name": "Taladrador" }

            ],
            "Instalaciones": [
                { "x": 0, "y": 1000, "state": 15, "name": "Fábrica de Robots" },
                { "x": 200, "y": 1000, "state": 15, "name": "Hangar" },
                { "x": 400, "y": 1000, "state": 15, "name": "Laboratorio de Investigación" },
                { "x": 600, "y": 1000, "state": 15, "name": "Depósito de la Alianza" },
                { "x": 800, "y": 1000, "state": 15, "name": "Silo de Misiles" },
                { "x": 1000, "y": 1000, "state": 15, "name": "Fábrica de Nanobots" },
                { "x": 1200, "y": 1000, "state": 15, "name": "Terraformador" },
                { "x": 2000, "y": 1000, "state": 15, "name": "Puerto Espacial" },
                { "x": 1400, "y": 1000, "state": 15, "name": "Base Lunar" },
                { "x": 1600, "y": 1000, "state": 15, "name": "Sensor Phalanx" },
                { "x": 1800, "y": 1000, "state": 15, "name": "Salto Cuántico" }
            ],
            "Defensas": [
                { "x": 0, "y": 2000, "state": 0, "name": "Lanzamisiles" },
                { "x": 200, "y": 2000, "state": 0, "name": "Láser Pequeño" },
                { "x": 400, "y": 2000, "state": 0, "name": "Láser Grande" },
                { "x": 600, "y": 2000, "state": 0, "name": "Cañon Gauss" },
                { "x": 800, "y": 2000, "state": 0, "name": "Cañon Ionico" },
                { "x": 1000, "y": 2000, "state": 0, "name": "Cañón de Plasma" },
                { "x": 1200, "y": 2000, "state": 1, "name": "Cupula Pequeña de Defensa" },
                { "x": 1400, "y": 2000, "state": 1, "name": "Cupula Grande de Defensa" },
                { "x": 1600, "y": 2000, "state": 0, "name": "Misil de Intercepción" },
                { "x": 1800, "y": 2000, "state": 0, "name": "Misil Interplanetario" }
            ],
            "Flota": [
                { "x": 0, "y": 3000, "state": 0, "name": "Cazador Ligero" },
                { "x": 200, "y": 3000, "state": 0, "name": "Cazador Pesado" },
                { "x": 400, "y": 3000, "state": 0, "name": "Crucero" },
                { "x": 600, "y": 3000, "state": 0, "name": "Nave de Batalla" },
                { "x": 800, "y": 3000, "state": 0, "name": "Acorazado" },
                { "x": 1000, "y": 3000, "state": 0, "name": "Bombardero" },
                { "x": 1200, "y": 3000, "state": 0, "name": "Destructor" },
                { "x": 1400, "y": 3000, "state": 0, "name": "Estrella de la Muerte" },
                { "x": 1600, "y": 3000, "state": 0, "name": "Nave Pequeña de Carga" },
                { "x": 1800, "y": 3000, "state": 0, "name": "Nave Grande de Carga" },
                { "x": 2000, "y": 3000, "state": 0, "name": "Nave Colonizadora" },
                { "x": 2200, "y": 3000, "state": 0, "name": "Reciclador" },
                { "x": 2400, "y": 3000, "state": 0, "name": "Sonda de Espionaje" },
                { "x": 2800, "y": 3000, "state": 0, "name": "Segador" },
                { "x": 3000, "y": 3000, "state": 0, "name": "Explorador" }
            ],
            "Investigacion": [
                { "x": 0, "y": 4000, "state": 20, "name": "Tecnología de Energía" },
                { "x": 200, "y": 4000, "state": 20, "name": "Tecnología de Láser" },
                { "x": 400, "y": 4000, "state": 20, "name": "Tecnología de Iones" },
                { "x": 600, "y": 4000, "state": 20, "name": "Tecnología de Hiperespacio" },
                { "x": 800, "y": 4000, "state": 20, "name": "Tecnología de Plasma" },
                { "x": 1000, "y": 4000, "state": 20, "name": "Tecnología de Combustible" },
                { "x": 1200, "y": 4000, "state": 20, "name": "Motor de Impulso" },
                { "x": 1400, "y": 4000, "state": 20, "name": "Propulsor Hiperespacial" },
                { "x": 1600, "y": 4000, "state": 20, "name": "Tecnología de Espionaje" },
                { "x": 1800, "y": 4000, "state": 20, "name": "Tecnología de Computación" },
                { "x": 2000, "y": 4000, "state": 20, "name": "Tecnología de Astrofísica" },
                { "x": 2200, "y": 4000, "state": 20, "name": "Red de investigacion intergaláctica" },
                { "x": 2400, "y": 4000, "state": 20, "name": "Tecnología de Graviton" },
                { "x": 2600, "y": 4000, "state": 20, "name": "Tecnología Militar" },
                { "x": 2800, "y": 4000, "state": 20, "name": "Tecnología de Defensa" },
                { "x": 3000, "y": 4000, "state": 20, "name": "Tecnología de Blindaje" }
            ]
        }
    
        # ===========================================================
        # 2) Scroll + Layout principal
        # ===========================================================

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        main = QWidget()
        scroll.setWidget(main)
        main_layout = QVBoxLayout(main)

        # ===========================================================
        # 3) Cargar sprite
        # ===========================================================
        #local_path=r"profile_data\cache\Cache\Cache_Data\f_000031"
        #if os.path.isfile(local_path):
        #    sprite = QPixmap(local_path)
        #else:
        sprite = QPixmap()
        sprite.loadFromData(self.load_image())

        # ===========================================================
        # 4) Columnas fijas por categoría
        # ===========================================================

        self.columns6 = ["Recursos", "Instalaciones", "Defensas"]
        self.columns8 = ["Flota", "Investigacion"]

        # ===========================================================
        # 5) Generar categorías e íconos
        # ===========================================================

        for category, items in self.iconData.items():
            # título
            title = QLabel(f"<h2>{category}</h2>")
            main_layout.addWidget(title)
            grid = QGridLayout()
            col_limit = 6 if category in self.columns6 else 8
            row = col = 0
            for icon_data in items:
                icon = IconWidget(sprite, icon_data)
                grid.addWidget(icon, row, col)
                col += 1
                if col >= col_limit:
                    col = 0
                    row += 1
            main_layout.addLayout(grid)

        # layout final
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)

    def load_image(self):
        import requests
        return requests.get("https://gf3.geo.gfsrv.net/cdn53/7a9861be0c38bf7de05a57c56d73cf.jpg").content
