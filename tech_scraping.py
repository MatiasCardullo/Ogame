import json
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, QTimer
from custom_page import CustomWebPage
from js_scripts import get_info, tech_scrapper, lf_tech_scrapper

def scrap_tech_tree(profile):#self.page.profile()
    """Abre ventana separada y scrapeá tecnologías con QWebEngineView"""
    
    scrap_win = QMainWindow()
    scrap_win.setWindowTitle("Scraping...")
    scrap_win.resize(1200, 700)
    
    scrap_web = QWebEngineView()
    scrap_web.setPage(CustomWebPage(profile, scrap_web))
    
    scrap_win.setCentralWidget(scrap_web)
    scrap_win.show()
    
    url = "https://s163-ar.ogame.gameforge.com/game/index.php?page=ajax&component=technologytree&ajax=1&technologyId=1&tab=3"
    scrap_web.load(QUrl(url))
    
    tech_list = []
    scraping_state = {'idx': 0}
    on_loaded_connection = None
    
    def extract_techs():
        scrap_web.page().runJavaScript(tech_scrapper, process_techs)
    
    def process_techs(techs):
        nonlocal tech_list
        tech_list = techs if techs else []
        print(f"Encontradas {len(tech_list)} tecnologías")
        # Desconectar extract_techs para que no se ejecute de nuevo
        scrap_web.loadFinished.disconnect(extract_techs)
        if tech_list:
            scraping_state['idx'] = 0
            fetch_next_info()
        else:
            scrap_win.close()
    
    def fetch_next_info():
        nonlocal on_loaded_connection
        
        idx = scraping_state['idx']
        if idx >= len(tech_list):
            with open("technologies_data.json", "w", encoding="utf-8") as f:
                json.dump(tech_list, f, ensure_ascii=False, indent=2)
            print("✅ Datos guardados en technologies_data.json")
            scrap_win.close()
            return
        
        tech = tech_list[idx]
        print(f"{idx+1}/{len(tech_list)}: {tech['name']}")
        url_info = f"https://s163-ar.ogame.gameforge.com/game/index.php?page=ajax&component=technologytree&ajax=1&technologyId={tech['technologyId']}&tab=2"
        
        # Desconectar conexión anterior si existe
        if on_loaded_connection is not None:
            try:
                scrap_web.loadFinished.disconnect(on_loaded_connection)
            except:
                pass
        
        # Nueva conexión
        def on_loaded():
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(300, extract_info)
        
        def extract_info():
            scrap_web.page().runJavaScript(get_info, got_info)
        
        def got_info(info):
            if scraping_state['idx'] < len(tech_list):
                tech_list[scraping_state['idx']]['info'] = info or ''
            scraping_state['idx'] += 1
            fetch_next_info()
        
        on_loaded_connection = on_loaded
        scrap_web.loadFinished.connect(on_loaded)
        scrap_web.load(QUrl(url_info))
    
    scrap_web.loadFinished.connect(extract_techs)

def scrap_lifeforms(profile):#self.page.profile()
    """Scrapea edificios y tecnologías de las formas de vida y guarda JSON."""

    scrap_win = QMainWindow()
    scrap_win.setWindowTitle("Scraping Formas de Vida...")
    scrap_win.resize(1200, 700)

    scrap_web = QWebEngineView()
    scrap_web.setPage(CustomWebPage(profile, scrap_web))

    scrap_win.setCentralWidget(scrap_web)
    scrap_win.show()

    url = "https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame&component=lfsettings"
    scrap_web.load(QUrl(url))

    # Estado
    lf_list = []
    flat_list = []
    on_loaded_connection = None

    def extract_lifeforms():
        scrap_web.page().runJavaScript(lf_tech_scrapper, process_lifeforms)

    def process_lifeforms(data):
        nonlocal lf_list, flat_list
        lf_list = data or []
        print(f"Encontradas {len(lf_list)} formas de vida")
        # desconectar para que no se ejecute otra vez
        try:
            scrap_web.loadFinished.disconnect(extract_lifeforms)
        except Exception:
            pass

        # preparar flat_list para iteración secuencial
        flat_list = []
        for lf_idx, lf in enumerate(lf_list):
            for typ in ('buildings', 'researches'):
                items = lf.get(typ, []) or []
                for item_idx, it in enumerate(items):
                    flat_list.append({
                        'lf_idx': lf_idx,
                        'type': typ,
                        'item_idx': item_idx,
                        'name': it.get('name',''),
                        'technologyId': it.get('technologyId'),
                        'href': it.get('href',''),
                        'info': ''
                    })

        if flat_list:
            # iniciar iteración
            fetch_next(0)
        else:
            # guardar aunque esté vacío
            with open('lifeforms_data.json', 'w', encoding='utf-8') as f:
                json.dump(lf_list, f, ensure_ascii=False, indent=2)
            print('✅ lifeforms_data.json guardado (vacío)')
            scrap_win.close()

    def fetch_next(idx):
        nonlocal on_loaded_connection
        if idx >= len(flat_list):
            # asignar infos de vuelta a lf_list ya que hemos ido rellenando flat_list
            for entry in flat_list:
                lf_idx = entry['lf_idx']
                typ = entry['type']
                item_idx = entry['item_idx']
                lf_list[lf_idx][typ][item_idx]['info'] = entry.get('info','')

            with open('lifeforms_data.json', 'w', encoding='utf-8') as f:
                json.dump(lf_list, f, ensure_ascii=False, indent=2)
            print('✅ lifeforms_data.json guardado')
            scrap_win.close()
            return

        entry = flat_list[idx]
        href = entry.get('href','')
        print(f"{idx+1}/{len(flat_list)}: {entry.get('name','(sin nombre)')}")

        # disconnect previous handler
        if on_loaded_connection is not None:
            try:
                scrap_web.loadFinished.disconnect(on_loaded_connection)
            except Exception:
                pass

        def on_loaded():
            QTimer.singleShot(300, extract_info)

        def extract_info():
            scrap_web.page().runJavaScript(get_info, lambda info: got_info(info, idx))

        def got_info(info, current_idx):
            # asignar info en flat_list
            flat_list[current_idx]['info'] = info or ''
            # continuar con siguiente
            fetch_next(current_idx+1)

        on_loaded_connection = on_loaded
        scrap_web.loadFinished.connect(on_loaded)
        # si href está vacío, saltar
        if not href:
            flat_list[idx]['info'] = ''
            fetch_next(idx+1)
        else:
            scrap_web.load(QUrl(href))

    scrap_web.loadFinished.connect(extract_lifeforms)

