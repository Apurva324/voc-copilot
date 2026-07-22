import sys
import shutil
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from scripts.auth import router as auth_router
from pymongo import MongoClient
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from scripts.normalise import process_single_file

app = FastAPI(title="Zomato VoC Copilot API")

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://voc-copilot.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register authentication routes under /api/auth
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

# Shared Ingestion Target Location
UPLOAD_DIR = BASE_DIR / "Data" / "Raw"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client["voc_database"]
feedback_collection = db["feedback"]
metrics_collection = db["metrics"]
datasets_collection = db["datasets"]

@app.get("/")
async def root():
    return {"status": "online"}

ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xls")

# =====================================================================
# INGEST FEED & DATASET REGISTRATION
# =====================================================================
@app.post("/api/upload")
async def import_feed(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only CSV or Excel (.xlsx, .xls) files allowed.")
    
    file_path = UPLOAD_DIR / file.filename
    try:
        # Save file stream to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        file_size_bytes = os.path.getsize(file_path)
        file_size_kb = round(file_size_bytes / 1024, 2)

        print(f" 💾 Saved incoming file upload stream to: {file_path}")
        
        # Run normalization pipeline
        process_single_file(file_path)

        # Count processed feedback rows for dataset log
        processed_count = feedback_collection.count_documents({})
        
        # Upsert dataset metadata record
        datasets_collection.update_one(
            {"filename": file.filename},
            {
                "$set": {
                    "filename": file.filename,
                    "file_size_kb": file_size_kb,
                    "uploaded_at": datetime.utcnow().isoformat() + "Z",
                    "rows_processed": processed_count,
                    "status": "Processed",
                    "format": suffix.replace(".", "").upper()
                }
            },
            upsert=True
        )

        return {"status": "success", "filename": file.filename, "size_kb": file_size_kb}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =====================================================================
# FETCH FEEDBACK RECORDS & SUMMARY METRICS
# =====================================================================
@app.get("/api/feedback")
async def get_feedback():
    return list(feedback_collection.find({}, {"_id": 0}))

@app.get("/api/feedback/summary")
async def get_summary():
    try:
        records = list(feedback_collection.find({}, {"_id": 0}))
        total = len(records)
        
        metrics_store = metrics_collection.find_one({}, {"_id": 0}) or {}
        noise_blocked = metrics_store.get("noise_blocked", 0)
        raw_volume = metrics_store.get("raw_stream_volume", total)

        cat_counts = {}
        ch_counts = {}
        for r in records:
            cat = r.get("category", "General Support Queries")
            ch = r.get("channel", "Unknown")
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            ch_counts[ch] = ch_counts.get(ch, 0) + 1

        return {
            "total": total,
            "totalRows": total,
            "raw_volume": raw_volume,
            "rawStreamVolume": raw_volume,
            "noise_blocked": noise_blocked,
            "redundantNoiseBlocked": noise_blocked,
            "categories": [{"name": k, "count": v, "percentage": round((v/total)*100) if total > 0 else 0} for k, v in cat_counts.items()],
            "channels": [{"name": k, "count": v, "percentage": round((v/total)*100) if total > 0 else 0} for k, v in ch_counts.items()]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard-metrics")
async def get_dashboard_metrics():
    latest_metrics = metrics_collection.find_one(sort=[("_id", -1)])
    if not latest_metrics:
        raise HTTPException(status_code=404, detail="No pipeline metrics generated yet.")
    
    latest_metrics["_id"] = str(latest_metrics["_id"])
    return latest_metrics

@app.get("/api/insights")
def get_insights(category: str = Query(None)):
    latest_metrics = metrics_collection.find_one(sort=[("_id", -1)])
    if not latest_metrics or "themes" not in latest_metrics:
        return []
        
    themes = latest_metrics["themes"]
    
    if category:
        matched = [t for t in themes if t["theme_name"].lower() == category.lower()]
        return matched if matched else []
        
    return themes

# =====================================================================
# RISK VELOCITY ROUTE
# =====================================================================
@app.get("/api/risk-velocity")
async def get_risk_velocity(aggregation: str = Query("daily")):
    records = list(feedback_collection.find({}, {"_id": 0}))
    if not records:
        return []

    time_buckets = defaultdict(list)

    for item in records:
        raw_ts = item.get("timestamp")
        if not raw_ts:
            continue

        try:
            ts_str = str(raw_ts).replace("Z", "")
            dt = datetime.fromisoformat(ts_str)
        except ValueError:
            continue

        if aggregation == "hourly":
            label = dt.strftime("%I:00 %p")
        elif aggregation == "weekly":
            label = f"Week {dt.isocalendar()[1]}"
        else:
            label = dt.strftime("%b %d")

        time_buckets[label].append(item)

    velocity_data = []
    max_count = 0

    for label, items in time_buckets.items():
        count = len(items)
        if count > max_count:
            max_count = count

        categories = [it.get("category") for it in items if it.get("category")]
        top_categories = list(dict.fromkeys(categories))[:3] if categories else ["General Issue"]

        quotes = [it.get("feedback_text") or it.get("quote") for it in items if it.get("feedback_text") or it.get("quote")]
        top_quotes = quotes[:2] if quotes else ["No detailed quote recorded."]

        velocity_data.append({
            "timeLabel": label,
            "count": count,
            "isPeak": False,
            "topCategories": top_categories,
            "topQuotes": top_quotes
        })

    for point in velocity_data:
        if max_count > 0 and point["count"] == max_count:
            point["isPeak"] = True

    return velocity_data

# =====================================================================
# DATASET MANAGEMENT ROUTES
# =====================================================================
@app.get("/api/datasets")
async def get_datasets():
    """Returns list of all uploaded datasets and their metadata logs."""
    datasets = list(datasets_collection.find({}, {"_id": 0}))
    return datasets

@app.delete("/api/datasets/{filename}")
async def delete_dataset(filename: str):
    """Deletes metadata entry and file from storage."""
    datasets_collection.delete_one({"filename": filename})
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        os.remove(file_path)
    return {"status": "deleted", "filename": filename}