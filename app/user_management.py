import logging
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
                               QComboBox, QFormLayout, QMessageBox, QListWidget, QAbstractItemView)
from PySide6.QtCore import Qt
from backend.database import Database

class UserManagementDialog(QDialog):
    def __init__(self, parent, conn, current_user):
        super().__init__(parent)
        self.conn = conn
        self.db = Database()
        self.current_user = current_user
        self.devices = ["door1", "camera1", "speakers"]  # List of available devices
        self.setWindowTitle("Manage Users")
        self.setMinimumSize(400, 500)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Form for adding/editing users
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(10)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Enter User ID")
        form_layout.addRow("User ID:", self.user_input)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("Enter PIN")
        form_layout.addRow("PIN:", self.pin_input)

        # Multi-select list for device permissions
        self.device_permissions = QListWidget()
        self.device_permissions.setSelectionMode(QAbstractItemView.MultiSelection)
        for device in self.devices:
            self.device_permissions.addItem(device)
        form_layout.addRow("Device Permissions:", self.device_permissions)

        layout.addLayout(form_layout)

        # Buttons for actions
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add User")
        self.add_button.clicked.connect(self.add_user)
        button_layout.addWidget(self.add_button)

        self.update_button = QPushButton("Update User")
        self.update_button.clicked.connect(self.update_user)
        button_layout.addWidget(self.update_button)

        self.delete_button = QPushButton("Delete User")
        self.delete_button.clicked.connect(self.delete_user)
        button_layout.addWidget(self.delete_button)

        layout.addLayout(button_layout)

        # List of existing users
        self.user_list = QListWidget()
        self.user_list.itemClicked.connect(self.load_user_data)
        layout.addWidget(self.user_list)

        self.load_users()

    def load_users(self):
        self.user_list.clear()
        users = self.db.get_all_users()
        for user in users:
            user_id, _, permissions = user
            permissions_list = self.db.get_user_permissions(user_id)
            self.user_list.addItem(f"{user_id} (Permissions: {', '.join(permissions_list)})")

    def load_user_data(self, item):
        user_id = item.text().split(" ")[0]
        user_data = self.db.get_user(user_id)
        if user_data:
            _, pin, permissions = user_data
            self.user_input.setText(user_id)
            self.pin_input.setText(pin)
            permissions_list = self.db.get_user_permissions(user_id)
            self.device_permissions.clearSelection()
            for i in range(self.device_permissions.count()):
                device_item = self.device_permissions.item(i)
                if device_item.text() in permissions_list:
                    device_item.setSelected(True)

    def add_user(self):
        user_id = self.user_input.text().strip()
        pin = self.pin_input.text().strip()
        selected_devices = [item.text() for item in self.device_permissions.selectedItems()]

        if not user_id or not pin:
            QMessageBox.warning(self, "Input Error", "User ID and PIN are required!")
            return

        if not selected_devices:
            QMessageBox.warning(self, "Input Error", "Please select at least one device permission!")
            return

        if self.db.add_user(user_id, pin, selected_devices):
            QMessageBox.information(self, "Success", f"User {user_id} added successfully!")
            self.load_users()
            self.clear_inputs()
        else:
            QMessageBox.warning(self, "Error", f"User {user_id} already exists!")

    def update_user(self):
        user_id = self.user_input.text().strip()
        pin = self.pin_input.text().strip()
        selected_devices = [item.text() for item in self.device_permissions.selectedItems()]

        if not user_id or not pin:
            QMessageBox.warning(self, "Input Error", "User ID and PIN are required!")
            return

        if not selected_devices:
            QMessageBox.warning(self, "Input Error", "Please select at least one device permission!")
            return

        if user_id == "master_user" and self.current_user != "master_user":
            QMessageBox.warning(self, "Access Denied", "Only master_user can update their own details!")
            return

        if self.db.update_user(user_id, pin, selected_devices):
            QMessageBox.information(self, "Success", f"User {user_id} updated successfully!")
            self.load_users()
            self.clear_inputs()
        else:
            QMessageBox.warning(self, "Error", f"User {user_id} not found!")

    def delete_user(self):
        user_id = self.user_input.text().strip()
        if not user_id:
            QMessageBox.warning(self, "Input Error", "Please select a user to delete!")
            return

        if user_id == "master_user":
            QMessageBox.warning(self, "Access Denied", "Cannot delete master_user!")
            return

        if self.db.delete_user(user_id):
            QMessageBox.information(self, "Success", f"User {user_id} deleted successfully!")
            self.load_users()
            self.clear_inputs()
        else:
            QMessageBox.warning(self, "Error", f"User {user_id} not found!")

    def clear_inputs(self):
        self.user_input.clear()
        self.pin_input.clear()
        self.device_permissions.clearSelection()