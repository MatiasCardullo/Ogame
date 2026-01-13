from pyparsing import col
import os, random, time, json, requests, browser_cookie3, sys, traceback
import sqlite3
from tqdm import tqdm
from text import cantidad

TABLE_SCANS = [("id", 'INTEGER PRIMARY KEY AUTOINCREMENT'), ("galaxy", 'INTEGER'), ("system", 'INTEGER'), ("scanned_at", 'REAL'), ("success", 'INTEGER')]
TABLE_PLAYERS = [("player_id", 'INTEGER PRIMARY KEY'), ("name", 'TEXT'), ("alliance_id", 'INTEGER'), ("alliance_tag", 'TEXT'), ("rank_position", 'INTEGER'), ("is_active", 'INTEGER'), ("is_inactive", 'INTEGER'), ("is_vacation", 'INTEGER'), ("is_banned", 'INTEGER')]
TABLE_PLANETS = [("planet_id", 'INTEGER PRIMARY KEY'), ("name", 'TEXT'), ("player_id", 'INTEGER'), ("image", 'TEXT'), ("is_destroyed", 'INTEGER'), ("activity", 'INTEGER'), ("scan_id", 'INTEGER'), ("position", 'INTEGER'), ("moon_id", 'INTEGER'),
                  ("can_attack", 'INTEGER'), ("can_transport", 'INTEGER'), ("can_deploy", 'INTEGER'), ("can_hold", 'INTEGER'), ("can_espionage", 'INTEGER')]
TABLE_MOONS = [("moon_id", " INTEGER PRIMARY KEY"),("name"," TEXT"),("size"," INTEGER"),("image"," TEXT"),("is_destroyed"," INTEGER"),("activity"," INTEGER"),
               ("can_attack"," INTEGER"),("can_transport"," INTEGER"),("can_deploy"," INTEGER"),("can_hold"," INTEGER"),("can_espionage"," INTEGER"),("can_destroy"," INTEGER")]
TABLE_DEBRIS = [("scan_id", 'INTEGER'), ("position", 'INTEGER'), ("metal", 'INTEGER'), ("crystal", 'INTEGER'), ("deuterium", 'INTEGER'), ("required_ships", 'INTEGER')]

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

def parse_mission_flags(available):
    flags = {
        1: "can_attack",
        3: "can_transport",
        4: "can_deploy",
        5: "can_hold",
        6: "can_espionage",
        9: "can_destroy",
    }

    result = {v: 0 for v in flags.values()}

    for m in available or []:
        mt = m.get("missionType")
        if mt in flags:
            result[flags[mt]] = 1

    return result

def sql_insert_values(table_cols):
    return f" ({', '.join(col for col, _ in table_cols)}) VALUES ({', '.join(['?'] * len(table_cols))})"

def sql_create(table):
    return f" ({', '.join([f'{col} {type_}' for col, type_ in table])})"

# ─────────────────────────────
# DB
# ─────────────────────────────

def init_db(db_path="galaxy.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.executescript(
        f"CREATE TABLE IF NOT EXISTS scans ({sql_create(TABLE_SCANS)} UNIQUE (galaxy, system));"
        f"CREATE TABLE IF NOT EXISTS players ({sql_create(TABLE_PLAYERS)});"
        f"CREATE TABLE IF NOT EXISTS planets ({sql_create(TABLE_PLANETS)});"
        f"CREATE TABLE IF NOT EXISTS moons ({sql_create(TABLE_MOONS)});"
        f"CREATE TABLE IF NOT EXISTS debris ({sql_create(TABLE_DEBRIS)}, PRIMARY KEY (scan_id, position));"
        "CREATE TABLE IF NOT EXISTS images (image_name TEXT PRIMARY KEY, image_src TEXT);"       
        "CREATE TABLE IF NOT EXISTS missions (missionType INTEGER PRIMARY KEY, name TEXT, link TEXT);"
    )
    conn.commit()

    MISSIONS = [
        (0, "Reubicar", "prepareMove"),
        (1, "Atacar", "attack"),
        (2, "Ataque conjunto", "unionAttack"),
        (3, "Transportar", "transport"),
        (4, "Desplegar", "deploy"),
        (5, "Mantener posición", "hold"),
        (6, "Espionaje", "espionage"),
        (7, "Colonizar", "colonize"),
        (8, "Recolectar", "recycle"),
        (9, "Destruir", "destroy"),
        (10, "Misil", "missileAttack"),
        (15, "Expedicíon", "expedition"),
        (18, "Forma de vida", "discovery")
    ]

    cur.executemany("""
        INSERT OR IGNORE INTO missions (missionType, name, link)
        VALUES (?, ?, ?)
    """, MISSIONS)

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
        def image(name, src):
            if name and src:
                cur.execute("""
                    INSERT OR IGNORE INTO images (image_name, image_src)
                    VALUES (?, ?)
                """, (name, src))
        
        cur = conn.cursor()
        now = time.time()

        text = text.strip()
        if not text.startswith("{"):
            return False

        data = json.loads(text)

        cur.execute("""
            INSERT INTO scans (galaxy, system, scanned_at, success)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(galaxy, system)
            DO UPDATE SET
                scanned_at = excluded.scanned_at,
                success = 1
        """, (galaxy, system, now))

        cur.execute("""
            SELECT id FROM scans WHERE galaxy = ? AND system = ?
        """, (galaxy, system))
        scan_id = cur.fetchone()[0]

        galaxy_content = data.get("system", {}).get("galaxyContent", [])

        for row in galaxy_content:
            pos = row.get("position")
            if not pos:
                continue

            player = row.get("player")
            if player:
                pId = player.get("playerId", 0)
                if pId != 99999:
                    cur.execute(f"INSERT OR REPLACE INTO players {sql_insert_values(TABLE_PLAYERS)}", (
                        pId,
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

            moon_id = None
            for body in planets:
                if not isinstance(body, dict):
                    continue

                ptype = body.get("planetType")
                missions = body.get("availableMissions", [])
                flags = parse_mission_flags(missions)
                # ── PLANETA
                if ptype == 1:
                    self.PLANETS += 1
                    image_name = body.get("imageInformation")
                    image_src = body.get("imageSrc")
                    image(image_name, image_src)
                    cur.execute(f"INSERT OR REPLACE INTO planets {sql_insert_values(TABLE_PLANETS)}", (
                        body.get("planetId"),
                        body.get("planetName"),
                        body.get("playerId"),
                        image_name,
                        int(body.get("isDestroyed", False)),
                        body.get("activity", {}).get("showActivity"),
                        scan_id,
                        pos,
                        None,
                        flags["can_attack"],
                        flags["can_transport"],
                        flags["can_hold"],
                        flags["can_espionage"]
                    ))

                # ── LUNA
                elif ptype == 3:
                    self.MOONS += 1
                    image_name = body.get("imageInformation")
                    image_src = body.get("imageSrc")
                    image(image_name, image_src)
                    moon_id = body.get("planetId")
                    cur.execute("""
                        INSERT OR REPLACE INTO moons (
                            moon_id, name, size,
                            image, destroyed, activity,
                            can_attack, can_transport,
                            can_hold, can_espionage,
                            can_destroy
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        moon_id,
                        body.get("planetName"),
                        body.get("size"),
                        image_name,
                        int(body.get("isDestroyed", False)),
                        body.get("activity", {}).get("showActivity"),
                        flags["can_attack"],
                        flags["can_transport"],
                        flags["can_hold"],
                        flags["can_espionage"],
                        flags["can_destroy"]
                    ))

                # ── ESCOMBROS
                elif ptype == 2:
                    self.DEBRIS += 1
                    res = body.get("resources", {})
                    m = int(res.get("metal", {}).get("amount", 0))
                    c = int(res.get("crystal", {}).get("amount", 0))
                    d = int(res.get("deuterium", {}).get("amount", 0))
                    self.METAL += m
                    self.CRYSTAL += c
                    self.DEUTERIUM += d
                    cur.execute(f"INSERT OR REPLACE INTO debris {sql_insert_values(TABLE_DEBRIS)}", (
                        scan_id, pos,
                        m, c, d,
                        body.get("requiredShips")
                    ))
            
            # ── si hubo luna, vincularla al planeta del slot
            if moon_id:
                cur.execute("""
                    UPDATE planets
                    SET moon_id = ?
                    WHERE scan_id = ? AND planet_id IS NOT NULL
                """, (moon_id, scan_id))

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
        pbar = tqdm(self.systems, desc=f"G{self.galaxy} escaneando", unit="sistem", ncols=size.columns-2)
        status_one = tqdm(total=0, bar_format="{desc}", position=1, ncols=size.columns-2)
        status_two = tqdm(total=0, bar_format="{desc}", position=2, ncols=size.columns-2)
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
