import os
import logging
import re
from PySide6.QtCore import QRunnable, Signal, QObject
import google.generativeai as genai
from utils.config import GOOGLE_API_KEY

class WorkerSignals(QObject):
    result_signal = Signal(str)

class GeminiWorker(QRunnable):
    def __init__(self, command, prompt):
        super().__init__()
        self.command = command
        self.prompt = prompt
        self.signals = WorkerSignals()

    def list_available_models(self):
        try:
            models = genai.list_models()
            available_models = [model.name for model in models if 'generateContent' in model.supported_generation_methods]
            logging.info(f"Available models: {available_models}")
            return available_models
        except Exception as e:
            logging.error(f"Failed to list models: {str(e)}")
            return []

    def run(self):
        try:
            if not GOOGLE_API_KEY:
                raise ValueError("Google API key not found in environment variables")

            api_key = GOOGLE_API_KEY.strip()
            if not re.match(r'^[A-Za-z0-9_-]+$', api_key):
                raise ValueError(f"Invalid API key format: {api_key}")

            genai.configure(api_key=api_key)
            model_name = 'gemini-1.5-pro'  # Updated model name
            try:
                model = genai.GenerativeModel(model_name)
            except Exception as e:
                logging.error(f"Failed to load model {model_name}: {str(e)}")
                available_models = self.list_available_models()
                error_msg = f"Error: Model {model_name} not found or not supported. Available models: {available_models}"
                self.signals.result_signal.emit(error_msg)
                return

            response = model.generate_content(self.prompt)
            
            if not response or not response.text:
                raise ValueError("Empty response from Gemini API")
            
            logging.info(f"Gemini API response for command '{self.command}': {response.text}")
            self.signals.result_signal.emit(response.text)
        except Exception as e:
            error_msg = f"Error: Failed to analyze command '{self.command}' - {str(e)}"
            logging.error(error_msg)
            self.signals.result_signal.emit(error_msg)