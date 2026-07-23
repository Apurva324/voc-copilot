import os
import sys
import json
import time
from pathlib import Path
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# STAGE 11: MONGODB CONFIGURATION
# =====================================================================
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["voc_database"]
feedback_collection = db["feedback"]
metrics_collection = db["metrics"]

# --- DYNAMIC GEMINI CLOUD ENGINE INITIALIZATION ---
AI_KEY = os.getenv("GEMINI_API_KEY")
if not AI_KEY:
    raise ValueError("❌ Environment Error: GEMINI_API_KEY environment variable is not set!")

ai_client = genai.Client(api_key=AI_KEY)

# =====================================================================
# STAGE 1: SEMANTIC DUPLICATE DETECTION (EMBEDDING & COSINE MATH)
# =====================================================================
DUPLICATE_THRESHOLD = 0.65
_embedding_model = None

def get_embedding_model():
    """Lazy-load the sentence-transformer model once and reuse it."""
    global _embedding_model
    if _embedding_model is None:
        print("📦 Loading sentence-transformer model (all-MiniLM-L6-v2)...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

def generate_embeddings_batch(texts):
    """Batch-encode all texts at once (not one-at-a-time in a loop)."""
    model = get_embedding_model()
    return model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

def calculate_cosine_similarity(vec1, vec2):
    if vec1 is None or vec2 is None:
        return 0.0
    return float(np.dot(vec1, vec2))

def debug_print_pairwise_similarities(records, embeddings, top_n=25):
    """Diagnostic only - prints highest scoring review pairs."""
    n = len(embeddings)
    pairs = []
    for i in range(n):
        for j in range(i):
            sim = float(np.dot(embeddings[i], embeddings[j]))
            pairs.append((sim, i, j))
    pairs.sort(reverse=True)

    print("\n" + "=" * 70)
    print(f"🔬 DEBUG: Top {top_n} most similar review pairs (out of {len(pairs)} total pairs)")
    print("=" * 70)
    for sim, i, j in pairs[:top_n]:
        text_i = records[i]["feedback_text"][:70]
        text_j = records[j]["feedback_text"][:70]
        print(f"  sim={sim:.3f}  |  [{i}] {text_i}")
        print(f"              |  [{j}] {text_j}")
    print("=" * 70)
    for t in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        count = sum(1 for sim, _, _ in pairs if sim >= t)
        print(f"  threshold {t:.2f} -> {count} pairs would match")
    print("=" * 70 + "\n")

# =====================================================================
# STAGE 2: CHUNK-BASED GEMINI ANALYSIS ENGINE
# =====================================================================
def analyze_chunk_with_gemini(chunk_texts):
    """Analyzes a smaller sub-batch of reviews to respect rate and context limits."""
    prompt = """
    You are an AI customer analytics system for a logistics and food delivery platform.
    Analyze the following array of CRITICAL customer reviews (1-star and 2-star ratings).
    
    For each review item, dynamically determine and extract:
    1. "category": A specific operational theme classification (e.g., 'Delivery Delays', 'Refund Tracking', 'Payment Errors', 'App Crashes', 'Food Integrity'). Do not use generic answers like 'Customer Support'.
    2. "sentiment": Analyze the raw emotional tone. Must be exactly one of: 'Positive', 'Neutral', or 'Negative'.
    3. "churn": Mark 'High Risk' if the text explicitly or implicitly mentions switching to competitors, uninstalling the app, or never ordering again. Otherwise, mark 'Low Risk'.
    4. "quote": Extract the most impactful exact phrase from the review text representing the core issue.
    5. "recommendation": Provide a specific, actionable product or operational recommendation to resolve this exact issue.
    
    Return a valid JSON array matching the EXACT length and sequential index order of the input array.
    Never output markdown code wrappers, explanations, or custom text outside this layout:
    [
      {
        "category": "Theme Name",
        "sentiment": "Positive/Neutral/Negative",
        "churn": "High Risk/Low Risk",
        "quote": "Extracted user quote text piece",
        "recommendation": "Tailored tactical solution recommendation text."
      }
    ]
    
    Data array:
    """ + json.dumps(chunk_texts)

    try:
        response = ai_client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"⚠️ Gemini Chunk Analysis Warning/Failure: {e}. Generating fallback values for this batch.")
        return [{
            "category": "General Support Queries",
            "sentiment": "Negative",
            "churn": "High Risk",
            "quote": t[:50],
            "recommendation": "Escalate to operational support."
        } for t in chunk_texts]

# =====================================================================
# END-TO-END PIPELINE PROCESSING
# =====================================================================
def process_single_file(file_path):
    # Wipe the workspace clean for active file upload session stream
    feedback_collection.delete_many({})
    metrics_collection.delete_many({})

    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".csv":
            df = pd.read_csv(file_path)
            print("CSV Loaded")
        elif suffix in (".xlsx", ".xls"):
            df = pd.read_excel(file_path, sheet_name=0)
            print(f"Excel Loaded ({suffix})")
        else:
            print(f"❌ Unsupported file type: {suffix or 'unknown'}. Expected .csv, .xlsx, or .xls")
            return
    except Exception as e:
        print(f"❌ Failed to parse data file stream: {e}")
        return

    # =====================================================================
    # STAGE 4: PREPROCESSING & COLUMN NORMALIZATION
    # =====================================================================
    df.columns = df.columns.str.strip()
    df = df.loc[:, ~df.columns.duplicated()]
    
    rename_map = {}
    for col in df.columns:
        c_clean = str(col).lower().replace("_", "").replace(" ", "").strip()
        if any(x in c_clean for x in ["feedback", "review", "comment", "message", "text"]):
            rename_map[col] = "feedback_text"
        elif any(x in c_clean for x in ["rating", "star", "score"]):
            rename_map[col] = "rating"
        elif any(x in c_clean for x in ["user", "name", "customer"]):
            rename_map[col] = "user"
        elif any(x in c_clean for x in ["timestamp", "date", "time"]):
            rename_map[col] = "timestamp"
        elif any(x in c_clean for x in ["source", "channel", "platform"]):
            rename_map[col] = "channel"

    df = df.rename(columns=rename_map)
    
    cleaned_records = []
    for row in df.to_dict(orient="records"):
        text = str(row.get("feedback_text", "")).strip()
        if not text or text.lower() == "nan" or "feedback_text" not in row:
            continue
        row["feedback_text"] = " ".join(text.split())
        cleaned_records.append(row)
        
    raw_feedback_received = len(cleaned_records)
    print(f"Reviews Cleaned. Total Raw Input Count: {raw_feedback_received}")

    if raw_feedback_received == 0:
        print("⚠️ Processing complete: Zero review records found.")
        return

    # =====================================================================
    # STAGE 1: SEMANTIC DEDUPLICATION ENGINE
    # =====================================================================
    unique_anchors = []
    seen_vectors = []
    duplicates_removed = 0
    
    batch_texts = [row["feedback_text"] for row in cleaned_records]
    batch_embeddings = generate_embeddings_batch(batch_texts)
    for row, vec in zip(cleaned_records, batch_embeddings):
        row["_vec"] = vec
    print("Embeddings Generated")

    if os.getenv("DEBUG_DEDUP") == "1":
        debug_print_pairwise_similarities(cleaned_records, batch_embeddings)

    for row in cleaned_records:
        current_vec = row["_vec"]
        is_duplicate = False
        
        for saved_vec in seen_vectors:
            similarity = calculate_cosine_similarity(current_vec, saved_vec)
            if similarity >= DUPLICATE_THRESHOLD:
                is_duplicate = True
                duplicates_removed += 1
                break
        
        if not is_duplicate:
            seen_vectors.append(current_vec)
            row.pop("_vec", None)
            unique_anchors.append(row)

    unique_customer_issues = len(unique_anchors)
    print(f"Deduplication Complete: {unique_customer_issues} unique, {duplicates_removed} duplicates.")

    if not unique_anchors:
        print("⚠️ Processing complete: Zero unique review elements left.")
        return

    # =====================================================================
    # STAGE 5: RATING FILTERING & SMART GEMINI TARGETING
    # =====================================================================
    # Filter 1-star & 2-star reviews for LLM analysis vs positive reviews
    critical_records = []
    non_critical_records = []

    for row in unique_anchors:
        raw_rating = row.get("rating")
        try:
            rating_val = int(float(raw_rating)) if pd.notna(raw_rating) and raw_rating != "" else 3
        except (ValueError, TypeError):
            rating_val = 3
            
        row["_parsed_rating"] = rating_val
        
        if rating_val <= 2:
            critical_records.append(row)
        else:
            non_critical_records.append(row)

    print(f"🎯 Rating Filter Applied: {len(critical_records)} critical reviews (1-2★) sent to AI, {len(non_critical_records)} positive/neutral reviews (3-5★) fast-tracked locally.")

    # Process CRITICAL records through Gemini in micro-chunks
    critical_texts = [r["feedback_text"] for r in critical_records]
    ai_critical_results = []
    chunk_size = 30

    if critical_texts:
        print(f"🚀 Processing {len(critical_texts)} critical complaints through Gemini in batches of {chunk_size}...")
        for i in range(0, len(critical_texts), chunk_size):
            chunk = critical_texts[i : i + chunk_size]
            chunk_res = analyze_chunk_with_gemini(chunk)
            ai_critical_results.extend(chunk_res)
            print(f"  └─ Processed critical batch {i // chunk_size + 1}/{(len(critical_texts) - 1) // chunk_size + 1}")
            time.sleep(1.0)

    # Attach Gemini analysis back to critical records
    for idx, row in enumerate(critical_records):
        row["_meta"] = ai_critical_results[idx] if idx < len(ai_critical_results) else {
            "category": "General Operational Issue",
            "sentiment": "Negative",
            "churn": "High Risk",
            "quote": row["feedback_text"][:50],
            "recommendation": "Investigate support escalation."
        }

    # Fast-track NON-CRITICAL (3-5 star) records locally without hitting Gemini
    for row in non_critical_records:
        r_val = row["_parsed_rating"]
        sentiment_label = "Positive" if r_val >= 4 else "Neutral"
        category_label = "Positive Feedback" if r_val >= 4 else "General Query"
        rec_label = "Maintain current service standards." if r_val >= 4 else "Monitor feedback trends."
        
        row["_meta"] = {
            "category": category_label,
            "sentiment": sentiment_label,
            "churn": "Low Risk",
            "quote": row["feedback_text"][:50],
            "recommendation": rec_label
        }

    # Recombine all records
    processed_records = critical_records + non_critical_records

    # =====================================================================
    # STAGE 6, 7 & 8: DASHBOARD METRICS CALCULATION
    # =====================================================================
    noise_reduction_percent = int((duplicates_removed / raw_feedback_received * 100)) if raw_feedback_received > 0 else 0
    
    positive_reviews = 0
    neutral_reviews = 0
    negative_reviews = 0
    high_churn_customers = 0
    
    theme_map = {}
    recommendations_list = []
    db_insert_list = []

    for row in processed_records:
        meta = row["_meta"]
        
        sent = meta.get("sentiment", "Neutral")
        if sent == "Positive": positive_reviews += 1
        elif sent == "Negative": negative_reviews += 1
        else: neutral_reviews += 1
        
        text_lower = row["feedback_text"].lower()
        is_churn_phrase = any(phrase in text_lower for phrase in [
            "switching to swiggy", "uninstalling", "never ordering again", 
            "will stop using zomato", "switch to swiggy", "delete app"
        ])
        if meta.get("churn") == "High Risk" or is_churn_phrase:
            high_churn_customers += 1

        theme_name = meta.get("category", "General Query")
        if theme_name not in theme_map:
            theme_map[theme_name] = {
                "theme_name": theme_name,
                "mention_count": 0,
                "representative_quote": meta.get("quote", row["feedback_text"]),
                "ai_recommendation": meta.get("recommendation", "Review operational metrics loop.")
            }
        theme_map[theme_name]["mention_count"] += 1

        db_insert_list.append({
            "feedback_text": row["feedback_text"],
            "user": str(row.get("user", "Anonymous")),
            "channel": str(row.get("channel", "Zomato Ingest")),
            "rating": row["_parsed_rating"],
            "timestamp": str(row.get("timestamp", "Recent")),
            "category": theme_name,
            "sentiment": sent,
            "quote": meta.get("quote", row["feedback_text"]),
            "recommendation": meta.get("recommendation", "N/A")
        })

    # Bulk insert feedback to MongoDB
    if db_insert_list:
        feedback_collection.insert_many(db_insert_list)

    themes_summary_list = list(theme_map.values())
    for t_name, t_data in theme_map.items():
        recommendations_list.append(t_data["ai_recommendation"])

    print("Dashboard Metrics Generated")

    # =====================================================================
    # STAGE 11: MONGODB BULK BLOCK EMISSION
    # =====================================================================
    metrics_payload = {
        "raw_feedback": raw_feedback_received,
        "unique_customer_issues": unique_customer_issues,
        "duplicates_removed": duplicates_removed,
        "noise_reduction_percent": noise_reduction_percent,
        "positive_reviews": positive_reviews,
        "neutral_reviews": neutral_reviews,
        "negative_reviews": negative_reviews,
        "high_churn_customers": high_churn_customers,
        "themes": themes_summary_list,
        "recommendations": recommendations_list
    }
    
    metrics_collection.insert_one(metrics_payload)
    print("MongoDB Metrics Document Updated Successfully.")

if __name__ == "__main__":
    pass