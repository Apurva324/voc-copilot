from pathlib import Path
import os

import pandas as pd
from PIL import Image
from dotenv import load_dotenv
from google import genai
BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "Data" / "Raw"
PROCESSED_DIR = BASE_DIR / "Data" / "Processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY not found. Check your .env file."
    )

client = genai.Client(api_key=API_KEY)

records = []
for image_path in RAW_DIR.glob("mock_whatsapp_*.png"):

    print(f"Processing {image_path.name}...")

    image = Image.open(image_path)

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=[
            image,
            """
You are extracting customer support conversations.

Extract only the actual chat.

Ignore:
- timestamps
- emojis
- profile pictures
- status bar
- navigation buttons
- WhatsApp UI

Return ONLY the conversation in chronological order.
"""
        ]
    )

    records.append({
        "source_id": image_path.stem,
        "user": "Unknown",
        "rating": None,
        "feedback_text": response.text.strip(),
        "timestamp": None,
        "app_version": None,
        "channel": "WhatsApp"
    })


df = pd.DataFrame(records)

output_file = PROCESSED_DIR / "whatsapp_feedback.csv"

df.to_csv(output_file, index=False)


print("WhatsApp extraction completed")
print(f"Saved to: {output_file}")
print(f"Chats extracted: {len(df)}")