import os, sys, time, json, requests, browser_cookie3
from datetime import datetime
from html.parser import HTMLParser
import re

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

def parse_fleet_response(html_text):
    """Parsea la respuesta HTML del event list y extrae información de flotas"""
    fleets = []
    
    # Buscar todas las filas de flota (eventFleet)
    fleet_pattern = r'<tr class="eventFleet"[^>]*id="eventRow-(\d+)"[^>]*data-mission-type="(\d+)"[^>]*data-return-flight="(true|false)"[^>]*data-arrival-time="(\d+)"[^>]*>(.*?)</tr>'
    
    for match in re.finditer(fleet_pattern, html_text, re.DOTALL):
        fleet_id = match.group(1)
        mission_type = int(match.group(2))
        return_flight = match.group(3) == "true"
        arrival_time = int(match.group(4))
        fleet_content = match.group(5)
        
        # Extraer tiempo de llegada en formato de reloj
        arrival_clock_match = re.search(r'<td class="arrivalTime">([^<]+)</td>', fleet_content)
        arrival_clock = arrival_clock_match.group(1) if arrival_clock_match else "—"
        
        # Extraer origen
        origin_match = re.search(r'<td class="originFleet">.*?<figure class="planetIcon ([^"]*)"[^>]*></figure>([^<]+)</td>', fleet_content, re.DOTALL)
        origin_type = origin_match.group(1) if origin_match else "planet"  # planet, moon
        origin_name = origin_match.group(2).strip() if origin_match else "—"
        
        # Extraer coordenadas de origen
        origin_coords_match = re.search(r'<td class="coordsOrigin">.*?\[([^\]]+)\]', fleet_content, re.DOTALL)
        origin_coords = origin_coords_match.group(1) if origin_coords_match else "—"
        
        # Extraer número de naves
        ships_count_match = re.search(r'<td class="detailsFleet">\s*<span>(\d+)</span>', fleet_content)
        ships_count = int(ships_count_match.group(1)) if ships_count_match else 0
        
        # Extraer destino
        dest_match = re.search(r'<td class="destFleet">.*?<figure class="planetIcon ([^"]*)"[^>]*></figure>([^<]+)</td>', fleet_content, re.DOTALL)
        dest_type = dest_match.group(1) if dest_match else "planet"  # planet, moon, tf (escombros)
        dest_name = dest_match.group(2).strip() if dest_match else "—"
        
        # Extraer coordenadas de destino
        dest_coords_match = re.search(r'<td class="destCoords">.*?\[([^\]]+)\]', fleet_content, re.DOTALL)
        dest_coords = dest_coords_match.group(1) if dest_coords_match else "—"
        
        # Extraer detalles de naves desde el tooltip (HTML decodificado)
        ships_detail = {}
        ships_tooltip_match = re.search(r'&lt;tr&gt;\s*&lt;td colspan="2"&gt;([^&]+)&lt;/td&gt;.*?&lt;td class="value"&gt;(\d+)&lt;/td&gt;', fleet_content, re.DOTALL)
        
        # Parsear tooltip HTML para obtener detalles de naves
        tooltip_match = re.search(r'title="([^"]*&lt;h1&gt;Fleet details[^"]*)"', fleet_content)
        if tooltip_match:
            tooltip_html = tooltip_match.group(1)
            # Decodificar HTML entities
            ship_lines = re.findall(r'&lt;td colspan="2"&gt;([^&]+)&lt;/td&gt;\s*&lt;td class="value"&gt;(\d+)&lt;/td&gt;', tooltip_html)
            for ship_name, count in ship_lines:
                ships_detail[ship_name.strip()] = int(count)
        
        # Obtener tipo de misión
        mission_types = {
            1: "Ataque",
            2: "Transportar",
            3: "Estacionar",
            4: "Espiar",
            5: "Colonizar",
            6: "Explosivo",
            7: "Defender",
            8: "Recolectar",
            9: "Comerciar",
            10: "Transportar tropas",
            11: "Parking (Lunas)",
            12: "Misión de Lunas",
            13: "Destruir",
            14: "Expedición",
            15: "Expedición (antiguo)",
            16: "Viajar Rápido"
        }
        
        mission_name = mission_types.get(mission_type, f"Tipo {mission_type}")
        
        fleet = {
            "id": fleet_id,
            "mission_type": mission_type,
            "mission_name": mission_name,
            "return_flight": return_flight,
            "arrival_time": arrival_time,
            "arrival_clock": arrival_clock,
            "origin": {
                "type": origin_type,
                "name": origin_name,
                "coords": origin_coords
            },
            "destination": {
                "type": dest_type,
                "name": dest_name,
                "coords": dest_coords
            },
            "ships_count": ships_count,
            "ships_detail": ships_detail
        }
        
        fleets.append(fleet)
    
    return fleets

class FleetWorker:
    """Worker para obtener información de flotas en movimiento"""
    def __init__(self, session=None):
        self.session = session or load_ogame_session("profile_data")
        self.base_url = "https://s163-ar.ogame.gameforge.com/game/index.php"
    
    def get_fleet_status(self):
        """Obtiene el estado actual de flotas"""
        try:
            params = {
                "page": "componentOnly",
                "component": "eventList",
                "ajax": "1"
            }
            
            r = self.session.get(self.base_url, params=params)
            r.raise_for_status()
            
            fleets = parse_fleet_response(r.text)
            return {
                "success": True,
                "fleets": fleets,
                "timestamp": time.time(),
                "count": len(fleets)
            }
        
        except Exception as e:
            print(f"[FLEET] Error obteniendo flotas: {e}")
            return {
                "success": False,
                "fleets": [],
                "error": str(e),
                "timestamp": time.time()
            }


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
            if token:
                payload["token"] = token
            r = session.post(BASE_URL, params=PARAMS, data=payload)
            token, parsed = parse_galaxy_response(r.text)
            print(f"G:{g} S:{s}")
            if parsed:
                data[str(g)][str(s)] = parsed
                time.sleep(0.7)
            time.sleep(0.3)
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