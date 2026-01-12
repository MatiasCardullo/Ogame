import os, random, time, json, requests, browser_cookie3, sys, traceback
import sqlite3
from tqdm import tqdm
from text import cantidad


# ─────────────────────────────
# Utils
# ─────────────────────────────

def close():
    print("\nCerrando en    ", end='')
    for i in range(5, 0, -1):
        print(f"\b\b{i} ", end='', flush=True)
        time.sleep(1)
    print("\r                ")
    sys.exit(1)


def load_ogame_session(profile_path):
    cj = browser_cookie3.chrome(
        cookie_file=f"{profile_path}/Cookies",
        domain_name="ogame.gameforge.com"
    )
    session = requests.Session()
    session.cookies.update(cj)
    session.headers.update({
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://s163-ar.ogame.gameforge.com/game/index.php?page=ingame&component=galaxy",
        "Origin": "https://s163-ar.ogame.gameforge.com",
    })
    return session


def ensure_logged_in(profile_name, galaxy=None, retry_wait=10):
    BASE_URL = "https://s163-ar.ogame.gameforge.com/game/index.php"
    while True:
        session = load_ogame_session(profile_name)
        try:
            r = session.get(f"{BASE_URL}?page=ingame&component=galaxy", timeout=10)
            if "component=galaxy" in r.text:
                if galaxy is not None:
                    print(f"\r[GALAXY {galaxy}] Logged          ")
                return session
        except Exception as e:
            print(f"\n[LOGIN] Error: {e}")

        if galaxy is not None:
            print(f"\r[GALAXY {galaxy}] Login...", end='', flush=True)
        time.sleep(retry_wait)


def parse_systems_arg(arg):
    if arg.isdigit():
        s = int(arg)
        return range(s, s + 1)

    if "-" in arg:
        a, b = arg.split("-", 1)
        if a.isdigit() and b.isdigit():
            return range(int(a), int(b) + 1)

    raise ValueError(f"Sistemas inválidos: '{arg}'")


# ─────────────────────────────
# DB
# ─────────────────────────────

def init_db(db_path="galaxy.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        galaxy INTEGER,
        system INTEGER,
        scanned_at REAL,
        success INTEGER
    );

    CREATE TABLE IF NOT EXISTS raw_response (
        scan_id INTEGER PRIMARY KEY,
        json TEXT
    );

    CREATE TABLE IF NOT EXISTS players (
        player_id INTEGER PRIMARY KEY,
        name TEXT,
        alliance_id INTEGER,
        alliance_tag TEXT,
        rank_position INTEGER,
        is_active INTEGER,
        is_inactive INTEGER,
        is_vacation INTEGER,
        is_banned INTEGER
    );

    CREATE TABLE IF NOT EXISTS planets (
        planet_id INTEGER PRIMARY KEY,
        galaxy INTEGER,
        system INTEGER,
        position INTEGER,
        type INTEGER,
        name TEXT,
        player_id INTEGER,
        size INTEGER,
        image TEXT,
        destroyed INTEGER,
        activity INTEGER,
        last_scan REAL
    );

    CREATE TABLE IF NOT EXISTS debris (
        galaxy INTEGER,
        system INTEGER,
        position INTEGER,
        metal INTEGER,
        crystal INTEGER,
        deuterium INTEGER,
        required_ships INTEGER,
        last_scan REAL,
        PRIMARY KEY (galaxy, system, position)
    );
    """)

    conn.commit()
    return conn


# ─────────────────────────────
# Galaxy Worker
# ─────────────────────────────

class GalaxyWorker:
    def __init__(self, galaxy, systems=None):
        self.galaxy = galaxy
        self.systems = systems or range(1, 500)

        self.PLANETS = 0
        self.MOONS = 0
        self.DEBRIS = 0
        self.METAL = 0
        self.CRYSTAL = 0
        self.DEUTERIUM = 0

    def parse_galaxy_response(self, text, conn, galaxy, system):
        cur = conn.cursor()
        now = time.time()

        text = text.strip()
        if not text.startswith("{"):
            return False

        data = json.loads(text)

        cur.execute("""
            INSERT INTO scans (galaxy, system, scanned_at, success)
            VALUES (?, ?, ?, 1)
        """, (galaxy, system, now))
        scan_id = cur.lastrowid

        cur.execute("""
            INSERT INTO raw_response (scan_id, json)
            VALUES (?, ?)
        """, (scan_id, text))

        galaxy_content = data.get("system", {}).get("galaxyContent", [])

        for row in galaxy_content:
            pos = row.get("position")
            if not pos:
                continue

            player = row.get("player")
            if player and "playerId" in player:
                cur.execute("""
                    INSERT OR IGNORE INTO players (
                        player_id, name, alliance_id, alliance_tag,
                        rank_position, is_active, is_inactive,
                        is_vacation, is_banned
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player["playerId"],
                    player.get("playerName"),
                    player.get("allianceId"),
                    player.get("allianceTag"),
                    player.get("highscorePositionPlayer"),
                    int(player.get("isActive", False)),
                    int(player.get("isInactive", False)),
                    int(player.get("isOnVacation", False)),
                    int(player.get("isBanned", False))
                ))

            planets = row.get("planets") or []
            if not isinstance(planets, list):
                planets = [planets]

            for body in planets:
                if not isinstance(body, dict):
                    continue

                ptype = body.get("planetType")

                # PLANETA
                if ptype == 1:
                    self.PLANETS += 1
                    cur.execute("""
                        INSERT OR REPLACE INTO planets (
                            planet_id, galaxy, system, position, type,
                            name, player_id, size, image,
                            destroyed, activity, last_scan
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        body.get("planetId"),
                        galaxy, system, pos, 1,
                        body.get("planetName"),
                        body.get("playerId"),
                        None,
                        body.get("imageInformation"),
                        int(body.get("isDestroyed", False)),
                        body.get("activity", {}).get("showActivity"),
                        now
                    ))

                # ESCOMBROS
                elif ptype == 2:
                    self.DEBRIS += 1
                    res = body.get("resources", {})
                    m = int(res.get("metal", {}).get("amount", 0))
                    c = int(res.get("crystal", {}).get("amount", 0))
                    d = int(res.get("deuterium", {}).get("amount", 0))

                    self.METAL += m
                    self.CRYSTAL += c
                    self.DEUTERIUM += d

                    cur.execute("""
                        INSERT OR REPLACE INTO debris (
                            galaxy, system, position,
                            metal, crystal, deuterium,
                            required_ships, last_scan
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        galaxy, system, pos,
                        m, c, d,
                        body.get("requiredShips"),
                        now
                    ))

                # LUNA
                elif ptype == 3:
                    self.MOONS += 1
                    cur.execute("""
                        INSERT OR REPLACE INTO planets (
                            planet_id, galaxy, system, position, type,
                            name, player_id, size, image,
                            destroyed, activity, last_scan
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        body.get("planetId"),
                        galaxy, system, pos, 3,
                        body.get("planetName"),
                        body.get("playerId"),
                        body.get("size"),
                        body.get("imageInformation"),
                        int(body.get("isDestroyed", False)),
                        body.get("activity", {}).get("showActivity"),
                        now
                    ))

        conn.commit()
        return True

    def run(self):
        BASE_URL = "https://s163-ar.ogame.gameforge.com/game/index.php"
        PARAMS = {
            "page": "ingame",
            "component": "galaxy",
            "action": "fetchGalaxyContent",
            "ajax": "1",
            "asJson": "1"
        }

        session = ensure_logged_in("profile_data", self.galaxy)
        conn = init_db("galaxy.db")

        size = os.get_terminal_size()
        pbar = tqdm(self.systems, desc=f"G{self.galaxy} escaneando", unit="sistema")
        status_one = tqdm(total=0, bar_format="{desc}", position=1)
        status_two = tqdm(total=0, bar_format="{desc}", position=2)

        for s in pbar:
            payload = {"galaxy": self.galaxy, "system": s}

            try:
                r = session.post(BASE_URL, params=PARAMS, data=payload, timeout=10)
                ok = self.parse_galaxy_response(r.text, conn, self.galaxy, s)

                if not ok:
                    session = ensure_logged_in("profile_data", self.galaxy)
                    continue

                status_one.set_description_str(
                    f"Sistema {s} | Planetas {self.PLANETS} | Lunas {self.MOONS}"
                )
                status_two.set_description_str(
                    f"Escombros {self.DEBRIS} "
                    f"M={cantidad(self.METAL)} "
                    f"C={cantidad(self.CRYSTAL)} "
                    f"D={cantidad(self.DEUTERIUM)}"
                )

                time.sleep(random.random())

            except Exception as e:
                tqdm.write(f"[ERROR] {self.galaxy}:{s} {e}")

        conn.close()


# ─────────────────────────────
# Main
# ─────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python galaxy_worker.py <galaxia>")
        print("  python galaxy_worker.py <galaxia> <sistema>")
        print("  python galaxy_worker.py <galaxia> <inicio-fin>")
        sys.exit(1)

    try:
        galaxy = int(sys.argv[1])
        systems = None

        if len(sys.argv) == 3:
            systems = parse_systems_arg(sys.argv[2])

        worker = GalaxyWorker(galaxy, systems)
        worker.run()
        close()

    except Exception as e:
        print(f"[GalaxyWorker] Error: {e}")
        traceback.print_exc()
        close()
