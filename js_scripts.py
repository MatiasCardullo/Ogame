# --- Extrae metadatos del jugador / planeta ---
extract_meta_script = """
(function() {
    const metas = document.getElementsByTagName('meta');
    let data = {};
    for (let m of metas) if (m.name && m.content) data[m.name] = m.content;
    return data;
})();
"""

detect_production_script = """
    (function() {
        return {
            building_present: !!document.querySelector('#productionboxbuildingcomponent'),
            building: !!document.querySelector('#productionboxbuildingcomponent .construction.active'),

            research_present: !!document.querySelector('#productionboxresearchcomponent'),
            research: !!document.querySelector('#productionboxresearchcomponent .construction.active'),

            lf_building_present: !!document.querySelector('#productionboxlfbuildingcomponent'),
            lf_building: !!document.querySelector('#productionboxlfbuildingcomponent .construction.active'),

            lf_research_present: !!document.querySelector('#productionboxlfresearchcomponent'),
            lf_research: !!document.querySelector('#productionboxlfresearchcomponent .construction.active'),

            shipyard_present: !!document.querySelector('#productionboxshipyardcomponent'),
            shipyard: !!document.querySelector('#productionboxshipyardcomponent .construction.active')
        };
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

tech_scrapper = """
(function() {
    let techs = [];
    let contentDiv = document.querySelector('div.content.technologies');
    if (!contentDiv) return [];
    let uls = contentDiv.querySelectorAll('ul');
    uls.forEach((ul) => {
        let h1 = null;
        let el = ul.previousElementSibling;
        while (el && el.tagName !== 'H1') el = el.previousElementSibling;
        let category = el ? el.textContent.trim() : '';
        
        ul.querySelectorAll('li').forEach(li => {
            let a = li.querySelector('a.technology');
            if (a) {
                let href = a.getAttribute('href') || '';
                let id = null;
                if (href.includes('technologyId=')) {
                    id = parseInt(href.split('technologyId=')[1].split('&')[0]);
                }
                techs.push({
                    name: a.textContent.trim(),
                    technologyId: id,
                    category: category,
                    href: href,
                    info: ''
                });
            }
        });
    });
    return techs;
})();
"""

lf_tech_scrapper = """
(function() {
    let container = document.querySelector('#technologies');
    if (!container) return [];
    let out = [];
    let items = container.querySelectorAll('div.lfsettingsContent');
    items.forEach((el, idx) => {
        let lfNameEl = el.querySelector('h3');
        let lfName = lfNameEl ? lfNameEl.textContent.trim() : ('lifeform-'+idx);
        let buildings = [];
        let researches = [];
        // buscar bloques que contengan technologyInfo
        let blocks = el.querySelectorAll('div');
        blocks.forEach(block => {
            let cat = block.getAttribute('data-category') || '';
            if (!cat) return;
            // find technologyInfo inside
            block.querySelectorAll('div.technologyInfo').forEach(ti => {
                let tnameEl = ti.querySelector('.technologyName');
                let tname = tnameEl ? tnameEl.textContent.trim() : '';
                let btn = ti.querySelector('button[data-target]');
                let href = btn ? btn.getAttribute('data-target') : '';
                let id = null;
                if (href && href.indexOf('technologyId=') !== -1) {
                    try { id = parseInt(href.split('technologyId=')[1].split('&')[0]); } catch(e) { id = null; }
                }
                let entry = { name: tname, technologyId: id, href: href, info: '' };
                if (cat.startsWith('buildingLifeform')) buildings.push(entry);
                if (cat.startsWith('researchLifeform')) researches.push(entry);
            });
        });
        out.push({ name: lfName, buildings: buildings, researches: researches });
    });
    return out;
})();
"""

get_info = """
                (function() {
                    let info = '';
                    let ps = document.querySelectorAll('p');
                    for (let p of ps) {
                        let t = p.textContent.trim();
                        if (t.length > 100) {
                            info = t;
                            break;
                        }
                    }
                    return info;
                })();
                """