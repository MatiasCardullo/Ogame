import os, sys, time, json, requests, browser_cookie3

def load_ogame_session(profile_path):
    cj = browser_cookie3.chrome(
        cookie_file=f"{profile_path}/Cookies",
        domain_name="ogame.gameforge.com"
    )
    session = requests.Session()
    session.cookies.update(cj)
    session.headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame&component=galaxy",
        "Origin": "https://s163-ar.ogame.gameforge.com",
    })
    return session

def parse_galaxy_response(text):
    text = text.strip()

    if not text.startswith("{"):
        print("⚠ Non-JSON response (first 200 chars):")
        print(text[:200])
        return None, {}

    data = json.loads(text)

    token = data.get("newAjaxToken")
    system = data.get("system") or {}
    galaxy_content = system.get("galaxyContent") or []

    parsed = {}

    for row in galaxy_content:
        pos = row.get("position")
        if not pos:
            continue

        entry = {}
        if pos == 16:
            planets = [row.get("planets")]
        else:
            planets = row.get("planets")

        for body in planets:
            if not isinstance(body, dict):
                continue

            ptype = body.get("planetType")

            if ptype == 1:
                entry["player"] = row.get("player", {}).get("playerName")
                entry["planet"] = {
                    "name": body.get("planetName"),
                    "isDestroyed": body.get("isDestroyed", False)
                }
            elif ptype == 2:
                res = body.get("resources") or {}
                entry["debris"] = {
                    "requiredShips": body.get("requiredShips"),
                    "metal": res.get("metal", {}).get("amount", 0),
                    "crystal": res.get("crystal", {}).get("amount", 0),
                    "deuterium": res.get("deuterium", {}).get("amount", 0)
                }
            elif ptype == 3:
                entry["player"] = row.get("player", {}).get("playerName")
                entry["moon"] = {
                    "name": body.get("planetName"),
                    "isDestroyed": body.get("isDestroyed", False),
                    "size": body.get("size")
                }

        if entry:
            parsed[str(pos)] = entry

    return token, parsed

class GalaxyWorker:
    def __init__(self, galaxy):
        self.galaxy = galaxy
        
    def run(self):
        BASE_URL = "https://s163-ar.ogame.gameforge.com/game/index.php"
        PARAMS = {
            "page": "ingame",
            "component": "galaxy",
            "action": "fetchGalaxyContent",
            "ajax": "1",
            "asJson": "1"
        }
        session = load_ogame_session("profile_data")
        data = {}
        token = None
        logged = False
        
        # Esperar login
        while not logged:
            r = session.get(f"{BASE_URL}?page=ingame&component=galaxy")
            if "component=galaxy" in r.text:
                logged = True
                print(f"[GALAXY {self.galaxy}] Logged")
                break
            time.sleep(10)
            print(f"[GALAXY {self.galaxy}] Login...")
            session = load_ogame_session("profile_data")
        
        # Iterar solo la galaxia especificada
        g = self.galaxy
        data[str(g)] = {}
        for s in range(1, 500):
            payload = {"galaxy": g, "system": s}
            #if token:
                #payload["token"] = token
            r = session.post(BASE_URL, params=PARAMS, data=payload)
            token, parsed = parse_galaxy_response(r.text)
            print(f"G:{g} S:{s}")
            if parsed:
                data[str(g)][str(s)] = parsed
                time.sleep(0.5)
        data["time"] = time.time()
        # Guardar en archivo específico para esta galaxia
        output_file = f"galaxy_data_g{g}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[GALAXY {self.galaxy}] Guardado en {output_file}")


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
    
    output_file = f"galaxy_data_g{galaxy}.json"
    if os.path.isfile(output_file):
        if len(sys.argv) > 2 and sys.argv[2] == 'f':
            print(f"Sobreescribiendo archivo {output_file}")
        else:
            print(f"Archivo {output_file} ya existe")
            sys.exit(1)
    worker = GalaxyWorker(galaxy)
    worker.run()


if __name__ == "__main__":
    main()