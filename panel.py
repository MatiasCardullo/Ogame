import time
from fleet_tab import update_fleet_origin_combo
from text import (
    cantidad, planet_production_entry,
    format_queue_entry, format_research_queue_entry
)


def refresh_resources_panel(self):
    """Actualiza la pestaña de Recursos y Colas"""
    html = """
    <style>
        body { background-color: #000; color: #EEE; font-family: Consolas; }
        table { border-collapse: collapse; margin-top: 10px; width: 100%; }
        th { background-color: #222; color: #0f0; border: 1px solid #333; padding: 8px; text-align: center; }
        td { background-color: #111; color: #EEE; border: 1px solid #333; padding: 6px; font-size: 12px; }
        .bar { font-family: monospace; }
        .research-section { background-color: #1a1a2e; padding: 8px; margin-top: 10px; border: 1px solid #0af; }
        .moon-section { background-color: #0a1a1a; padding: 4px 6px; margin-top: 4px; border-left: 2px solid #0af; font-size: 11px; }
    </style>
    <h2>🌌 Recursos y Colas</h2>
    """

    if not self.planets_data:
        html += "<p>No hay datos de planetas aún.</p>"
        self.resources_label.setText(html)
        return

    # Extraer solo planetas (no lunas) para las columnas, ordenados por coordenadas
    planet_info = []
    for planet_id, pdata in self.planets_data.items():
        name = pdata.get("name", "")
        coords = pdata.get("coords", "")
        planet_info.append((name, coords, planet_id))
    
    # Ordenar por coordenadas (G:S:P)
    def coords_sort_key(item):
        name, coords, pid = item
        try:
            parts = coords.split(":")
            g = int(parts[0]) if len(parts) > 0 else 0
            s = int(parts[1]) if len(parts) > 1 else 0
            p = int(parts[2]) if len(parts) > 2 else 0
            return (g, s, p)
        except (ValueError, IndexError):
            return (0, 0, 0)
    
    planet_info.sort(key=coords_sort_key)
    
    now = int(time.time())

    # ----- Investigaciones (global, deduplicadas por label+name)
    unique_research = {}
    for planet_key, pdata in self.planets_data.items():
        queues = pdata.get("queues", [])
        for q in queues:
            label = (q.get("label", "") or "")
            name = (q.get("name", "") or "")
            is_research = (
                "Investigación" in label or "🧬" in label or
                "investig" in label.lower() or "research" in label.lower()
            )
            if is_research:
                key = f"{label}|{name}".strip().lower()
                if key not in unique_research:
                    unique_research[key] = q

    for q in getattr(self, 'research_data', {}).values():
        label = (q.get("label", "") or "")
        name = (q.get("name", "") or "")
        key = f"{label}|{name}".strip().lower()
        if key not in unique_research:
            unique_research[key] = q

    if unique_research:
        html += "<div class='research-section'><b>🧬 Investigaciones:</b><br>"
        for entry in unique_research.values():
            end = int(entry.get("end", now))
            if end <= now:
                continue
            html += format_research_queue_entry(entry, now, self.current_update_interval == 1000) + "<br>"
        html += "</div>"

    # ----- Tabla recursos + colas por planeta
    html += "<table><tr><th>Recurso</th>"
    for name, coords, key in planet_info:
        if not coords == "":
            html += f"<th>{name}<br><small>{coords}</small></th>"
    html += "</tr>"

    resource_specs = ["Metal", "Crystal", "Deuterium", "Energy"]
    for rname in resource_specs:
        #rkey, capkey, prodkey, color = spec
        aux = f"<tr><td><b>{rname}</b></td>"
        for name, coords, key in planet_info:
            pdata = self.planets_data[key]
            r = pdata["resources"]

            rname = rname.lower()
            if rname == "energy":
                aux += f"<td>⚡ {r.get(rname, 0)}</td>"
                continue
            elif rname == "metal": color = "#555"
            elif rname == "crystal": color = "#aff"
            elif rname == "deuterium": color = "#0f8"
            aux += planet_production_entry(r.get(rname, 0), r.get(f"cap_{rname}", 1), r.get(f"prod_{rname}", 0), color)
            
            # Mostrar lunas si existen
            moons = pdata.get("moons", {})
            if moons:
                for moon_key, moon_data in moons.items():
                    moon_resources = moon_data.get("resources", {})
                    moon_cant = moon_resources.get(rname, 0)
                    if moon_cant>0:
                        aux += "<div class='moon-section'>"
                        moon_name = moon_data.get("name", "Moon")
                        aux += f"🌙 {moon_name}: {cantidad(moon_cant)}"
                        aux += "</div>"
            aux += "</td>"
            
        html += aux
        html += "</tr>"

    # ----- Colas (no investigación) — agrupar por tipo y mostrar por planeta
    queue_types = {
        "🏗️ Construcciones": [],
        "🚀 Hangar": [],
        "🌿 Forma de Vida": []
    }

    for name, coords, key in planet_info:
        for q in self.planets_data[key].get("queues", []):
            label = q.get("label", "")
            end = int(q.get("end", now))
            if end <= now:
                continue
            if "Investigación" in label or "🧬" in label:
                continue
            elif "Forma de Vida" in label or "lf" in label.lower():
                queue_types["🌿 Forma de Vida"].append((name, coords, q))
            elif "Hangar" in label or "🚀" in label:
                queue_types["🚀 Hangar"].append((name, coords, q))
            else:
                queue_types["🏗️ Construcciones"].append((name, coords, q))
        
        # Agregar colas de lunas también
        moons = self.planets_data[key].get("moons", {})
        for moon_key, moon_data in moons.items():
            for q in moon_data.get("queues", []):
                label = q.get("label", "")
                end = int(q.get("end", now))
                if end <= now:
                    continue
                # Para lunas, solo mostrar construcciones
                queue_types["🏗️ Construcciones"].append((name, coords, q, moon_data.get("name", "Moon")))

    for qtype, entries in queue_types.items():
        if not entries:
            continue

        html += f"<tr><td><b>{qtype}</b></td>"

        for name, coords, key in planet_info:
            # Colas del planeta: filtrar y extraer solo el dict q
            planet_entries = [e[2] for e in entries if len(e) == 3 and e[0] == name and e[1] == coords]
            # Colas de lunas del planeta: extraer (q_dict, moon_name)
            moon_entries = [(e[2], e[3]) for e in entries if len(e) == 4 and e[0] == name and e[1] == coords]
            
            if not planet_entries and not moon_entries:
                html += "<td>—</td>"
                continue

            html += "<td>"
            
            # Mostrar colas del planeta
            for idx, q in enumerate(planet_entries):
                html += format_queue_entry(q, now, self.current_update_interval == 1000)
                if idx < len(planet_entries) - 1 or moon_entries:
                    html += "<br>"
            
            # Mostrar colas de lunas
            for midx, (q, moon_name) in enumerate(moon_entries):
                html += f"<div class='moon-section'>🌙 {moon_name}<br>"
                html += format_queue_entry(q, now, self.current_update_interval == 1000)
                html += "</div>"
                if midx < len(moon_entries) - 1:
                    html += "<br>"
            
            html += "</td>"

        html += "</tr>"
    html += "</table>"

    self.resources_label.setHtml(html)

# Función removida: refresh_fleets_panel
# Las flotas ahora se muestran en la página de flotas de pages_views[1]

# ====================================================================
#  UPDATE PLANET DATA (API nueva con queues que incluyen id)
# ====================================================================
def update_planet_data(self, planet_name, coords, resources, queues, is_moon=False, parent_planet_key=None):
    """
    Recibe:
        - planet_name (str)
        - coords (str)
        - resources (dict)
        - queues (list of queue dicts, cada uno con 'id','label','name','start','end','planet_name','coords',...)
        - is_moon (bool): indica si es una luna
        - parent_planet_key (str): ID del planeta padre (si es luna)
    """
    # Normalizar recursos: asegurar last_update timestamp
    resources = resources or {}
    if "last_update" not in resources:
        resources["last_update"] = time.time()

    # Usar el planet_id real de OGame
    planet_id = getattr(self, 'current_main_web_planet_id', None)
    if not planet_id:
        # Fallback: usar coords como id si no hay planet_id
        planet_id = coords
    
    # Filtrar las queues: solo edificios para lunas
    qlist = []
    for q in queues or []:
        qid = q.get("id")
        if not qid:
            continue
        q_planet = q.get("planet_name", planet_name)
        q_coords = q.get("coords", coords)


        entry = {
            "id": qid,
            "label": q.get("label", ""),
            "name": q.get("name", ""),
            "level": q.get("level", ""),
            "start": int(q.get("start", time.time())),
            "end": int(q.get("end", time.time())),
            "planet_name": q_planet,
            "coords": q_coords
        }

        # Si es global (research), almacenarla en research_data
        if q_planet is None or str(q_planet).upper() == "GLOBAL":
            self.research_data[qid] = entry
            continue

        # Si la cola pertenece a este planeta, verificar nombre Y coordenadas
        # Esto es importante cuando hay múltiples planetas con el mismo nombre
        if q_planet == planet_name and q_coords == coords:
            qlist.append(entry)

    if is_moon and parent_planet_key:
        # Guardar luna de forma anidada dentro del planeta usando el ID del planeta padre
        if parent_planet_key not in self.planets_data:
            # Si el planeta padre no existe aún, crear un placeholder
            self.planets_data[parent_planet_key] = {
                "id": parent_planet_key,
                "name": "",
                "coords": "",
                "resources": {},
                "queues": [],
                "moons": {}
            }
        # Inicializar estructura de moons si no existe
        if "moons" not in self.planets_data[parent_planet_key]:
            self.planets_data[parent_planet_key]["moons"] = {}
        # Guardar luna dentro del planeta usando su planet_id real
        self.planets_data[parent_planet_key]["moons"][planet_id] = {
            "id": planet_id,
            "name": planet_name,
            "coords": coords,
            "resources": resources,
            "queues": qlist,
            "last_update": time.time()
        }
    else:
        # Guardar planeta normalmente
        pdata = self.planets_data.get(planet_id, {})
        pdata["id"] = planet_id
        pdata["name"] = planet_name
        pdata["coords"] = coords
        pdata["resources"] = resources
        pdata["queues"] = qlist
        pdata["last_update"] = time.time()
        # Asegurar que existe la estructura de moons
        if "moons" not in pdata:
            pdata["moons"] = {}
        self.planets_data[planet_id] = pdata

    # Refrescar UI
    try:
        self.refresh_main_panel()
        update_fleet_origin_combo(self)  # Actualizar combo de planetas
    except Exception as e:
        print("[DEBUG] Error updated_planet_data:", e)

