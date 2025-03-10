import streamlit as st
from transformers import BertTokenizer, BertForSequenceClassification
import torch

# Load fine-tuned model
model = BertForSequenceClassification.from_pretrained("./fine_tuned_bert")
tokenizer = BertTokenizer.from_pretrained("./fine_tuned_bert")

# Streamlit UI
st.title("IoT Command Risk Detector")
st.write("Enter an IoT command to check for security risks:")

# Input
command = st.text_input("IoT Command", "unlock the door when I am close")

# Predict risk
if st.button("Analyze"):
    inputs = tokenizer(command, return_tensors="pt", truncation=True, padding=True, max_length=64)
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        prediction = torch.argmax(logits, dim=1).item()

    # Display result
    if prediction == 1:
        st.error("🚨 Risk Detected: This command is potentially unsafe!")
    else:
        st.success("✅ No Risk Detected: This command appears safe.")
        
import shap

# Add this after the prediction code
if prediction == 1:
    explainer = shap.Explainer(model, tokenizer)
    shap_values = explainer([command])
    st.write("### Why was this flagged as risky?")
    shap.plots.text(shap_values[0], display=False)
    st.pyplot()