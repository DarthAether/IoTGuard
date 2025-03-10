import google.generativeai as genai
import tkinter as tk
from tkinter import messagebox, filedialog
import json
import logging
from datetime import datetime

# Configure Google API Key
GOOGLE_API_KEY = "AIzaSyBrXhE8U15tkd6Sm279L8S9OP3misl2Yj8"
genai.configure(api_key=GOOGLE_API_KEY)

# Set up logging
logging.basicConfig(filename='iotguard_log.txt', level=logging.INFO, 
                    format='%(asctime)s - %(message)s')

# Initialize Gemini model
try:
    model = genai.GenerativeModel('gemini-1.5-flash')
except AttributeError:
    print("Error: 'GenerativeModel' not found. Please update google-generativeai to 0.7.2 or higher.")
    exit(1)

custom_risks = []

def analyze_command_with_gemini(command):
    prompt = f"""
    You are an IoT security expert. Analyze this IoT command for security risks:
    Command: "{command}"
    
    Respond in this format:
    - Risk Level: [Low/Medium/High/Critical]
    - Explanation: [Why is this risky?]
    - Suggestion: [How to mitigate the risk?]
    
    If no risks are detected:
    - Risk Level: None
    - Explanation: No significant security risks identified.
    - Suggestion: No action required.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini API error: {str(e)}")
        return f"Error: Could not analyze command - {str(e)}"

def check_risks(command):
    gemini_response = analyze_command_with_gemini(command)
    detected_risks = []
    
    if gemini_response.startswith("Error:"):
        return detected_risks
    
    lines = gemini_response.split('\n')
    risk_data = {}
    
    for line in lines:
        if line.startswith("- Risk Level:"):
            risk_data["risk_level"] = line.split(":")[1].strip()
        elif line.startswith("- Explanation:"):
            risk_data["explanation"] = line.split(":")[1].strip()
        elif line.startswith("- Suggestion:"):
            risk_data["suggestion"] = line.split(":")[1].strip()
    
    if "risk_level" in risk_data and risk_data["risk_level"] != "None":
        detected_risks.append(risk_data)
        logging.info(f"Risk detected for: {command} - {risk_data['risk_level']}")
    elif risk_data.get("risk_level") == "None":
        logging.info(f"No risks detected for: {command}")
    
    return detected_risks

def save_risks():
    file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
    if file_path:
        with open(file_path, 'w') as file:
            json.dump(custom_risks, file, indent=4)
        messagebox.showinfo("Success", "Custom risks saved!")

def load_risks():
    global custom_risks
    file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if file_path:
        with open(file_path, 'r') as file:
            custom_risks = json.load(file)
        messagebox.showinfo("Success", "Custom risks loaded!")

def add_custom_risk():
    fields = {
        "trigger": entry_trigger.get().strip(),
        "condition": entry_condition.get().strip() or None,
        "device": entry_device.get().strip(),
        "risk_level": entry_risk_level.get().strip(),
        "explanation": entry_explanation.get().strip(),
        "suggestion": entry_suggestion.get().strip()
    }
    
    if not all(fields[k] for k in ["trigger", "device", "risk_level", "explanation", "suggestion"]):
        messagebox.showwarning("Input Error", "All fields except Condition are mandatory!")
        return
    
    new_risk = {"risk_id": len(custom_risks) + 1, **fields}
    custom_risks.append(new_risk)
    messagebox.showinfo("Success", "Custom risk added!")
    clear_custom_risk_fields()

def clear_custom_risk_fields():
    entry_trigger.delete(0, tk.END)
    entry_condition.delete(0, tk.END)
    entry_device.delete(0, tk.END)
    entry_risk_level.delete(0, tk.END)
    entry_explanation.delete(0, tk.END)
    entry_suggestion.delete(0, tk.END)

def on_submit():
    command = entry_command.get().strip()
    if not command:
        messagebox.showwarning("Input Error", "Enter a command!")
        return
    
    detected_risks = check_risks(command)
    result_text.delete(1.0, tk.END)
    
    if detected_risks:
        result_text.insert(tk.END, f"Command: {command}\nRisks Detected:\n")
        for risk in detected_risks:
            result_text.insert(tk.END, f"- Risk Level: {risk['risk_level']}\n")
            result_text.insert(tk.END, f"  Explanation: {risk['explanation']}\n")
            result_text.insert(tk.END, f"  Suggestion: {risk['suggestion']}\n\n")
    else:
        result_text.insert(tk.END, f"Command: {command}\nNo risks detected. Looks safe!\n")
    
    logging.info(f"Command processed: {command}")

# GUI Setup
root = tk.Tk()
root.title("IoTGuard - Powered by Gemini AI")
root.geometry("600x700")

frame_command = tk.LabelFrame(root, text="Enter IoT Command", padx=10, pady=10)
frame_command.pack(padx=10, pady=5, fill="x")
entry_command = tk.Entry(frame_command, width=50)
entry_command.pack(pady=5)
tk.Button(frame_command, text="Check Risks", command=on_submit).pack(pady=5)

frame_risk = tk.LabelFrame(root, text="Add Custom Risk", padx=10, pady=10)
frame_risk.pack(padx=10, pady=5, fill="x")

for label, var in [("Trigger", "entry_trigger"), ("Condition (Optional)", "entry_condition"), 
                   ("Device", "entry_device"), ("Risk Level", "entry_risk_level"), 
                   ("Explanation", "entry_explanation"), ("Suggestion", "entry_suggestion")]:
    tk.Label(frame_risk, text=label).pack()
    globals()[var] = tk.Entry(frame_risk, width=50)
    globals()[var].pack(pady=2)

tk.Button(frame_risk, text="Add Risk", command=add_custom_risk).pack(pady=5)

frame_buttons = tk.Frame(root)
frame_buttons.pack(pady=5)
tk.Button(frame_buttons, text="Save Custom Risks", command=save_risks).grid(row=0, column=0, padx=5)
tk.Button(frame_buttons, text="Load Custom Risks", command=load_risks).grid(row=0, column=1, padx=5)

result_text = tk.Text(root, height=10, width=60, wrap="word")
result_text.pack(padx=10, pady=10)

root.mainloop()