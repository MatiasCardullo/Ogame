from bs4 import BeautifulSoup
from pathlib import Path
import sqlite3
from tqdm import tqdm


HTML_FOLDER = Path("messages_log")
DB_PATH = Path("output/ogame_messages.db")

# ───────────────── DB ─────────────────

def init_db(conn):
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY,
        msg_type INTEGER,
        title TEXT,
        sender TEXT,
        date TEXT,
        timestamp INTEGER,
        source_coords TEXT,
        target_coords TEXT,
        content TEXT,
        cargo_json TEXT,
        combat_json TEXT,
        espionage_json TEXT,
        source_file TEXT
    );

    CREATE TABLE IF NOT EXISTS loot (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER,
        resource TEXT,
        amount INTEGER,
        FOREIGN KEY(message_id) REFERENCES messages(id)
    );

    CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
    CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(msg_type);
    """)

    conn.commit()

# ───────────────── Parsing helpers ─────────────────

def clean_text(tag):
    if not tag:
        return ""
    return "\n".join(
        line.strip()
        for line in tag.get_text("\n").splitlines()
        if line.strip()
    )

def parse_loot(msg):
    loot = []
    for item in msg.select(".loot-item"):
        name = item.select_one(".loot-name")
        amount = item.select_one(".amount")
        if name and amount:
            loot.append((
                name.text.strip(),
                int(amount.text.replace(".", ""))
            ))
    return loot

def parse_message(msg, source_file):
    raw = msg.select_one(".rawMessageData")
    if not raw:
        return None, []

    msg_id = int(msg["data-msg-id"])
    msg_type = int(raw.get("data-raw-messagetype", 0))

    cargo = raw.get("data-raw-cargo")
    combat = raw.get("data-raw-result")
    espionage = raw.get("data-raw-research") or raw.get("data-raw-fleet")

    message = (
        msg_id,
        msg_type,
        msg.select_one(".msgTitle").get_text(" ", strip=True),
        msg.select_one(".msgSender").text.strip(),
        msg.select_one(".msgDate").text.strip(),
        int(raw.get("data-raw-timestamp", 0)),
        raw.get("data-raw-sourceplanetcoordinates"),
        raw.get("data-raw-targetplanetcoordinates"),
        clean_text(msg.select_one(".msgContent")),
        cargo,
        combat,
        espionage,
        source_file
    )

    loot = parse_loot(msg)
    return message, loot

# ───────────────── Processing ─────────────────

def process_html(conn, html_path):
    soup = BeautifulSoup(html_path.read_text(encoding="utf8"), "lxml")
    cur = conn.cursor()

    msgs = soup.select("div.msg[data-msg-id]")
    for msg in tqdm(msgs, desc=html_path.name, leave=False):
        data, loot = parse_message(msg, html_path.name)
        if not data:
            continue

        cur.execute("""
        INSERT OR IGNORE INTO messages
        (id, msg_type, title, sender, date, timestamp,
         source_coords, target_coords, content,
         cargo_json, combat_json, espionage_json, source_file)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)

        for res, amount in loot:
            cur.execute("""
            INSERT INTO loot (message_id, resource, amount)
            VALUES (?, ?, ?)
            """, (data[0], res, amount))
    conn.commit()

def main():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    html_files = list(HTML_FOLDER.rglob("*.html"))

    for html in tqdm(html_files, desc="Procesando HTML", unit="archivo"):
        process_html(conn, html)

    conn.close()
    print("✅ Importación completa")

if __name__ == "__main__":
    main()
