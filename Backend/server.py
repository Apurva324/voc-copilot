import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, BackgroundTask, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient

# Import the core pipeline processor from scripts/normalise.py
from scripts.normalise import process_single_file

load_dotenv()

# =====================================================================
# MONGODB & APP CONFIGURATION
# =====================================================================
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("❌ Environment Error: MONGO_URI is not set in environment!")

client = MongoClient(MONGO_URI)
db = client["voc_database"]
datasets_collection = db["datasets"]

app = FastAPI(title="Voice of Customer API Engine", version="2.0")

# Enable CORS for React / Next.js frontend calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory to temporarily stage uploaded files for ingestion
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# =====================================================================
# BACKGROUND WORKER TASK
# =====================================================================
def run_ingestion_pipeline(dataset_id: str, file_path: str):
    """
    Executes the ingestion and LLM pipeline asynchronously in the background.
    Updates MongoDB dataset status on success or failure.
    """
    try:
        print(f"⚙️ [Background Worker] Starting pipeline for dataset {dataset_id}...")
        
        # Execute the core normalization, deduplication, and Gemini analysis
        process_single_file(file_path)
        
        # Update status in datasets collection to Processed
        datasets_collection.update_one(
            {"dataset_id": dataset_id},
            {
                "$set": {
                    "status": "Processed",
                    "completed_at": datetime.utcnow().isoformat()
                }
            }
        )
        print(f"✅ [Background Worker] Dataset {dataset_id} processed successfully.")
        
    except Exception as e:
        print(f"❌ [Background Worker Error] Failed processing dataset {dataset_id}: {e}")
        datasets_collection.update_one(
            {"dataset_id": dataset_id},
            {
                "$set": {
                    "status": "Failed",
                    "error_message": str(e),
                    "completed_at": datetime.utcnow().isoformat()
                }
            }
        )
    finally:
        # Cleanup temporary uploaded file from local disk
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"🧹 Staged file cleaned up: {file_path}")
            except Exception as cleanup_err:
                print(f"⚠️ Could not delete staged file {file_path}: {cleanup_err}")

# =====================================================================
# API ENDPOINTS
# =====================================================================

@app.post("/api/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Handles CSV/Excel file uploads.
    Saves file, registers dataset as 'Processing...', and delegates pipeline 
    execution to a background task for immediate response (<1 sec).
    """
    filename = file.filename
    suffix = Path(filename).suffix.lower()

    if suffix not in [".csv", ".xlsx", ".xls"]:
        raise HTTPException(
            status_code=400, 
            detail="Unsupported file type. Please upload a .csv, .xlsx, or .xls file."
        )

    # Generate a unique ID and file path
    dataset_id = str(uuid.uuid4())
    staged_filename = f"{dataset_id}_{filename}"
    staged_file_path = UPLOAD_DIR / staged_filename

    # Save file stream to local storage
    try:
        with open(staged_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Create dataset tracking entry in MongoDB
    dataset_record = {
        "dataset_id": dataset_id,
        "filename": filename,
        "status": "Processing...",
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None
    }
    datasets_collection.insert_one(dataset_record)

    # Hand off processing to BackgroundTasks (non-blocking)
    background_tasks.add_task(
        run_ingestion_pipeline, 
        dataset_id=dataset_id, 
        file_path=str(staged_file_path)
    )

    # Return instant HTTP 200 response
    return {
        "message": "File received! Pipeline is processing dataset in background.",
        "dataset_id": dataset_id,
        "status": "Processing..."
    }

@app.get("/api/datasets")
def get_datasets():
    """Returns status of all datasets for UI status tracking."""
    datasets = list(datasets_collection.find({}, {"_id": 0}).sort("created_at", -1))
    return {"datasets": datasets}

@app.get("/health")
def health_check():
    """Simple API health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)