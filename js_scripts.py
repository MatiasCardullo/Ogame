# Detectar si estamos en el juego
in_game = """
    (function() {
        const metas = document.getElementsByTagName('meta');
        for (let m of metas) {
            if (m.name && m.name.startsWith('ogame-player-name')) 
                return true;
        }
        return false;
    })();
"""

# --- Extrae metadatos del jugador / planeta ---
extract_meta_script = """
    (function() {
        const metas = document.getElementsByTagName('meta');
        let data = {};
        for (let m of metas) if (m.name && m.content) data[m.name] = m.content;
        return data;
    })();
"""

extract_resources_script = """
    (function() {
        try {
            const scripts = document.getElementsByTagName('script');
            for (let i = 0; i < scripts.length; i++) {
                const txt = scripts[i].textContent || '';
                const m = txt.match(/reloadResources\s*\(\s*(\{[\s\S]*?\})\s*\)\s*;/);
                if (m && m[1]) {
                    const obj = JSON.parse(m[1]);
                    if (obj && obj.resources) {
                        const r = obj.resources;
                        const data = {
                            metal: r.metal?.amount ?? 0,
                            crystal: r.crystal?.amount ?? 0,
                            deuterium: r.deuterium?.amount ?? 0,
                            energy: r.energy?.amount ?? 0,
                            population: r.population?.amount ?? 0,
                            food: r.food?.amount ?? 0,
                            prod_metal: r.metal?.production ?? 0,
                            prod_crystal: r.crystal?.production ?? 0,
                            prod_deuterium: r.deuterium?.production ?? 0,
                            prod_population: r.population?.growthRate ?? 0,
                            prod_food: r.food?.production ?? 0,
                            capacity_metal: r.metal?.storage ?? 0,
                            capacity_crystal: r.crystal?.storage ?? 0,
                            capacity_deuterium: r.deuterium?.storage ?? 0,
                            capacity_population: r.population?.storage ?? 0,
                            capacity_food: r.food?.storage ?? 0
                        };
                        console.log("[OGameDebug] Recursos extraídos:", data);
                        return data;
                    }
                }
            }
        } catch(e) {
            console.log("[OGameDebug] Error al leer recursos:", e);
        }
        return {
            metal:0, crystal:0, deuterium:0, energy:0,
            prod_metal:0, prod_crystal:0, prod_deuterium:0,
            capacity_metal:0, capacity_crystal:0, capacity_deuterium:0
        };
    })();
"""

# --- Extrae colas de construcción / investigación / flota / forma de vida ---
extract_queue_functions = """
    function extract_building() {
        const box = document.querySelector('#productionboxbuildingcomponent .construction.active');
        if (!box) return [];
        const name = box.querySelector('th')?.textContent?.trim() || "";
        const timeEl = box.querySelector('time.countdown');
        if (!timeEl) return [];
        return [{
            label: "🏗️ Edificio",
            name: name,
            start: parseInt(timeEl.dataset.start || "0"),
            end: parseInt(timeEl.dataset.end || "0")
        }];
    }

    function extract_research() {
        const box = document.querySelector('#productionboxresearchcomponent .construction.active');
        if (!box) return [];
        const name = box.querySelector('th')?.textContent?.trim() || "";
        const timeEl = box.querySelector('time.countdown');
        if (!timeEl) return [];
        return [{
            label: "🧬 Investigación",
            name: name,
            start: parseInt(timeEl.dataset.start || "0"),
            end: parseInt(timeEl.dataset.end || "0")
        }];
    }

    function extract_lf_building() {
        const box = document.querySelector('#productionboxlfbuildingcomponent .construction.active');
        if (!box) return [];
        const name = box.querySelector('th')?.textContent?.trim() || "";
        const timeEl = box.querySelector('time.countdown');
        if (!timeEl) return [];
        return [{
            label: "🌿 Edificio Forma de Vida",
            name: name,
            start: parseInt(timeEl.dataset.start || "0"),
            end: parseInt(timeEl.dataset.end || "0")
        }];
    }

    function extract_lf_research() {
        const box = document.querySelector('#productionboxlfresearchcomponent .construction.active');
        if (!box) return [];
        const name = box.querySelector('th')?.textContent?.trim() || "";
        const timeEl = box.querySelector('time.countdown');
        if (!timeEl) return [];
        return [{
            label: "🧬 Investigación Forma de Vida",
            name: name,
            start: parseInt(timeEl.dataset.start || "0"),
            end: parseInt(timeEl.dataset.end || "0")
        }];
    }

    function extract_shipyard() {
        const box = document.querySelector('#productionboxshipyardcomponent .construction.active');
        if (!box) return [];

        const name = box.querySelector('th')?.textContent?.trim() || '';
        const timeEl = box.querySelector('time.shipyardCountdown, time.shipyardCountdownUnit');
        const str = timeEl?.textContent?.trim() || "";
        if (!str) return [];

        const match = str.match(/(?:(\\d+)h)?\\s*(?:(\\d+)m)?\\s*(?:(\\d+)s)?/);
        const h = parseInt(match?.[1] || '0');
        const m = parseInt(match?.[2] || '0');
        const s = parseInt(match?.[3] || '0');
        const duration = h*3600 + m*60 + s;

        const now = Math.floor(Date.now()/1000);
        return [{
            label: "🚀 Hangar",
            name: name,
            start: now,
            end: now + duration
        }];
    }
"""

extract_planet_array = """
    (function() {
        console.log("[DEBUG JS] Buscando planetList...");
        
        // Intentar encontrar planetList en el documento
        let planetList = document.getElementById('planetList');
        console.log("[DEBUG JS] planetList encontrado:", !!planetList);
        
        if (!planetList) {
            console.log("[DEBUG JS] Intentando buscar en iframe...");
            const iframes = document.querySelectorAll('iframe');
            console.log("[DEBUG JS] Iframes encontrados:", iframes.length);
            for (let iframe of iframes) {
                try {
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                    if (iframeDoc) {
                        planetList = iframeDoc.getElementById('planetList');
                        if (planetList) {
                            console.log("[DEBUG JS] planetList encontrado en iframe");
                            break;
                        }
                    }
                } catch(e) {
                    console.log("[DEBUG JS] Error accediendo iframe:", e.message);
                }
            }
        }
        
        if (!planetList) {
            console.log("[DEBUG JS] No se encontró planetList en ningún lugar");
            return null;
        }
        
        console.log("[DEBUG JS] Buscando enlaces de planetas...");
        const planets = [];

        document.querySelectorAll('#planetList .smallplanet').forEach(planetEl => {
            const planetId = planetEl.id.replace('planet-', '');
            const nameEl = planetEl.querySelector('.planet-name');
            const coordsEl = planetEl.querySelector('.planet-koords');
            const planetName = nameEl ? nameEl.textContent.trim() : null;
            const coords = coordsEl ? coordsEl.textContent.trim() : null;
            const moonLink = planetEl.querySelector('.moonlink');
            let moon = null;
            if (moonLink) {
                const moonCp = new URL(moonLink.href).searchParams.get('cp');
                const moonImg = moonLink.querySelector('img');
                moon = {
                    id: moonCp,
                    name: moonImg ? moonImg.alt.trim() : 'Moon'
                };
            }
            planets.push({
                id: planetId,
                name: planetName,
                coords: coords,
                moon: moon
            });
        });
        
        console.log("[DEBUG JS] Total links retornados:", planets.length);
        return planets.length > 0 ? planets : null;
    })();
    """

extract_auction_script = """
(function() {
    const auction = {};
    const box = document.querySelector('.left_content');
    if (!box) return { error: "No se encontró .left_content" };

    // Ítem actual (si hay imagen)
    const img = box.querySelector('.image_140px img');
    auction.item = img?.getAttribute('alt') || '—';
    auction.image = img?.getAttribute('src') || '';

    // Info de subasta o próxima subasta
    const info = box.querySelector('.auction_info')?.textContent?.trim() || '';
    auction.info = info;

    // Puja actual y mejor postor (si existen)
    auction.currentBid = box.querySelector('.currentSum')?.textContent?.trim() || '—';
    auction.highestBidder = box.querySelector('.currentPlayer')?.textContent?.trim() || '—';

    // Detectar si es subasta activa o próxima
    const next = box.querySelector('#nextAuction')?.textContent?.trim();
    if (next) {
        auction.status = 'Próxima subasta';
        auction.timeLeft = next;
    } else {
        const match = info.match(/approx\.\s*(.+)/i);
        auction.status = 'Subasta activa';
        auction.timeLeft = match ? match[1] : (info || '—');
    }

    return auction;
})();
"""

extract_fleets_script = """
    (function() {
        const result = {
            fleets: [],
            fleetSlots: { current: 0, max: 0 },
            expSlots: { current: 0, max: 0 }
        };
        
        // Extraer slots de flotas y expediciones
        const fleetSlotsSpan = document.querySelector('span.fleetSlots');
        if (fleetSlotsSpan) {
            const current = fleetSlotsSpan.querySelector('span.current');
            const all = fleetSlotsSpan.querySelector('span.all');
            if (current && all) {
                result.fleetSlots.current = parseInt(current.textContent.trim());
                result.fleetSlots.max = parseInt(all.textContent.trim());
            }
        }
        
        const expSlotsSpan = document.querySelector('span.expSlots');
        if (expSlotsSpan) {
            const current = expSlotsSpan.querySelector('span.current');
            const all = expSlotsSpan.querySelector('span.all');
            if (current && all) {
                result.expSlots.current = parseInt(current.textContent.trim());
                result.expSlots.max = parseInt(all.textContent.trim());
            }
        }
        
        // Buscar elementos con clase 'fleetDetails' (usado en fleet_page.html)
        const fleetDivs = document.querySelectorAll('div.fleetDetails');
        
        if (fleetDivs.length === 0) {
            console.log("[OGameDebug] No se encontraron flotas con div.fleetDetails");
            return result;
        }
        
        for (let fleetDiv of fleetDivs) {
            try {
                const fleet = {};
                
                // Obtener el atributo data-mission-type
                const missionType = fleetDiv.getAttribute('data-mission-type');
                const missionMap = {
                    '1': 'Ataque',
                    '3': 'Transporte',
                    '4': 'Estacionamiento',
                    '6': 'Espionaje',
                    '8': 'Recolecta escombros',
                    '15': 'Expedición',
                    '18': 'Viaje de vuelta'
                };
                fleet.mission_name = missionMap[missionType] || `Misión ${missionType}`;
                fleet.mission_type = missionType;
                
                // Detectar si es vuelo de regreso
                fleet.return_flight = fleetDiv.getAttribute('data-return-flight') === 'true';
                
                // Origen - buscar en span.originCoords y span.originPlanet
                const originCoords = fleetDiv.querySelector('span.originCoords a');
                const originPlanet = fleetDiv.querySelector('span.originPlanet');
                
                fleet.origin = {
                    coords: originCoords ? originCoords.textContent.trim() : '—',
                    name: originPlanet ? originPlanet.textContent.trim().replace(/\\s+/g, ' ') : '—'
                };
                
                // Destino - buscar en span.destinationCoords y span.destinationPlanet
                const destCoords = fleetDiv.querySelector('span.destinationCoords a');
                const destPlanet = fleetDiv.querySelector('span.destinationPlanet');
                
                // Extraer nombre del planeta del destino
                let destName = '—';
                if (destPlanet) {
                    const textContent = destPlanet.textContent.trim();
                    if (textContent) {
                        destName = textContent;
                    }
                }
                
                // Si no hay nombre, intentar desde el tooltip title
                if (destName === '—' && destCoords) {
                    const title = destCoords.parentElement.getAttribute('title');
                    if (title) {
                        destName = title;
                    }
                }
                
                fleet.destination = {
                    coords: destCoords ? destCoords.textContent.trim() : '—',
                    name: destName
                };
                
                // Contar naves desde el tooltip
                let shipsCount = 0;
                const fleetId = fleetDiv.id.replace('fleet', '');
                const tooltipDiv = document.querySelector(`#bl${fleetId}`);
                
                if (tooltipDiv) {
                    const shipRows = tooltipDiv.querySelectorAll('table.fleetinfo tr');
                    for (let row of shipRows) {
                        const valueCell = row.querySelector('td.value');
                        if (valueCell) {
                            const count = parseInt(valueCell.textContent.trim());
                            if (!isNaN(count)) {
                                shipsCount += count;
                            }
                        }
                    }
                }
                fleet.ships_count = shipsCount;
                
                // Hora de llegada
                const arrivalTime = fleetDiv.getAttribute('data-arrival-time');
                fleet.arrival_time = arrivalTime ? parseInt(arrivalTime) : 0;
                
                // Reloj de llegada (absTime)
                const absTimeSpan = fleetDiv.querySelector('span.absTime');
                fleet.arrival_clock = absTimeSpan ? absTimeSpan.textContent.trim() : '—';
                
                result.fleets.push(fleet);
                console.log("[OGameDebug] Flota extraída:", fleet);
            } catch (e) {
                console.log("[OGameDebug] Error extrayendo flota:", e);
            }
        }
        
        console.log("[OGameDebug] Total de flotas extraídas:", result.fleets.length);
        console.log("[OGameDebug] Slots - Flotas:", result.fleetSlots, "Expediciones:", result.expSlots);
        return result;
    })();
"""
