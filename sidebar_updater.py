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
    function debug(msg) {
        try { console.log('[OGameDebug]', msg); } catch(e) {}
    }

    const sections = {
        '🏗️ Edificio': '#productionboxbuildingcomponent .construction.active',
        '🧬 Investigación': '#productionboxresearchcomponent .construction.active',
        '🚀 Hangar': '#productionboxshipyardcomponent .construction.active'
    };

    let result = [];

    for (const [label, selector] of Object.entries(sections)) {
        const box = document.querySelector(selector);
        if (!box) {
            debug(label + ' → no encontrado');
            continue;
        }

        const name = box.querySelector('th')?.textContent?.trim() || '';
        const level = box.querySelector('.level')?.textContent?.trim() || '';

        let timeEl = box.querySelector('time.shipyardCountdown, time.shipyardCountdownUnit, time.countdown');
        let time = timeEl?.textContent?.trim() || '';
        let start = parseInt(timeEl?.dataset.start || '0');
        let end = parseInt(timeEl?.dataset.end || '0');

        debug(label + ' encontrado: ' + name + ' (time=' + time + ', start=' + start + ', end=' + end + ')');

        // --- Si no hay dataset válido, buscar dentro de los <script> ---
        if (!end || end <= start) {
            const scripts = Array.from(document.getElementsByTagName('script'));
            for (const s of scripts) {
                const txt = s.textContent;

                // 🛰 Buscar la línea del Hangar: CountdownTimer('shipyardCountdown', start, url, null, true, minutos)
                const m = txt.match(/new\\s+CountdownTimer\\(['"]shipyardCountdown['"],\\s*(\\d+),[^,]*,[^,]*,\\s*true,\\s*(\\d+)\\)/);
                if (m) {
                    start = parseInt(m[1]);
                    const minutes = parseInt(m[2]);
                    end = start + minutes * 60;
                    debug('→ Detectado CountdownTimer del hangar: start=' + start + ', duracionMin=' + minutes + ', end=' + end);
                    break;
                }

                // 🔧 Si no se encontró, intentar con CountdownTimerUnit
                const m2 = txt.match(/new\\s+CountdownTimerUnit\\(['"]shipyardCountdownUnit['"],\\s*(\\d+),\\s*(\\d+),/);
                if (m2) {
                    start = parseInt(m2[1]);
                    end = parseInt(m2[2]);
                    debug('→ Detectado CountdownTimerUnit: start=' + start + ', end=' + end);
                    break;
                }
            }
        }

        if (end && start && end > start) {
            const remaining = Math.max(0, end - Math.floor(Date.now() / 1000));
            const minutes = Math.floor(remaining / 60);
            const seconds = remaining % 60;
            time = `${minutes}m ${seconds.toString().padStart(2, '0')}s`;
        }

        debug(label + ' → FINAL: ' + name + ' | start=' + start + ' | end=' + end + ' | time=' + time);

        if (name && end && end > start) {
            result.push({ label, name, level, time, start, end });
        }
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
