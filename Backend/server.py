import sys
import shutil
import os
import uuid
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks
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
# BACKGROUND WORKER: RUNS THE FULL PIPELINE WITHOUT BLOCKING THE REQUEST
# =====================================================================
def run_ingestion_pipeline(dataset_id: str, file_path: str, filename: str, file_size_kb: float, suffix: str):
    def progress_callback(chunk_idx, total_chunks):
        datasets_collection.update_one(
            {"dataset_id": dataset_id},
            {"$set": {
                "status": "Processing",
                "chunks_done": chunk_idx,
                "chunks_total": total_chunks
            }}
        )

    try:
        print(f"⚙️ [Background Worker] Starting pipeline for dataset {dataset_id}...")
        process_single_file(file_path, progress_callback=progress_callback)

        processed_count = feedback_collection.count_documents({})
        datasets_collection.update_one(
            {"dataset_id": dataset_id},
            {"$set": {
                "status": "Processed",
                "rows_processed": processed_count,
                "completed_at": datetime.utcnow().isoformat() + "Z"
            }}
        )
        print(f"✅ [Background Worker] Dataset {dataset_id} processed successfully.")
    except Exception as e:
        print(f"❌ [Background Worker Error] Failed processing dataset {dataset_id}: {e}")
        datasets_collection.update_one(
            {"dataset_id": dataset_id},
            {"$set": {
                "status": "Failed",
                "error_message": str(e),
                "completed_at": datetime.utcnow().isoformat() + "Z"
            }}
        )

# =====================================================================
# INGEST FEED & DATASET REGISTRATION (NON-BLOCKING)
# =====================================================================
@app.post("/api/upload")
async def import_feed(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only CSV or Excel (.xlsx, .xls) files allowed.")

    dataset_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{dataset_id}_{file.filename}"

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size_kb = round(os.path.getsize(file_path) / 1024, 2)
        print(f" 💾 Saved incoming file upload stream to: {file_path}")

        # Register the dataset as "Processing" immediately
        datasets_collection.update_one(
            {"filename": file.filename},
            {
                "$set": {
                    "dataset_id": dataset_id,
                    "filename": file.filename,
                    "file_size_kb": file_size_kb,
                    "uploaded_at": datetime.utcnow().isoformat() + "Z",
                    "status": "Processing",
                    "chunks_done": 0,
                    "chunks_total": None,
                    "format": suffix.replace(".", "").upper()
                }
            },
            upsert=True
        )

        # Hand off the actual (potentially long-running) pipeline to a background task
        background_tasks.add_task(
            run_ingestion_pipeline,
            dataset_id=dataset_id,
            file_path=str(file_path),
            filename=file.filename,
            file_size_kb=file_size_kb,
            suffix=suffix
        )

        # Respond immediately so the request never times out, regardless of dataset size
        return {
            "status": "processing",
            "dataset_id": dataset_id,
            "filename": file.filename,
            "size_kb": file_size_kb,
            "message": "File received. Processing in the background - poll /api/datasets/{dataset_id}/status for progress."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/datasets/{dataset_id}/status")
async def get_dataset_status(dataset_id: str):
    """Lightweight polling endpoint for the frontend to track long-running uploads."""
    record = datasets_collection.find_one({"dataset_id": dataset_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return record

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