"""
Módulo para enviar flotas en OGame
"""
import requests
import time
from worker import load_ogame_session

def send_fleet(fleet_data, profile_path="profile_data"):
    """
    Envía una flota en OGame
    
    fleet_data: {
        "mission": "Expedición",
        "origin": "Nombre (G:S:P)",
        "destination": "G:S:P",
        "ships": {"Cazador Ligero": 100, "Cazador Pesado": 50, ...},
        "timing_type": "Enviar ahora" | "Cuando esté disponible" | "Programar hora específica",
        "scheduled_time": timestamp o None
    }
    
    Mapeo de IDs de naves:
    am204 = Cazador Ligero (Light Fighter)
    am205 = Cazador Pesado (Heavy Fighter)
    am206 = Crucero (Cruiser)
    am207 = Nave de Batalla (Battleship)
    am215 = Acorazado (Battlecruiser)
    am211 = Bombardero (Bomber)
    am213 = Destructor (Destroyer)
    am214 = Estrella de la Muerte (Deathstar)
    am202 = Nave Pequeña de Carga (Small Cargo)
    am203 = Nave Grande de Carga (Large Cargo)
    am208 = Nave Colonizadora (Colony Ship)
    am209 = Reciclador (Recycler)
    am210 = Sonda de Espionaje (Espionage Probe)
    am218 = Segador (Reaper)
    am219 = Explorador (Pathfinder)
    
    Mapeo de misiones:
    1 = Ataque
    3 = Transporte
    4 = Estacionamiento
    6 = Espionaje
    8 = Recolecta escombros
    15 = Expedición
    """
    
    # Mapeo de nombres de naves a IDs
    SHIP_ID_MAP = {
        "Cazador Ligero": "am204",
        "Cazador Pesado": "am205",
        "Crucero": "am206",
        "Nave de Batalla": "am207",
        "Acorazado": "am215",
        "Bombardero": "am211",
        "Destructor": "am213",
        "Estrella de la Muerte": "am214",
        "Nave Pequeña de Carga": "am202",
        "Nave Grande de Carga": "am203",
        "Nave Colonizadora": "am208",
        "Reciclador": "am209",
        "Sonda de Espionaje": "am210",
        "Segador": "am218",
        "Explorador": "am219"
    }
    
    # Mapeo de misiones
    MISSION_MAP = {
        "Ataque": "1",
        "Transporte": "3",
        "Estacionamiento": "4",
        "Espionaje": "6",
        "Recolecta escombros": "8",
        "Expedición": "15"
    }
    
    try:
        # Cargar sesión del navegador
        session = load_ogame_session(profile_path)
        
        # Extraer coordenadas de destino
        g, s, p = map(int, fleet_data["destination"].split(":"))
        
        # Construir payload POST
        payload = {
            "galaxy": str(g),
            "system": str(s),
            "position": str(p),
            "type": "1",  # 1 = planeta, 3 = luna
            "mission": MISSION_MAP.get(fleet_data["mission"], "1"),
            "speed": "100",  # Velocidad máxima
        }
        
        # Agregar naves
        for ship_name, count in fleet_data["ships"].items():
            ship_id = SHIP_ID_MAP.get(ship_name)
            if ship_id:
                payload[ship_id] = str(count)
        
        # Endpoint para enviar flota
        url = "https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame&component=fleetdispatch&action=sendFleet"
        
        response = session.post(url, data=payload, timeout=15)
        
        if response.status_code == 200:
            print(f"✅ Flota enviada exitosamente a {g}:{s}:{p}")
            return True, "Flota enviada"
        else:
            print(f"❌ Error al enviar flota: {response.status_code}")
            return False, f"Error {response.status_code}"
    
    except Exception as e:
        print(f"❌ Error enviando flota: {str(e)}")
        return False, str(e)


def send_scheduled_fleets(scheduled_fleets, profile_path="profile_data"):
    """
    Envía múltiples flotas programadas
    """
    results = []
    
    for fleet in scheduled_fleets:
        if fleet["status"] == "Enviada":
            continue
        
        # Verificar si es hora de enviar
        timing_type = fleet.get("timing_type", "Enviar ahora")
        
        if timing_type == "Enviar ahora":
            should_send = True
        elif timing_type == "Cuando esté disponible":
            # TODO: Verificar si hay expediciones en movimiento
            should_send = True
        else:  # "Programar hora específica"
            current_time = time.time()
            scheduled_time = fleet.get("scheduled_time", 0)
            should_send = current_time >= scheduled_time
        
        if should_send:
            success, message = send_fleet(fleet, profile_path)
            
            if success:
                fleet["status"] = "Enviada"
                # Decrementar el contador de repeticiones
                fleet["repeat_remaining"] = fleet.get("repeat_remaining", 1) - 1
                if fleet["repeat_remaining"] <= 0:
                    fleet["status"] = "Completada"
            
            results.append({
                "fleet_id": fleet.get("id"),
                "success": success,
                "message": message
            })
    
    return results
