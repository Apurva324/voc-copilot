import os
import sys
import json
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
# Similarity threshold for the sentence-transformer embedding space.
# This is NOT the same scale as character n-gram overlap. For SHORT,
# paraphrased reviews (different words, same complaint - e.g. "refund is
# still pending" vs "still waiting for my refund"), MiniLM cosine scores
# often land lower than you'd expect - commonly 0.55-0.70 - while truly
# unrelated reviews sit below 0.4.
# DO NOT trust this number blind. Run once with DEBUG_DEDUP=1, read the
# printed pairs + threshold sweep, and set this to just below where your
# real duplicate pairs cluster.
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
    """Batch-encode all texts at once (not one-at-a-time in a loop).
    Embeddings are L2-normalized, so cosine similarity == dot product."""
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
    """
    Diagnostic only - not part of the dedup decision.
    Prints the highest-scoring review pairs so you can see the REAL
    similarity distribution in your data and pick a threshold that
    actually matches it, instead of guessing a number blind.
    Enable with: DEBUG_DEDUP=1 as an environment variable.
    """
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
    # Quick threshold sweep so you can see how many duplicates each cutoff would produce
    for t in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        count = sum(1 for sim, _, _ in pairs if sim >= t)
        print(f"  threshold {t:.2f} -> {count} pairs would match")
    print("=" * 70 + "\n")

# =====================================================================
# END-TO-END PIPELINE PROCESSING
# =====================================================================
def process_single_file(file_path):
    # Wipe the workspace clean for the active file upload session stream
    feedback_collection.delete_many({})
    metrics_collection.delete_many({})

    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    try:
        if suffix == ".csv":
            df = pd.read_csv(file_path)
            print("CSV Loaded")
        elif suffix in (".xlsx", ".xls"):
            # requires openpyxl for .xlsx (pip install openpyxl)
            df = pd.read_excel(file_path, sheet_name=0)
            print(f"Excel Loaded ({suffix})")
        else:
            print(f"❌ Unsupported file type: {suffix or 'unknown'}. Expected .csv, .xlsx, or .xls")
            return
    except Exception as e:
        print(f"❌ Failed to parse data file stream: {e}")
        return

    # =====================================================================
    # STAGE 4: IMPROVE PREPROCESSING
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
    print("Reviews Cleaned")

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

    # --- DIAGNOSTIC: inspect the real similarity distribution ---
    # Set DEBUG_DEDUP=1 to see the top pairwise scores and a threshold
    # sweep. Use this to pick DUPLICATE_THRESHOLD empirically for your
    # actual data instead of guessing a number blind.
    if os.getenv("DEBUG_DEDUP") == "1":
        debug_print_pairwise_similarities(cleaned_records, batch_embeddings)

    for row in cleaned_records:
        current_vec = row["_vec"]
        is_duplicate = False
        
        for saved_vec in seen_vectors:
            similarity = calculate_cosine_similarity(current_vec, saved_vec)
            # Sentence-embedding cutoff - tuned for MiniLM's cosine scale,
            # not the old character n-gram scale
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
    # STAGE 2 & 5: GEMINI ANALYSIS VIA CHUNKED BATCH CALLS
    # =====================================================================
    # A single prompt containing thousands of reviews doesn't scale - it risks
    # hitting context/token limits, is fragile (one failure loses everything),
    # and LLMs return more reliable structured JSON on smaller batches.
    # Instead, we chunk the unique reviews and call Gemini once per chunk,
    # then stitch all the results back together in original order.
    import time

    pure_texts = [r["feedback_text"] for r in unique_anchors]

    GEMINI_BATCH_SIZE = 15   # reviews per Gemini call - keeps prompts small & reliable
    MAX_RETRIES = 3

    def build_prompt(batch_texts):
        return """
        You are an AI customer analytics system for a logistics and food delivery platform.
        Analyze the following array of UNIQUE customer reviews.

        For each review item, dynamically determine and extract:
        1. "category": A specific operational theme classification (e.g., 'Delivery Delays', 'Refund Tracking', 'Payment Errors', 'App Crashes', 'Food Integrity'). Do not use generic answers like 'Customer Support'.
        2. "sentiment": Analyze the raw emotional tone. Must be exactly one of: 'Positive', 'Neutral', or 'Negative'.
        3. "churn": Mark 'High Risk' if the text explicitly or implicitly mentions switching to competitors, uninstalling the app, or never ordering again. Otherwise, mark 'Low Risk'.
        4. "quote": Extract the most impactful exact phrase from the review text representing the core issue.
        5. "recommendation": Provide a specific, actionable product or operational recommendation to resolve this exact issue.

        Return a valid JSON array matching the EXACT length and sequential index order of the input array.
        Never output markdown code wrappers (like ```json), explanations, or custom text outside this layout:
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
        """ + json.dumps(batch_texts)

    def classify_chunk(batch_texts):
        """Call Gemini for a single chunk, with retry on transient errors.
        Falls back to neutral placeholders for this chunk only if it never
        succeeds, so one bad chunk can't take down the whole pipeline."""
        for attempt in range(MAX_RETRIES):
            try:
                response = ai_client.models.generate_content(
                    model='gemini-3.5-flash',
                    contents=build_prompt(batch_texts),
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    ),
                )
                parsed = json.loads(response.text)
                if isinstance(parsed, list) and len(parsed) == len(batch_texts):
                    return parsed
                print(f"⚠️ Chunk returned mismatched length ({len(parsed)} vs {len(batch_texts)}), retrying...")
            except Exception as e:
                is_transient = "503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                if is_transient and attempt < MAX_RETRIES - 1:
                    delay = 2 ** attempt
                    print(f"⚠️ Gemini chunk call failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                print(f"❌ Gemini chunk call failed after {attempt + 1} attempt(s): {e}")
                break

        # Fallback for just this chunk - pipeline keeps going for everything else
        return [
            {
                "category": "General Support",
                "sentiment": "Neutral",
                "churn": "Low Risk",
                "quote": text[:80],
                "recommendation": "AI analysis unavailable for this batch - review manually."
            }
            for text in batch_texts
        ]

    ai_analysis = []
    total_chunks = (len(pure_texts) + GEMINI_BATCH_SIZE - 1) // GEMINI_BATCH_SIZE
    for chunk_idx, i in enumerate(range(0, len(pure_texts), GEMINI_BATCH_SIZE), start=1):
        batch = pure_texts[i:i + GEMINI_BATCH_SIZE]
        print(f"🚀 Processing Gemini chunk {chunk_idx}/{total_chunks} ({len(batch)} reviews)...")
        ai_analysis.extend(classify_chunk(batch))

    print(f"🚀 Gemini Dynamic Parsing Engine Analysis Complete. ({len(ai_analysis)} reviews classified across {total_chunks} chunks)")

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

    for idx, row in enumerate(unique_anchors):
        meta = ai_analysis[idx] if idx < len(ai_analysis) else {
            "category": "General Support", "sentiment": "Neutral", "churn": "Low Risk", 
            "quote": row["feedback_text"][:50], "recommendation": "Monitor stream."
        }
        
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

        # Check for float 'NaN' or missing data structures safely
        raw_rating = row.get("rating")
        if pd.isna(raw_rating) or raw_rating == "" or raw_rating is None:
            rating_content = 3
        else:
            try:
                rating_content = int(float(raw_rating))
            except (ValueError, TypeError):
                rating_content = 3

        feedback_collection.insert_one({
            "feedback_text": row["feedback_text"],
            "user": str(row.get("user", "Anonymous")),
            "channel": str(row.get("channel", "Zomato Ingest")),
            "rating": rating_content,
            "timestamp": str(row.get("timestamp", "Recent")),
            "category": theme_name,
            "sentiment": sent,
            "quote": meta.get("quote", row["feedback_text"]),
            "recommendation": meta.get("recommendation", "N/A")
        })

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