import torch
from transformers import BertTokenizer, BertModel
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import tkinter as tk
from tkinter import messagebox, filedialog
import json

# Load pre-trained BERT model and tokenizer
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
model = BertModel.from_pretrained('bert-base-uncased')

# Predefined risks for IoT commands
risks = [
    {
        "risk_id": 1,
        "trigger": "unlock",
        "condition": "when I am close",
        "device": "door",
        "risk_level": "High",
        "explanation": "Proximity-based unlocking can be spoofed, allowing unauthorized access.",
        "suggestion": "Use fingerprint or PIN-based authentication instead."
    },
    {
        "risk_id": 2,
        "trigger": "disable",
        "condition": None,
        "device": "security camera",
        "risk_level": "Critical",
        "explanation": "Disabling security cameras could leave your property unmonitored, increasing the risk of intrusion.",
        "suggestion": "Ensure camera disable commands require admin authentication."
    },
    {
        "risk_id": 3,
        "trigger": "turn off",
        "condition": None,
        "device": "alarm system",
        "risk_level": "Critical",
        "explanation": "Turning off the alarm system without strong authentication may allow burglars to disable security.",
        "suggestion": "Require multi-factor authentication for alarm control."
    },
    {
        "risk_id": 4,
        "trigger": "open",
        "condition": "at 8 PM",
        "device": "garage door",
        "risk_level": "Medium",
        "explanation": "Time-based automatic opening may be exploited if someone knows your schedule.",
        "suggestion": "Include an additional condition like proximity or authentication."
    },
    {
        "risk_id": 5,
        "trigger": "play",
        "condition": "when I am in the kitchen",
        "device": "music",
        "risk_level": "Low",
        "explanation": "This command doesn't pose significant risks but might trigger unintentionally if not well-defined.",
        "suggestion": "Add more specific location-based criteria, like device pairing or user confirmation."
    },
    {
        "risk_id": 6,
        "trigger": "unlock",
        "condition": "for delivery",
        "device": "door",
        "risk_level": "High",
        "explanation": "Unlocking for deliveries may expose your property to unauthorized access if the delivery personnel’s identity is not verified.",
        "suggestion": "Use a one-time authentication code for delivery personnel."
    },
    {
        "risk_id": 7,
        "trigger": "disable",
        "condition": "for 10 minutes",
        "device": "fire alarm",
        "risk_level": "Critical",
        "explanation": "Disabling fire alarms, even temporarily, increases the risk of fire hazards going undetected.",
        "suggestion": "Only allow disabling with admin-level authentication and log the event."
    },
    {
        "risk_id": 8,
        "trigger": "start",
        "condition": None,
        "device": "car engine",
        "risk_level": "High",
        "explanation": "Starting the car engine remotely without user verification may lead to unauthorized use.",
        "suggestion": "Ensure the command requires user proximity or authentication."
    },
    {
        "risk_id": 9,
        "trigger": "open",
        "condition": "during the night",
        "device": "window blinds",
        "risk_level": "Medium",
        "explanation": "Opening window blinds at night could reveal your home to external threats.",
        "suggestion": "Consider adding a time-based lockout to prevent opening during night hours."
    },
    {
        "risk_id": 10,
        "trigger": "start",
        "condition": "on low battery",
        "device": "robot vacuum",
        "risk_level": "Medium",
        "explanation": "Starting the robot vacuum on low battery might cause it to stop mid-cleaning.",
        "suggestion": "Ensure the vacuum starts only when the battery is sufficiently charged."
    }
]

def preprocess_command(command):
    """Preprocess the command: tokenize it using BERT tokenizer and get embeddings."""
    inputs = tokenizer(command, return_tensors='pt', padding=True, truncation=True, max_length=64)
    with torch.no_grad():
        outputs = model(**inputs)
        embeddings = outputs.last_hidden_state.mean(dim=1)  # Pool embeddings to a single vector
    return embeddings

def compute_similarity(command_embeddings, risk_embeddings):
    """Compute cosine similarity between command embeddings and risk embeddings."""
    similarity_scores = cosine_similarity(command_embeddings.detach().numpy(), risk_embeddings)
    return similarity_scores

def check_risks(command, risks):
    """Analyze the user's command for potential risks using BERT embeddings."""
    detected_risks = []
    command_embeddings = preprocess_command(command)
    
    for risk in risks:
        risk_description = f"{risk['trigger']} {risk['condition'] if risk['condition'] else ''} {risk['device']}"
        risk_embeddings = preprocess_command(risk_description)
        similarity_scores = compute_similarity(command_embeddings, risk_embeddings)
        if similarity_scores > 0.8:  # Threshold for detection
            detected_risks.append(risk)
    return detected_risks

def save_risks_to_file():
    """Save the current risks to a JSON file."""
    file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if file_path:
        with open(file_path, 'w') as file:
            json.dump(risks, file, indent=4)
        messagebox.showinfo("Success", "Risks saved successfully!")

def load_risks_from_file():
    """Load risks from a JSON file."""
    global risks
    file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if file_path:
        with open(file_path, 'r') as file:
            risks = json.load(file)
        messagebox.showinfo("Success", "Risks loaded successfully!")

def add_custom_risk():
    """Add a custom risk dynamically."""
    trigger = entry_trigger.get().strip()
    condition = entry_condition.get().strip()
    device = entry_device.get().strip()
    risk_level = entry_risk_level.get().strip()
    explanation = entry_explanation.get().strip()
    suggestion = entry_suggestion.get().strip()

    if not trigger or not device or not risk_level or not explanation or not suggestion:
        messagebox.showwarning("Input Error", "All fields except condition are required!")
        return

    new_risk = {
        "risk_id": len(risks) + 1,
        "trigger": trigger,
        "condition": condition if condition else None,
        "device": device,
        "risk_level": risk_level,
        "explanation": explanation,
        "suggestion": suggestion,
    }
    risks.append(new_risk)
    messagebox.showinfo("Success", "Custom risk added successfully!")

def on_submit():
    command = entry.get().strip()
    if not command:
        messagebox.showwarning("Input Error", "Please enter a command.")
        return

    detected_risks = check_risks(command, risks)

    result_text.delete(1.0, tk.END)
    if detected_risks:
        result_text.insert(tk.END, f"Command: {command}\nRisks Detected:\n")
        for risk in detected_risks:
            result_text.insert(tk.END, f"- Risk Level: {risk['risk_level']}\n")
            result_text.insert(tk.END, f"  Explanation: {risk['explanation']}\n")
            result_text.insert(tk.END, f"  Suggestion: {risk['suggestion']}\n\n")
    else:
        result_text.insert(tk.END, f"Command: {command}\nNo risks detected. Command appears safe.\n")

# GUI Setup
root = tk.Tk()
root.title("IoT Command Risk Detector")

# Command input
label = tk.Label(root, text="Enter IoT Command:")
label.pack(pady=5)
entry = tk.Entry(root, width=50)
entry.pack(pady=5)

# Buttons
submit_button = tk.Button(root, text="Submit", command=on_submit)
submit_button.pack(pady=5)

save_button = tk.Button(root, text="Save Risks", command=save_risks_to_file)
save_button.pack(pady=5)

load_button = tk.Button(root, text="Load Risks", command=load_risks_from_file)
load_button.pack(pady=5)

# Custom risk input
custom_risk_label = tk.Label(root, text="Add Custom Risk:")
custom_risk_label.pack(pady=5)

entry_trigger = tk.Entry(root, width=50)
entry_trigger.pack(pady=2)
entry_trigger.insert(0, "Trigger")

entry_condition = tk.Entry(root, width=50)
entry_condition.pack(pady=2)
entry_condition.insert(0, "Condition (Optional)")

entry_device = tk.Entry(root, width=50)
entry_device.pack(pady=2)
entry_device.insert(0, "Device")

entry_risk_level = tk.Entry(root, width=50)
entry_risk_level.pack(pady=2)
entry_risk_level.insert(0, "Risk Level")

entry_explanation = tk.Entry(root, width=50)
entry_explanation.pack(pady=2)
entry_explanation.insert(0, "Explanation")

entry_suggestion = tk.Entry(root, width=50)
entry_suggestion.pack(pady=2)
entry_suggestion.insert(0, "Suggestion")

add_risk_button = tk.Button(root, text="Add Risk", command=add_custom_risk)
add_risk_button.pack(pady=5)

# Results text box
result_text = tk.Text(root, height=10, width=50)
result_text.pack(pady=5)

# Run GUI
root.mainloop()
