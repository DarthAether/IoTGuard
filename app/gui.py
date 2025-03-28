import json
import time
import logging
from datetime import datetime
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
                              QTextBrowser, QLabel, QMessageBox, QComboBox, QFormLayout, QTreeWidget, 
                              QTreeWidgetItem, QSystemTrayIcon, QMenu, QApplication, QSizePolicy, QScrollArea, QGridLayout)
from PySide6.QtGui import QLinearGradient, QBrush, QPalette, QColor, QFont, QIcon
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QSize, QThreadPool, QTimer
from app.user_management import UserManagementDialog
from app.theme import set_theme, toggle_theme
from app.animations import setup_animations
from backend.iot_backend import IoTBackend
from backend.database import Database
from backend.gemini_worker import GeminiWorker
from utils.helpers import normalize_time_format, get_risk_icon, get_learn_more_message

class IoTGuardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IoTGuard - Smart Home Security")
        self.setMinimumSize(600, 700)
        self.is_dark_theme = True
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4)

        self.db = Database()
        self.iot = IoTBackend(self.db.conn)
        self.command_history = []
        self.command_cache = {}
        self.current_user = None

        self.setup_ui()
        self.setup_tray()
        self.load_history()
        set_theme(self)
        self.hide_loading()
        logging.info("GUI initialized successfully")

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        header_layout = QHBoxLayout()
        self.logo = QLabel("🔒 IoTGuard")
        self.logo.setFont(QFont("Arial", 24, QFont.Bold))
        header_layout.addWidget(self.logo)
        self.tagline = QLabel("Secure Your Smart Home")
        self.tagline.setFont(QFont("Arial", 14))
        header_layout.addWidget(self.tagline, stretch=1)
        self.theme_toggle = QPushButton("Toggle Theme")
        self.theme_toggle.clicked.connect(lambda: toggle_theme(self))
        self.theme_toggle.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        header_layout.addWidget(self.theme_toggle)
        scroll_layout.addLayout(header_layout)

        input_widget = QWidget()
        input_layout = QFormLayout(input_widget)
        input_layout.setVerticalSpacing(10)
        input_layout.setHorizontalSpacing(15)
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Enter User ID")
        self.user_input.setEnabled(True)
        self.user_input.setMinimumHeight(30)
        self.user_input.setMaximumWidth(300)
        self.user_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.user_input.setFocusPolicy(Qt.StrongFocus)
        input_layout.addRow("User ID:", self.user_input)
        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setEnabled(True)
        self.pin_input.setMinimumHeight(30)
        self.user_input.setMaximumWidth(300)
        self.pin_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.pin_input.setFocusPolicy(Qt.StrongFocus)
        input_layout.addRow("PIN:", self.pin_input)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["Select Device"] + self.iot.get_devices())
        self.device_combo.setEnabled(True)
        self.device_combo.setMinimumHeight(30)
        self.device_combo.setMaximumWidth(300)
        self.device_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.device_combo.setFocusPolicy(Qt.StrongFocus)
        input_layout.addRow("Device:", self.device_combo)
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter IoT command")
        self.command_input.setEnabled(True)
        self.command_input.setMinimumHeight(30)
        self.command_input.setMaximumWidth(300)
        self.command_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.command_input.setFocusPolicy(Qt.StrongFocus)
        input_layout.addRow("Command:", self.command_input)
        self.submit_button = QPushButton("Check Risks")
        self.submit_button.clicked.connect(self.on_submit)
        self.submit_button.setEnabled(True)
        self.submit_button.setMinimumHeight(40)
        self.submit_button.setMaximumWidth(150)
        self.submit_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        input_layout.addRow("", self.submit_button)
        scroll_layout.addWidget(input_widget)

        self.loading_label = QLabel("Analyzing...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setMinimumHeight(30)
        self.loading_label.setVisible(False)
        scroll_layout.addWidget(self.loading_label)

        rule_layout = QHBoxLayout()
        rule_label = QLabel("Set Security Rule:")
        rule_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.rules_combo = QComboBox()
        self.rules_combo.addItems([
            "Always require authentication for door commands",
            "Never disable cameras at night",
            "Block commands from unknown devices",
            "No rules"
        ])
        self.rules_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.rules_combo.setMaximumWidth(400)
        rule_layout.addWidget(rule_label)
        rule_layout.addWidget(self.rules_combo, stretch=1)
        scroll_layout.addLayout(rule_layout)

        status_widget = QWidget()
        status_layout = QGridLayout(status_widget)
        self.status_label = QLabel("Command Status:")
        self.status_icon = QLabel("🔵")
        self.device_status = QLabel("Device Status: " + self.update_device_status())
        self.device_status.setWordWrap(True)
        self.device_status.setMaximumWidth(400)
        status_layout.addWidget(self.status_label, 0, 0)
        status_layout.addWidget(self.status_icon, 0, 1)
        status_layout.addWidget(self.device_status, 1, 0, 1, 2)
        scroll_layout.addWidget(status_widget)

        self.result_text = QTextBrowser()
        self.result_text.setOpenLinks(False)
        self.result_text.anchorClicked.connect(self.on_learn_more_clicked)
        self.result_text.setMinimumHeight(150)
        self.result_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_text.setVisible(True)
        scroll_layout.addWidget(self.result_text, stretch=3)

        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabel("Command History")
        self.history_tree.setMinimumHeight(150)
        self.history_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll_layout.addWidget(self.history_tree, stretch=2)

        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText("Search history...")
        self.history_search.textChanged.connect(self.filter_history)
        self.history_search.setMinimumHeight(30)
        self.history_search.setMaximumWidth(400)
        self.history_search.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        scroll_layout.addWidget(self.history_search)

        self.manage_users_button = QPushButton("Manage Users")
        self.manage_users_button.clicked.connect(self.show_user_management)
        self.manage_users_button.setMinimumHeight(40)
        self.manage_users_button.setMaximumWidth(150)
        self.manage_users_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        scroll_layout.addWidget(self.manage_users_button)

        self.premium_label = QLabel("Real-Time Alerts Enabled (Premium)")
        self.premium_label.setAlignment(Qt.AlignCenter)
        scroll_layout.addWidget(self.premium_label)

        scroll_layout.addStretch(1)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(QIcon(), self)
        tray_menu = QMenu()
        tray_menu.addAction("Show", self.show)
        tray_menu.addAction("Exit", QApplication.quit)
        self.tray.setContextMenu(tray_menu)
        self.tray.show()

    def load_history(self):
        try:
            with open('resources/history.json', 'r') as f:
                content = f.read().strip()
                if content:
                    self.command_history = json.loads(content)
                else:
                    self.command_history = []
        except FileNotFoundError:
            self.command_history = []
        except json.JSONDecodeError:
            self.command_history = []
        for entry in self.command_history:
            QTreeWidgetItem(self.history_tree, [entry])

    def save_history(self):
        with open('resources/history.json', 'w') as f:
            entries = [self.history_tree.topLevelItem(i).text(0) for i in range(self.history_tree.topLevelItemCount())]
            json.dump(entries, f, indent=4)

    def filter_history(self, text):
        for i in range(self.history_tree.topLevelItemCount()):
            item = self.history_tree.topLevelItem(i)
            item.setHidden(text.lower() not in item.text(0).lower())

    def update_device_status(self):
        return ", ".join(f"{name} - {status}" for name, status in self.iot.devices.items())

    def apply_security_rule(self, command, rule):
        logging.info(f"Applying security rule: {rule} to command: {command}")
        if rule == "Always require authentication for door commands" and "door" in command.lower():
            return f"{command} with authentication", None
        elif rule == "Never disable cameras at night" and "disable" in command.lower() and "camera" in command.lower():
            return None, "Use 'adjust camera settings' instead of disabling cameras."
        elif rule == "Block commands from unknown devices" and "known_device" not in command.lower():
            return None, "Use a known device to issue the command."
        return command, None

    def check_risks(self, command):
        user_id = self.user_input.text().strip()
        pin = self.pin_input.text().strip()
        device = self.device_combo.currentText() if self.device_combo.currentText() != "Select Device" else None
        logging.info(f"Checking risks for command: {command}, user_id: {user_id}, pin: {pin}, device: {device}")
        if not user_id or not pin or not command:
            logging.warning("Validation failed: Missing User ID, PIN, or Command")
            QMessageBox.warning(self, "Input Error", "Please enter User ID, PIN, and Command!")
            return

        if not self.db.validate_user(user_id, pin):
            logging.warning(f"Validation failed: Invalid User ID or PIN for user_id: {user_id}")
            QMessageBox.warning(self, "Error", "Invalid User ID or PIN!")
            return

        # Check device permissions
        if device:
            user_permissions = self.db.get_user_permissions(user_id)
            if device not in user_permissions:
                logging.warning(f"User {user_id} does not have permission to control device {device}")
                QMessageBox.warning(self, "Permission Denied", f"You do not have permission to control device {device}!")
                return

        self.current_user = user_id
        cache_key = f"{user_id}:{command}"
        if cache_key in self.command_cache:
            logging.info(f"Found cached response for {cache_key}")
            self.on_gemini_response(self.command_cache[cache_key])
            return

        rule = self.rules_combo.currentText()
        modified_command, suggestion = self.apply_security_rule(command, rule)
        if modified_command is None:
            logging.info(f"Command blocked by rule: {rule}")
            self.update_ui([{"risk_level": "Blocked", "explanation": f"Command blocked by rule: {rule}", 
                            "suggestion": suggestion, "safe_variation_1": "None", "safe_variation_2": "None"}], 
                           None, None, user_id, pin)
        else:
            logging.info(f"Proceeding with Gemini analysis for command: {modified_command or command}")
            self.analyze_command_with_gemini(modified_command or command, user_id)

    def analyze_command_with_gemini(self, command, user_id):
        device = self.device_combo.currentText() if self.device_combo.currentText() != "Select Device" else None
        prompt = f"""
        You are an IoT security expert. Analyze this IoT command:
        Command: "{command}"
        User ID: "{user_id}"
        Device: "{device}"

        Respond in this format:
        - Risk Level: [None/Low/Medium/High/Critical]
        - Explanation: [1-2 sentences]
        - Suggestion: [1-2 sentences]
        - Safe Command Variation 1: [Safe version]
        - Safe Command Variation 2: [Another safe version]
        """
        logging.info(f"Starting Gemini analysis for command: {command}, user_id: {user_id}, device: {device}")
        worker = GeminiWorker(command, prompt)
        worker.signals.result_signal.connect(self.on_gemini_response)
        self.show_loading()

        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(lambda: self.on_gemini_timeout(worker))
        self.timeout_timer.start(10000)

        self.thread_pool.start(worker)
        logging.info("Gemini worker thread started")

    def on_gemini_timeout(self, worker):
        if worker.isRunning():
            logging.error("Gemini API call timed out after 10 seconds")
            self.hide_loading()
            self.result_text.setText("<p style='color: #FF6B6B;'>Error: Gemini API call timed out. Please check your API key or network connection.</p>")
            self.status_icon.setText("🔴")

    def on_gemini_response(self, response):
        self.timeout_timer.stop()
        self.hide_loading()
        logging.info(f"Raw Gemini response: {response}")
        if response.startswith("Error:"):
            error_message = response
            if "API_KEY_INVALID" in response:
                error_message = "Error: Invalid API key. Please update the GOOGLE_API_KEY in the .env file with a valid Gemini API key."
            self.result_text.setText(f"<p style='color: #FF6B6B;'>{error_message}</p>")
            self.status_icon.setText("🔴")
            QMessageBox.critical(self, "API Error", error_message)
            return

        risks = self.parse_gemini_response(response)
        user_id = self.user_input.text().strip()
        pin = self.pin_input.text().strip()
        device = self.device_combo.currentText() if self.device_combo.currentText() != "Select Device" else None
        command = self.command_input.text().strip()

        if risks and risks[0]["risk_level"] != "None":
            self.command_cache[f"{user_id}:{command}"] = response
            safe_v1 = normalize_time_format(command, risks[0]["safe_variation_1"])
            safe_v2 = normalize_time_format(command, risks[0]["safe_variation_2"])
            self.update_ui(risks, safe_v1, safe_v2, user_id, pin, device)
            self.tray.showMessage("IoTGuard Alert", f"Risk detected: {risks[0]['risk_level']}", QSystemTrayIcon.Warning)
        else:
            self.command_cache[f"{user_id}:{command}"] = response
            self.update_ui([], None, None, user_id, pin, device)

    def parse_gemini_response(self, response):
        lines = response.split('\n')
        risk_data = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("- Risk Level:"):
                risk_data["risk_level"] = line.split(":", 1)[1].strip()
            elif line.startswith("- Explanation:"):
                risk_data["explanation"] = line.split(":", 1)[1].strip()
            elif line.startswith("- Suggestion:"):
                risk_data["suggestion"] = line.split(":", 1)[1].strip()
            elif line.startswith("- Safe Command Variation 1:"):
                risk_data["safe_variation_1"] = line.split(":", 1)[1].strip()
                if not risk_data["safe_variation_1"].endswith('"') and risk_data["safe_variation_1"].startswith('"'):
                    risk_data["safe_variation_1"] += '"'
            elif line.startswith("- Safe Command Variation 2:"):
                risk_data["safe_variation_2"] = line.split(":", 1)[1].strip()
                if not risk_data["safe_variation_2"].endswith('"') and risk_data["safe_variation_2"].startswith('"'):
                    risk_data["safe_variation_2"] += '"'
        return [risk_data] if risk_data.get("risk_level") else []

    def update_ui(self, risks, safe_v1, safe_v2, user_id, pin, device):
        command = self.command_input.text().strip()
        execution_result = self.iot.execute_command(command, user_id, pin, device) if not risks else "Command not executed"
        logging.info(f"Updating UI with risks: {risks}, execution_result: {execution_result}")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        risk_level = risks[0]["risk_level"] if risks else "None"
        history_entry = f"[{timestamp}] {user_id}: {command} (Device: {device}) - Risk: {risk_level} - Result: {execution_result}"
        QTreeWidgetItem(self.history_tree, [history_entry])
        self.command_history.append(history_entry)
        if len(self.command_history) > 10:
            self.history_tree.takeTopLevelItem(0)
            self.command_history.pop(0)
        self.save_history()

        self.device_status.setText("Device Status: " + self.update_device_status())
        self.result_text.clear()
        if risks:
            risk_level = risks[0]["risk_level"]
            color = "#FF6B6B" if risk_level in ["High", "Critical"] else "#FBBF24" if risk_level == "Medium" else "#4A90E2"
            self.result_text.append(f"<h3 style='color: {color};'>Command Analysis: {command}</h3>")
            self.result_text.append(f"<p><strong>Risk Level:</strong> {risk_level} {get_risk_icon(risk_level)}</p>")
            self.result_text.append(f"<p><strong>Why It's Risky:</strong> {risks[0]['explanation']}</p>")
            self.result_text.append(f"<p><strong>Suggestion:</strong> <span style='color: #4CAF50;'>{risks[0]['suggestion']}</span></p>")
            if safe_v1 and safe_v1 != "None": 
                self.result_text.append(f"<p><strong>Safe Alternative 1:</strong> <span style='word-wrap: break-word;'>{safe_v1}</span></p>")
            if safe_v2 and safe_v2 != "None": 
                self.result_text.append(f"<p><strong>Safe Alternative 2:</strong> <span style='word-wrap: break-word;'>{safe_v2}</span></p>")
            self.result_text.append(f"<p><a href='learn_more_{risk_level}'>Learn More</a></p>")
            self.status_icon.setText("🔴")
        else:
            self.result_text.append(f"<h3 style='color: #4CAF50;'>Command Analysis: {command}</h3>")
            self.result_text.append(f"<p>Execution Result: {execution_result}</p>")
            self.result_text.append("<p>No risks identified. ✅</p>")
            self.status_icon.setText("🟢")

    def show_loading(self):
        self.loading_label.setText("Analyzing...")
        self.loading_label.setVisible(True)
        self.submit_button.setEnabled(False)
        logging.info("Showing loading indicator")

    def hide_loading(self):
        self.loading_label.setVisible(False)
        self.submit_button.setEnabled(True)
        logging.info("Hiding loading indicator")

    def on_learn_more_clicked(self, url):
        risk_level = url.toString().split('_')[-1]
        message = get_learn_more_message(risk_level)
        detailed_message = f"{risk_level} Risk Details:\n\n{message}\n\nAdditional Tips:\n"
        if risk_level == "High":
            detailed_message += "- Always use multi-factor authentication for critical commands.\n- Regularly audit user access and revoke unnecessary privileges."
        elif risk_level == "Medium":
            detailed_message += "- Consider implementing time-based access controls.\n- Monitor device logs for unusual activity."
        elif risk_level == "Low":
            detailed_message += "- Ensure all devices are updated with the latest firmware.\n- Use strong, unique passwords for each device."
        QMessageBox.information(self, f"{risk_level} Risk Details", detailed_message)

    def show_user_management(self):
        if self.current_user != "master_user":
            QMessageBox.warning(self, "Access Denied", "Only master user can manage users!")
            return
        dialog = UserManagementDialog(self, self.db.conn, self.current_user)
        dialog.exec()

    def on_submit(self):
        command = self.command_input.text().strip()
        user_id = self.user_input.text().strip()
        pin = self.pin_input.text().strip()
        device = self.device_combo.currentText()
        logging.info(f"Submit clicked - User ID: {user_id}, PIN: {pin}, Device: {device}, Command: {command}")
        if not command or len(command) > 100:
            logging.warning("Validation failed: Command must be non-empty and under 100 characters")
            QMessageBox.warning(self, "Input Error", "Command must be non-empty and under 100 characters!")
            return
        self.check_risks(command)