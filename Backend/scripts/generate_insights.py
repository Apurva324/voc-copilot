import os
import json
from pathlib import Path
from pymongo import MongoClient
import certifi
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
import numpy as np
import requests
import re
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# 1. MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client["voc_database"]
feedback_collection = db["feedback"]
insights_collection = db["insights"]

BASE_DIR = Path(__file__).resolve().parent.parent
INSIGHTS_JSON_PATH = BASE_DIR / "Data" / "Processed" / "product_insights.json"

print(" Loading local Semantic Embedding Model (all-MiniLM-L6-v2)...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def clean_json_string(raw_string):
    """Cleans up markdown code blocks or hidden spacing wrapping the JSON text."""
    clean_str = raw_string.strip()
    clean_str = re.sub(r'^```json\s*', '', clean_str, flags=re.IGNORECASE)
    clean_str = re.sub(r'^```\s*', '', clean_str)
    clean_str = re.sub(r'\s*```$', '', clean_str)
    return clean_str.strip()

def generate_semantic_insights():
    print(" Querying master feedback records from Atlas...")
    records = list(feedback_collection.find({}, {"_id": 0}))
    
    if len(records) < 5:
        print(" Not enough data points to calculate clusters. Need at least 5 records.")
        return

    texts = [str(r.get("feedback_text", "")) for r in records if r.get("feedback_text")]
    
    print(f" Converting {len(texts)} reviews into numerical vector embeddings...")
    embeddings = embedding_model.encode(texts)
    
    num_clusters = min(5, len(texts))
    print(f" Running K-Means clustering algorithm to isolate {num_clusters} core themes...")
    kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(embeddings)
    
    clustered_groups = {i: [] for i in range(num_clusters)}
    for idx, label in enumerate(cluster_labels):
        clustered_groups[label].append(records[idx])
        
    compiled_themes = []
    
    for cluster_id, cluster_records in clustered_groups.items():
        if not cluster_records:
            continue
            
        print(f"\n Analyzing Cluster #{cluster_id} containing {len(cluster_records)} signals...")
        
        sample_quotes = [r.get("feedback_text", "") for r in cluster_records[:3]]
        
        prompt = f"""
        You are an elite Product Strategy AI. Analyze these customer review samples belonging to the exact same semantic cluster problem.
        
        CRITICAL TEXT EVIDENCE:
        {json.dumps(sample_quotes, indent=2)}
        
        Generate a unified strategic breakdown for this cluster in JSON format matching this exact schema:
        {{
            "theme_name": "Short, clear title of the feature or problem (e.g., App Crashing & Payments)",
            "churn_risk": "HIGH", "MEDIUM", or "LOW",
            "roadmap_recommendation": "One specific, highly actionable architectural or process engineering resolution fix."
        }}
        Return ONLY valid raw JSON. Do not include markdown code blocks.
        """
        
        # Pull API Key safely
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        
        theme_obj = None
        
        try:
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2
            }
            
            response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            ai_res = response.json()["choices"][0]["message"]["content"]
            cleaned_res = clean_json_string(ai_res)
            parsed_res = json.loads(cleaned_res)
            
            theme_obj = {
                "theme_name": parsed_res.get("theme_name", f"Theme Category #{cluster_id}"),
                "count": len(cluster_records),
                "percentage": f"{round((len(cluster_records) / len(records)) * 100, 1)}%",
                "churn_risk": parsed_res.get("churn_risk", "MEDIUM"),
                "customer_quotes": sample_quotes,
                "roadmap_recommendation": parsed_res.get("roadmap_recommendation", "Investigate logs.")
            }
            print(f"Successfully compiled LLM Strategy for Cluster #{cluster_id}")
            
        except Exception as e:
            #  CRITICAL FALLBACK: If Groq fails/blocks you, build a structural card anyway so the UI updates
            print(f" LLM generation failed for cluster {cluster_id}: {e}")
            print(" Applying structural fallback layout...")
            
            theme_obj = {
                "theme_name": f"Algorithmic Theme Cluster #{cluster_id + 1}",
                "count": len(cluster_records),
                "percentage": f"{round((len(cluster_records) / len(records)) * 100, 1)}%",
                "churn_risk": "HIGH" if len(cluster_records) > 2 else "MEDIUM",
                "customer_quotes": sample_quotes,
                "roadmap_recommendation": f"Review the {len(cluster_records)} matching complaints clustered in this section."
            }
            
        if theme_obj:
            compiled_themes.append(theme_obj)
            
    # 5. Pack everything together and overwrite the final data payloads
    final_insight_payload = {
        "total_analyzed": len(records),
        "themes": compiled_themes
    }
    
    INSIGHTS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(INSIGHTS_JSON_PATH, "w") as f:
        json.dump(final_insight_payload, f, indent=4)
        
    insights_collection.delete_many({}) 
    insights_collection.insert_one(final_insight_payload)
    print("\n Database fully loaded with theme records.")

if __name__ == "__main__":
    generate_semantic_insights()