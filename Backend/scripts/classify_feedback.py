import os
import json
from pathlib import Path
from pymongo import MongoClient, UpdateOne
import certifi
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv

# 1. Automatically find and load the .env from 'voc-copilot/.env'
dotenv_path = find_dotenv()
load_dotenv(dotenv_path, override=True)

# 2. Database & API Key Verification Configuration
MONGO_URI = os.getenv("MONGO_URI")
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print(f"Error: GROQ_API_KEY is missing!")
    print(f"Searched inside .env file at: {dotenv_path}")
    exit(1)

try:
    client_db = MongoClient(
        MONGO_URI, 
        serverSelectionTimeoutMS=5000,
        tls=True,
        tlsAllowInvalidCertificates=True
    )
    db = client_db["voc_database"]
    feedback_collection = db["feedback"]
    print(" Connected to MongoDB Atlas successfully!")
except Exception as e:
    print(f" Failed to connect to MongoDB Atlas: {e}")
    exit(1)

# Initialize Groq client using OpenAI SDK compatibility layer
client_ai = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

def classify_batch(texts):
    """Sends a batch of customer texts to LLaMA 3.3 for ultra-fast structured processing."""
    prompt = """
    You are an expert operations analyst at Zomato. Analyze the following list of customer feedback entries.
    For each entry, determine the core operational issue and overall sentiment.

    Allowed Categories:
    - Delivery Delay (weather, traffic, delays)
    - Food Quality & Packaging (spilled food, cold items, bad taste)
    - App & Payment Issues (app crashes, login failure, checkout bugs, double payments)
    - Refund & Customer Support (refunds not processed, bad support agent)
    - Pricing & Charges (platform fees, delivery charges, price hikes)
    - Positive Feedback (compliments, good service, discounts working)
    - Other (anything else)

    Allowed Sentiments: Positive, Neutral, Negative

    Return ONLY a raw JSON array matching this exact format, with no markdown code blocks:
    [
      {"category": "Category Name", "sentiment": "Sentiment"}
    ]
    """
    
    # Build a clean structure for the prompt context window
    formatted_input = [{"id": idx, "text": text} for idx, text in enumerate(texts)]
    
    try:
        response = client_ai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(formatted_input)}
            ],
            temperature=0.1, # Keep it strictly deterministic
        )
        
        raw_res = response.choices[0].message.content.strip()
        if raw_res.startswith("```"):
            raw_res = raw_res.strip("```json").strip("```").strip()
            
        return json.loads(raw_res)
    except Exception as e:
        print(f"Batch classification failed: {e}")
        # Return fallback items if the api hits an issue
        return [{"category": "Other", "sentiment": "Neutral"} for _ in texts]

def run_pipeline():
    # Fetch only documents that have not been assigned an AI category yet
    print(" Fetching unclassified records from MongoDB...")
    unlabeled_records = list(feedback_collection.find({"category": {"$exists": False}}))
    
    if not unlabeled_records:
        print(" All records in MongoDB are already classified!")
        return
        
    # Cap batch at 40 rows for testing velocity (Remove or adjust as needed)
    records_to_process = unlabeled_records[:50]
    
    print(f" Found {len(unlabeled_records)} total unlabeled records. Processing a slice of {len(records_to_process)} entries through LLaMA 3.3...")
    
    batch_size = 10
    operations = []
    
    for i in range(0, len(records_to_process), batch_size):
        batch = records_to_process[i:i+batch_size]
        texts = [record["feedback_text"] for record in batch]
        
        print(f"   ↳ Processing items {i+1} to {i+len(texts)}...")
        results = classify_batch(texts)
        
        # Match LLM results back to their specific MongoDB document IDs
        for idx, res in enumerate(results):
            if idx < len(batch):
                target_record = batch[idx]
                category = res.get("category", "Other")
                sentiment = res.get("sentiment", "Neutral")
                
                operations.append(
                    UpdateOne(
                        {"_id": target_record["_id"]},
                        {"$set": {"category": category, "sentiment": sentiment}}
                    )
                )
                
    # Bulk update the classified records back into MongoDB Atlas
    if operations:
        try:
            print(" Syncing enriched classifications back to MongoDB Atlas...")
            result = feedback_collection.bulk_write(operations, ordered=False)
            print(f" SUCCESS! Enriched operational data written to Atlas: {result.modified_count} documents updated.")
        except Exception as e:
            print(f"Error during bulk write sync: {e}")

if __name__ == "__main__":
    run_pipeline()