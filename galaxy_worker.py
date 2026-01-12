import os, random
import time, json, requests, browser_cookie3, sys, traceback
from tqdm import tqdm
from text import cantidad, draw_box

def close():
    print("\nCerrando en    ", end='')
    for i in range(99, 0, -1):
        print('\b' if i>8 else '', end='')
        print(f"\b\b{i} ", end='', flush=True)
        time.sleep(1)
    print("\r                ")
    sys.exit(1)

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

def ensure_logged_in(profile_name, galaxy=None, retry_wait=10):
    BASE_URL = "https://s163-ar.ogame.gameforge.com/game/index.php"
    while True:
        session = load_ogame_session(profile_name)
        try:
            r = session.get(f"{BASE_URL}?page=ingame&component=galaxy", timeout=10)
            if "component=galaxy" in r.text:
                if galaxy is not None:
                    print(f"\r[GALAXY {galaxy}] Logged          ")
                return session
        except Exception as e:
            print(f"\n[LOGIN] Error: {e}")

        if galaxy is not None:
            print(f"\r[GALAXY {galaxy}] Login...", end='', flush=True)
        time.sleep(retry_wait)

def parse_systems_arg(arg):
    # Caso: número único
    if arg.isdigit():
        s = int(arg)
        return range(s, s + 1)

    # Caso: rango A-B
    if "-" in arg:
        start, end = arg.split("-", 1)
        if start.isdigit() and end.isdigit():
            start, end = int(start), int(end)
            if start <= end:
                return range(start, end + 1)

    raise ValueError(f"Sistemas inválidos: '{arg}'")

class GalaxyWorker:
    def __init__(self, galaxy, systems=None, full_scan=True):
        self.galaxy = galaxy
        self.systems = systems or range(1, 500)
        self.full_scan = full_scan
        self.PLANETS = 0
        self.MOONS = 0
        self.DEBRIS = 0
        self.METAL = 0
        self.CRYSTAL = 0
        self.DEUTERIUM = 0

    def parse_galaxy_response(self, text, response=None):
        # Extraer cookie de sesión de la respuesta si existe
        session_cookie = None
        if response:
            if "prsess_100170" in response.cookies:
                session_cookie = response.cookies["prsess_100170"]
        
        text = text.strip()
        if not text.startswith("{"):
            print("\n⚠️ Non-JSON response (first 200 chars):")
            print(text[:200])
            return {}, session_cookie

        data = json.loads(text)        
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
                    self.PLANETS+=1
                    entry["player"] = row.get("player", {}).get("playerName")
                    entry["planet"] = {
                        "name": body.get("planetName"),
                        "isDestroyed": body.get("isDestroyed", False)
                    }
                elif ptype == 2:
                    self.DEBRIS+=1
                    res = body.get("resources") or {}
                    m = int(res.get("metal", {}).get("amount",0))
                    c = int(res.get("crystal", {}).get("amount",0))
                    d = int(res.get("deuterium", {}).get("amount",0))
                    if m: self.METAL += m
                    if c: self.CRYSTAL += c
                    if d: self.DEUTERIUM += d
                    entry["debris"] = {
                        "requiredShips": body.get("requiredShips"),
                        "metal": m, "crystal": c, "deuterium": d
                    }
                elif ptype == 3:
                    self.MOONS+=1
                    entry["player"] = row.get("player", {}).get("playerName")
                    entry["moon"] = {
                        "name": body.get("planetName"),
                        "isDestroyed": body.get("isDestroyed", False),
                        "size": body.get("size")
                    }

            if entry:
                parsed[str(pos)] = entry

        parsed["updated"] = time.time()
        return parsed, session_cookie

    def run(self):
        BASE_URL = "https://s163-ar.ogame.gameforge.com/game/index.php"
        PARAMS = {
            "page": "ingame",
            "component": "galaxy",
            "action": "fetchGalaxyContent",
            "ajax": "1",
            "asJson": "1"
        }

        g = self.galaxy
        output_file = f"galaxy_data_g{g}.json"

        # ── login inicial
        session = ensure_logged_in("profile_data", g)

        # ── cargar datos previos si existen
        if not self.full_scan and os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            tqdm.write(f"[GALAXY {g}] Archivo existente cargado, mergeando datos")
        else:
            data = {}

        data.setdefault(str(g), {})

        pbar = tqdm(
            self.systems,
            desc=f"G{g} escaneando",
            unit="sistema",
            dynamic_ncols=True,
            position=0
        )
        status_one = tqdm(
            total=0,
            bar_format="{desc}",
            position=1
        )
        status_two = tqdm(
            total=0,
            bar_format="{desc}",
            position=2
        )
        for s in pbar:
            payload = {"galaxy": g, "system": s}
            max_retries = 5
            retry_count = 0
            parsed = None

            while retry_count < max_retries and parsed is None:
                try:
                    r = session.post(BASE_URL, params=PARAMS, data=payload, timeout=10)
                    parsed, session_cookie = self.parse_galaxy_response(r.text, r)
                    
                    # Actualizar la cookie de sesión si se recibió una nueva
                    if session_cookie:
                        session.cookies.set("prsess_100170", session_cookie)

                    if parsed == {}:
                        tqdm.write(f"{g}:{s} vacío → relogin")
                        session = ensure_logged_in("profile_data", g)
                        retry_count += 1
                        continue

                    if parsed is None:
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(2 ** retry_count)
                        else:
                            tqdm.write(f"[ERROR] {g}:{s} inválido tras {max_retries} reintentos")
                    else:
                        break

                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        time.sleep(2 ** retry_count)
                    else:
                        tqdm.write(f"[ERROR] {g}:{s} conexión fallida: {e}")

            # guardar resultado
            data[str(g)][str(s)] = parsed
            time.sleep(random.random())  # evitar rate limiting
            # ── actualizar barra con stats
            if parsed:
                status_one.set_description_str(
                    f"Sistema {s} Espacios ocupados: {len(parsed) - 1} "
                    f"Planetas: {self.PLANETS} Lunas: {self.MOONS}"
                )
                status_two.set_description_str(
                    f"Escombros: {self.DEBRIS} > "
                    f"M={cantidad(self.METAL)} "
                    f"C={cantidad(self.CRYSTAL)} "
                    f"D={cantidad(self.DEUTERIUM)}"
                )
        pbar.close()
        status_one.close()
        status_two.close()

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        tqdm.write(f"[GALAXY {g}] Guardado en {output_file}")

if __name__ == "__main__":
    full_scan = len(sys.argv) < 3

    if len(sys.argv) < 2:
        print("Uso:")
        print("  python galaxy_worker.py <galaxia>")
        print("  python galaxy_worker.py <galaxia> <sistema>")
        print("  python galaxy_worker.py <galaxia> <inicio-fin>")
        sys.exit(1)

    try:
        galaxy_num = int(sys.argv[1])
        if not (1 <= galaxy_num <= 5):
            raise ValueError("La galaxia debe estar entre 1 y 5")
        if full_scan:
            systems = None
            print(f"[GalaxyWorker] Galaxia {galaxy_num} | Sistemas 1-499")
        else:
            systems = parse_systems_arg(sys.argv[2])
            print(f"[GalaxyWorker] Galaxia {galaxy_num} | Sistemas {systems.start}-{systems.stop - 1}")
        worker = GalaxyWorker(galaxy_num, systems, full_scan)
        worker.run()
        print(f"[GalaxyWorker] Galaxia {galaxy_num} completada")
        close()
    except ValueError as e:
        print(f"Error: {e}")
        close()
    except Exception as e:
        print(f"[GalaxyWorker] Error en galaxia: {e}")
        traceback.print_exc()
        close()
