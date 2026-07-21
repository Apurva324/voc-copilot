import os
from datetime import datetime
from pymongo import MongoClient
from sentence_transformers import SentenceTransformer

# Initialize the embedding model globally so it stays warm in memory
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

def ingest_feedback_with_deduplication(feedback_collection, raw_text: str, customer_name: str, channel: str, rating: int, timestamp: str):
    """
    Ingests a raw review, checks the Atlas Vector Search Index for a near-match,
    and deduplicates or inserts accordingly.
    """
    if not raw_text.strip():
        return "SKIPPED"

    # 1. Generate local vector embedding
    vector = embedding_model.encode(raw_text).tolist()
    
    # 2. Query MongoDB Atlas Vector Index for the closest match
    pipeline = [
        {
            "$vectorSearch": {
                "index": "vector_index",
                "path": "embedding",
                "queryVector": vector,
                "numCandidates": 5,
                "limit": 1
            }
        },
        {
            "$project": {
                "feedback_text": 1,
                "impact_count": 1,
                "score": {"$meta": "vectorSearchScore"}
            }
        }
    ]
    
    try:
        results = list(feedback_collection.aggregate(pipeline))
        MATCH_THRESHOLD = 0.93  # Threshold for intercepting near-duplicate text
        
        if results and results[0]["score"] >= MATCH_THRESHOLD:
            matched_doc = results[0]
            
            # Semantic match found! Increment counter and log structural metadata
            feedback_collection.update_one(
                {"_id": matched_doc["_id"]},
                {
                    "$set": {"impact_count": matched_doc.get("impact_count", 1) + 1},
                    "$push": {
                        "meta_logs": {
                            "customer_name": customer_name,
                            "channel": channel,
                            "rating": rating,
                            "timestamp": timestamp or datetime.utcnow().isoformat()
                        }
                    }
                }
            )
            return "UPDATED"
            
        else:
            # New unique user issue discovered. Store baseline anchor node
            new_doc = {
                "feedback_text": raw_text,
                "customer_name": customer_name,
                "channel": channel,
                "rating": rating,
                "timestamp": timestamp,
                "embedding": vector,
                "impact_count": 1,
                "meta_logs": [{
                    "customer_name": customer_name,
                    "channel": channel,
                    "rating": rating,
                    "timestamp": timestamp or datetime.utcnow().isoformat()
                }]
            }
            feedback_collection.insert_one(new_doc)
            return "INSERTED"
            
    except Exception as e:
        print(f"Deduplication failure: {e}")
        return "FAILED"