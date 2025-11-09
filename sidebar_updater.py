# --- Extrae metadatos del jugador / planeta ---
extract_meta_script = """
(function() {
    const metas = document.getElementsByTagName('meta');
    let data = {};
    for (let m of metas) if (m.name && m.content) data[m.name] = m.content;
    return data;
})();
"""

# --- Extrae recursos del DOM ---
extract_resources_script = """
(function() {
    let ids = ['metal_box', 'crystal_box', 'deuterium_box', 'energy_box'];
    let data = {};
    for (let id of ids) {
        let el = document.getElementById(id);
        if (el) {
            let valueEl = el.querySelector('.value');
            data[id] = valueEl ? valueEl.textContent.trim() : '—';
        }
    }
    return data;
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







