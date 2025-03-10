from transformers import BertTokenizer, BertForSequenceClassification, Trainer, TrainingArguments
from sklearn.model_selection import train_test_split
import torch

# Improved dataset
data = [
    {"text": "unlock the door when I am close", "label": 1},
    {"text": "disable the security camera", "label": 1},
    {"text": "play music in the kitchen", "label": 0},
    {"text": "start the car engine remotely", "label": 1},
    {"text": "open the garage door at 8 PM", "label": 1},
    {"text": "turn off the alarm system", "label": 1},
    {"text": "adjust the thermostat temperature", "label": 0},
    {"text": "share access to all devices", "label": 1},
    {"text": "enable guest mode on the smart lock", "label": 0},
    {"text": "disable the fire alarm for 10 minutes", "label": 1},
    {"text": "start the robot vacuum on low battery", "label": 1},
    {"text": "turn on the lights in the living room", "label": 0},
    {"text": "unlock the door for delivery", "label": 1},
    {"text": "play a movie on the smart TV", "label": 0},
    {"text": "disable the motion sensors", "label": 1},
    {"text": "open the window blinds during the night", "label": 1},
    {"text": "set the thermostat to 72 degrees", "label": 0},
    {"text": "disable all security features", "label": 1},
    {"text": "start the washing machine", "label": 0},
    {"text": "unlock the door without authentication", "label": 1},
]

# Prepare dataset
texts = [item["text"] for item in data]
labels = [item["label"] for item in data]

# Split data
train_texts, val_texts, train_labels, val_labels = train_test_split(texts, labels, test_size=0.2)

# Load tokenizer and model
tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
model = BertForSequenceClassification.from_pretrained("bert-base-uncased", num_labels=2)

# Tokenize data
train_encodings = tokenizer(train_texts, truncation=True, padding=True, max_length=64)
val_encodings = tokenizer(val_texts, truncation=True, padding=True, max_length=64)

# Create dataset
class IoTDataset(torch.utils.data.Dataset):
    def __init__(self, encodings, labels):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx):
        item = {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

train_dataset = IoTDataset(train_encodings, train_labels)
val_dataset = IoTDataset(val_encodings, val_labels)

# Fine-tune model
training_args = TrainingArguments(
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    logging_dir="./logs",
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
)

trainer.train()
trainer.save_model("./fine_tuned_bert")
tokenizer.save_pretrained("./fine_tuned_bert")