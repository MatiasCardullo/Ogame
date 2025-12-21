import json, os, sys

def extract_debris_list(galaxy_data: dict, g):
    normal_debris = []
    expedition_debris = []

    systems = galaxy_data[str(g)]
    for s, positions in systems.items():
        for pos, entry in positions.items():
            debris = entry.get("debris")
            if not debris:
                continue
            
            if int(pos) == 16:
                expedition_debris.append({
                    "galaxy": g,
                    "system": int(s),
                    "metal": debris.get("metal", 0),
                    "crystal": debris.get("crystal", 0),
                    "deuterium": debris.get("deuterium", 0),
                    "requiredShips": debris.get("requiredShips")
                })
            else:
                normal_debris.append({
                    "galaxy": g,
                    "system": int(s),
                    "position": int(pos),
                    "metal": debris.get("metal", 0),
                    "crystal": debris.get("crystal", 0),
                    "deuterium": debris.get("deuterium", 0),
                    "requiredShips": debris.get("requiredShips")
                })

    return normal_debris, expedition_debris

def main():
    if len(sys.argv) < 2:
        print("Uso: python worker.py <galaxy_number>")
        print("Ejemplo: python worker.py 1")
        sys.exit(1)
    
    try:
        galaxy = int(sys.argv[1])
        if galaxy < 1 or galaxy > 5:
            print("Galaxia debe estar entre 1 y 5")
            sys.exit(1)
    except ValueError:
        print("La galaxia debe ser un número")
        sys.exit(1)
    
    with open(f"galaxy_data_g{galaxy}.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    normal, exp = extract_debris_list(data, galaxy)

    normal.sort(key=lambda x: x["requiredShips"], reverse=True)
    exp.sort(key=lambda x: x["requiredShips"], reverse=True)
    print("Recyclers")
    print("\n".join([f"System: {item['system']}, Required Ships: {item['requiredShips']}" for item in normal]))
    print("PathFinder")
    print("\n".join([f"System: {item['system']}, Required Ships: {item['requiredShips']}" for item in exp]))

if __name__ == "__main__":
    main()