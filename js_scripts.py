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
                        prod_metal: r.metal?.production ?? 0,
                        prod_crystal: r.crystal?.production ?? 0,
                        prod_deuterium: r.deuterium?.production ?? 0,
                        capacity_metal: r.metal?.storage ?? 0,
                        capacity_crystal: r.crystal?.storage ?? 0,
                        capacity_deuterium: r.deuterium?.storage ?? 0
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
