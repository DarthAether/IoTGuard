from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QPoint, QSize
from PySide6.QtWidgets import QGraphicsOpacityEffect  # Changed from QtGui to QtWidgets

def setup_animations(window):
    # Logo Fade-In
    logo_effect = QGraphicsOpacityEffect(window.logo)
    window.logo.setGraphicsEffect(logo_effect)
    window.logo_animation = QPropertyAnimation(logo_effect, b"opacity")
    window.logo_animation.setDuration(1500)
    window.logo_animation.setStartValue(0)
    window.logo_animation.setEndValue(1)
    window.logo_animation.setEasingCurve(QEasingCurve.InOutQuad)
    window.logo_animation.start()

    # Input Slide-In
    window.input_animation = QPropertyAnimation(window.centralWidget().layout().itemAt(1).widget(), b"pos")
    window.input_animation.setDuration(1000)
    window.input_animation.setStartValue(QPoint(-500, 0))
    window.input_animation.setEndValue(QPoint(0, 0))
    window.input_animation.setEasingCurve(QEasingCurve.InOutQuad)
    window.input_animation.start()

    # Button Press
    window.button_size_animation = QPropertyAnimation(window.submit_button, b"minimumSize")
    window.button_size_animation_2 = QPropertyAnimation(window.submit_button, b"maximumSize")
    window.submit_button.clicked.connect(lambda: animate_button(window))

    # Loading Pulse
    loading_effect = QGraphicsOpacityEffect(window.loading_label)
    window.loading_label.setGraphicsEffect(loading_effect)
    window.loading_animation = QPropertyAnimation(loading_effect, b"opacity")
    window.loading_animation.setDuration(800)
    window.loading_animation.setStartValue(0.3)
    window.loading_animation.setEndValue(1)
    window.loading_animation.setEasingCurve(QEasingCurve.InOutSine)
    window.loading_animation.setLoopCount(-1)

    # Result Fade-In
    result_effect = QGraphicsOpacityEffect(window.result_text)
    window.result_text.setGraphicsEffect(result_effect)
    window.result_animation = QPropertyAnimation(result_effect, b"opacity")
    window.result_animation.setDuration(1000)
    window.result_animation.setStartValue(0)
    window.result_animation.setEndValue(1)
    window.result_animation.setEasingCurve(QEasingCurve.InOutQuad)

def animate_button(window):
    original_size = QSize(120, 40)
    scaled_size = QSize(110, 36)
    window.button_size_animation.setDuration(100)
    window.button_size_animation.setStartValue(original_size)
    window.button_size_animation.setEndValue(scaled_size)
    window.button_size_animation_2.setDuration(100)
    window.button_size_animation_2.setStartValue(original_size)
    window.button_size_animation_2.setEndValue(scaled_size)
    reverse1 = QPropertyAnimation(window.submit_button, b"minimumSize")
    reverse1.setDuration(100)
    reverse1.setStartValue(scaled_size)
    reverse1.setEndValue(original_size)
    reverse2 = QPropertyAnimation(window.submit_button, b"maximumSize")
    reverse2.setDuration(100)
    reverse2.setStartValue(scaled_size)
    reverse2.setEndValue(original_size)
    window.button_size_animation.finished.connect(reverse1.start)
    window.button_size_animation_2.finished.connect(reverse2.start)
    window.button_size_animation.start()
    window.button_size_animation_2.start()