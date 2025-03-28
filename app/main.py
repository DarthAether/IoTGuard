import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PySide6.QtWidgets import QApplication
from app.gui import IoTGuardWindow
from utils.logging_setup import setup_logging

if __name__ == "__main__":
    setup_logging()
    app = QApplication(sys.argv)
    window = IoTGuardWindow()
    window.show()
    sys.exit(app.exec())