import mysql.connector
from mysql.connector import Error
from config import Config


# ── Connection ─────────────────────────────────────────────────────────────────
def get_connection():
    try:
        conn = mysql.connector.connect(
            host     = Config.DB_HOST,
            user     = Config.DB_USER,
            password = Config.DB_PASSWORD,
            database = Config.DB_NAME
        )
        return conn
    except Error as e:
        print(f"[DB] Connection error: {e}")
        return None


# ── Init: create DB + all tables ───────────────────────────────────────────────
def init_db():
    try:
        conn = mysql.connector.connect(
            host     = Config.DB_HOST,
            user     = Config.DB_USER,
            password = Config.DB_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME}")
        cursor.execute(f"USE {Config.DB_NAME}")

        # ── users ──────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                full_name       VARCHAR(100) NOT NULL,
                username        VARCHAR(50)  NOT NULL UNIQUE,
                email           VARCHAR(100) NOT NULL UNIQUE,
                password_hash   VARCHAR(255) NOT NULL,
                role            ENUM('admin','analyst','viewer') DEFAULT 'analyst',
                is_active       BOOLEAN      DEFAULT TRUE,
                created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
                last_login      DATETIME     NULL,
                login_count     INT          DEFAULT 0,
                total_analysed  INT          DEFAULT 0
            )
        """)

        # ── login_logs ─────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS login_logs (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                user_id     INT          NOT NULL,
                username    VARCHAR(50),
                login_time  DATETIME     DEFAULT CURRENT_TIMESTAMP,
                ip_address  VARCHAR(45),
                status      ENUM('success','failed') DEFAULT 'success',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # ── transactions ───────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id                  INT AUTO_INCREMENT PRIMARY KEY,
                transaction_id      VARCHAR(30)    NOT NULL UNIQUE,
                user_id             VARCHAR(10),
                analysed_by         VARCHAR(50),
                timestamp           DATETIME,
                amount              DECIMAL(12,2),
                merchant            VARCHAR(100),
                location            VARCHAR(100),
                device              VARCHAR(50),
                payment_method      VARCHAR(50),
                hour_of_day         INT,
                day_of_week         INT,
                failed_attempts     INT            DEFAULT 0,
                txn_velocity        INT            DEFAULT 1,
                account_age_days    INT,
                avg_user_amount     DECIMAL(12,2),
                amount_deviation    DECIMAL(10,4),
                is_foreign_location TINYINT(1)     DEFAULT 0,
                is_unusual_device   TINYINT(1)     DEFAULT 0,
                is_fraud            TINYINT(1)     DEFAULT 0,
                risk_score          DECIMAL(5,2),
                risk_level          ENUM('LOW','MEDIUM','HIGH','CRITICAL') DEFAULT 'LOW',
                recommended_action  VARCHAR(20),
                created_at          DATETIME       DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ── alerts ─────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id             INT AUTO_INCREMENT PRIMARY KEY,
                transaction_id VARCHAR(30),
                risk_score     DECIMAL(5,2),
                risk_level     VARCHAR(10),
                action         VARCHAR(20),
                sms_message    TEXT,
                email_subject  VARCHAR(255),
                email_body     TEXT,
                alert_time     DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_sent        BOOLEAN  DEFAULT FALSE,
                FOREIGN KEY (transaction_id)
                    REFERENCES transactions(transaction_id)
                    ON DELETE CASCADE
            )
        """)

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database initialised successfully.")
        return True
    except Error as e:
        print(f"❌ DB init error: {e}")
        return False


# ══════════════════════════════════════════════════════
#  USER AUTH
# ══════════════════════════════════════════════════════

def get_user_by_username(username: str):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM users WHERE username=%s AND is_active=TRUE",
            (username,)
        )
        return cur.fetchone()
    except Error as e:
        print(f"[DB] get_user_by_username: {e}")
        return None
    finally:
        cur.close(); conn.close()


def get_user_by_email(email: str):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        return cur.fetchone()
    except Error:
        return None
    finally:
        cur.close(); conn.close()


def create_user(full_name, username, email, password_hash, role="analyst") -> bool:
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (full_name, username, email, password_hash, role)
            VALUES (%s,%s,%s,%s,%s)
        """, (full_name, username, email, password_hash, role))
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] create_user: {e}")
        return False
    finally:
        cur.close(); conn.close()


def update_last_login(username: str, ip: str = ""):
    """Update last_login, increment login_count, and write a login log."""
    conn = get_connection()
    if not conn:
        return
    try:
        cur = conn.cursor(dictionary=True)
        # Get user id
        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        row = cur.fetchone()
        if not row:
            return
        uid = row["id"]
        # Update user record
        cur.execute("""
            UPDATE users
            SET last_login=NOW(), login_count=login_count+1
            WHERE id=%s
        """, (uid,))
        # Insert login log
        cur.execute("""
            INSERT INTO login_logs (user_id, username, ip_address, status)
            VALUES (%s,%s,%s,'success')
        """, (uid, username, ip or "unknown"))
        conn.commit()
    except Error as e:
        print(f"[DB] update_last_login: {e}")
    finally:
        cur.close(); conn.close()


def log_failed_login(username: str, ip: str = ""):
    """Record a failed login attempt (username may not exist)."""
    conn = get_connection()
    if not conn:
        return
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id FROM users WHERE username=%s", (username,))
        row = cur.fetchone()
        uid = row["id"] if row else 0
        if uid:
            cur.execute("""
                INSERT INTO login_logs (user_id, username, ip_address, status)
                VALUES (%s,%s,%s,'failed')
            """, (uid, username, ip or "unknown"))
            conn.commit()
    except Error:
        pass
    finally:
        cur.close(); conn.close()


def get_user_stats(username: str) -> dict:
    """Return per-user stats: total analysed, login count, last login."""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT full_name, role, login_count, total_analysed,
                   last_login, created_at
            FROM users WHERE username=%s
        """, (username,))
        row = cur.fetchone() or {}
        # Count transactions analysed by this user
        cur.execute("""
            SELECT COUNT(*) AS cnt FROM transactions
            WHERE analysed_by=%s
        """, (username,))
        txn_row = cur.fetchone()
        row["analysed_count"] = txn_row["cnt"] if txn_row else 0
        return row
    except Error as e:
        print(f"[DB] get_user_stats: {e}")
        return {}
    finally:
        cur.close(); conn.close()


def get_all_users() -> list:
    """Admin: list all users with their transaction counts."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id, u.full_name, u.username, u.email, u.role,
                   u.is_active, u.login_count, u.total_analysed,
                   u.last_login, u.created_at,
                   COUNT(t.id) AS txn_count
            FROM users u
            LEFT JOIN transactions t ON t.analysed_by = u.username
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """)
        return cur.fetchall()
    except Error as e:
        print(f"[DB] get_all_users: {e}")
        return []
    finally:
        cur.close(); conn.close()


# ══════════════════════════════════════════════════════
#  TRANSACTIONS
# ══════════════════════════════════════════════════════

def insert_transaction(txn: dict, analysed_by: str = "") -> bool:
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT IGNORE INTO transactions
            (transaction_id, user_id, analysed_by, timestamp, amount,
             merchant, location, device, payment_method,
             hour_of_day, day_of_week, failed_attempts, txn_velocity,
             account_age_days, avg_user_amount, amount_deviation,
             is_foreign_location, is_unusual_device, is_fraud,
             risk_score, risk_level, recommended_action)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            txn.get("transaction_id"), txn.get("user_id"),
            analysed_by,               txn.get("timestamp"),
            txn.get("amount"),         txn.get("merchant"),
            txn.get("location"),       txn.get("device"),
            txn.get("payment_method"), txn.get("hour_of_day"),
            txn.get("day_of_week"),    txn.get("failed_attempts"),
            txn.get("txn_velocity"),   txn.get("account_age_days"),
            txn.get("avg_user_amount"),txn.get("amount_deviation"),
            txn.get("is_foreign_location"), txn.get("is_unusual_device"),
            txn.get("is_fraud"),       txn.get("risk_score"),
            txn.get("risk_level"),     txn.get("recommended_action"),
        ))
        # Increment user's total_analysed counter
        if analysed_by:
            cur.execute("""
                UPDATE users SET total_analysed=total_analysed+1
                WHERE username=%s
            """, (analysed_by,))
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] insert_transaction: {e}")
        return False
    finally:
        cur.close(); conn.close()


def insert_alert(alert: dict) -> bool:
    conn = get_connection()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO alerts
            (transaction_id, risk_score, risk_level, action,
             sms_message, email_subject, email_body)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            alert.get("transaction_id"), alert.get("risk_score"),
            alert.get("risk_level"),     alert.get("action"),
            alert.get("sms_message"),    alert.get("email_subject"),
            alert.get("email_body"),
        ))
        conn.commit()
        return True
    except Error as e:
        print(f"[DB] insert_alert: {e}")
        return False
    finally:
        cur.close(); conn.close()


def load_transactions_from_db(limit=500, level=None, analysed_by=None):
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        where, params = [], []
        if level:
            where.append("risk_level=%s"); params.append(level.upper())
        if analysed_by:
            where.append("analysed_by=%s"); params.append(analysed_by)
        sql  = "SELECT * FROM transactions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY created_at DESC LIMIT {int(limit)}"
        cur.execute(sql, params)
        return cur.fetchall()
    except Error as e:
        print(f"[DB] load_transactions: {e}")
        return []
    finally:
        cur.close(); conn.close()


# ══════════════════════════════════════════════════════
#  STATS
# ══════════════════════════════════════════════════════

def get_db_stats() -> dict:
    """Global stats across all transactions."""
    conn = get_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT
                COUNT(*)                     AS total,
                COALESCE(SUM(is_fraud),0)    AS fraud,
                COALESCE(SUM(risk_level='CRITICAL'),0) AS critical,
                COALESCE(SUM(risk_level='HIGH'),0)     AS high,
                COALESCE(SUM(risk_level='MEDIUM'),0)   AS medium,
                COALESCE(SUM(risk_level='LOW'),0)      AS low,
                COALESCE(ROUND(AVG(risk_score),2),0)   AS avg_risk,
                COUNT(DISTINCT analysed_by)            AS total_users
            FROM transactions
        """)
        return cur.fetchone() or {}
    except Error as e:
        print(f"[DB] get_db_stats: {e}")
        return {}
    finally:
        cur.close(); conn.close()


def get_transaction_count_by_user() -> list:
    """Per-user transaction count — for admin dashboard."""
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT analysed_by AS username,
                   COUNT(*)              AS total,
                   SUM(is_fraud)         AS fraud_found,
                   SUM(risk_level='CRITICAL') AS critical,
                   SUM(risk_level='HIGH')     AS high,
                   ROUND(AVG(risk_score),1)   AS avg_score
            FROM transactions
            WHERE analysed_by IS NOT NULL AND analysed_by != ''
            GROUP BY analysed_by
            ORDER BY total DESC
        """)
        return cur.fetchall()
    except Error as e:
        print(f"[DB] get_txn_count_by_user: {e}")
        return []
    finally:
        cur.close(); conn.close()


def get_recent_login_logs(limit=20) -> list:
    conn = get_connection()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT username, login_time, ip_address, status
            FROM login_logs
            ORDER BY login_time DESC
            LIMIT %s
        """, (limit,))
        return cur.fetchall()
    except Error as e:
        print(f"[DB] get_recent_login_logs: {e}")
        return []
    finally:
        cur.close(); conn.close()
