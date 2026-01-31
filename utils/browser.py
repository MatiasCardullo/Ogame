import time
import requests
import browser_cookie3

def load_ogame_session(profile_path, server):
    """Carga una sesión de OGame usando las cookies del navegador."""
    base_url = "ogame.gameforge.com"
    cj = browser_cookie3.chrome(
        cookie_file=f"{profile_path}/Cookies",
        domain_name=base_url
    )
    session = requests.Session()
    session.cookies.update(cj)
    session.headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": f"https://{server}.{base_url}/game/index.php?page=ingame&component=galaxy",
        "Origin": "https://{server}.{base_url}",
    })
    return session

def ensure_logged_in(profile_path, server, url, retry_wait=10):
    """Verifica que se está logged in y retorna una sesión válida."""
    BASE_URL = f"https://{server}.ogame.gameforge.com/game/index.php"
    while True:
        session = load_ogame_session(profile_path, server)
        try:
            r = session.get(f"{BASE_URL}{url}", timeout=10)
            if "page=ingame" in r.text:
                print(f"\r Logged    ", end='')
                return session
        except Exception as e:
            print(f"\n[LOGIN] Error: {e}")

        print(f"\r Login...", end='')
        time.sleep(retry_wait)