"""
Módulo para enviar flotas en OGame con validaciones y manejo de errores
Estrategia de token AJAX: Se obtiene de cualquier endpoint API exitoso
"""
import requests
import time
import json
from datetime import datetime, timedelta
from worker import load_ogame_session
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
        print(f"[FLEET] ✅ Usando token en cache")
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
        
        print(f"[FLEET] Respuesta de eventList: {response.status_code}")
        
        # Intenta parsear como JSON
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
        
        # Si la respuesta es HTML, buscar el token con regex
        import re
        token_match = re.search(r'"newAjaxToken"\s*:\s*"([a-f0-9]{32})"', response.text)
        if token_match:
            token = token_match.group(1)
            _token_cache["token"] = token
            _token_cache["timestamp"] = datetime.now()
            print(f"[FLEET] ✅ Token AJAX obtenido de HTML: {token[:16]}...")
            return token
        
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
        
        # URL del endpoint - IMPORTANTE: incluir &ajax=1&asJson=1 para JSON response
        url = "https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame&component=fleetdispatch&action=sendFleet&ajax=1&asJson=1"
        
        # Actualizar Referer para que sea realista
        session.headers.update({
            "Referer": f"https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame&component=fleetdispatch&mission={mission_id}&position={p}&type=1&galaxy={g}&system={s}"
        })
        
        print(f"[FLEET] Enviando {total_ships} naves a {g}:{s}:{p}")
        print(f"[FLEET] Misión: {mission_name}")
        print(f"[FLEET] Token: {ajax_token[:16]}...")
        
        response = session.post(url, data=payload, timeout=10)
        
        print(f"[FLEET] Respuesta HTTP: {response.status_code}")
        
        # Verificar respuesta
        if response.status_code == 200:
            try:
                response_data = response.json()
                print(f"[FLEET] Respuesta JSON: {response_data}")
                
                # Actualizar token para próximo envío
                update_token_from_response(response_data)
                
                # Verificar si el envío fue exitoso
                if response_data.get("success"):
                    message = response_data.get("message", "Flota enviada")
                    print(f"✅ Flota enviada exitosamente")
                    print(f"   {message}")
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
        import traceback
        traceback.print_exc()
        return False, f"Error: {str(e)}"

def send_scheduled_fleets(scheduled_fleets, profile_path="profile_data", fleets_data=None):
    """
    Envía múltiples flotas programadas
    """
    results = []
    current_time = time.time()
    
    for fleet in scheduled_fleets:
        # Saltar si ya fue completada
        if fleet.get("status") == "Completada":
            continue
        
        # Si ya fue enviada y aún hay repeticiones, esperar antes de la siguiente
        if fleet.get("status") == "Enviada" and fleet.get("repeat_remaining", 0) > 0:
            fleet["status"] = "Pendiente"
        elif fleet.get("status") == "Enviada":
            continue
        
        # Verificar si es hora de enviar
        timing_type = fleet.get("timing_type", "Enviar ahora")
        should_send = False
        
        if timing_type == "Enviar ahora":
            should_send = True
        elif timing_type == "Cuando esté disponible":
            # "Cuando esté disponible" = enviar todas las expediciones programadas en secuencia
            # sin restricciones. Simplemente envíalas una tras otra.
            should_send = True
        elif timing_type == "Programar hora específica":
            scheduled_time = fleet.get("scheduled_time", 0)
            should_send = current_time >= scheduled_time
        
        if should_send:
            print(f"\n{'='*60}")
            print(f"Enviando flota: {fleet.get('mission')} → {fleet.get('destination')}")
            print(f"{'='*60}")
            
            success, message = send_fleet(fleet, profile_path)
            
            if success:
                fleet["status"] = "Enviada"
                fleet["repeat_remaining"] = fleet.get("repeat_remaining", 1) - 1
                
                if fleet["repeat_remaining"] <= 0:
                    fleet["status"] = "Completada"
                    print(f"✅ Flota completada")
                else:
                    print(f"🔄 Repetición: {fleet['repeat_remaining']} restantes")
                
                # Esperar entre envíos
                time.sleep(1)
            
            results.append({
                "fleet_id": fleet.get("id"),
                "mission": fleet.get("mission"),
                "destination": fleet.get("destination"),
                "success": success,
                "message": message
            })
    
    return results
