import mysql.connector

MYSQL_ROOT_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "22Mayo97."
}

DB_NAME = "ogame167"

def init_database():
    """
    Inicializa la base de datos ogame y todas sus tablas.
    Es seguro llamarla múltiples veces.
    """
    # 1️⃣ Conectar sin DB
    conn = mysql.connector.connect(**MYSQL_ROOT_CONFIG)
    cur = conn.cursor()

    # 2️⃣ Crear DB si no existe
    cur.execute(f"""
        CREATE DATABASE IF NOT EXISTS {DB_NAME}
        CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci
    """)

    cur.close()
    conn.close()

    # 3️⃣ Conectar a la DB ya creada
    conn = mysql.connector.connect(
        host=MYSQL_ROOT_CONFIG["host"],
        user=MYSQL_ROOT_CONFIG["user"],
        password=MYSQL_ROOT_CONFIG["password"],
        database=DB_NAME,
        autocommit=True
    )
    cur = conn.cursor()

    # 4️⃣ Crear tablas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INT PRIMARY KEY,
            msg_type INT NOT NULL,
            title VARCHAR(64),
            sender VARCHAR(64),
            date_str VARCHAR(64),
            timestamp INT,
            INDEX idx_msg_type (msg_type),
            INDEX idx_timestamp (timestamp)
        ) ENGINE=InnoDB
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS espionage_reports (
            message_id INT PRIMARY KEY,
            hashcode VARCHAR(64),
            buildings JSON,
            lfbuildings JSON,
            research JSON,
            lfresearch JSON,
            defense JSON,
            fleet JSON,
            characterclass JSON,
            sourceplayerid INT,
            targetplayerid INT,
            sourceplanetid INT,
            targetplanetid INT,
            counterespionagechance INT,
            FOREIGN KEY (message_id) REFERENCES messages(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS combat_reports (
            message_id INT PRIMARY KEY,
            hashcode VARCHAR(64),
            coords VARCHAR(16),
            combatrounds JSON,
            defenderspaceobject JSON,
            fleets JSON,
            result JSON,
            FOREIGN KEY (message_id) REFERENCES messages(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS debris_reports (
            message_id INT PRIMARY KEY,
            hashcode VARCHAR(64),
            coords VARCHAR(16),
            debrisresources JSON,
            recycledresources JSON,
            recycleramount INT,
            totalcapacity INT,
            FOREIGN KEY (message_id) REFERENCES messages(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)

    cur.execute("""
        CREATE TABLE expedition_reports (
            message_id INT PRIMARY KEY,
            timestamp INT NOT NULL,
            coords VARCHAR(16) NOT NULL,
            expedition_result ENUM(
                'nothing',
                'shipwrecks',
                'ressources',
                'darkmatter',
                'navigation',
                'combatAliens',
                'combatPirates',
                'items',
                'trader',
                'fleetLost'
            ) NOT NULL,
            extra_data JSON,
            combat_message_id INT,
            UNIQUE KEY uniq_expedition (timestamp, coords),
            FOREIGN KEY (message_id) REFERENCES messages(id)
                ON DELETE CASCADE,
            FOREIGN KEY (combat_message_id) REFERENCES messages(id)
                ON DELETE SET NULL
        ) ENGINE=InnoDB;
    """)

    cur.execute("""
        CREATE TABLE lifeform_reports (
            message_id INT PRIMARY KEY,
            timestamp INT NOT NULL,
            coords VARCHAR(16) NOT NULL,
            discovery_type ENUM(
                'ship-lost',
                'lifeform-xp',
                'artifacts'
            ) NOT NULL,
            extra_data JSON,
            UNIQUE KEY uniq_lifeform (timestamp, coords),
            FOREIGN KEY (message_id) REFERENCES messages(id)
                ON DELETE CASCADE
        ) ENGINE=InnoDB;
    """)

    cur.close()
    return conn
