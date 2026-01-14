import math, csv
from dataclasses import dataclass

@dataclass
class Building:
    name: str

    def cost(self, level):
        raise NotImplementedError

    def production(self, level, A=1.0):
        return 0

    def energy(self, level):
        return 0

    def capacity(self, level):
        return None

class MetalMine(Building):
    def __init__(self):
        super().__init__("Metal Mine")

    def cost(self, level):
        factor = 1.5 ** (level - 1)
        return {
            "metal": 60 * factor,
            "crystal": 15 * factor
        }

    def production(self, level, A=1.0):
        return 30 * A * level * (1.1 ** level)

    def energy(self, level):
        return 10 * level * (1.1 ** level)

class CrystalMine(Building):
    def __init__(self):
        super().__init__("Crystal Mine")

    def cost(self, level):
        factor = 1.6 ** (level - 1)
        return {
            "metal": 48 * factor,
            "crystal": 24 * factor
        }

    def production(self, level, A=1.0):
        return 20 * A * level * (1.1 ** level)

    def energy(self, level):
        return 10 * level * (1.1 ** level)

class SolarPlant(Building):
    def __init__(self):
        super().__init__("Solar Plant")

    def cost(self, level):
        factor = 1.5 ** (level - 1)
        return {
            "metal": 75 * factor,
            "crystal": 30 * factor
        }

    def production(self, level):
        return 20 * level * (1.1 ** level)

class Storage(Building):
    def __init__(self, name, metal_base, crystal_base=0):
        super().__init__(name)
        self.metal_base = metal_base
        self.crystal_base = crystal_base

    def cost(self, level):
        factor = 2 ** (level - 1)
        return {
            "metal": self.metal_base * factor,
            "crystal": self.crystal_base * factor
        }

    def capacity(self, level):
        return 5000 * (2.5 * math.exp((20 / 33) * level))

class PlanetState:
    def __init__(
        self,
        levels=None,
        resources=None
    ):
        self.levels = levels or {
            "Metal Mine": 0,
            "Crystal Mine": 0,
            "Solar Plant": 0,
            "Metal Storage": 0,
            "Crystal Storage": 0
        }

        self.resources = resources or {
            "metal": 0.0,
            "crystal": 0.0
        }

        self.time = 0.0  # horas simuladas

    def clone(self):
        return PlanetState(
            levels=self.levels.copy(),
            resources=self.resources.copy()
        )

def evaluate_state(state, buildings):
    metal_prod = 0
    crystal_prod = 0
    energy_used = 0
    energy_prod = 0

    for b in buildings:
        lvl = state.levels[b.name]
        if lvl <= 0:
            continue

        if b.name == "Metal Mine":
            metal_prod += b.production(lvl)
            energy_used += b.energy(lvl)

        elif b.name == "Crystal Mine":
            crystal_prod += b.production(lvl)
            energy_used += b.energy(lvl)

        elif b.name == "Solar Plant":
            energy_prod += b.production(lvl)

    energy_balance = energy_prod - energy_used

    return {
        "metal/h": metal_prod,
        "crystal/h": crystal_prod,
        "energy": energy_balance,
        "total_prod": metal_prod + crystal_prod
    }

def can_afford(cost, resources):
    return all(resources.get(k, 0) >= v for k, v in cost.items())


def pay_cost(resources, cost):
    for k, v in cost.items():
        resources[k] -= v

def production_per_hour(state, buildings):
    metal = crystal = 0
    energy_used = energy_prod = 0

    for b in buildings:
        lvl = state.levels[b.name]
        if lvl <= 0:
            continue

        if b.name == "Metal Mine":
            metal += b.production(lvl)
            energy_used += b.energy(lvl)

        elif b.name == "Crystal Mine":
            crystal += b.production(lvl)
            energy_used += b.energy(lvl)

        elif b.name == "Solar Plant":
            energy_prod += b.production(lvl)

    if energy_prod < energy_used:
        factor = energy_prod / energy_used
        metal *= factor
        crystal *= factor

    return metal, crystal

def advance_until_affordable(state, cost, buildings):
    metal_h, crystal_h = production_per_hour(state, buildings)

    t_metal = (
        max(0, cost.get("metal", 0) - state.resources["metal"]) / metal_h
        if metal_h > 0 else float("inf")
    )
    t_crystal = (
        max(0, cost.get("crystal", 0) - state.resources["crystal"]) / crystal_h
        if crystal_h > 0 else float("inf")
    )

    dt = max(t_metal, t_crystal)

    state.resources["metal"] += metal_h * dt
    state.resources["crystal"] += crystal_h * dt
    state.time += dt

def simulate_next_best(state, buildings):
    best = None

    base_eval = evaluate_state(state, buildings)

    for b in buildings:
        test_state = state.clone()
        test_state.levels[b.name] += 1

        eval_after = evaluate_state(test_state, buildings)

        gain = eval_after["total_prod"] - base_eval["total_prod"]

        if eval_after["energy"] < 0:
            continue  # inválido

        score = gain

        if best is None or score > best["score"]:
            best = {
                "building": b.name,
                "score": score,
                "state": test_state
            }

    return best

def build(state, building, buildings):
    next_level = state.levels[building.name] + 1
    cost = building.cost(next_level)

    if not can_afford(cost, state.resources):
        advance_until_affordable(state, cost, buildings)

    pay_cost(state.resources, cost)
    state.levels[building.name] = next_level

def snapshot(state, buildings, built=None):
    metal_h, crystal_h = production_per_hour(state, buildings)

    row = {
        "time_h": round(state.time, 2),
        "built": built,
        "metal_h": round(metal_h, 2),
        "crystal_h": round(crystal_h, 2),
        "metal": round(state.resources["metal"], 2),
        "crystal": round(state.resources["crystal"], 2)
    }

    for k, v in state.levels.items():
        row[k] = v

    return row

def run_simulation(state, buildings, steps, csv_path):
    rows = []

    for _ in range(steps):
        best = simulate_next_best(state, buildings)
        if not best:
            break

        build(state, next(b for b in buildings if b.name == best["building"]), buildings)
        rows.append(snapshot(state, buildings, best["building"]))

    with open(csv_path, "w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

if __name__ == "__main__":
    buildings = [
        MetalMine(),
        CrystalMine(),
        SolarPlant(),
        Storage("Metal Storage", 1000),
        Storage("Crystal Storage", 1000, 500)
    ]

    state = PlanetState(
        levels={
            "Metal Mine": 0,
            "Crystal Mine": 0,
            "Solar Plant": 0,
            "Metal Storage": 0,
            "Crystal Storage": 0
        },
        resources={
            "metal": 100000,
            "crystal": 100000
        }
    )

    run_simulation(
        state=state,
        buildings=buildings,
        steps=50,
        csv_path="ogame_simulation.csv"
    )

