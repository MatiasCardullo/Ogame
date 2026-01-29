import sys, math, csv
from dataclasses import dataclass
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QTableWidget, QTableWidgetItem, 
    QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
)
from text import time_str

# =========================
# EDIFICIOS
# =========================

UNIVERSE_ACCELERATION = 3

@dataclass
class Building:
    name: str
    cost_factor: float
    metal_base: float
    crystal_base: float
    deuterium_base: float = 0
    def cost(self, level):
        f = self.cost_factor ** (level - 1)
        return {
            "metal": self.metal_base * f,
            "crystal": self.crystal_base * f,
            "deuterium": self.deuterium_base * f
        }
    def production(self, level):
        return 0
    def energy(self, level):
        return 0
    
class MetalMine(Building):
    def __init__(self):
        super().__init__("Metal Mine", 1.5, 60, 15)

    def production(self, level):
        return 30 * UNIVERSE_ACCELERATION + 30 * UNIVERSE_ACCELERATION * level * (1.1 ** level)

    def energy(self, level):
        return 10 * level * (1.1 ** level)

class CrystalMine(Building):
    def __init__(self):
        super().__init__("Crystal Mine", 1.6, 48, 24)

    def production(self, level):
        return 15 * UNIVERSE_ACCELERATION + 20 * UNIVERSE_ACCELERATION * level * (1.1 ** level)

    def energy(self, level):
        return 10 * level * (1.1 ** level)

class DeutSynth(Building):
    def __init__(self):
        super().__init__("Deuterium Synthesizer", 1.6, 225, 75)

    def production(self, level):
        return 20 * level * (1.1 ** level)

    def energy(self, level):
        return 20 * level * (1.1 ** level)

class SolarPlant(Building):
    def __init__(self):
        super().__init__("Solar Plant", 1.5, 75, 30)

    def energy(self, level):
        return 20 * level * (1.1 ** level)

class Storage(Building):
    def __init__(self, name, metal_base, crystal_base=0):
        super().__init__(name, 2, metal_base, crystal_base)

    def capacity(self, level):
        return 5000 * (2.5 * math.exp((20 / 33) * level))

class MetalStorage(Storage):
    def __init__(self):
        super().__init__("Metal Storage", 1000)

class CrystalStorage(Storage):
    def __init__(self):
        super().__init__("Crystal Storage", 1000, 500)

class DeutTank(Storage):
    def __init__(self):
        super().__init__("Deuterium Tank", 1000, 1000)

class Robots(Building):
    def __init__(self):
        super().__init__("Robotics Factory", 2, 400, 120, 120)

class Nanite(Building):
    def __init__(self):
        super().__init__("Nanite Factory", 2, 1000000, 500000, 100000)

buildings = [
    MetalMine(),
    CrystalMine(),
    DeutSynth(),
    SolarPlant(),
    MetalStorage(),
    CrystalStorage(),
    DeutTank(),
    Robots(),
    Nanite()
]

# =========================
# ESTADO
# =========================

class PlanetState:
    def __init__(self, metal, crystal, deut):
        self.levels = {}
        self.resources = {
            "metal": metal,
            "crystal": crystal,
            "deuterium": deut
        }
        self.time = 0.0

    def clone(self):
        s = PlanetState(0, 0, 0)
        s.levels = self.levels.copy()
        s.resources = self.resources.copy()
        s.time = self.time
        return s

def build_time(cost, robotics, nanite):
    return (cost["metal"] + cost["crystal"]) / (2500*(1+robotics)*(2**nanite))
    
# =========================
# ECONOMÍA
# =========================

def storage_capacity(state):
    caps = {
        "metal": 1000,
        "crystal": 1000,
        "deuterium": 1000
    }
    for b in buildings:
        lvl = state.levels.get(b.name, 0)
        if b.name == "Metal Storage":
            caps["metal"] = b.capacity(lvl)
        elif b.name == "Crystal Storage":
            caps["crystal"] = b.capacity(lvl)
        elif b.name == "Deuterium Tank":
            caps["deuterium"] = b.capacity(lvl)
    return caps

def energy_capacity(state):
    energy = 0
    for b in buildings:
        lvl = state.levels.get(b.name, 0)
        if lvl <= 0:
            continue
        if b.name == "Solar Plant":
            energy += b.energy(lvl)
        else:
            energy -= b.energy(lvl)
    return energy

def production_per_hour(state):
    m = c = d = 0
    used = prod = 0
    for b in buildings:
        lvl = state.levels.get(b.name, 0)
        if lvl <= 0:
            continue
        if b.name == "Metal Mine":
            m += b.production(lvl)
            used += b.energy(lvl)
        elif b.name == "Crystal Mine":
            c += b.production(lvl)
            used += b.energy(lvl)
        elif b.name == "Deuterium Synthesizer":
            d += b.production(lvl)
            used += b.energy(lvl)
        elif b.name == "Solar Plant":
            prod += b.energy(lvl)
    if used > 0 and prod < used:
        factor = prod / used
        m *= factor
        c *= factor
        d *= factor
    return {
        "energy": prod - used,
        "metal": m,
        "crystal": c,
        "deuterium": d
    }

def advance_time(state, dt):
    prod = production_per_hour(state)
    caps = storage_capacity(state)
    for r in caps.keys():
        if state.resources[r] < caps[r]:
            state.resources[r] = min(state.resources[r] + prod[r] * dt, caps["metal"])
    state.time += dt

def time_to_fill(state):
    prod = production_per_hour(state)
    caps = storage_capacity(state)
    def t(res, cap, prod):
        if prod == 0:
            return sys.maxsize
        return (cap - res) / prod
    return {
        "metal": t(state.resources["metal"], caps["metal"], prod["metal"]),
        "crystal": t(state.resources["crystal"], caps["crystal"], prod["crystal"]),
        "deuterium": t(state.resources["deuterium"], caps["deuterium"], prod["deuterium"])
    }

def has_resources(now, cost):
    for r in ["metal", "crystal", "deuterium"]:
        if now[r] < cost[r]:
            return False
    return True

def needs_storage_upgrade(state, cost):
    caps = storage_capacity(state)
    upgrade = None
    for r, v in cost.items():
        if v > caps[r]:
            upgrade = r
    for r in ["deuterium", "crystal", "metal"]:
        if caps[r]  < state.resources[r] * 1.5:
            upgrade =  r
    mapping = {
        "metal": "Metal Storage",
        "crystal": "Crystal Storage",
        "deuterium": "Deuterium Tank"
    }
    if upgrade:
        return mapping[upgrade]
    return None

def needs_energy_upgrade(state, to_use):
    now = energy_capacity(state)
    return now < to_use

def choose_next_mine(state):
    times = time_to_fill(state)
    times["crystal"] *=0.66
    times["deuterium"] *=0.33
    resource = max(times, key=times.get)
    mapping = {
        "metal": "Metal Mine",
        "crystal": "Crystal Mine",
        "deuterium": "Deuterium Synthesizer"
    }
    return mapping[resource]

def can_upgrade_factory(state):
    m = state.resources["metal"]
    c = state.resources["crystal"]
    d = state.resources["deuterium"]
    level = state.levels["Robotics Factory"]
    if level < 10:
        target = Robots()
        cost = target.cost(level + 1)
        can = True
        for r in cost.keys():
            if state.resources[r] < cost[r]:
                can = False
        if can:
            return target
    else:
        level = state.levels["Nanite Factory"]
        target = Nanite()
        cost = target.cost(level + 1)
        can = True
        for r in cost.keys():
            if state.resources[r] < cost[r]:
                can = False
        if can:
            return target
    return None

# =========================
# SIMULACIÓN
# =========================

def run_simulation(state, steps):
    rows = []
    last_time = 0
    for _ in range(steps):
        target = ""
        up_factory = can_upgrade_factory(state)
        if up_factory:
            target = up_factory
        else:
            up_mine = choose_next_mine(state)
            target = next(b for b in buildings if b.name == up_mine)
            next_level = state.levels[target.name] + 1
            cost = target.cost(next_level)
            up_storage = needs_storage_upgrade(state, cost)
            if up_storage:
                target = next(b for b in buildings if b.name == up_storage)
            else:
                energy = target.energy(next_level)
                up_energy = needs_energy_upgrade(state, energy)
                if up_energy:
                    target = SolarPlant()
        next_level = state.levels[target.name] + 1
        cost = target.cost(next_level)
        prod = production_per_hour(state)
        #print(f"Produccion: {m_h}m {c_h}c {d_h}d")
        def wait(req, have, prod):
            if req < have:
                return 0
            if prod == 0:
                return 0
            return (req - have) / prod
        resource_wait = max(
            wait(cost.get("metal", 0), state.resources["metal"], prod["metal"]),
            wait(cost.get("crystal", 0), state.resources["crystal"], prod["crystal"]),
            wait(cost.get("deuterium", 0), state.resources["deuterium"], prod["deuterium"])
        )
        dt = max(resource_wait, build_time(cost, state.levels["Robotics Factory"], state.levels["Nanite Factory"]))
        advance_time(state, dt)
        for r, v in cost.items():
            aux = math.ceil(state.resources[r]) - math.floor(v)
            state.resources[r] = aux
        state.levels[target.name] += 1
        rows.append({
            "time_h": time_str((state.time - last_time)*3600),
            "built": target.name,
            **state.levels,
            "metal": int(state.resources["metal"]),
            "crystal": int(state.resources["crystal"]),
            "deuterium": int(state.resources["deuterium"])
        })
        last_time = state.time
    return state, rows


# =========================
# UI
# =========================

class SimulatorUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OGame Simulator")
        self.metal = QLineEdit("32000000")
        self.crystal = QLineEdit("16000000")
        self.deut = QLineEdit("3300000")
        self.steps = QLineEdit("35")
        self.table = QTableWidget()
        self.state = None
        layout = QVBoxLayout()
        for label, field in [
            ("Metal inicial", self.metal),
            ("Crystal inicial", self.crystal),
            ("Deuterium inicial", self.deut),
            ("Pasos simulación", self.steps)
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(field)
            layout.addLayout(row)
        buttons = QHBoxLayout()
        btn1 = QPushButton("Ejecutar simulación")
        btn2 = QPushButton("Continuar simulación")
        btn1.clicked.connect(self.run)
        btn2.clicked.connect(self.rerun)
        buttons.addWidget(btn1)
        buttons.addWidget(btn2)
        layout.addLayout(buttons)
        layout.addWidget(self.table)
        self.setLayout(layout)

    def run(self, state = None):
        if not state:
            state = PlanetState(
                int(self.metal.text()),
                int(self.crystal.text()),
                int(self.deut.text())
            )
            for b in buildings:
                state.levels.setdefault(b.name, 0)
        state, rows = run_simulation(state, int(self.steps.text()))
        header = rows[0].keys()
        self.table.setColumnCount(len(header))
        self.table.setHorizontalHeaderLabels(header)
        self.table.setRowCount(len(rows))
        for h in range(len(rows)):
            row = rows[h]
            self.table.setRowHeight(h,1)
            column = 0
            for i in row.keys():
                item = row.get(i)
                newItem = QTableWidgetItem(str(item))
                self.table.setItem(h, column, newItem)
                column += 1
        self.state = state
        #if rows:
        #    with open("ogame_simulation.csv", "w", newline="", encoding="utf8") as f:
        #        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        #        writer.writeheader()
        #        writer.writerows(rows)
        #QMessageBox.information(self, "Listo",
        #    "Simulación finalizada\nCSV generado correctamente"
        #)

    def rerun(self):
        self.run(self.state)

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = SimulatorUI()
    ui.show()
    sys.exit(app.exec())
