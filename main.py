import google.generativeai as genai
import logging
from datetime import datetime
import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QLineEdit, QPushButton, QTextEdit, QLabel, QMessageBox, 
                               QGraphicsOpacityEffect, QScrollArea, QListWidget, QListWidgetItem, 
                               QComboBox)
from PySide6.QtGui import QLinearGradient, QBrush, QPalette, QColor, QFont, QIcon
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint, QSize, QThread, Signal

# Configure Google API Key
GOOGLE_API_KEY = "AIzaSyBrXhE8U15tkd6Sm279L8S9OP3misl2Yj8"
genai.configure(api_key=GOOGLE_API_KEY)

# Set up logging
logging.basicConfig(filename='iotguard_log.txt', level=logging.INFO, 
                    format='%(asctime)s - %(message)s')
logging.info("Starting IoTGuard application with PySide6...")

# Initialize Gemini model
model = genai.GenerativeModel('gemini-1.5-flash')

# Background thread for Gemini API calls
class GeminiWorker(QThread):
    result_signal = Signal(str)

    def __init__(self, command, prompt):
        super().__init__()
        self.command = command
        self.prompt = prompt

    def run(self):
        try:
            response = model.generate_content(self.prompt)
            logging.info("Gemini response received.")
            self.result_signal.emit(response.text.strip())
        except Exception as e:
            logging.error(f"Gemini API error: {str(e)}")
            self.result_signal.emit(f"Error: Could not analyze command - {str(e)}")

class IoTGuardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logging.info("Initializing IoTGuard window...")
        self.setWindowTitle("IoTGuard - Smart Home Security")
        self.setGeometry(100, 100, 450, 700)

        # Set gradient background
        palette = self.palette()
        gradient = QLinearGradient(0, 0, 0, 700)
        gradient.setColorAt(0, QColor("#2A4365"))  # Dark blue
        gradient.setColorAt(1, QColor("#1A202C"))  # Darker gray-blue
        palette.setBrush(QPalette.Window, QBrush(gradient))
        self.setPalette(palette)
        logging.info("Gradient background set.")

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header with Logo and Tagline
        header_layout = QHBoxLayout()
        self.logo = QLabel("🔒 IoTGuard")
        logo_font = QFont("Arial", 28, QFont.Bold)
        self.logo.setFont(logo_font)
        self.logo.setStyleSheet("color: #E2E8F0; background: transparent; padding: 10px;")
        self.logo_effect = QGraphicsOpacityEffect(self.logo)
        self.logo.setGraphicsEffect(self.logo_effect)
        self.logo_effect.setOpacity(0)
        header_layout.addWidget(self.logo)

        self.tagline = QLabel("Secure Your Smart Home")
        self.tagline.setStyleSheet("font-size: 16px; color: #A0AEC0; font-style: italic; background: transparent;")
        header_layout.addWidget(self.tagline)
        layout.addLayout(header_layout)
        logging.info("Header added with opacity effect.")

        # Fade-In Animation for Logo
        self.logo_animation = QPropertyAnimation(self.logo_effect, b"opacity")
        self.logo_animation.setDuration(1500)
        self.logo_animation.setStartValue(0)
        self.logo_animation.setEndValue(1)
        self.logo_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.logo_animation.start()
        logging.info("Logo fade-in animation started.")

        # Command Input Section
        input_section = QWidget()
        input_layout = QHBoxLayout(input_section)
        input_layout.setSpacing(10)

        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Enter IoT command (e.g., 'unlock door')")
        self.command_input.setStyleSheet("""
            font-size: 16px; 
            padding: 12px; 
            background-color: #2D3748; 
            color: #E2E8F0; 
            border: none; 
            border-radius: 10px;
            box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.3);
        """)
        input_layout.addWidget(self.command_input)

        self.submit_button = QPushButton("Check Risks")
        self.submit_button.setStyleSheet("""
            font-size: 14px; 
            padding: 12px; 
            background-color: #3182CE; 
            color: white; 
            border: none; 
            border-radius: 10px;
            box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.3);
        """)
        self.submit_button.setFixedSize(120, 40)
        self.submit_button.clicked.connect(self.on_submit)
        input_layout.addWidget(self.submit_button)
        layout.addWidget(input_section)
        logging.info("Input section added.")

        # Slide-In Animation for Input Section
        self.input_animation = QPropertyAnimation(input_section, b"pos")
        self.input_animation.setDuration(1000)
        self.input_animation.setStartValue(QPoint(-450, input_section.y()))
        self.input_animation.setEndValue(QPoint(0, input_section.y()))
        self.input_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.input_animation.start()
        logging.info("Input slide-in animation started.")

        # Button Press Animation (Scale Effect)
        self.button_size_animation = QPropertyAnimation(self.submit_button, b"minimumSize")
        self.button_size_animation_2 = QPropertyAnimation(self.submit_button, b"maximumSize")
        self.submit_button.clicked.connect(self.animate_button)

        # Loading Indicator
        self.loading_label = QLabel("Analyzing...")
        self.loading_label.setStyleSheet("""
            font-size: 14px; 
            color: #A0AEC0; 
            background: transparent; 
            padding: 5px;
        """)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_effect = QGraphicsOpacityEffect(self.loading_label)
        self.loading_label.setGraphicsEffect(self.loading_effect)
        self.loading_effect.setOpacity(0)  # Hidden by default
        layout.addWidget(self.loading_label)
        logging.info("Loading indicator added.")

        # Pulsing Animation for Loading Indicator
        self.loading_animation = QPropertyAnimation(self.loading_effect, b"opacity")
        self.loading_animation.setDuration(800)
        self.loading_animation.setStartValue(0.3)
        self.loading_animation.setEndValue(1)
        self.loading_animation.setEasingCurve(QEasingCurve.InOutSine)
        self.loading_animation.setLoopCount(-1)  # Loop indefinitely

        # Security Rules Editor
        rules_label = QLabel("Set Security Rule:")
        rules_label.setStyleSheet("font-size: 14px; color: #A0AEC0; background: transparent;")
        layout.addWidget(rules_label)

        self.rules_combo = QComboBox()
        self.rules_combo.addItems([
            "Always require authentication for door commands",
            "Never disable cameras at night",
            "Block commands from unknown devices",
            "No rules"
        ])
        self.rules_combo.setStyleSheet("""
            font-size: 14px; 
            padding: 8px; 
            background-color: #2D3748; 
            color: #E2E8F0; 
            border: none; 
            border-radius: 8px;
        """)
        layout.addWidget(self.rules_combo)
        logging.info("Security rules editor added.")

        # Command Status Indicator
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Command Status:")
        self.status_label.setStyleSheet("font-size: 14px; color: #A0AEC0; background: transparent;")
        status_layout.addWidget(self.status_label)

        self.status_icon = QLabel("🔵")
        self.status_icon.setStyleSheet("font-size: 16px; background: transparent;")
        status_layout.addWidget(self.status_icon)
        layout.addLayout(status_layout)
        logging.info("Command status indicator added.")

        # Result Display with Fade-In Animation
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setStyleSheet("""
            font-size: 14px; 
            padding: 15px; 
            background-color: #2D3748; 
            color: #E2E8F0; 
            border: none; 
            border-radius: 10px;
            box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.3);
        """)
        self.result_effect = QGraphicsOpacityEffect(self.result_text)
        self.result_text.setGraphicsEffect(self.result_effect)
        self.result_effect.setOpacity(0)
        layout.addWidget(self.result_text)
        logging.info("Result text area added with opacity effect.")

        # Command History Log
        history_label = QLabel("Command History:")
        history_label.setStyleSheet("font-size: 14px; color: #A0AEC0; background: transparent;")
        layout.addWidget(history_label)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet("""
            font-size: 14px; 
            padding: 10px; 
            background-color: #2D3748; 
            color: #E2E8F0; 
            border: none; 
            border-radius: 10px;
            box-shadow: 0px 2px 5px rgba(0, 0, 0, 0.3);
        """)
        scroll = QScrollArea()
        scroll.setWidget(self.history_list)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(150)
        scroll.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(scroll)
        logging.info("Command history log added.")

        # Store command history
        self.command_history = []

    def animate_button(self):
        """Animate the button with a uniform scale effect."""
        original_size = QSize(120, 40)
        scaled_size = QSize(110, 36)

        self.button_size_animation.setDuration(100)
        self.button_size_animation.setStartValue(original_size)
        self.button_size_animation.setEndValue(scaled_size)
        self.button_size_animation.setEasingCurve(QEasingCurve.InOutQuad)

        self.button_size_animation_2.setDuration(100)
        self.button_size_animation_2.setStartValue(original_size)
        self.button_size_animation_2.setEndValue(scaled_size)
        self.button_size_animation_2.setEasingCurve(QEasingCurve.InOutQuad)

        self.button_size_animation_reverse = QPropertyAnimation(self.submit_button, b"minimumSize")
        self.button_size_animation_reverse.setDuration(100)
        self.button_size_animation_reverse.setStartValue(scaled_size)
        self.button_size_animation_reverse.setEndValue(original_size)
        self.button_size_animation_reverse.setEasingCurve(QEasingCurve.InOutQuad)

        self.button_size_animation_2_reverse = QPropertyAnimation(self.submit_button, b"maximumSize")
        self.button_size_animation_2_reverse.setDuration(100)
        self.button_size_animation_2_reverse.setStartValue(scaled_size)
        self.button_size_animation_2_reverse.setEndValue(original_size)
        self.button_size_animation_2_reverse.setEasingCurve(QEasingCurve.InOutQuad)

        self.button_size_animation.finished.connect(self.button_size_animation_reverse.start)
        self.button_size_animation_2.finished.connect(self.button_size_animation_2_reverse.start)

        self.button_size_animation.start()
        self.button_size_animation_2.start()
        logging.info("Button press animation started.")

    def show_loading(self):
        """Show the loading animation."""
        self.loading_effect.setOpacity(1)  # Make visible
        self.loading_animation.start()
        self.submit_button.setEnabled(False)  # Disable button during loading
        logging.info("Loading animation started.")

    def hide_loading(self):
        """Hide the loading animation."""
        self.loading_animation.stop()
        self.loading_effect.setOpacity(0)  # Hide
        self.submit_button.setEnabled(True)  # Re-enable button
        logging.info("Loading animation stopped.")

    def apply_security_rule(self, command, rule):
        """Apply user-defined security rules to the command."""
        if rule == "Always require authentication for door commands" and "door" in command.lower():
            return f"{command} with authentication"
        elif rule == "Never disable cameras at night" and "disable" in command.lower() and "camera" in command.lower():
            return None  # Block the command
        elif rule == "Block commands from unknown devices":
            return command if "known_device" in command.lower() else None
        return command

    def analyze_command_with_gemini(self, command):
        prompt = f"""
        You are an IoT security expert. Analyze this IoT command for security risks in a smart home system:
        Command: "{command}"
        
        Respond in this exact format:
        - Risk Level: [Low/Medium/High/Critical]
        - Explanation: [Why is this risky?]
        - Suggestion: [How to mitigate the risk?]
        - Safe Command Variation 1: [A completely safe version of the command]
        - Safe Command Variation 2: [Another completely safe version of the command]
        
        If no risks are detected:
        - Risk Level: None
        - Explanation: No significant security risks identified.
        - Suggestion: No action required.
        - Safe Command Variation 1: None
        - Safe Command Variation 2: None
        """
        self.worker = GeminiWorker(command, prompt)
        self.worker.result_signal.connect(self.on_gemini_response)
        self.show_loading()
        self.worker.start()

    def on_gemini_response(self, gemini_response):
        self.hide_loading()
        detected_risks = []
        
        if gemini_response.startswith("Error:"):
            self.result_text.clear()
            self.result_text.append(gemini_response)
            self.status_icon.setText("🔴")
            return
        
        lines = gemini_response.split('\n')
        risk_data = {}
        
        for line in lines:
            if line.startswith("- Risk Level:"):
                risk_data["risk_level"] = line.split(":")[1].strip()
            elif line.startswith("- Explanation:"):
                risk_data["explanation"] = line.split(":")[1].strip()
            elif line.startswith("- Suggestion:"):
                risk_data["suggestion"] = line.split(":")[1].strip()
            elif line.startswith("- Safe Command Variation 1:"):
                risk_data["safe_variation_1"] = line.split(":")[1].strip()
            elif line.startswith("- Safe Command Variation 2:"):
                risk_data["safe_variation_2"] = line.split(":")[1].strip()
        
        command = self.command_input.text().strip()
        if "risk_level" in risk_data and risk_data["risk_level"] != "None":
            detected_risks.append(risk_data)
            logging.info(f"Risk detected for: {command} - {risk_data['risk_level']}")
            self.update_ui(detected_risks, risk_data.get("safe_variation_1"), risk_data.get("safe_variation_2"))
        else:
            logging.info(f"No risks detected for: {command}")
            self.update_ui(detected_risks, None, None)

    def check_risks(self, command):
        # Apply security rules
        rule = self.rules_combo.currentText()
        modified_command = self.apply_security_rule(command, rule)
        if modified_command is None:
            return [{"risk_level": "Blocked", "explanation": f"Command blocked by rule: {rule}", "suggestion": "Modify the command to comply with the rule.", "safe_variation_1": "None", "safe_variation_2": "None"}], None, None
        elif modified_command != command:
            command = modified_command
            logging.info(f"Command modified by rule: {command}")
        
        self.analyze_command_with_gemini(command)

    def update_ui(self, detected_risks, safe_variation_1, safe_variation_2):
        command = self.command_input.text().strip()
        
        # Update command history
        risk_level = detected_risks[0]["risk_level"] if detected_risks else "None"
        history_entry = f"{command} - Risk: {risk_level}"
        self.command_history.append(history_entry)
        self.history_list.addItem(QListWidgetItem(history_entry))
        if len(self.command_history) > 10:
            self.command_history.pop(0)
            self.history_list.takeItem(0)

        # Update result display
        self.result_text.clear()
        if detected_risks:
            self.result_text.append(f"Command: {command}\nRisks Detected:\n")
            for risk in detected_risks:
                self.result_text.append(f"- Risk Level: {risk['risk_level']}\n  Explanation: {risk['explanation']}\n  Suggestion: {risk['suggestion']}\n  Safe Variation 1: {safe_variation_1}\n  Safe Variation 2: {safe_variation_2}\n")
            self.status_icon.setText("🔴")
        else:
            self.result_text.append(f"Command: {command}\nNo vulnerabilities detected.")
            self.status_icon.setText("🟢")
        
        # Fade-In Animation for Result Text
        self.result_animation = QPropertyAnimation(self.result_effect, b"opacity")
        self.result_animation.setDuration(1000)
        self.result_animation.setStartValue(0)
        self.result_animation.setEndValue(1)
        self.result_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.result_animation.start()
        logging.info("Result fade-in animation started.")
        
        logging.info(f"Command processed: {command}")

    def on_submit(self):
        command = self.command_input.text().strip()
        if not command:
            QMessageBox.warning(self, "Input Error", "Enter a command!")
            return
        
        self.check_risks(command)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IoTGuardWindow()
    window.show()
    logging.info("Window displayed.")
    sys.exit(app.exec())