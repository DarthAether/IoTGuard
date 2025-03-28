import sqlite3
import logging
import json

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('resources/users.db')
        self.create_tables()
        self.initialize_default_users()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                pin TEXT NOT NULL,
                device_permissions TEXT NOT NULL  -- JSON string of permitted devices
            )
        ''')
        self.conn.commit()
        logging.info("Database tables created successfully")

    def initialize_default_users(self):
        cursor = self.conn.cursor()
        # Check if master_user exists, if not, create it with permissions for all devices
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", ("master_user",))
        if not cursor.fetchone():
            default_permissions = json.dumps(["door1", "camera1", "speakers"])  # All devices
            cursor.execute(
                "INSERT INTO users (user_id, pin, device_permissions) VALUES (?, ?, ?)",
                ("master_user", "1234", default_permissions)
            )
            self.conn.commit()
            logging.info("Default master_user created with full device permissions")

    def validate_user(self, user_id: str, pin: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT user_id FROM users WHERE user_id = ? AND pin = ?",
            (user_id, pin)
        )
        result = cursor.fetchone()
        return result is not None

    def get_user(self, user_id: str) -> tuple:
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, pin, device_permissions FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

    def add_user(self, user_id: str, pin: str, device_permissions: list) -> bool:
        cursor = self.conn.cursor()
        try:
            permissions_json = json.dumps(device_permissions)
            cursor.execute(
                "INSERT INTO users (user_id, pin, device_permissions) VALUES (?, ?, ?)",
                (user_id, pin, permissions_json)
            )
            self.conn.commit()
            logging.info(f"User {user_id} added with permissions: {device_permissions}")
            return True
        except sqlite3.IntegrityError:
            logging.warning(f"Failed to add user {user_id}: User ID already exists")
            return False

    def update_user(self, user_id: str, pin: str, device_permissions: list) -> bool:
        cursor = self.conn.cursor()
        permissions_json = json.dumps(device_permissions)
        cursor.execute(
            "UPDATE users SET pin = ?, device_permissions = ? WHERE user_id = ?",
            (pin, permissions_json, user_id)
        )
        self.conn.commit()
        logging.info(f"User {user_id} updated with new pin and permissions: {device_permissions}")
        return True

    def delete_user(self, user_id: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        self.conn.commit()
        logging.info(f"User {user_id} deleted")
        return True

    def get_all_users(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, pin, device_permissions FROM users")
        return cursor.fetchall()

    def get_user_permissions(self, user_id: str) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT device_permissions FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result:
            return json.loads(result[0])
        return []