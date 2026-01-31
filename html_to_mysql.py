import json
from tkinter import NO
import mysql.connector, os
from pathlib import Path
from bs4 import BeautifulSoup
from tqdm import tqdm
from db_init import init_database
from concurrent.futures import ThreadPoolExecutor, as_completed


# ───────── CONFIG ─────────


HTML_FOLDER = Path("messages_log")

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "22Mayo97.",
    "database": "ogame167",
}

def get_conn():
    return mysql.connector.connect(
        **MYSQL_CONFIG,
        autocommit=True
    )


def parse_base_message(msg):
    raw = msg.select_one(".rawMessageData")
    if not raw:
        print(f"not raw in message: {msg:25s}")
        return None
    return {
        "id": int(msg["data-msg-id"]),
        "msg_type": int(raw.get("data-raw-messagetype", 0)),
        "title": msg.select_one(".msgTitle").get_text(" ", strip=True),
        "sender": msg.select_one(".msgSender").get_text(strip=True),
        "date_str": msg.select_one(".msgDate").get_text(strip=True),
        "timestamp": int(raw.get("data-raw-timestamp", 0)),
        "raw": raw
    }

def insert_message(cur, base):
    cur.execute("""
        INSERT IGNORE INTO messages
        (id, msg_type, title, sender, date_str, timestamp)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        base["id"],
        base["msg_type"],
        base["title"],
        base["sender"],
        base["date_str"],
        base["timestamp"]
    ))

def insert_espionage(cur, base):
    r = base["raw"]
    characterclass = r.get("data-raw-characterclass")
    if isinstance(characterclass, dict):
        characterclass = json.dumps(characterclass) 
    else:
        characterclass = None
    cur.execute("""
        INSERT IGNORE INTO espionage_reports (
            message_id, hashcode,
            buildings, lfbuildings, research, lfresearch,
            defense, fleet,
            characterclass,
            sourceplayerid, targetplayerid,
            sourceplanetid, targetplanetid,
            counterespionagechance
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        base["id"],
        r.get("data-raw-hashcode"),
        r.get("data-raw-buildings"),
        r.get("data-raw-lfbuildings"),
        r.get("data-raw-research"),
        r.get("data-raw-lfresearch"),
        r.get("data-raw-defense"),
        r.get("data-raw-fleet"),
        characterclass,
        r.get("data-raw-sourceplayerid"),
        r.get("data-raw-targetplayerid"),
        r.get("data-raw-sourceplanetid"),
        r.get("data-raw-targetplanetid"),
        r.get("data-raw-counterespionagechance")
    ))

def insert_combat(cur, base):
    r = base["raw"]
    cur.execute("""
        INSERT IGNORE INTO combat_reports (
            message_id, hashcode, coords,
            combatrounds, defenderspaceobject,
            fleets, result
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (
        base["id"],
        r.get("data-raw-hashcode"),
        r.get("data-raw-coords"),
        r.get("data-raw-combatrounds"),
        r.get("data-raw-defenderspaceobject"),
        r.get("data-raw-fleets"),
        r.get("data-raw-result")
    ))

def insert_debris(cur, base):
    r = base["raw"]
    cur.execute("""
        INSERT IGNORE INTO debris_reports (
            message_id, hashcode, coords,
            debrisresources, recycledresources,
            recycleramount, totalcapacity
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (
        base["id"],
        r.get("data-raw-hashcode"),
        r.get("data-raw-coords"),
        r.get("data-raw-debrisresources"),
        r.get("data-raw-recycledresources"),
        r.get("data-raw-recycleramount"),
        r.get("data-raw-totalcapacity")
    ))

def link_combat_exact(cur, timestamp, coords):
    cur.execute("""
        SELECT m.id
        FROM combat_reports c
        JOIN messages m ON m.id = c.message_id
        WHERE c.coords = %s
          AND m.timestamp = %s
        LIMIT 1
    """, (coords, timestamp))

    row = cur.fetchone()
    return row[0] if row else None

def insert_expedition(cur, base):
    r = base["raw"]
    result = r.get("data-raw-expeditionresult")

    extra_data = None

    if result == "shipwrecks":
        extra_data = r.get("data-raw-technologiesgained")

    elif result in ("ressources", "darkmatter"):
        extra_data = r.get("data-raw-resourcesgained")

    elif result == "navigation":
        extra_data = r.get("data-raw-navigation")

    elif result == "items":
        extra_data = r.get("data-raw-itemsgained")

    elif result == "trader":
        extra_data = r.get("data-raw-resources")

    elif result == "fleetLost":
        extra_data = r.get("data-raw-shipslost")

    combat_id = None
    if result in ("combatAliens", "combatPirates"):
        combat_id = link_combat_exact(
            cur,
            base["timestamp"],
            r.get("data-raw-coords")
        )

    cur.execute("""
        INSERT IGNORE INTO expedition_reports (
            message_id, timestamp, coords,
            expedition_result, extra_data,
            combat_message_id
        ) VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        base["id"],
        base["timestamp"],
        r.get("data-raw-coords"),
        result,
        extra_data,
        combat_id
    ))

def insert_lifeform(cur, base):
    r = base["raw"]
    dtype = r.get("data-raw-discoverytype")
    extra_data = None
    if dtype == "lifeform-xp":
        extra_data = {
            "lifeform": int(r.get("data-raw-lifeform")),
            "xp": int(r.get("data-raw-lifeformgainedexperience"))
        }
    elif dtype == "artifacts":
        extra_data = {
            "artifactsfound": int(r.get("data-raw-artifactsfound")),
            "artifactssize": r.get("data-raw-artifactssize")
        }
    extra_data = json.dumps(extra_data) if extra_data else None
    cur.execute("""
        INSERT IGNORE INTO lifeform_reports (
            message_id, timestamp, coords,
            discovery_type, extra_data
        ) VALUES (%s,%s,%s,%s,%s)
    """, (
        base["id"],
        base["timestamp"],
        r.get("data-raw-coords"),
        dtype,
        extra_data
    ))

def insert_specific(cur, base):
    t = base["msg_type"]
    if t == 0:
        insert_espionage(cur, base)
    elif t == 25:
        insert_combat(cur, base)
    elif t == 32:
        insert_debris(cur, base)
    elif t == 41:
        insert_expedition(cur, base)
    elif t == 61:
        insert_lifeform(cur, base)

def process_html_file(html_path):
    conn = get_conn()
    cur = conn.cursor()
    soup = BeautifulSoup(html_path.read_text(encoding="utf8"), "lxml")
    msgs = soup.select("div.msg[data-msg-id]")
    for msg in msgs:
        base = parse_base_message(msg)
        if not base:
            continue
        insert_message(cur, base)
        insert_specific(cur, base)
    cur.close()
    conn.close()

def main():
    #init_database()  # SOLO UNA VEZ
    html_files = list(HTML_FOLDER.rglob("*.html"))
    max_workers = os.cpu_count()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(process_html_file, html)
            for html in html_files
        ]
        for _ in tqdm(as_completed(futures),
                      total=len(futures),
                      desc="Procesando HTMLs",
                      unit="archivo"):
            pass
    print("✅ Importación completa")

if __name__ == "__main__":
    main()
