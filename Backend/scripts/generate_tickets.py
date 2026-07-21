import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# 1. Load environment variables
load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    print(" Error: GROQ_API_KEY is missing from your .env file!")
    exit(1)

# 2. Initialize OpenAI client mapped to Groq
client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1"
)

prompt = """
Generate a JSON list containing exactly 5 realistic customer support chat transcripts between Zomato customer care executives and frustrated users in India. 
Cover issues like 'refund not processed', 'coupon code not working', 'food spilled', and 'wrong order delivered'. 

Return ONLY valid raw JSON data matching this exact schema layout without any markdown code blocks, backticks, or wrappers:
[
  {
    "ticket_id": "ZM-101",
    "customer_name": "Rahul Sharma",
    "timestamp": "2026-07-15T12:00:00Z",
    "issue_category": "Refund Issue",
    "transcript": "Customer: I ordered food 2 hours ago... Executive: Checking..."
  }
]
"""

print(" Sending request to LLaMA 3.3 on Groq...")

try:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    
    # Extract the raw content text
    raw_content = response.choices[0].message.content.strip()
    
    print(" Raw LLM Output Received! Checking structure...")
    
    # Strip away any markdown formatting if the model ignored instructions and included it
    if raw_content.startswith("```"):
        raw_content = raw_content.strip("```json").strip("```").strip()

    # Validate that it is indeed correct JSON before writing
    parsed_json = json.loads(raw_content)
    
    # Save formatted JSON file
    with open("mock_support_tickets.json", "w") as f:
        json.dump(parsed_json, f, indent=4)
        
    print(" SUCCESS! Saved mock tickets to 'mock_support_tickets.json'")

except json.JSONDecodeError:
    print(" JSON Parsing Error! The model didn't return clean JSON. Here is what it sent:")
    print(raw_content)
except Exception as e:
    print(f" An unexpected API error occurred: {str(e)}")