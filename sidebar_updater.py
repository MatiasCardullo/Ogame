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
    function debug(msg) { try { console.log("[OGameDebug]", msg); } catch(e) {} }

    try {
        const scripts = document.getElementsByTagName('script');
        for (let i = 0; i < scripts.length; i++) {
            const txt = scripts[i].textContent || '';
            const m = txt.match(/reloadResources\\s*\\(\\s*(\\{[\\s\\S]*?\\})\\s*\\)\\s*;/);
            if (m && m[1]) {
                const obj = JSON.parse(m[1]);
                if (obj && obj.resources) {
                    const r = obj.resources;
                    const data = {
                        metal: String(r.metal?.amount ?? '—'),
                        crystal: String(r.crystal?.amount ?? '—'),
                        deuterium: String(r.deuterium?.amount ?? '—'),
                        energy: String(r.energy?.amount ?? '—'),
                        prod_metal: String(r.metal?.production ?? '0'),
                        prod_crystal: String(r.crystal?.production ?? '0'),
                        prod_deuterium: String(r.deuterium?.production ?? '0')
                    };
                    debug("Datos extraídos del JSON con producción: " + JSON.stringify(data));
                    return data;
                }
            }
        }
    } catch(e) { debug("Error: " + e); }

    return { metal:'—', crystal:'—', deuterium:'—', energy:'—', prod_metal:'0', prod_crystal:'0', prod_deuterium:'0' };
})();
"""

# --- Extrae colas de construcción / investigación / flota ---
extract_queue_script = """
(function() {
    const sections = {
        '🏗️ Edificio': '#productionboxbuildingcomponent .construction.active',
        '🧬 Investigación': '#productionboxresearchcomponent .construction.active',
        '🚀 Hangar': '#productionboxshipyardcomponent .construction.active'
    };

    let result = [];

    for (const [label, selector] of Object.entries(sections)) {
        const box = document.querySelector(selector);
        if (!box) continue;

        const name = box.querySelector('th')?.textContent?.trim() || '';
        const level = box.querySelector('.level')?.textContent?.trim() || '';
        const timeEl = box.querySelector('time.countdown');
        const time = timeEl?.textContent?.trim() || '';
        const start = parseInt(timeEl?.dataset.start || '0');
        const end = parseInt(timeEl?.dataset.end || '0');

        if (name && time && start && end) {
            result.push({ label, name, level, time, start, end });
        }
    }

    return result;
})();
"""







