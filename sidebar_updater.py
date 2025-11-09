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
    function debug(msg) {
        try { console.log("[OGameDebug]", msg); } catch(e) {}
    }

    // --- Intentar leer el JSON de reloadResources ---
    try {
        const scripts = document.getElementsByTagName('script');
        for (let i = 0; i < scripts.length; i++) {
            const txt = scripts[i].textContent || '';
            const m = txt.match(/reloadResources\\s*\\(\\s*(\\{[\\s\\S]*?\\})\\s*\\)\\s*;/);
            if (m && m[1]) {
                debug("Encontrado JSON en reloadResources()");
                try {
                    const obj = JSON.parse(m[1]);
                    if (obj && obj.resources) {
                        const r = obj.resources;
                        const data = {
                            metal: String(r.metal?.amount ?? '—'),
                            crystal: String(r.crystal?.amount ?? '—'),
                            deuterium: String(r.deuterium?.amount ?? '—'),
                            energy: String(r.energy?.amount ?? '—')
                        };
                        debug("Datos extraídos del JSON: " + JSON.stringify(data));
                        return data;  // ✅ retorna directamente al callback Python
                    }
                } catch(e) { debug("Error al parsear JSON: " + e); }
            }
        }
    } catch(e) { debug("Error general JSON: " + e); }

    // --- Fallback DOM ---
    try {
        const mapping = { '0': 'metal', '1': 'crystal', '2': 'deuterium', '3': 'energy' };
        let data = {};
        Object.keys(mapping).forEach(function(idx) {
            let el = document.querySelector('td.normalmark[data-resourceidx=\"' + idx + '\"] span') ||
                     document.querySelector('td.normalmark[data-resourceidx=\"' + idx + '\"]');
            let txt = el ? (el.textContent || el.innerText || '').trim() : '—';
            data[mapping[idx]] = txt || '—';
        });
        debug("Fallback DOM data: " + JSON.stringify(data));
        return data;
    } catch(e) {
        debug("Error final: " + e);
        return { metal: '—', crystal: '—', deuterium: '—', energy: '—' };
    }
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







