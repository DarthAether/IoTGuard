def normalize_time_format(command, variation):
    if " pm" in command.lower() or " am" in command.lower():
        if " 20" in variation or " 21" in variation or " 22" in variation or " 23" in variation:
            time_part = variation.split(" at ")[-1].split()[0]
            hour = int(time_part)
            period = "pm" if hour >= 12 else "am"
            hour = hour % 12 or 12
            variation = variation.replace(f" at {time_part}", f" at {hour} {period}")
    return variation

def get_risk_icon(risk_level):
    return {"Critical": "🚨", "High": "⚠️", "Medium": "🔔", "Low": "ℹ️"}.get(risk_level, "")

def get_learn_more_message(risk_level):
    messages = {
        "Critical": "Critical risks pose an immediate threat. Use strong authentication and encryption.",
        "High": "High risks may allow unauthorized access. Implement MFA and update firmware.",
        "Medium": "Medium risks indicate potential issues. Use MFA and specific commands.",
        "Low": "Low risks are minor. Review logs and add security layers.",
        "Blocked": "Blocked by rule. Adjust command or rule settings."
    }
    return messages.get(risk_level, "No info available.")