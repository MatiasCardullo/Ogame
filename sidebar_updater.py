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
    function debug(msg) { try { console.log('[OGameDebug]', msg); } catch(e) {} }

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
        if (!name) continue;

        // 🔹 Edificios e investigaciones: tiempos absolutos
        if (label !== '🚀 Hangar') {
            const timeEl = box.querySelector('time.countdown');
            const time = timeEl?.textContent?.trim() || '';
            const start = parseInt(timeEl?.dataset.start || '0');
            const end = parseInt(timeEl?.dataset.end || '0');
            if (name && time && start && end) {
                result.push({ label, name, time, start, end });
            }
            continue;
        }

        // 🚀 Hangar: sin timestamps absolutos
        const timeEl = box.querySelector('time.shipyardCountdown, time.shipyardCountdownUnit');
        const timeStr = timeEl?.textContent?.trim() || '';
        if (!timeStr) continue;

        // Parsear duración desde texto (por ejemplo "3m 41s")
        const m = timeStr.match(/(?:(\\d+)h)?\\s*(?:(\\d+)m)?\\s*(?:(\\d+)s)?/);
        const h = parseInt(m?.[1] || '0');
        const min = parseInt(m?.[2] || '0');
        const sec = parseInt(m?.[3] || '0');
        const duration = h*3600 + min*60 + sec;

        const now = Math.floor(Date.now()/1000);
        const start = now;
        const end = now + duration;

        debug('Hangar detectado: ' + name + ' (' + duration + 's)');

        result.push({ label, name, time: timeStr, start, end });
    }

    return result;
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
        const match = info.match(/approx\\.\\s*(.+)/i);
        auction.status = 'Subasta activa';
        auction.timeLeft = match ? match[1] : (info || '—');
    }

    return auction;
})();
"""
