import sys, math, csv
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox
)

# =========================
# EDIFICIOS
# =========================

@dataclass
class Building:
    name: str
    def cost(self, level):
        raise NotImplementedError
    def production(self, level):
        return 0
    def energy(self, level):
        return 0
    def capacity(self, level):
        return 0

class MetalMine(Building):
    def __init__(self):
        super().__init__("Metal Mine")

    def cost(self, level):
        f = 1.5 ** (level - 1)
        return {"metal": 60 * f, "crystal": 15 * f}

    def production(self, level):
        return 30 * level * (1.1 ** level)

    def energy(self, level):
        return 10 * level * (1.1 ** level)

class CrystalMine(Building):
    def __init__(self):
        super().__init__("Crystal Mine")

    def cost(self, level):
        f = 1.6 ** (level - 1)
        return {"metal": 48 * f, "crystal": 24 * f}

    def production(self, level):
        return 20 * level * (1.1 ** level)

    def energy(self, level):
        return 10 * level * (1.1 ** level)

class DeuteriumSynthesizer(Building):
    def __init__(self):
        super().__init__("Deuterium Synthesizer")

    def cost(self, level):
        f = 1.6 ** (level - 1)
        return {"metal": 225 * f, "crystal": 75 * f}

    def production(self, level):
        return 20 * level * (1.1 ** level)

    def energy(self, level):
        return 20 * level * (1.1 ** level)

class SolarPlant(Building):
    def __init__(self):
        super().__init__("Solar Plant")

    def cost(self, level):
        f = 1.5 ** (level - 1)
        return {"metal": 75 * f, "crystal": 30 * f}

    def production(self, level):
        return 20 * level * (1.1 ** level)

class Storage(Building):
    def __init__(self, name, metal_base, crystal_base=0):
        super().__init__(name)
        self.metal_base = metal_base
        self.crystal_base = crystal_base

    def cost(self, level):
        f = 2 ** (level - 1)
        return {
            "metal": self.metal_base * f,
            "crystal": self.crystal_base * f
        }

    def capacity(self, level):
        return 5000 * (2.5 * math.exp((20 / 33) * level))

class MetalStorage(Storage):
    def __init__(self):
        super().__init__("Metal Storage", 1000)

class CrystalStorage(Storage):
    def __init__(self):
        super().__init__("Crystal Storage", 1000, 500)

class DeuteriumTank(Storage):
    def __init__(self):
        super().__init__("Deuterium Tank", 1000, 1000)

buildings = [
    MetalMine(),
    CrystalMine(),
    DeuteriumSynthesizer(),
    SolarPlant(),
    MetalStorage(),
    CrystalStorage(),
    DeuteriumTank()
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
            energy += b.production(lvl)
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
            prod += b.production(lvl)
    if used > 0 and prod < used:
        factor = prod / used
        m *= factor
        c *= factor
        d *= factor
    return prod - used, m, c, d

def advance_time(state, dt):
    dt = math.ceil(dt)
    _, m_h, c_h, d_h = production_per_hour(state)
    caps = storage_capacity(state)
    state.resources["metal"] = min(state.resources["metal"] + m_h * dt, caps["metal"])
    state.resources["crystal"] = min(state.resources["crystal"] + c_h * dt, caps["crystal"])
    state.resources["deuterium"] = min(state.resources["deuterium"] + d_h * dt, caps["deuterium"])
    state.time += dt

def time_to_fill(state,):
    _ ,m_h, c_h, d_h = production_per_hour(state)
    caps = storage_capacity(state)
    def t(res, cap, prod):
        if prod == 0:
            return sys.maxsize
        return (cap - res) / prod
    return {
        "metal": t(state.resources["metal"], caps["metal"], m_h),
        "crystal": t(state.resources["crystal"], caps["crystal"], c_h),
        "deuterium": t(state.resources["deuterium"], caps["deuterium"], d_h)
    }

def needs_storage_upgrade(state, cost):
    caps = storage_capacity(state)
    for r, v in cost.items():
        if v > caps[r]:
            return r
    for r, v in caps.items():
        if v * 0.8 < state.resources[r]:
            return r
    return None

def needs_energy_upgrade(state, to_use):
    now = energy_capacity(state)
    return now < to_use

def choose_next_building(state):
    times = time_to_fill(state)
    resource = max(times, key=times.get)
    mapping = {
        "metal": "Metal Mine",
        "crystal": "Crystal Mine",
        "deuterium": "Deuterium Synthesizer"
    }
    return mapping[resource]


# =========================
# SIMULACIÓN
# =========================

def run_simulation(state, steps, csv_path):
    rows = []
    for b in buildings:
        state.levels.setdefault(b.name, 0)
    for _ in range(steps):
        target_name = choose_next_building(state)
        target = next(b for b in buildings if b.name == target_name)
        next_level = state.levels[target.name] + 1
        energy = target.energy(next_level)
        needed = needs_energy_upgrade(state, energy)
        if needed:
            target = next(b for b in buildings if b.name == "Solar Plant")
            next_level = state.levels[target.name] + 1
        cost = target.cost(next_level)
        
        needed = needs_storage_upgrade(state, cost)
        if needed:
            store_map = {
                "metal": "Metal Storage",
                "crystal": "Crystal Storage",
                "deuterium": "Deuterium Tank"
            }
            target = next(b for b in buildings if b.name == store_map[needed])
            next_level = state.levels[target.name] + 1
            cost = target.cost(next_level)
        
        energy, m_h, c_h, d_h = production_per_hour(state)
        #print(f"Produccion: {m_h}m {c_h}c {d_h}d")
        def wait(req, have, prod):
            if req < have:
                return 0
            if prod == 0:
                return 0
            return (req - have) / prod
        dt = max(
            wait(cost.get("metal", 0), state.resources["metal"], m_h),
            wait(cost.get("crystal", 0), state.resources["crystal"], c_h),
            wait(cost.get("deuterium", 0), state.resources["deuterium"], d_h)
        )
        if not math.isfinite(dt):
            break
        advance_time(state, dt)
        for r, v in cost.items():
            aux = math.ceil(state.resources[r]) - int(v)
            state.resources[r] = state.resources[r] - v
        state.levels[target.name] += 1
        rows.append({
            "time_h": state.time,
            "built": target.name,
            **state.levels,
            "metal": int(state.resources["metal"]),
            "crystal": int(state.resources["crystal"]),
            "deuterium": int(state.resources["deuterium"])
        })

    if rows:
        with open(csv_path, "w", newline="", encoding="utf8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


# =========================
# UI
# =========================

class SimulatorUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OGame Simulator")
        self.metal = QLineEdit("1000")
        self.crystal = QLineEdit("1000")
        self.deut = QLineEdit("0")
        self.steps = QLineEdit("200")
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
        btn = QPushButton("Ejecutar simulación")
        btn.clicked.connect(self.run)
        layout.addWidget(btn)
        self.setLayout(layout)

    def run(self):
        state = PlanetState(
            int(self.metal.text()),
            int(self.crystal.text()),
            int(self.deut.text())
        )
        run_simulation(state, int(self.steps.text()), "ogame_simulation.csv")
        QMessageBox.information(
            self,
            "Listo",
            "Simulación finalizada\nCSV generado correctamente"
        )


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    ui = SimulatorUI()
    ui.show()
    sys.exit(app.exec())
