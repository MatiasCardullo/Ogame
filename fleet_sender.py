"""
Módulo para enviar flotas en OGame con validaciones y manejo de errores
Estrategia de token AJAX: Se obtiene de cualquier endpoint API exitoso
"""
import requests, time, json, traceback
from datetime import datetime
from galaxy_worker import load_ogame_session
from typing import Optional

# Cache global para el token AJAX
_token_cache = {
    "token": None,
    "timestamp": None,
    "duration": 3600  # 1 hora en segundos
}

def _is_token_valid():
    """Verifica si el token en cache es válido."""
    if not _token_cache["token"] or not _token_cache["timestamp"]:
        return False
    
    elapsed = (datetime.now() - _token_cache["timestamp"]).total_seconds()
    return elapsed < _token_cache["duration"]

def get_ajax_token(session) -> Optional[str]:
    """
    Obtiene el token AJAX necesario para enviar la flota.
    
    Estrategia:
    1. Intenta usar el token en cache si aún es válido
    2. Si no, llama a eventList API que retorna un newAjaxToken
    3. Cachea el token para futuras solicitudes
    
    OGame retorna 'newAjaxToken' en la respuesta de cualquier llamada API exitosa.
    """
    
    # Retornar token en cache si es válido
    if _is_token_valid():
        #print(f"[FLEET] ✅ Usando token en cache")
        return _token_cache["token"]
    
    try:
        print(f"[FLEET] 🔄 Obteniendo nuevo token AJAX...")
        
        # Llamar a eventList que siempre retorna un token
        url = "https://s163-ar.ogame.gameforge.com/game/index.php?page=componentOnly&component=eventList&ajax=1&asJson=1"
        
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
        }
        
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()
                
        try:
            data = response.json()
            if isinstance(data, dict) and "newAjaxToken" in data:
                token = data["newAjaxToken"]
                _token_cache["token"] = token
                _token_cache["timestamp"] = datetime.now()
                print(f"[FLEET] ✅ Token AJAX obtenido de JSON: {token[:16]}...")
                return token
        except json.JSONDecodeError:
            pass
        
        print("[FLEET] ⚠️  No se pudo extraer token AJAX")
        return None
        
    except Exception as e:
        print(f"[FLEET] ⚠️  Error obteniendo token AJAX: {str(e)}")
        return None

def update_token_from_response(response_data: dict):
    """
    Actualiza el token en cache desde una respuesta exitosa.
    Se llama después de cada POST exitoso para mantener el token fresco.
    """
    if isinstance(response_data, dict) and "newAjaxToken" in response_data:
        token = response_data["newAjaxToken"]
        _token_cache["token"] = token
        _token_cache["timestamp"] = datetime.now()
        print(f"[FLEET] 🔄 Token actualizado desde respuesta: {token[:16]}...")

def send_fleet(fleet_data, profile_path="profile_data"):
    """
    Envía una flota en OGame
    """
    
    # Mapeo de nombres de naves a IDs OGame (am202-am219)
    SHIP_ID_MAP = {
        "Nave Pequeña de Carga": "am202",
        "Nave Grande de Carga": "am203",
        "Cazador Ligero": "am204",
        "Cazador Pesado": "am205",
        "Crucero": "am206",
        "Nave de Batalla": "am207",
        "Nave Colonizadora": "am208",
        "Reciclador": "am209",
        "Sonda de Espionaje": "am210",
        "Bombardero": "am211",
        "Destructor": "am213",
        "Estrella de la Muerte": "am214",
        "Acorazado": "am215",
        "Segador": "am218",
        "Explorador": "am219"
    }
    
    # Mapeo de misiones (nombres en español a IDs numéricos)
    MISSION_MAP = {
        "Ataque": "1",
        "Transporte": "3",
        "Estacionamiento": "4",
        "Espionaje": "6",
        "Recolecta escombros": "8",
        "Expedición": "15"
    }
    
    try:
        # Cargar sesión del navegador Chrome
        print(f"[FLEET] Cargando sesión desde {profile_path}...")
        session = load_ogame_session(profile_path)
        
        # Obtener token AJAX (es CRÍTICO para el envío)
        ajax_token = get_ajax_token(session)
        if not ajax_token:
            return False, "No se pudo obtener el token AJAX"
        
        # Extraer coordenadas de destino
        try:
            g, s, p = map(int, fleet_data["destination"].split(":"))
        except (ValueError, KeyError) as e:
            return False, f"Destino inválido: {fleet_data.get('destination', 'N/A')}"
        
        # Verificar misión válida
        mission_name = fleet_data.get("mission", "Ataque")
        mission_id = MISSION_MAP.get(mission_name, "1")
        
        # Construir payload POST - EXACTAMENTE como en el HAR archivado
        payload = {
            "token": ajax_token,  # CRÍTICO: debe incluirse el token
            "galaxy": str(g),
            "system": str(s),
            "position": str(p),
            "type": "1",  # 1 = planeta, 3 = luna
            "mission": mission_id,
            "speed": "10",  # Velocidad (10 = máxima)
            # Parámetros de carga de recursos
            "metal": "0",
            "crystal": "0",
            "deuterium": "0",
            "food": "0",
            # Prioridades de recursos
            "prioMetal": "2",
            "prioCrystal": "3",
            "prioDeuterium": "4",
            "prioFood": "1",
            # Opciones adicionales
            "retreatAfterDefenderRetreat": "0",
            "lootFoodOnAttack": "0",
            "union": "0",
            "holdingtime": "1",
        }
        
        # Agregar naves al payload
        total_ships = 0
        for ship_name, count in fleet_data.get("ships", {}).items():
            ship_id = SHIP_ID_MAP.get(ship_name)
            if ship_id:
                try:
                    ship_count = int(count)
                    if ship_count > 0:
                        payload[ship_id] = str(ship_count)
                        total_ships += ship_count
                except (ValueError, TypeError):
                    continue
        
        if total_ships == 0:
            return False, "No hay naves para enviar"
        
        # Usar el id del planeta origen si fue provisto en fleet_data (campo origin_id)
        cp_val = fleet_data.get("origin_id") if isinstance(fleet_data, dict) else None
        cp_str = str(int(cp_val))

        # URL del endpoint - IMPORTANTE: incluir &ajax=1&asJson=1 para JSON response
        url = f"https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame&component=fleetdispatch&cp={cp_str}&action=sendFleet&ajax=1&asJson=1"
        # Actualizar Referer para que sea realista
        session.headers.update({
            "Referer": f"https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame&component=fleetdispatch&cp={cp_str}&mission={mission_id}&position={p}&type=1&galaxy={g}&system={s}"
        })
        
        print(f"[FLEET] Enviando {total_ships} naves a {g}:{s}:{p} - Misión: {mission_name}")
        
        response = session.post(url, data=payload, timeout=10)
        
        # Verificar respuesta
        if response.status_code == 200:
            try:
                response_data = response.json()
                
                with open("fleets.log", "a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now()}] Respuesta JSON: {response_data}\n")
                # Actualizar token para próximo envío
                update_token_from_response(response_data)
                
                # Verificar si el envío fue exitoso
                if response_data.get("success"):
                    message = response_data.get("message", "Flota enviada")
                    print(f"✅ {message}")
                    return True, f"Flota enviada: {total_ships} naves"
                else:
                    # Manejar errores
                    errors = response_data.get("errors", [])
                    if errors and isinstance(errors, list) and len(errors) > 0:
                        error_obj = errors[0]
                        error_msg = error_obj.get("message", "Error desconocido")
                        error_code = error_obj.get("error", "N/A")
                        print(f"❌ Error {error_code}: {error_msg}")
                        return False, f"Error {error_code}: {error_msg}"
                    else:
                        error_msg = response_data.get("message", "Error desconocido")
                        print(f"❌ Error: {error_msg}")
                        return False, error_msg
                    
            except json.JSONDecodeError as e:
                print(f"❌ Error parseando JSON: {response.text[:300]}")
                return False, "Respuesta JSON inválida"
        else:
            print(f"❌ Error HTTP {response.status_code}: {response.text[:300]}")
            return False, f"Error HTTP {response.status_code}"
    
    except requests.exceptions.ConnectionError:
        return False, "Error de conexión"
    except requests.exceptions.Timeout:
        return False, "Timeout en la conexión"
    except FileNotFoundError:
        return False, f"Cookies no encontradas en {profile_path}"
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return False, f"Error: {str(e)}"

def send_scheduled_fleets(scheduled_fleets, profile_path="profile_data", fleet_slots=None, exp_slots=None):
    """
    Envía múltiples flotas programadas respetando los slots disponibles.
    
    Args:
        scheduled_fleets: lista de flotas programadas
        profile_path: ruta al profile de Chrome
        fleet_slots: dict con {"current": int, "max": int} de slots de flotas
        exp_slots: dict con {"current": int, "max": int} de slots de expediciones
    """
    results = []
    current_time = time.time()
    
    # Calcular slots disponibles
    available_fleet_slots = fleet_slots.get("max", 0) - fleet_slots.get("current", 0)
    available_exp_slots = exp_slots.get("max", 0) - exp_slots.get("current", 0)
    
    #print(f"\n[FLEET-SENDER] Slots disponibles:")
    #print(f"  - Flotas: {available_fleet_slots}/{fleet_slots.get('max', 0)}")
    #print(f"  - Expediciones: {available_exp_slots}/{exp_slots.get('max', 0)}")

    for fleet in scheduled_fleets:
        # Saltar si ya fue completada
        if fleet.get("status") == "Completada":
            continue

        if fleet.get("status") == "Enviada" and fleet.get("repeat_remaining", 0) > 0:
            fleet["status"] = "Pendiente"
        elif fleet.get("status") == "Enviada":
            continue
        
        # Verificar si es hora de enviar
        timing_type = fleet.get("timing_type", "Enviar ahora")
        should_send = False
        
        if timing_type == "Enviar ahora":
            should_send = True
        elif timing_type == "Programar hora específica":
            scheduled_time = fleet.get("scheduled_time", 0)
            should_send = current_time >= scheduled_time
        elif timing_type == "Cuando esté disponible":
            # Esperar a que haya slots disponibles según el tipo de misión
            is_expedition = fleet.get("mission", "").lower() == "expedición"
            if is_expedition:
                should_send = available_exp_slots > 0
            else:
                should_send = available_fleet_slots > 0

        # No enviar si no hay slots disponibles
        if not should_send:
            if timing_type != "Cuando esté disponible":
                # Si no es "Cuando esté disponible", verificar slots de todas formas
                is_expedition = fleet.get("mission", "").lower() == "expedición"
                if is_expedition and available_exp_slots <= 0:
                    print(f"⚠️  No hay slots de expediciones disponibles")
                    continue
                elif not is_expedition and available_fleet_slots <= 0:
                    print(f"⚠️  No hay slots de flotas disponibles")
                    continue
            else:
                continue

        print(f"\n{'='*60}")
        print(f"Enviando flota: {fleet.get('mission')} → {fleet.get('destination')}")
        print(f"{'='*60}")

        success, message = send_fleet(fleet, profile_path)
        
        if success:
            # Decrementar el slot disponible según el tipo de misión
            is_expedition = fleet.get("mission", "").lower() == "expedición"
            if is_expedition:
                available_exp_slots -= 1
                print(f"✅ Expedición enviada. Slots restantes: {available_exp_slots}")
            else:
                available_fleet_slots -= 1
                print(f"✅ Flota enviada. Slots restantes: {available_fleet_slots}")
            
            fleet["repeat_remaining"] = fleet.get("repeat_remaining", 1) - 1
            
            # Reintentar repeticiones si hay slots disponibles
            while fleet["repeat_remaining"] > 0:
                if is_expedition and available_exp_slots <= 0:
                    break
                elif not is_expedition and available_fleet_slots <= 0:
                    break
                
                success, message = send_fleet(fleet, profile_path)
                if success:
                    fleet["repeat_remaining"] -= 1
                    if is_expedition:
                        available_exp_slots -= 1
                    else:
                        available_fleet_slots -= 1
                    print(f"✅ Repetición enviada. Repeticiones restantes: {fleet['repeat_remaining']}")
                else:
                    print(f"❌ Error en repetición: {message}")
                    break
            
            # Actualizar estado
            if timing_type == "Cuando esté disponible":
                fleet["status"] = "Pendiente"
                fleet["repeat_remaining"] = fleet["repeat_count"]
            else:
                fleet["status"] = "Completada"
        else:
            print(f"❌ Error al enviar: {message}")

        results.append({
            "fleet_id": fleet.get("id"),
            "mission": fleet.get("mission"),
            "destination": fleet.get("destination"),
            "success": success,
            "message": message
        })

    return results
