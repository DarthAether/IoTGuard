import sqlite3
import logging
from backend.database import Database

class IoTBackend:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.db = Database()
        self.devices = {
            "door1": "locked",
            "camera1": "on",
            "speakers": "off"
        }
        logging.info("IoTBackend initialized with devices: %s", self.devices)

    def get_devices(self):
        return list(self.devices.keys())

    def execute_command(self, command: str, user_id: str, pin: str, device: str = None):
        logging.info(f"Executing command: {command} for user: {user_id} on device: {device}")
        
        # Validate user permissions for the device
        if device:
            user_permissions = self.db.get_user_permissions(user_id)
            if device not in user_permissions:
                logging.error(f"User {user_id} does not have permission to control device {device}")
                return f"Permission denied: You do not have access to device {device}"

        if device and device not in self.devices:
            logging.error(f"Device {device} not found")
            return f"Device {device} not found"

        # Simulate command execution
        if "unlock door" in command.lower() and (device == "door1" or not device):
            self.devices["door1"] = "unlocked"
            return "Door unlocked successfully"
        elif "lock door" in command.lower() and (device == "door1" or not device):
            self.devices["door1"] = "locked"
            return "Door locked successfully"
        elif "play music" in command.lower() and (device == "speakers" or not device):
            self.devices["speakers"] = "on"
            return "Music playing on speakers"
        elif "stop music" in command.lower() and (device == "speakers" or not device):
            self.devices["speakers"] = "off"
            return "Music stopped on speakers"
        else:
            logging.warning(f"Unsupported command: {command}")
            return "Unsupported command"