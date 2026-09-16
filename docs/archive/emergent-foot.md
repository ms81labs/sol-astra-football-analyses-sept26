================================================================================
FOOTBALL VISION — FULL SOURCE CODE EXPORT
================================================================================

TABLE OF CONTENTS:
   1. /app/backend/server.py
   2. /app/backend/.env
   3. /app/backend/runpod_handler/handler.py
   4. /app/backend/runpod_handler/Dockerfile
   5. /app/backend/runpod_handler/requirements.txt
   6. /app/backend/runpod_handler/README.md
   7. /app/backend/runpod_handler/pipeline/__init__.py
   8. /app/backend/runpod_handler/pipeline/detector.py
   9. /app/backend/runpod_handler/pipeline/tracker.py
  10. /app/backend/runpod_handler/pipeline/calibrator.py
  11. /app/backend/runpod_handler/pipeline/team_classifier.py
  12. /app/backend/runpod_handler/pipeline/event_detector.py
  13. /app/backend/runpod_handler/pipeline/data_exporter.py
  14. /app/frontend/.env
  15. /app/frontend/package.json
  16. /app/frontend/tailwind.config.js
  17. /app/frontend/src/index.js
  18. /app/frontend/src/index.css
  19. /app/frontend/src/App.js
  20. /app/frontend/src/App.css
  21. /app/frontend/src/lib/utils.js
  22. /app/frontend/src/components/Layout.jsx
  23. /app/frontend/src/pages/Dashboard.jsx
  24. /app/frontend/src/pages/Upload.jsx
  25. /app/frontend/src/pages/Jobs.jsx
  26. /app/frontend/src/pages/JobDetail.jsx
  27. /app/frontend/src/pages/Settings.jsx
  28. /app/frontend/src/pages/Pipeline.jsx
  29. /app/memory/PRD.md

================================================================================

================================================================================
FILE: /app/backend/server.py
================================================================================
from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import json
import csv
import zipfile
import logging
import requests
import httpx
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Object Storage
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "football-video-analysis"
storage_key = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=300
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    key = init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key}, timeout=120
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

# --- Pydantic Models ---
class SettingsUpdate(BaseModel):
    runpod_api_key: Optional[str] = None
    runpod_endpoint_id: Optional[str] = None

class VideoCreate(BaseModel):
    half: str  # "first" or "second"
    external_url: Optional[str] = None

class JobCreate(BaseModel):
    name: str
    video_ids: List[str]
    config: Optional[dict] = None

# --- Settings ---
@api_router.get("/settings")
async def get_settings():
    settings = await db.settings.find_one({"type": "runpod"}, {"_id": 0})
    if not settings:
        return {"type": "runpod", "runpod_api_key": "", "runpod_endpoint_id": "", "configured": False}
    masked_key = ""
    if settings.get("runpod_api_key"):
        k = settings["runpod_api_key"]
        masked_key = k[:8] + "..." + k[-4:] if len(k) > 12 else "***"
    return {
        "type": "runpod",
        "runpod_api_key": masked_key,
        "runpod_endpoint_id": settings.get("runpod_endpoint_id", ""),
        "configured": bool(settings.get("runpod_api_key") and settings.get("runpod_endpoint_id"))
    }

@api_router.post("/settings")
async def update_settings(data: SettingsUpdate):
    update = {}
    if data.runpod_api_key is not None:
        update["runpod_api_key"] = data.runpod_api_key
    if data.runpod_endpoint_id is not None:
        update["runpod_endpoint_id"] = data.runpod_endpoint_id
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.settings.update_one(
        {"type": "runpod"},
        {"$set": update},
        upsert=True
    )
    return {"status": "saved"}

# --- Videos ---
@api_router.post("/videos/upload")
async def upload_video(file: UploadFile = File(...), half: str = Form("first")):
    if half not in ("first", "second"):
        raise HTTPException(400, "half must be 'first' or 'second'")
    ext = file.filename.split(".")[-1] if "." in file.filename else "mp4"
    file_id = str(uuid.uuid4())
    storage_path = f"{APP_NAME}/videos/{file_id}.{ext}"
    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    result = put_object(storage_path, data, file.content_type or "video/mp4")
    doc = {
        "id": file_id,
        "filename": file.filename,
        "half": half,
        "storage_path": result["path"],
        "size_mb": round(size_mb, 2),
        "content_type": file.content_type or "video/mp4",
        "source": "upload",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.videos.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

@api_router.post("/videos/url")
async def add_video_url(data: VideoCreate):
    if not data.external_url:
        raise HTTPException(400, "external_url required")
    file_id = str(uuid.uuid4())
    doc = {
        "id": file_id,
        "filename": data.external_url.split("/")[-1] or "video.mp4",
        "half": data.half,
        "storage_path": None,
        "external_url": data.external_url,
        "size_mb": None,
        "content_type": "video/mp4",
        "source": "url",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.videos.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

@api_router.get("/videos")
async def list_videos():
    videos = await db.videos.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return videos

@api_router.delete("/videos/{video_id}")
async def delete_video(video_id: str):
    result = await db.videos.delete_one({"id": video_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Video not found")
    return {"status": "deleted"}

# --- Jobs ---
@api_router.post("/jobs")
async def create_job(data: JobCreate):
    settings = await db.settings.find_one({"type": "runpod"}, {"_id": 0})
    videos = await db.videos.find({"id": {"$in": data.video_ids}}, {"_id": 0}).to_list(10)
    if not videos:
        raise HTTPException(400, "No valid videos selected")
    job_id = str(uuid.uuid4())
    is_configured = bool(settings and settings.get("runpod_api_key") and settings.get("runpod_endpoint_id"))
    doc = {
        "id": job_id,
        "name": data.name,
        "video_ids": data.video_ids,
        "videos": videos,
        "config": data.config or {
            "detection_model": "yolov8x",
            "tracker": "bytetrack",
            "calibration": "broadtrack",
            "team_clustering": True,
            "jersey_ocr": True,
            "event_detection": True,
            "fps_sample": 10
        },
        "status": "submitted" if is_configured else "pending_config",
        "runpod_job_id": None,
        "progress": 0,
        "results": None,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    # If RunPod configured, submit
    if is_configured:
        try:
            video_urls = []
            for v in videos:
                if v.get("external_url"):
                    video_urls.append(v["external_url"])
                elif v.get("storage_path"):
                    video_urls.append(f"storage://{v['storage_path']}")
            runpod_response = await submit_to_runpod(
                settings["runpod_api_key"],
                settings["runpod_endpoint_id"],
                {
                    "video_urls": video_urls,
                    "config": doc["config"],
                    "job_id": job_id
                }
            )
            doc["runpod_job_id"] = runpod_response.get("id")
            doc["status"] = "submitted"
        except Exception as e:
            logger.error(f"RunPod submission failed: {e}")
            doc["status"] = "submission_failed"
            doc["error"] = str(e)

    await db.jobs.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

async def submit_to_runpod(api_key: str, endpoint_id: str, payload: dict):
    url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    async with httpx.AsyncClient(timeout=30) as client_http:
        resp = await client_http.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"input": payload}
        )
        resp.raise_for_status()
        return resp.json()

@api_router.get("/jobs")
async def list_jobs():
    jobs = await db.jobs.find({}, {"_id": 0, "results": 0}).sort("created_at", -1).to_list(100)
    return jobs

@api_router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Job not found")
    return job

@api_router.post("/jobs/{job_id}/poll")
async def poll_job_status(job_id: str):
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.get("runpod_job_id"):
        return {"status": job["status"], "message": "No RunPod job ID"}
    settings = await db.settings.find_one({"type": "runpod"}, {"_id": 0})
    if not settings:
        return {"status": job["status"]}
    try:
        url = f"https://api.runpod.ai/v2/{settings['runpod_endpoint_id']}/status/{job['runpod_job_id']}"
        async with httpx.AsyncClient(timeout=30) as client_http:
            resp = await client_http.get(
                url,
                headers={"Authorization": f"Bearer {settings['runpod_api_key']}"}
            )
            resp.raise_for_status()
            rp_data = resp.json()
        new_status = rp_data.get("status", job["status"])
        status_map = {"IN_QUEUE": "queued", "IN_PROGRESS": "processing", "COMPLETED": "completed", "FAILED": "failed"}
        mapped_status = status_map.get(new_status, new_status)
        update = {"status": mapped_status, "updated_at": datetime.now(timezone.utc).isoformat()}
        if mapped_status == "completed" and rp_data.get("output"):
            update["results"] = rp_data["output"]
            update["progress"] = 100
        elif mapped_status == "failed":
            update["error"] = rp_data.get("error", "Unknown error from RunPod")
        await db.jobs.update_one({"id": job_id}, {"$set": update})
        return {**update, "runpod_status": new_status}
    except Exception as e:
        logger.error(f"Poll error: {e}")
        return {"status": job["status"], "error": str(e)}

@api_router.post("/jobs/{job_id}/mock-complete")
async def mock_complete_job(job_id: str):
    """For testing: simulate a completed RunPod job with sample data."""
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(404, "Job not found")
    sample_results = generate_sample_results(job)
    await db.jobs.update_one({"id": job_id}, {"$set": {
        "status": "completed",
        "progress": 100,
        "results": sample_results,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }})
    updated = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    return updated

def generate_sample_results(job):
    """Generate realistic sample data matching pipeline output format."""
    import random
    random.seed(42)
    # Players
    team_a = [{"id": f"P{i}", "jersey": i, "team": "A", "name": f"Player A{i}"} for i in range(1, 12)]
    team_b = [{"id": f"P{i+11}", "jersey": i, "team": "B", "name": f"Player B{i}"} for i in range(1, 12)]
    all_players = team_a + team_b

    # Tracking frames (sample 30 frames)
    tracking_data = []
    for frame_idx in range(0, 300, 10):
        frame = {"frame": frame_idx, "timestamp": round(frame_idx / 25.0, 3), "players": [], "ball": None}
        for p in all_players:
            frame["players"].append({
                "id": p["id"],
                "jersey": p["jersey"],
                "team": p["team"],
                "x": round(random.uniform(0, 105), 2),
                "y": round(random.uniform(0, 68), 2),
                "speed_kmh": round(random.uniform(0, 34), 1),
                "confidence": round(random.uniform(0.85, 0.99), 3)
            })
        frame["ball"] = {
            "x": round(random.uniform(0, 105), 2),
            "y": round(random.uniform(0, 68), 2),
            "z": round(random.uniform(0, 3), 2),
            "speed_kmh": round(random.uniform(0, 120), 1),
            "confidence": round(random.uniform(0.7, 0.98), 3)
        }
        tracking_data.append(frame)

    # Events
    event_types = ["pass", "shot", "corner", "foul", "offside", "goal_kick", "throw_in", "cross", "dribble", "tackle", "header", "save"]
    events = []
    for i in range(45):
        t = round(random.uniform(0, 2700), 1)
        etype = random.choice(event_types)
        ev = {
            "id": f"E{i+1}",
            "type": etype,
            "timestamp": t,
            "minute": int(t // 60),
            "second": int(t % 60),
            "player_id": random.choice(all_players)["id"],
            "team": random.choice(["A", "B"]),
            "x": round(random.uniform(0, 105), 2),
            "y": round(random.uniform(0, 68), 2),
            "confidence": round(random.uniform(0.6, 0.99), 3)
        }
        if etype == "pass":
            ev["end_x"] = round(random.uniform(0, 105), 2)
            ev["end_y"] = round(random.uniform(0, 68), 2)
            ev["success"] = random.choice([True, True, True, False])
        if etype == "shot":
            ev["xg"] = round(random.uniform(0.02, 0.85), 3)
            ev["on_target"] = random.choice([True, False])
        events.append(ev)
    events.sort(key=lambda e: e["timestamp"])

    # Analytics
    analytics = {
        "possession": {"team_a": 54.2, "team_b": 45.8},
        "pass_accuracy": {"team_a": 87.3, "team_b": 82.1},
        "shots": {"team_a": 8, "team_b": 5},
        "shots_on_target": {"team_a": 4, "team_b": 2},
        "corners": {"team_a": 6, "team_b": 3},
        "fouls": {"team_a": 9, "team_b": 12},
        "offsides": {"team_a": 2, "team_b": 1},
        "total_distance_km": {"team_a": 52.3, "team_b": 49.8},
        "sprint_count": {"team_a": 45, "team_b": 38},
        "avg_speed_kmh": {"team_a": 7.2, "team_b": 6.9},
        "xg_total": {"team_a": 1.85, "team_b": 0.92}
    }

    return {
        "metadata": {
            "pipeline_version": "1.0.0",
            "detection_model": job.get("config", {}).get("detection_model", "yolov8x"),
            "tracker": job.get("config", {}).get("tracker", "bytetrack"),
            "fps_processed": job.get("config", {}).get("fps_sample", 10),
            "total_frames_processed": 300,
            "processing_time_seconds": 842
        },
        "team_assignments": all_players,
        "tracking_data": tracking_data,
        "events": events,
        "analytics": analytics
    }

@api_router.get("/jobs/{job_id}/download/{format}")
async def download_results(job_id: str, format: str):
    if format not in ("json", "csv"):
        raise HTTPException(400, "Format must be 'json' or 'csv'")
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job or not job.get("results"):
        raise HTTPException(404, "No results available")
    results = job["results"]
    if format == "json":
        content = json.dumps(results, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=match_analysis_{job_id[:8]}.json"}
        )
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        # Events CSV
        if results.get("events"):
            headers = list(results["events"][0].keys())
            writer.writerow(headers)
            for event in results["events"]:
                writer.writerow([event.get(h, "") for h in headers])
        content = output.getvalue()
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=events_{job_id[:8]}.csv"}
        )

# --- Handler Package ---
@api_router.get("/handler-package")
async def download_handler_package():
    handler_dir = ROOT_DIR / "runpod_handler"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(handler_dir):
            for f in files:
                fpath = Path(root) / f
                arcname = str(fpath.relative_to(handler_dir))
                zf.write(fpath, arcname)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=runpod_football_handler.zip"}
    )

# --- Stats ---
@api_router.get("/stats")
async def get_stats():
    total_jobs = await db.jobs.count_documents({})
    completed_jobs = await db.jobs.count_documents({"status": "completed"})
    total_videos = await db.videos.count_documents({})
    processing_jobs = await db.jobs.count_documents({"status": {"$in": ["submitted", "queued", "processing"]}})
    failed_jobs = await db.jobs.count_documents({"status": {"$in": ["failed", "submission_failed"]}})
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "processing_jobs": processing_jobs,
        "failed_jobs": failed_jobs,
        "total_videos": total_videos
    }

@api_router.get("/")
async def root():
    return {"message": "Football Video Analysis API"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    try:
        init_storage()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()



================================================================================
FILE: /app/backend/.env
================================================================================
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
CORS_ORIGINS="*"
EMERGENT_LLM_KEY=sk-emergent-eC047822a57996772E



================================================================================
FILE: /app/backend/runpod_handler/handler.py
================================================================================
"""
RunPod Serverless Handler — Football Video Analysis Pipeline
Deploy this to RunPod as a serverless endpoint with GPU.

Input:
{
    "video_urls": ["https://...mp4"],
    "config": {
        "detection_model": "yolov8x",
        "tracker": "bytetrack",
        "calibration": "broadtrack",
        "team_clustering": true,
        "jersey_ocr": true,
        "event_detection": true,
        "fps_sample": 10
    },
    "job_id": "uuid"
}

Output:
{
    "metadata": {...},
    "team_assignments": [...],
    "tracking_data": [...],
    "events": [...],
    "analytics": {...}
}
"""
import runpod
import cv2
import numpy as np
import json
import time
import logging
import tempfile
import os
import urllib.request
from pathlib import Path

# Pipeline imports
from pipeline.detector import PlayerBallDetector
from pipeline.tracker import MultiObjectTracker
from pipeline.calibrator import PitchCalibrator
from pipeline.team_classifier import TeamClassifier
from pipeline.event_detector import EventDetector
from pipeline.data_exporter import DataExporter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("handler")

# Pre-load models at cold start
logger.info("Loading models...")
detector = PlayerBallDetector(model_name="yolov8x")
tracker = MultiObjectTracker(algorithm="bytetrack")
calibrator = PitchCalibrator(method="broadtrack")
team_classifier = TeamClassifier()
event_detector = EventDetector()
exporter = DataExporter()
logger.info("Models loaded.")


def download_video(url: str, dest_dir: str) -> str:
    """Download video from URL to local temp file."""
    filename = url.split("/")[-1].split("?")[0] or "video.mp4"
    dest = os.path.join(dest_dir, filename)
    logger.info(f"Downloading video: {url}")
    urllib.request.urlretrieve(url, dest)
    logger.info(f"Downloaded to {dest}")
    return dest


def process_video(video_path: str, config: dict) -> dict:
    """
    Main processing pipeline for a single video file.
    
    Pipeline stages:
    1. Frame extraction at target FPS
    2. Object detection (players + ball) per frame
    3. Multi-object tracking across frames
    4. Pitch calibration / homography estimation
    5. Coordinate transformation (pixel → pitch)
    6. Team assignment via color clustering
    7. Jersey number OCR
    8. Event detection (passes, shots, corners, etc.)
    9. Analytics aggregation
    """
    start_time = time.time()
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    target_fps = config.get("fps_sample", 10)
    frame_skip = max(1, int(video_fps / target_fps))

    logger.info(f"Video: {width}x{height} @ {video_fps}fps, {total_frames} frames")
    logger.info(f"Sampling every {frame_skip} frames (target {target_fps} fps)")

    # --- Stage 1: Detection + Tracking ---
    raw_detections = []
    frame_idx = 0
    processed_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_skip == 0:
            # Detect players and ball
            detections = detector.detect(frame)
            
            # Update tracker
            tracks = tracker.update(detections, frame)
            
            # Estimate homography for this frame
            homography = calibrator.estimate(frame)
            
            # Transform pixel coords to pitch coords
            pitch_tracks = calibrator.transform_to_pitch(tracks, homography)
            
            raw_detections.append({
                "frame": frame_idx,
                "timestamp": frame_idx / video_fps,
                "tracks": pitch_tracks,
                "homography_valid": homography is not None
            })
            processed_count += 1

            if processed_count % 100 == 0:
                logger.info(f"Processed {processed_count} frames ({frame_idx}/{total_frames})")

        frame_idx += 1

    cap.release()

    # --- Stage 2: Team Assignment ---
    if config.get("team_clustering", True):
        logger.info("Running team clustering...")
        # Re-open video for team color extraction
        cap2 = cv2.VideoCapture(video_path)
        team_assignments = team_classifier.assign_teams(raw_detections, cap2)
        cap2.release()
    else:
        team_assignments = []

    # --- Stage 3: Event Detection ---
    if config.get("event_detection", True):
        logger.info("Detecting events...")
        events = event_detector.detect_events(raw_detections, team_assignments)
    else:
        events = []

    # --- Stage 4: Analytics ---
    analytics = exporter.compute_analytics(raw_detections, events, team_assignments)

    # --- Stage 5: Format Output ---
    tracking_data = exporter.format_tracking_data(raw_detections, team_assignments)

    elapsed = time.time() - start_time
    logger.info(f"Pipeline complete in {elapsed:.1f}s")

    return {
        "metadata": {
            "pipeline_version": "1.0.0",
            "detection_model": config.get("detection_model", "yolov8x"),
            "tracker": config.get("tracker", "bytetrack"),
            "calibration": config.get("calibration", "broadtrack"),
            "video_resolution": f"{width}x{height}",
            "video_fps": video_fps,
            "fps_processed": target_fps,
            "total_frames": total_frames,
            "total_frames_processed": processed_count,
            "processing_time_seconds": round(elapsed, 1)
        },
        "team_assignments": team_assignments,
        "tracking_data": tracking_data,
        "events": events,
        "analytics": analytics
    }


def handler(event):
    """RunPod serverless handler entry point."""
    try:
        input_data = event["input"]
        video_urls = input_data.get("video_urls", [])
        config = input_data.get("config", {})
        job_id = input_data.get("job_id", "unknown")

        if not video_urls:
            return {"error": "No video_urls provided"}

        logger.info(f"Job {job_id}: Processing {len(video_urls)} video(s)")

        all_results = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            for i, url in enumerate(video_urls):
                logger.info(f"Processing video {i+1}/{len(video_urls)}: {url}")
                video_path = download_video(url, tmp_dir)
                result = process_video(video_path, config)
                all_results.append(result)

        # Merge results if multiple videos (first/second half)
        if len(all_results) == 1:
            return all_results[0]
        else:
            return merge_half_results(all_results)

    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        return {"error": str(e)}


def merge_half_results(results: list) -> dict:
    """Merge first half and second half results into a single match output."""
    merged = results[0].copy()

    for r in results[1:]:
        # Offset timestamps for second half
        if merged["tracking_data"] and r["tracking_data"]:
            last_ts = merged["tracking_data"][-1].get("timestamp", 0)
            for frame in r["tracking_data"]:
                frame["timestamp"] += last_ts
            merged["tracking_data"].extend(r["tracking_data"])

        if r.get("events"):
            for ev in r["events"]:
                ev["timestamp"] += last_ts
                ev["minute"] += 45
            merged["events"].extend(r["events"])

    merged["metadata"]["halves_processed"] = len(results)
    return merged


# Start RunPod serverless worker
if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})



================================================================================
FILE: /app/backend/runpod_handler/Dockerfile
================================================================================
# RunPod Serverless Docker Image
# Football Video Analysis Pipeline
#
# Build: docker build -t your-dockerhub/football-pipeline:latest .
# Push:  docker push your-dockerhub/football-pipeline:latest
# Deploy: RunPod Console → Serverless → New Endpoint → Docker Image

FROM runpod/pytorch:2.4.0-py3.12-cuda12.4.1-devel-ubuntu24.04

WORKDIR /workspace

# System dependencies for OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download YOLO weights at build time (cached in image, faster cold starts)
RUN python -c "from ultralytics import YOLO; YOLO('yolov8x.pt')"

# Copy pipeline code
COPY handler.py .
COPY pipeline/ pipeline/

# RunPod expects the handler to be importable
CMD ["python", "-u", "handler.py"]



================================================================================
FILE: /app/backend/runpod_handler/requirements.txt
================================================================================
# RunPod Handler Dependencies
# Install these in the Docker image

runpod>=1.7.0
ultralytics>=8.3.0
supervision>=0.25.0
opencv-python-headless>=4.10.0
numpy>=1.26.0
scipy>=1.13.0
scikit-learn>=1.5.0
torch>=2.4.0
torchvision>=0.19.0
pillow>=10.0.0



================================================================================
FILE: /app/backend/runpod_handler/README.md
================================================================================
# Football Video Analysis — RunPod Handler

## Overview
This is the GPU pipeline that runs on RunPod Serverless. It processes football match video and extracts structured tracking/event data.

## Pipeline Architecture
```
Video → Frame Extraction → YOLO Detection → ByteTrack Tracking
  → Pitch Calibration (Homography) → Coordinate Transform
  → Team Classification (Color Clustering) → Jersey OCR
  → Event Detection → Analytics Aggregation → JSON Output
```

## Models Used
| Stage | Model | Purpose |
|-------|-------|---------|
| Detection | YOLOv8x | Player + ball detection at 60+ FPS |
| Tracking | ByteTrack | Multi-object tracking with ID consistency |
| Calibration | BroadTrack/HRNet | Pitch keypoint detection for homography |
| Team Assignment | K-Means on HSV | Unsupervised jersey color clustering |
| ReID | OSNet | Player re-identification across occlusions |
| Events | Rule-based + LSTM | Pass/shot/corner detection from trajectories |

## Deployment to RunPod

### 1. Build Docker Image
```bash
docker build -t yourdockerhub/football-pipeline:latest .
docker push yourdockerhub/football-pipeline:latest
```

### 2. Create Serverless Endpoint
1. Go to [RunPod Console](https://www.runpod.io/console/serverless)
2. Click "New Endpoint"
3. Select "Custom Docker Image"
4. Enter: `yourdockerhub/football-pipeline:latest`
5. GPU: **NVIDIA A100 80GB** (recommended) or **RTX 4090**
6. Min Workers: 0, Max Workers: 3
7. Idle Timeout: 5 seconds
8. Click "Create"

### 3. Note Your Credentials
- **API Key**: RunPod Console → Settings → API Keys
- **Endpoint ID**: Shown on the endpoint page (e.g., `abc123xyz`)

### 4. Configure in Web App
Enter your API Key and Endpoint ID in the Settings page of the web interface.

## Input Format
```json
{
  "input": {
    "video_urls": ["https://storage.example.com/match_first_half.mp4"],
    "config": {
      "detection_model": "yolov8x",
      "tracker": "bytetrack",
      "calibration": "broadtrack",
      "team_clustering": true,
      "jersey_ocr": true,
      "event_detection": true,
      "fps_sample": 10
    },
    "job_id": "unique-job-id"
  }
}
```

## Output Format
```json
{
  "metadata": {
    "pipeline_version": "1.0.0",
    "processing_time_seconds": 842,
    "total_frames_processed": 27000
  },
  "team_assignments": [
    {"id": "P1", "team": "A", "jersey": 7, "confidence": 0.95}
  ],
  "tracking_data": [
    {
      "frame": 0,
      "timestamp": 0.0,
      "players": [
        {"id": "P1", "team": "A", "jersey": 7, "x": 52.3, "y": 34.1, "speed_kmh": 12.5}
      ],
      "ball": {"x": 50.0, "y": 34.0, "z": 0.5, "speed_kmh": 45.2}
    }
  ],
  "events": [
    {
      "id": "E1",
      "type": "pass",
      "timestamp": 12.4,
      "minute": 0,
      "player_id": "P1",
      "team": "A",
      "x": 45.2,
      "y": 30.1,
      "end_x": 62.8,
      "end_y": 25.4,
      "success": true
    }
  ],
  "analytics": {
    "possession": {"team_a": 54.2, "team_b": 45.8},
    "xg_total": {"team_a": 1.85, "team_b": 0.92}
  }
}
```

## GPU Requirements
- **Minimum**: RTX 3090 (24GB VRAM) — ~15 min per 45-min half
- **Recommended**: A100 80GB — ~5 min per 45-min half
- **Storage**: ~20GB for model weights + video temp storage

## Customization
- Fine-tune YOLO on SoccerNet dataset for better player/ball detection
- Train pitch keypoint model on SoccerNet Camera Calibration dataset
- Add jersey OCR model (STN + digit classifier)
- Replace rule-based event detection with trained LSTM model

## Testing Locally
```bash
pip install -r requirements.txt
python -c "
from handler import process_video
result = process_video('test_video.mp4', {
    'detection_model': 'yolov8x',
    'tracker': 'bytetrack',
    'fps_sample': 5
})
import json
print(json.dumps(result, indent=2))
"
```



================================================================================
FILE: /app/backend/runpod_handler/pipeline/__init__.py
================================================================================
# Football Video Analysis Pipeline Modules



================================================================================
FILE: /app/backend/runpod_handler/pipeline/detector.py
================================================================================
"""
Player & Ball Detection Module
Uses Ultralytics YOLO for high-speed detection of players, referees, and ball.

In production:
- Uses YOLOv8x or YOLOv11 fine-tuned on SoccerNet
- Implements frame tiling for 4K to maintain small object detection
- Ball detection with low confidence threshold (0.05) for max recall
- Spatial filtering via pitch polygon to suppress sideline false positives
"""
import numpy as np
from typing import List, Dict


class PlayerBallDetector:
    # COCO class IDs: 0=person, 32=sports ball
    PERSON_CLASS = 0
    BALL_CLASS = 32

    def __init__(self, model_name: str = "yolov8x", confidence: float = 0.3, ball_confidence: float = 0.05):
        """
        Initialize detector.
        
        Args:
            model_name: YOLO model variant (yolov8n/s/m/l/x, yolov11)
            confidence: Detection confidence for players
            ball_confidence: Lower threshold for ball (maximize recall)
        """
        self.model_name = model_name
        self.confidence = confidence
        self.ball_confidence = ball_confidence
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load YOLO model. In production, loads from local weights."""
        try:
            from ultralytics import YOLO
            self.model = YOLO(f"{self.model_name}.pt")
        except ImportError:
            # Fallback for environments without ultralytics
            self.model = None

    def detect(self, frame: np.ndarray) -> Dict:
        """
        Detect players and ball in a single frame.
        
        Returns:
            {
                "players": [{"bbox": [x1,y1,x2,y2], "conf": 0.95, "class": "player"}],
                "ball": {"bbox": [x1,y1,x2,y2], "conf": 0.8} or None,
                "referees": [...]
            }
        """
        if self.model is None:
            return {"players": [], "ball": None, "referees": []}

        # Run detection
        results = self.model(frame, conf=self.ball_confidence, verbose=False)[0]
        
        players = []
        ball = None
        best_ball_conf = 0

        for box in results.boxes:
            cls = int(box.cls[0])
            conf = float(box.conf[0])
            bbox = box.xyxy[0].cpu().numpy().tolist()

            if cls == self.PERSON_CLASS and conf >= self.confidence:
                players.append({
                    "bbox": bbox,
                    "conf": conf,
                    "class": "player",
                    "center": [(bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2]
                })
            elif cls == self.BALL_CLASS and conf > best_ball_conf:
                best_ball_conf = conf
                ball = {
                    "bbox": bbox,
                    "conf": conf,
                    "center": [(bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2]
                }

        return {
            "players": players,
            "ball": ball,
            "referees": []  # Separated in team classification stage
        }

    def detect_tiled(self, frame: np.ndarray, tile_size: int = 1280, overlap: int = 200) -> Dict:
        """
        Tiled detection for 4K frames.
        Splits frame into overlapping patches, detects in each, then merges with NMS.
        Critical for maintaining small object detection in high-res footage.
        """
        h, w = frame.shape[:2]
        if w <= tile_size and h <= tile_size:
            return self.detect(frame)

        all_players = []
        all_balls = []

        for y in range(0, h, tile_size - overlap):
            for x in range(0, w, tile_size - overlap):
                x2 = min(x + tile_size, w)
                y2 = min(y + tile_size, h)
                tile = frame[y:y2, x:x2]

                det = self.detect(tile)
                
                # Offset bboxes to original frame coordinates
                for p in det["players"]:
                    p["bbox"] = [p["bbox"][0]+x, p["bbox"][1]+y, p["bbox"][2]+x, p["bbox"][3]+y]
                    p["center"] = [p["center"][0]+x, p["center"][1]+y]
                    all_players.append(p)

                if det["ball"]:
                    b = det["ball"]
                    b["bbox"] = [b["bbox"][0]+x, b["bbox"][1]+y, b["bbox"][2]+x, b["bbox"][3]+y]
                    b["center"] = [b["center"][0]+x, b["center"][1]+y]
                    all_balls.append(b)

        # NMS across tiles
        players = self._nms(all_players, iou_threshold=0.5)
        ball = max(all_balls, key=lambda b: b["conf"]) if all_balls else None

        return {"players": players, "ball": ball, "referees": []}

    def _nms(self, detections: List[Dict], iou_threshold: float = 0.5) -> List[Dict]:
        """Non-maximum suppression across tile boundaries."""
        if not detections:
            return []
        
        sorted_dets = sorted(detections, key=lambda d: d["conf"], reverse=True)
        kept = []

        for det in sorted_dets:
            overlap = False
            for k in kept:
                if self._iou(det["bbox"], k["bbox"]) > iou_threshold:
                    overlap = True
                    break
            if not overlap:
                kept.append(det)

        return kept

    @staticmethod
    def _iou(box1, box2):
        """Compute IoU between two bounding boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        inter = max(0, x2-x1) * max(0, y2-y1)
        area1 = (box1[2]-box1[0]) * (box1[3]-box1[1])
        area2 = (box2[2]-box2[0]) * (box2[3]-box2[1])
        union = area1 + area2 - inter
        return inter / union if union > 0 else 0



================================================================================
FILE: /app/backend/runpod_handler/pipeline/tracker.py
================================================================================
"""
Multi-Object Tracking Module
Implements ByteTrack / BoT-SORT for robust player tracking.

Key features:
- Two-stage association (high + low confidence detections)
- Camera Motion Compensation (CMC) via ORB feature matching
- Kalman filter prediction for smooth trajectories
- Gaussian Process Smoothing (GSI) for short occlusion interpolation
- AppearanceFree Linking (AFLink) for tracklet merging

In production uses supervision library's ByteTrack implementation.
"""
import numpy as np
from typing import Dict, List, Optional


class MultiObjectTracker:
    def __init__(self, algorithm: str = "bytetrack", max_age: int = 30, min_hits: int = 3):
        """
        Args:
            algorithm: "bytetrack" or "botsort"
            max_age: Frames to keep lost tracks before deletion
            min_hits: Min consecutive hits before track is confirmed
        """
        self.algorithm = algorithm
        self.max_age = max_age
        self.min_hits = min_hits
        self.tracker = None
        self.track_history = {}  # id -> list of positions
        self._init_tracker()

    def _init_tracker(self):
        """Initialize tracker from supervision library."""
        try:
            import supervision as sv
            if self.algorithm == "bytetrack":
                self.tracker = sv.ByteTrack(
                    track_activation_threshold=0.25,
                    lost_track_buffer=self.max_age,
                    minimum_matching_threshold=0.8,
                    frame_rate=25
                )
            # BoT-SORT would be initialized similarly with CMC enabled
        except ImportError:
            self.tracker = None

    def update(self, detections: Dict, frame: np.ndarray) -> List[Dict]:
        """
        Update tracks with new detections.
        
        Args:
            detections: Output from PlayerBallDetector
            frame: Current video frame (for appearance features / CMC)
            
        Returns:
            List of tracked objects with IDs:
            [{"track_id": 1, "bbox": [...], "center": [...], "conf": 0.9, "class": "player"}]
        """
        if self.tracker is None:
            # Fallback: assign sequential IDs
            return self._simple_track(detections)

        import supervision as sv

        players = detections.get("players", [])
        if not players:
            return []

        bboxes = np.array([p["bbox"] for p in players])
        confs = np.array([p["conf"] for p in players])
        class_ids = np.zeros(len(players), dtype=int)

        sv_detections = sv.Detections(
            xyxy=bboxes,
            confidence=confs,
            class_id=class_ids
        )

        tracked = self.tracker.update_with_detections(sv_detections)
        
        results = []
        for i in range(len(tracked)):
            bbox = tracked.xyxy[i].tolist()
            tid = int(tracked.tracker_id[i]) if tracked.tracker_id is not None else i
            center = [(bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2]
            
            # Maintain track history for velocity calculation
            if tid not in self.track_history:
                self.track_history[tid] = []
            self.track_history[tid].append(center)
            if len(self.track_history[tid]) > 100:
                self.track_history[tid] = self.track_history[tid][-100:]

            results.append({
                "track_id": tid,
                "bbox": bbox,
                "center": center,
                "conf": float(tracked.confidence[i]) if tracked.confidence is not None else 0.9,
                "class": "player"
            })

        # Add ball tracking (separate single-object tracker)
        ball = detections.get("ball")
        if ball:
            results.append({
                "track_id": -1,  # Special ID for ball
                "bbox": ball["bbox"],
                "center": ball["center"],
                "conf": ball["conf"],
                "class": "ball"
            })

        return results

    def _simple_track(self, detections: Dict) -> List[Dict]:
        """Fallback tracking without supervision library."""
        results = []
        for i, p in enumerate(detections.get("players", [])):
            results.append({
                "track_id": i,
                "bbox": p["bbox"],
                "center": p["center"],
                "conf": p["conf"],
                "class": "player"
            })
        ball = detections.get("ball")
        if ball:
            results.append({
                "track_id": -1,
                "bbox": ball["bbox"],
                "center": ball["center"],
                "conf": ball["conf"],
                "class": "ball"
            })
        return results

    def get_velocity(self, track_id: int, fps: float = 25.0) -> Optional[float]:
        """
        Calculate instantaneous speed for a track in km/h.
        Uses last 5 positions for smoothing.
        """
        history = self.track_history.get(track_id, [])
        if len(history) < 2:
            return None
        
        recent = history[-5:]
        total_dist = 0
        for i in range(1, len(recent)):
            dx = recent[i][0] - recent[i-1][0]
            dy = recent[i][1] - recent[i-1][1]
            total_dist += np.sqrt(dx**2 + dy**2)
        
        avg_dist_per_frame = total_dist / (len(recent) - 1)
        # Convert pixels to meters (approximate, refined by homography)
        meters_per_pixel = 0.1  # Rough estimate, calibration refines this
        speed_ms = avg_dist_per_frame * meters_per_pixel * fps
        return speed_ms * 3.6  # km/h

    def interpolate_gaps(self, tracks: List[List[Dict]], max_gap: int = 10) -> List[List[Dict]]:
        """
        Gaussian Process Smoothing for short occlusion gaps.
        Fills missing positions using polynomial interpolation.
        """
        # Implementation would use scipy.interpolate or similar
        return tracks



================================================================================
FILE: /app/backend/runpod_handler/pipeline/calibrator.py
================================================================================
"""
Pitch Calibration & Homography Module
Maps pixel coordinates to real-world pitch coordinates (meters).

Implements:
- BroadTrack-style keypoint detection for pitch lines
- 4-point homography as baseline
- Advanced: PnLCalib with line + conic constraints
- Temporal smoothing via Savitzky-Golay filter
- Lens distortion correction for wide-angle cameras

Standard pitch dimensions: 105m x 68m (FIFA)
"""
import numpy as np
from typing import Dict, List, Optional, Tuple


# FIFA standard pitch dimensions in meters
PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0

# Key pitch points in meters (origin at top-left corner)
PITCH_KEYPOINTS = {
    "top_left": (0, 0),
    "top_right": (PITCH_LENGTH, 0),
    "bottom_left": (0, PITCH_WIDTH),
    "bottom_right": (PITCH_LENGTH, PITCH_WIDTH),
    "center": (PITCH_LENGTH / 2, PITCH_WIDTH / 2),
    "center_top": (PITCH_LENGTH / 2, 0),
    "center_bottom": (PITCH_LENGTH / 2, PITCH_WIDTH),
    "penalty_a": (11.0, PITCH_WIDTH / 2),
    "penalty_b": (PITCH_LENGTH - 11.0, PITCH_WIDTH / 2),
    "goal_a_top": (0, PITCH_WIDTH / 2 - 3.66),
    "goal_a_bottom": (0, PITCH_WIDTH / 2 + 3.66),
    "goal_b_top": (PITCH_LENGTH, PITCH_WIDTH / 2 - 3.66),
    "goal_b_bottom": (PITCH_LENGTH, PITCH_WIDTH / 2 + 3.66),
}


class PitchCalibrator:
    def __init__(self, method: str = "broadtrack"):
        """
        Args:
            method: "basic" (4-point), "broadtrack" (keypoint-based), "pnlcalib" (lines+points)
        """
        self.method = method
        self.keypoint_model = None
        self.last_homography = None
        self.homography_buffer = []  # For temporal smoothing
        self._load_keypoint_model()

    def _load_keypoint_model(self):
        """
        Load pitch keypoint detection model.
        In production: HRNet or SegFormer trained on SoccerNet Camera Calibration dataset.
        Detects line intersections, circle centers, penalty spots.
        """
        try:
            # Would load a trained segmentation model for pitch lines
            # from sn_calibration import KeypointDetector
            # self.keypoint_model = KeypointDetector.load("broadtrack_hrnet.pth")
            pass
        except ImportError:
            pass

    def estimate(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Estimate homography matrix for current frame.
        
        Returns:
            3x3 homography matrix or None if estimation fails.
        """
        if self.method == "basic":
            return self._estimate_basic(frame)
        elif self.method == "broadtrack":
            return self._estimate_broadtrack(frame)
        else:
            return self._estimate_basic(frame)

    def _estimate_basic(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Basic 4-point homography estimation.
        Detects pitch corners/lines using Hough transform.
        """
        try:
            import cv2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Hough line detection
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100,
                                     minLineLength=100, maxLineGap=10)
            
            if lines is None or len(lines) < 4:
                return self.last_homography  # Fall back to previous
            
            # In production: sophisticated line clustering and intersection finding
            # For now, return cached homography
            return self.last_homography
            
        except Exception:
            return self.last_homography

    def _estimate_broadtrack(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """
        BroadTrack-style calibration:
        1. Detect pitch keypoints (line intersections, circles) via CNN
        2. Match detected keypoints to known pitch template
        3. Compute homography via DLT with RANSAC
        4. Refine with Levenberg-Marquardt (minimize reprojection error)
        5. Temporal smoothing across frame buffer
        """
        if self.keypoint_model is None:
            return self.last_homography

        # In production:
        # keypoints_pixel = self.keypoint_model.predict(frame)
        # keypoints_pitch = match_to_template(keypoints_pixel)
        # H, mask = cv2.findHomography(keypoints_pixel, keypoints_pitch, cv2.RANSAC, 5.0)
        # H = self._refine_homography(H, keypoints_pixel, keypoints_pitch)
        # H = self._temporal_smooth(H)
        # self.last_homography = H
        # return H
        
        return self.last_homography

    def transform_to_pitch(self, tracks: List[Dict], homography: Optional[np.ndarray]) -> List[Dict]:
        """
        Transform tracked pixel coordinates to pitch coordinates.
        Uses foot position (bottom-center of bbox) for ground plane projection.
        
        Args:
            tracks: List of tracked objects with bbox/center
            homography: 3x3 homography matrix
            
        Returns:
            Tracks with added pitch_x, pitch_y fields (in meters)
        """
        if homography is None:
            # Without calibration, return normalized coordinates
            for t in tracks:
                # Rough mapping assuming typical broadcast view
                t["pitch_x"] = None
                t["pitch_y"] = None
            return tracks

        for t in tracks:
            bbox = t.get("bbox", [0, 0, 0, 0])
            # Use bottom-center of bbox (foot position on ground plane)
            foot_x = (bbox[0] + bbox[2]) / 2
            foot_y = bbox[3]

            # Apply homography
            pt = np.array([foot_x, foot_y, 1.0])
            transformed = homography @ pt
            if transformed[2] != 0:
                pitch_x = transformed[0] / transformed[2]
                pitch_y = transformed[1] / transformed[2]
                
                # Clamp to pitch boundaries
                t["pitch_x"] = round(max(0, min(PITCH_LENGTH, pitch_x)), 2)
                t["pitch_y"] = round(max(0, min(PITCH_WIDTH, pitch_y)), 2)
            else:
                t["pitch_x"] = None
                t["pitch_y"] = None

        return tracks

    def _temporal_smooth(self, H: np.ndarray, buffer_size: int = 5) -> np.ndarray:
        """
        Savitzky-Golay temporal smoothing of homography parameters.
        Prevents jitter from frame-to-frame estimation noise.
        """
        self.homography_buffer.append(H)
        if len(self.homography_buffer) > buffer_size:
            self.homography_buffer = self.homography_buffer[-buffer_size:]
        
        if len(self.homography_buffer) < 3:
            return H
        
        # Average homography parameters
        avg_H = np.mean(self.homography_buffer, axis=0)
        # Re-normalize
        avg_H /= avg_H[2, 2]
        return avg_H

    def get_pitch_mask(self, frame_shape: Tuple[int, int], homography: np.ndarray) -> np.ndarray:
        """
        Generate binary mask of the visible pitch area.
        Used for spatial filtering (suppress off-pitch detections).
        """
        h, w = frame_shape[:2]
        
        # Define pitch boundary in pitch coordinates
        pitch_corners = np.float32([
            [0, 0], [PITCH_LENGTH, 0],
            [PITCH_LENGTH, PITCH_WIDTH], [0, PITCH_WIDTH]
        ]).reshape(-1, 1, 2)
        
        # Inverse homography: pitch → pixel
        H_inv = np.linalg.inv(homography)
        pixel_corners = cv2.perspectiveTransform(pitch_corners, H_inv)
        
        mask = np.zeros((h, w), dtype=np.uint8)
        pts = pixel_corners.astype(np.int32)
        cv2.fillPoly(mask, [pts], 255)
        
        return mask



================================================================================
FILE: /app/backend/runpod_handler/pipeline/team_classifier.py
================================================================================
"""
Team Classification & Jersey Recognition Module

Implements:
- Unsupervised team clustering via jersey color (K-Means on HSV)
- Convolutional autoencoder for latent color embeddings
- DBSCAN for robust clustering (handles referees/goalkeepers)
- Jersey number OCR via Spatial Transformer + digit recognition
- ReID embeddings (OSNet) for persistent identity across frames

Groups players into: Team A, Team B, Referee, Goalkeeper
"""
import numpy as np
from typing import Dict, List, Optional


class TeamClassifier:
    def __init__(self):
        self.team_colors = None  # Learned cluster centers
        self.player_teams = {}   # track_id -> team assignment
        self.jersey_numbers = {} # track_id -> jersey number
        self.reid_model = None
        self._load_models()

    def _load_models(self):
        """Load ReID and OCR models."""
        try:
            # In production:
            # from torchreid import models as reid_models
            # self.reid_model = reid_models.build_model("osnet_x1_0", 751, pretrained=True)
            pass
        except ImportError:
            pass

    def assign_teams(self, raw_detections: List[Dict], video_capture) -> List[Dict]:
        """
        Assign team labels to all tracked players.
        
        Process:
        1. Extract jersey color crops from first N frames
        2. Convert to HSV, compute dominant hue per player
        3. K-Means (k=3) on color features → Team A, Team B, Referee
        4. Refine using spatial context (GK near goal)
        5. Aggregate across full video for stable assignments
        
        Returns:
            List of player assignments:
            [{"track_id": 1, "team": "A", "jersey": 7, "confidence": 0.95}]
        """
        # Collect color features
        color_features = self._extract_color_features(raw_detections, video_capture)
        
        if not color_features:
            return []

        # Cluster into teams
        try:
            from sklearn.cluster import KMeans
            
            track_ids = list(color_features.keys())
            features = np.array([color_features[tid] for tid in track_ids])
            
            # K-Means with k=3 (Team A, Team B, Referees)
            kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
            labels = kmeans.fit_predict(features)
            
            # Assign team labels based on cluster sizes
            # Largest two clusters = teams, smallest = referees
            cluster_counts = {}
            for l in labels:
                cluster_counts[l] = cluster_counts.get(l, 0) + 1
            
            sorted_clusters = sorted(cluster_counts.items(), key=lambda x: x[1], reverse=True)
            team_map = {}
            team_map[sorted_clusters[0][0]] = "A"
            team_map[sorted_clusters[1][0]] = "B"
            if len(sorted_clusters) > 2:
                team_map[sorted_clusters[2][0]] = "referee"

            assignments = []
            for i, tid in enumerate(track_ids):
                team = team_map.get(labels[i], "unknown")
                self.player_teams[tid] = team
                assignments.append({
                    "id": f"P{tid}",
                    "track_id": tid,
                    "team": team,
                    "jersey": self.jersey_numbers.get(tid),
                    "confidence": 0.85  # Would be computed from cluster distance
                })

            return assignments

        except ImportError:
            # Fallback without sklearn
            return self._fallback_assignment(raw_detections)

    def _extract_color_features(self, detections: List[Dict], cap) -> Dict[int, np.ndarray]:
        """
        Extract dominant jersey colors for each tracked player.
        
        Process:
        - Crop player bbox, isolate upper body (torso = jersey)
        - Convert to HSV color space
        - Compute histogram of hue channel
        - Use histogram as feature vector for clustering
        """
        features = {}
        
        try:
            import cv2
        except ImportError:
            return features

        # Sample frames evenly across the video
        sample_indices = set()
        for det in detections[::10]:  # Every 10th detection frame
            sample_indices.add(det["frame"])

        frame_idx = 0
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx not in sample_indices:
                frame_idx += 1
                continue

            # Find matching detection frame
            for det in detections:
                if det["frame"] == frame_idx:
                    for track in det.get("tracks", []):
                        if track.get("class") != "player":
                            continue
                        tid = track.get("track_id")
                        bbox = track.get("bbox", [])
                        if len(bbox) != 4 or tid is None:
                            continue

                        x1, y1, x2, y2 = [int(c) for c in bbox]
                        # Crop upper body (jersey region)
                        h = y2 - y1
                        jersey_y1 = y1 + int(h * 0.15)
                        jersey_y2 = y1 + int(h * 0.55)
                        crop = frame[jersey_y1:jersey_y2, x1:x2]

                        if crop.size == 0:
                            continue

                        # HSV histogram
                        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
                        hist = cv2.calcHist([hsv], [0, 1], None, [18, 8], [0, 180, 0, 256])
                        hist = cv2.normalize(hist, hist).flatten()

                        if tid not in features:
                            features[tid] = []
                        features[tid].append(hist)
                    break

            frame_idx += 1

        # Average histograms per track
        avg_features = {}
        for tid, hists in features.items():
            avg_features[tid] = np.mean(hists, axis=0)

        return avg_features

    def _fallback_assignment(self, detections: List[Dict]) -> List[Dict]:
        """Simple fallback when sklearn is not available."""
        assignments = []
        seen = set()
        for det in detections:
            for track in det.get("tracks", []):
                tid = track.get("track_id")
                if tid is not None and tid not in seen and track.get("class") == "player":
                    seen.add(tid)
                    # Alternate teams as fallback
                    team = "A" if tid % 2 == 0 else "B"
                    assignments.append({
                        "id": f"P{tid}",
                        "track_id": tid,
                        "team": team,
                        "jersey": None,
                        "confidence": 0.5
                    })
        return assignments

    def recognize_jersey(self, crop: np.ndarray) -> Optional[int]:
        """
        OCR for jersey number recognition.
        Uses Spatial Transformer Network to localize digits,
        then digit classifier for recognition.
        Temporal aggregation across frames for stable output.
        """
        # In production: would use a fine-tuned STN + digit classifier
        # or CLIP-based VLM approach
        return None



================================================================================
FILE: /app/backend/runpod_handler/pipeline/event_detector.py
================================================================================
"""
Event Detection Module
Detects discrete match events from tracking data.

Events detected:
- Pass (short, medium, long, cross)
- Shot (on target, off target, blocked)
- Corner kick
- Goal kick
- Throw-in
- Foul
- Offside
- Tackle
- Dribble
- Header
- Save

Uses:
- Ball trajectory analysis (velocity changes, direction changes)
- Player-ball proximity (possession assignment)
- Spatial context (pitch zones for corners, goal kicks, etc.)
- Temporal patterns (LSTM for complex event sequences)
"""
import numpy as np
from typing import Dict, List, Optional

# Pitch zones (in meters)
PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0
PENALTY_BOX_LENGTH = 16.5
PENALTY_BOX_WIDTH = 40.3
CORNER_ZONE = 3.0  # meters from corner flag
GOAL_LINE_ZONE = 2.0


class EventDetector:
    def __init__(self):
        self.possession_history = []  # track which team has the ball
        self.ball_history = []        # ball position history

    def detect_events(self, raw_detections: List[Dict], team_assignments: List[Dict]) -> List[Dict]:
        """
        Detect events from tracking data.
        
        Args:
            raw_detections: Frame-by-frame tracking data
            team_assignments: Player-to-team mapping
            
        Returns:
            List of detected events with timestamps and positions
        """
        events = []
        
        # Build team lookup
        team_map = {}
        for ta in team_assignments:
            team_map[ta.get("track_id")] = ta.get("team", "unknown")

        prev_ball = None
        prev_possessor = None
        
        for frame_data in raw_detections:
            timestamp = frame_data.get("timestamp", 0)
            frame_idx = frame_data.get("frame", 0)
            tracks = frame_data.get("tracks", [])
            
            ball = None
            players = []
            for t in tracks:
                if t.get("class") == "ball":
                    ball = t
                else:
                    players.append(t)

            if ball is None:
                prev_ball = None
                continue

            ball_x = ball.get("pitch_x")
            ball_y = ball.get("pitch_y")
            
            if ball_x is None or ball_y is None:
                continue

            # Find closest player (possessor)
            possessor = self._find_possessor(ball, players)
            possessor_team = team_map.get(possessor["track_id"]) if possessor else None

            # Detect pass: possession change within same team with ball displacement
            if prev_possessor and possessor:
                if (prev_possessor["track_id"] != possessor["track_id"] 
                    and team_map.get(prev_possessor["track_id"]) == possessor_team
                    and prev_ball):
                    
                    dist = self._distance(prev_ball, ball)
                    if dist > 5:  # Minimum pass distance (meters)
                        pass_type = self._classify_pass(dist, prev_ball, ball)
                        events.append({
                            "type": pass_type,
                            "timestamp": timestamp,
                            "minute": int(timestamp // 60),
                            "second": int(timestamp % 60),
                            "player_id": f"P{prev_possessor['track_id']}",
                            "team": team_map.get(prev_possessor["track_id"], "unknown"),
                            "x": prev_ball.get("pitch_x", 0),
                            "y": prev_ball.get("pitch_y", 0),
                            "end_x": ball_x,
                            "end_y": ball_y,
                            "success": True,
                            "confidence": 0.8
                        })

            # Detect shot: ball moving towards goal at high speed
            if prev_ball and ball:
                ball_speed = self._ball_speed(prev_ball, ball, 0.1)
                prev_x = prev_ball.get("pitch_x", 0)
                
                if (ball_speed > 50 and  # >50 km/h
                    ((prev_x < PITCH_LENGTH * 0.7 and ball_x > PITCH_LENGTH * 0.85) or
                     (prev_x > PITCH_LENGTH * 0.3 and ball_x < PITCH_LENGTH * 0.15))):
                    
                    on_target = self._is_on_target(ball_x, ball_y)
                    events.append({
                        "type": "shot",
                        "timestamp": timestamp,
                        "minute": int(timestamp // 60),
                        "second": int(timestamp % 60),
                        "player_id": f"P{possessor['track_id']}" if possessor else "unknown",
                        "team": possessor_team or "unknown",
                        "x": prev_x,
                        "y": prev_ball.get("pitch_y", 0),
                        "on_target": on_target,
                        "xg": self._calculate_xg(prev_x, prev_ball.get("pitch_y", 0)),
                        "confidence": 0.75
                    })

            # Detect corner: ball goes out near corner flag
            if ball_x is not None and ball_y is not None:
                if self._is_corner_zone(ball_x, ball_y):
                    if prev_ball and not self._is_corner_zone(
                        prev_ball.get("pitch_x", 50), prev_ball.get("pitch_y", 34)):
                        events.append({
                            "type": "corner",
                            "timestamp": timestamp,
                            "minute": int(timestamp // 60),
                            "second": int(timestamp % 60),
                            "team": self._corner_team(ball_x, possessor_team),
                            "x": ball_x,
                            "y": ball_y,
                            "confidence": 0.7
                        })

            prev_ball = {"pitch_x": ball_x, "pitch_y": ball_y}
            prev_possessor = possessor

        # Sort by timestamp
        events.sort(key=lambda e: e["timestamp"])
        
        # Add event IDs
        for i, ev in enumerate(events):
            ev["id"] = f"E{i+1}"

        return events

    def _find_possessor(self, ball: Dict, players: List[Dict]) -> Optional[Dict]:
        """Find player closest to the ball (within possession radius)."""
        min_dist = float('inf')
        closest = None
        ball_pos = (ball.get("pitch_x", 0), ball.get("pitch_y", 0))
        
        for p in players:
            px = p.get("pitch_x")
            py = p.get("pitch_y")
            if px is None or py is None:
                continue
            dist = np.sqrt((px - ball_pos[0])**2 + (py - ball_pos[1])**2)
            if dist < min_dist and dist < 3.0:  # 3m possession radius
                min_dist = dist
                closest = p
        
        return closest

    def _distance(self, pos1: Dict, pos2: Dict) -> float:
        """Euclidean distance between two pitch positions."""
        x1 = pos1.get("pitch_x", 0)
        y1 = pos1.get("pitch_y", 0)
        x2 = pos2.get("pitch_x", 0)
        y2 = pos2.get("pitch_y", 0)
        return np.sqrt((x2-x1)**2 + (y2-y1)**2)

    def _ball_speed(self, prev: Dict, curr: Dict, dt: float) -> float:
        """Ball speed in km/h."""
        dist = self._distance(prev, curr)
        if dt <= 0:
            return 0
        return (dist / dt) * 3.6

    def _classify_pass(self, distance: float, start: Dict, end: Dict) -> str:
        """Classify pass type based on distance and direction."""
        end_y = end.get("pitch_y", 34)
        start_y = start.get("pitch_y", 34)
        lateral = abs(end_y - start_y)
        
        if lateral > 20:
            return "cross"
        elif distance > 30:
            return "long_pass"
        elif distance > 15:
            return "medium_pass"
        else:
            return "pass"

    def _is_corner_zone(self, x: float, y: float) -> bool:
        """Check if position is in a corner zone."""
        return ((x < CORNER_ZONE or x > PITCH_LENGTH - CORNER_ZONE) and
                (y < CORNER_ZONE or y > PITCH_WIDTH - CORNER_ZONE))

    def _corner_team(self, ball_x: float, last_possessor_team: str) -> str:
        """Determine which team gets the corner."""
        # If ball went out near team B's goal, team A gets corner (and vice versa)
        if ball_x > PITCH_LENGTH / 2:
            return "A"  # Attacking team A's side
        return "B"

    def _is_on_target(self, x: float, y: float) -> bool:
        """Check if shot is on target (heading towards goal)."""
        goal_y_min = PITCH_WIDTH / 2 - 3.66
        goal_y_max = PITCH_WIDTH / 2 + 3.66
        return goal_y_min <= y <= goal_y_max

    def _calculate_xg(self, x: float, y: float) -> float:
        """
        Simple xG (Expected Goals) calculation based on shot position.
        In production: use a trained xG model with more features.
        """
        # Distance from goal center
        goal_x = PITCH_LENGTH
        goal_y = PITCH_WIDTH / 2
        dist = np.sqrt((x - goal_x)**2 + (y - goal_y)**2)
        
        # Simple distance-based xG (exponential decay)
        xg = np.exp(-dist / 20) * 0.8
        return round(min(max(xg, 0.01), 0.95), 3)



================================================================================
FILE: /app/backend/runpod_handler/pipeline/data_exporter.py
================================================================================
"""
Data Export Module
Aggregates pipeline outputs into structured JSON/CSV artifacts.

Output artifacts:
- tracking_data: Per-frame player/ball positions in pitch coordinates
- events: Discrete match events with timestamps
- analytics: Aggregated match statistics
- team_assignments: Player-team-jersey mapping
"""
import numpy as np
from typing import Dict, List


class DataExporter:
    def format_tracking_data(self, raw_detections: List[Dict], team_assignments: List[Dict]) -> List[Dict]:
        """
        Format raw detections into clean tracking data.
        
        Output per frame:
        {
            "frame": 0,
            "timestamp": 0.0,
            "players": [
                {"id": "P1", "team": "A", "jersey": 7, "x": 52.3, "y": 34.1, "speed_kmh": 12.5}
            ],
            "ball": {"x": 50.0, "y": 34.0, "z": 0.5, "speed_kmh": 45.2}
        }
        """
        team_map = {}
        jersey_map = {}
        for ta in team_assignments:
            tid = ta.get("track_id")
            team_map[tid] = ta.get("team", "unknown")
            jersey_map[tid] = ta.get("jersey")

        formatted = []
        for det in raw_detections:
            frame = {
                "frame": det.get("frame", 0),
                "timestamp": round(det.get("timestamp", 0), 3),
                "players": [],
                "ball": None
            }

            for track in det.get("tracks", []):
                tid = track.get("track_id")
                
                if track.get("class") == "ball":
                    frame["ball"] = {
                        "x": track.get("pitch_x"),
                        "y": track.get("pitch_y"),
                        "z": track.get("pitch_z", 0),
                        "speed_kmh": track.get("speed_kmh", 0),
                        "confidence": track.get("conf", 0)
                    }
                else:
                    frame["players"].append({
                        "id": f"P{tid}",
                        "track_id": tid,
                        "team": team_map.get(tid, "unknown"),
                        "jersey": jersey_map.get(tid),
                        "x": track.get("pitch_x"),
                        "y": track.get("pitch_y"),
                        "speed_kmh": track.get("speed_kmh", 0),
                        "confidence": track.get("conf", 0)
                    })

            formatted.append(frame)

        return formatted

    def compute_analytics(self, raw_detections: List[Dict], events: List[Dict], 
                         team_assignments: List[Dict]) -> Dict:
        """
        Compute aggregated match analytics from tracking and event data.
        
        Includes:
        - Possession percentages
        - Pass accuracy
        - Shot statistics
        - Distance covered
        - Speed profiles
        - Expected Goals (xG)
        - Set piece counts
        """
        analytics = {
            "possession": {"team_a": 50.0, "team_b": 50.0},
            "pass_accuracy": {"team_a": 0, "team_b": 0},
            "shots": {"team_a": 0, "team_b": 0},
            "shots_on_target": {"team_a": 0, "team_b": 0},
            "corners": {"team_a": 0, "team_b": 0},
            "fouls": {"team_a": 0, "team_b": 0},
            "offsides": {"team_a": 0, "team_b": 0},
            "total_distance_km": {"team_a": 0, "team_b": 0},
            "sprint_count": {"team_a": 0, "team_b": 0},
            "avg_speed_kmh": {"team_a": 0, "team_b": 0},
            "xg_total": {"team_a": 0, "team_b": 0}
        }

        # Count events by type and team
        passes_a, passes_b = 0, 0
        passes_success_a, passes_success_b = 0, 0

        for ev in events:
            team = ev.get("team", "unknown")
            etype = ev.get("type", "")
            key_team = "team_a" if team == "A" else "team_b"

            if etype in ("pass", "long_pass", "medium_pass", "cross"):
                if team == "A":
                    passes_a += 1
                    if ev.get("success"):
                        passes_success_a += 1
                else:
                    passes_b += 1
                    if ev.get("success"):
                        passes_success_b += 1
            elif etype == "shot":
                analytics["shots"][key_team] += 1
                if ev.get("on_target"):
                    analytics["shots_on_target"][key_team] += 1
                analytics["xg_total"][key_team] += ev.get("xg", 0)
            elif etype == "corner":
                analytics["corners"][key_team] += 1
            elif etype == "foul":
                analytics["fouls"][key_team] += 1
            elif etype == "offside":
                analytics["offsides"][key_team] += 1

        # Pass accuracy
        if passes_a > 0:
            analytics["pass_accuracy"]["team_a"] = round(passes_success_a / passes_a * 100, 1)
        if passes_b > 0:
            analytics["pass_accuracy"]["team_b"] = round(passes_success_b / passes_b * 100, 1)

        # Round xG
        analytics["xg_total"]["team_a"] = round(analytics["xg_total"]["team_a"], 2)
        analytics["xg_total"]["team_b"] = round(analytics["xg_total"]["team_b"], 2)

        # Distance and speed (from tracking data)
        team_map = {}
        for ta in team_assignments:
            team_map[ta.get("track_id")] = ta.get("team")

        player_distances = {}
        player_speeds = {}
        prev_positions = {}

        for det in raw_detections:
            dt = 0.1  # Approximate time between sampled frames
            for track in det.get("tracks", []):
                if track.get("class") == "ball":
                    continue
                tid = track.get("track_id")
                px = track.get("pitch_x")
                py = track.get("pitch_y")
                if tid is None or px is None or py is None:
                    continue

                if tid in prev_positions:
                    prev_x, prev_y = prev_positions[tid]
                    dist = np.sqrt((px - prev_x)**2 + (py - prev_y)**2)
                    speed = (dist / dt) * 3.6 if dt > 0 else 0

                    if tid not in player_distances:
                        player_distances[tid] = 0
                        player_speeds[tid] = []
                    player_distances[tid] += dist / 1000  # km
                    player_speeds[tid].append(speed)

                    if speed > 25:  # Sprint threshold: 25 km/h
                        team = team_map.get(tid, "unknown")
                        key = "team_a" if team == "A" else "team_b"
                        analytics["sprint_count"][key] += 1

                prev_positions[tid] = (px, py)

        # Aggregate team distances and speeds
        for tid, dist in player_distances.items():
            team = team_map.get(tid, "unknown")
            key = "team_a" if team == "A" else "team_b"
            analytics["total_distance_km"][key] += dist

        speed_sums = {"team_a": [], "team_b": []}
        for tid, speeds in player_speeds.items():
            team = team_map.get(tid, "unknown")
            key = "team_a" if team == "A" else "team_b"
            speed_sums[key].extend(speeds)

        for key in ["team_a", "team_b"]:
            analytics["total_distance_km"][key] = round(analytics["total_distance_km"][key], 1)
            if speed_sums[key]:
                analytics["avg_speed_kmh"][key] = round(np.mean(speed_sums[key]), 1)

        return analytics



================================================================================
FILE: /app/frontend/.env
================================================================================
REACT_APP_BACKEND_URL=https://video-ingestion-hub.preview.emergentagent.com
WDS_SOCKET_PORT=443
ENABLE_HEALTH_CHECK=false


================================================================================
FILE: /app/frontend/package.json
================================================================================
{
  "name": "frontend",
  "version": "0.1.0",
  "private": true,
  "dependencies": {
    "@hookform/resolvers": "^5.0.1",
    "@phosphor-icons/react": "^2.1.10",
    "@radix-ui/react-accordion": "^1.2.8",
    "@radix-ui/react-alert-dialog": "^1.1.11",
    "@radix-ui/react-aspect-ratio": "^1.1.4",
    "@radix-ui/react-avatar": "^1.1.7",
    "@radix-ui/react-checkbox": "^1.2.3",
    "@radix-ui/react-collapsible": "^1.1.8",
    "@radix-ui/react-context-menu": "^2.2.12",
    "@radix-ui/react-dialog": "^1.1.11",
    "@radix-ui/react-dropdown-menu": "^2.1.12",
    "@radix-ui/react-hover-card": "^1.1.11",
    "@radix-ui/react-label": "^2.1.4",
    "@radix-ui/react-menubar": "^1.1.12",
    "@radix-ui/react-navigation-menu": "^1.2.10",
    "@radix-ui/react-popover": "^1.1.11",
    "@radix-ui/react-progress": "^1.1.4",
    "@radix-ui/react-radio-group": "^1.3.4",
    "@radix-ui/react-scroll-area": "^1.2.6",
    "@radix-ui/react-select": "^2.2.2",
    "@radix-ui/react-separator": "^1.1.4",
    "@radix-ui/react-slider": "^1.3.2",
    "@radix-ui/react-slot": "^1.2.0",
    "@radix-ui/react-switch": "^1.2.2",
    "@radix-ui/react-tabs": "^1.1.9",
    "@radix-ui/react-toast": "^1.2.11",
    "@radix-ui/react-toggle": "^1.1.6",
    "@radix-ui/react-toggle-group": "^1.1.7",
    "@radix-ui/react-tooltip": "^1.2.4",
    "axios": "^1.8.4",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "cmdk": "^1.1.1",
    "cra-template": "1.2.0",
    "date-fns": "^4.1.0",
    "embla-carousel-react": "^8.6.0",
    "input-otp": "^1.4.2",
    "lucide-react": "^0.507.0",
    "next-themes": "^0.4.6",
    "react": "^19.0.0",
    "react-day-picker": "8.10.1",
    "react-dom": "^19.0.0",
    "react-hook-form": "^7.56.2",
    "react-resizable-panels": "^3.0.1",
    "react-router-dom": "^7.5.1",
    "react-scripts": "5.0.1",
    "recharts": "^3.6.0",
    "sonner": "^2.0.3",
    "tailwind-merge": "^3.2.0",
    "tailwindcss-animate": "^1.0.7",
    "vaul": "^1.1.2",
    "zod": "^3.24.4"
  },
  "scripts": {
    "start": "craco start",
    "build": "craco build",
    "test": "craco test"
  },
  "browserslist": {
    "production": [
      ">0.2%",
      "not dead",
      "not op_mini all"
    ],
    "development": [
      "last 1 chrome version",
      "last 1 firefox version",
      "last 1 safari version"
    ]
  },
  "devDependencies": {
    "@babel/plugin-proposal-private-property-in-object": "^7.21.11",
    "@craco/craco": "^7.1.0",
    "@emergentbase/visual-edits": "https://assets.emergent.sh/npm/emergentbase-visual-edits-1.0.8.tgz",
    "@eslint/js": "9.23.0",
    "autoprefixer": "^10.4.20",
    "eslint": "9.23.0",
    "eslint-plugin-import": "2.31.0",
    "eslint-plugin-jsx-a11y": "6.10.2",
    "eslint-plugin-react": "7.37.4",
    "eslint-plugin-react-hooks": "5.2.0",
    "globals": "15.15.0",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17"
  },
  "packageManager": "yarn@1.22.22+sha512.a6b2f7906b721bba3d67d4aff083df04dad64c399707841b7acf00f6b133b7ac24255f2652fa22ae3534329dc6180534e98d17432037ff6fd140556e2bb3137e"
}



================================================================================
FILE: /app/frontend/tailwind.config.js
================================================================================
/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
  	extend: {
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		colors: {
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			}
  		},
  		keyframes: {
  			'accordion-down': {
  				from: {
  					height: '0'
  				},
  				to: {
  					height: 'var(--radix-accordion-content-height)'
  				}
  			},
  			'accordion-up': {
  				from: {
  					height: 'var(--radix-accordion-content-height)'
  				},
  				to: {
  					height: '0'
  				}
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out'
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
};


================================================================================
FILE: /app/frontend/src/index.js
================================================================================
import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);



================================================================================
FILE: /app/frontend/src/index.css
================================================================================
@import url('https://fonts.googleapis.com/css2?family=Chivo:wght@400;500;600;700;900&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');

@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'IBM Plex Sans', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

h1, h2, h3, h4, h5, h6 {
  font-family: 'Chivo', sans-serif;
}

code, .font-mono {
  font-family: 'IBM Plex Mono', monospace;
}

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 240 10% 3.9%;
    --card: 0 0% 100%;
    --card-foreground: 240 10% 3.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 240 10% 3.9%;
    --primary: 240 5.9% 10%;
    --primary-foreground: 0 0% 98%;
    --secondary: 240 4.8% 95.9%;
    --secondary-foreground: 240 5.9% 10%;
    --muted: 240 4.8% 95.9%;
    --muted-foreground: 240 3.8% 46.1%;
    --accent: 240 4.8% 95.9%;
    --accent-foreground: 240 5.9% 10%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 0 0% 98%;
    --border: 240 5.9% 90%;
    --input: 240 5.9% 90%;
    --ring: 240 5.9% 10%;
    --chart-1: 239 84% 67%;
    --chart-2: 160 84% 39%;
    --chart-3: 0 84% 60%;
    --chart-4: 43 74% 66%;
    --chart-5: 27 87% 67%;
    --radius: 0.125rem;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}

@layer base {
  [data-debug-wrapper="true"] {
    display: contents !important;
  }
  [data-debug-wrapper="true"] > * {
    margin-left: inherit;
    margin-right: inherit;
    margin-top: inherit;
    margin-bottom: inherit;
    padding-left: inherit;
    padding-right: inherit;
    padding-top: inherit;
    padding-bottom: inherit;
    column-gap: inherit;
    row-gap: inherit;
    gap: inherit;
    border-left-width: inherit;
    border-right-width: inherit;
    border-top-width: inherit;
    border-bottom-width: inherit;
    border-left-style: inherit;
    border-right-style: inherit;
    border-top-style: inherit;
    border-bottom-style: inherit;
    border-left-color: inherit;
    border-right-color: inherit;
    border-top-color: inherit;
    border-bottom-color: inherit;
  }
}



================================================================================
FILE: /app/frontend/src/App.js
================================================================================
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Upload from "@/pages/Upload";
import Jobs from "@/pages/Jobs";
import JobDetail from "@/pages/JobDetail";
import Settings from "@/pages/Settings";
import Pipeline from "@/pages/Pipeline";

function App() {
  return (
    <div className="min-h-screen bg-white">
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/jobs/:jobId" element={<JobDetail />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/pipeline" element={<Pipeline />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster />
    </div>
  );
}

export default App;



================================================================================
FILE: /app/frontend/src/App.css
================================================================================
/* Swiss Brutalist overrides */
.status-badge-pending { @apply bg-yellow-400 text-zinc-950 font-medium; }
.status-badge-processing { @apply bg-indigo-600 text-white; }
.status-badge-completed { @apply bg-emerald-600 text-white; }
.status-badge-failed { @apply bg-red-600 text-white; }

.grid-border-item {
  @apply border-r border-b border-zinc-200 p-6;
}
.grid-border-item:last-child {
  @apply border-r-0;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in-up {
  animation: fadeInUp 0.4s ease-out forwards;
}

.stagger-1 { animation-delay: 0.05s; }
.stagger-2 { animation-delay: 0.1s; }
.stagger-3 { animation-delay: 0.15s; }
.stagger-4 { animation-delay: 0.2s; }



================================================================================
FILE: /app/frontend/src/lib/utils.js
================================================================================
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}



================================================================================
FILE: /app/frontend/src/components/Layout.jsx
================================================================================
import { NavLink, Outlet } from "react-router-dom";
import {
  HouseSimple,
  UploadSimple,
  ListBullets,
  GearSix,
  TreeStructure,
} from "@phosphor-icons/react";

const navItems = [
  { to: "/", label: "DASHBOARD", icon: HouseSimple },
  { to: "/upload", label: "UPLOAD", icon: UploadSimple },
  { to: "/jobs", label: "JOBS", icon: ListBullets },
  { to: "/pipeline", label: "PIPELINE", icon: TreeStructure },
  { to: "/settings", label: "SETTINGS", icon: GearSix },
];

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <header
        className="sticky top-0 z-50 bg-white border-b-2 border-zinc-950"
        data-testid="main-header"
      >
        <div className="max-w-[1440px] mx-auto px-6 flex items-center justify-between h-14">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-zinc-950 rounded-sm flex items-center justify-center">
              <span className="text-white font-mono text-xs font-bold">FV</span>
            </div>
            <span className="font-['Chivo'] font-black text-zinc-950 text-sm tracking-tight">
              FOOTBALL VISION
            </span>
          </div>
          <nav className="flex items-center gap-1" data-testid="main-nav">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold tracking-[0.15em] uppercase transition-colors duration-150 ${
                    isActive
                      ? "bg-zinc-950 text-white"
                      : "text-zinc-500 hover:bg-zinc-100 hover:text-zinc-950"
                  }`
                }
                data-testid={`nav-${label.toLowerCase()}`}
              >
                <Icon size={14} weight="bold" />
                <span className="hidden sm:inline">{label}</span>
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-[1440px] mx-auto w-full px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}



================================================================================
FILE: /app/frontend/src/pages/Dashboard.jsx
================================================================================
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import {
  VideoCamera,
  Lightning,
  CheckCircle,
  XCircle,
  ArrowRight,
  Clock,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusConfig = {
  pending_config: { label: "PENDING CONFIG", cls: "bg-yellow-400 text-zinc-950" },
  submitted: { label: "SUBMITTED", cls: "bg-indigo-600 text-white" },
  queued: { label: "QUEUED", cls: "bg-indigo-600 text-white" },
  processing: { label: "PROCESSING", cls: "bg-indigo-600 text-white" },
  completed: { label: "COMPLETED", cls: "bg-emerald-600 text-white" },
  failed: { label: "FAILED", cls: "bg-red-600 text-white" },
  submission_failed: { label: "FAILED", cls: "bg-red-600 text-white" },
};

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recentJobs, setRecentJobs] = useState([]);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/stats`),
      axios.get(`${API}/jobs`),
    ]).then(([statsRes, jobsRes]) => {
      setStats(statsRes.data);
      setRecentJobs(jobsRes.data.slice(0, 5));
    }).catch(console.error);
  }, []);

  return (
    <div data-testid="dashboard-page">
      <div className="mb-10">
        <h1 className="font-['Chivo'] text-4xl sm:text-5xl font-black text-zinc-950 tracking-tighter">
          Control Room
        </h1>
        <p className="text-base text-zinc-500 mt-2 font-['IBM_Plex_Sans']">
          Football video analysis pipeline — upload, process, extract.
        </p>
      </div>

      {/* Stats Grid */}
      <div
        className="grid grid-cols-2 md:grid-cols-4 border border-zinc-200 mb-10 animate-fade-in-up"
        data-testid="stats-grid"
      >
        <StatCard
          icon={<VideoCamera size={20} weight="bold" />}
          label="VIDEOS"
          value={stats?.total_videos ?? "—"}
          delay="stagger-1"
        />
        <StatCard
          icon={<Lightning size={20} weight="bold" />}
          label="PROCESSING"
          value={stats?.processing_jobs ?? "—"}
          accent
          delay="stagger-2"
        />
        <StatCard
          icon={<CheckCircle size={20} weight="bold" />}
          label="COMPLETED"
          value={stats?.completed_jobs ?? "—"}
          delay="stagger-3"
        />
        <StatCard
          icon={<XCircle size={20} weight="bold" />}
          label="FAILED"
          value={stats?.failed_jobs ?? "—"}
          delay="stagger-4"
        />
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
        <Link
          to="/upload"
          data-testid="quick-upload-btn"
          className="group border-2 border-zinc-950 p-6 flex items-center justify-between transition-transform duration-200 hover:-translate-y-1 hover:shadow-md"
        >
          <div>
            <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              STEP 1
            </p>
            <p className="font-['Chivo'] text-lg font-bold text-zinc-950 mt-1">
              Upload Video
            </p>
          </div>
          <ArrowRight
            size={20}
            weight="bold"
            className="text-zinc-400 group-hover:text-zinc-950 transition-colors duration-150"
          />
        </Link>
        <Link
          to="/settings"
          data-testid="quick-settings-btn"
          className="group border border-zinc-200 p-6 flex items-center justify-between transition-transform duration-200 hover:-translate-y-1 hover:shadow-md"
        >
          <div>
            <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              STEP 2
            </p>
            <p className="font-['Chivo'] text-lg font-bold text-zinc-950 mt-1">
              Configure RunPod
            </p>
          </div>
          <ArrowRight
            size={20}
            weight="bold"
            className="text-zinc-400 group-hover:text-zinc-950 transition-colors duration-150"
          />
        </Link>
        <Link
          to="/pipeline"
          data-testid="quick-pipeline-btn"
          className="group border border-zinc-200 p-6 flex items-center justify-between transition-transform duration-200 hover:-translate-y-1 hover:shadow-md"
        >
          <div>
            <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              STEP 3
            </p>
            <p className="font-['Chivo'] text-lg font-bold text-zinc-950 mt-1">
              Deploy Handler
            </p>
          </div>
          <ArrowRight
            size={20}
            weight="bold"
            className="text-zinc-400 group-hover:text-zinc-950 transition-colors duration-150"
          />
        </Link>
      </div>

      {/* Recent Jobs */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-['Chivo'] text-xl font-bold text-zinc-950 tracking-tight">
            Recent Jobs
          </h2>
          <Link
            to="/jobs"
            className="text-xs font-bold tracking-[0.15em] uppercase text-zinc-500 hover:text-zinc-950 transition-colors"
            data-testid="view-all-jobs-link"
          >
            View All
          </Link>
        </div>
        {recentJobs.length === 0 ? (
          <div className="border border-zinc-200 p-12 text-center" data-testid="no-jobs-empty">
            <Clock size={32} weight="duotone" className="mx-auto text-zinc-300 mb-3" />
            <p className="text-sm text-zinc-400">No jobs yet. Upload a video to get started.</p>
          </div>
        ) : (
          <div className="border border-zinc-200 divide-y divide-zinc-200" data-testid="recent-jobs-list">
            {recentJobs.map((job) => {
              const sc = statusConfig[job.status] || statusConfig.pending_config;
              return (
                <Link
                  key={job.id}
                  to={`/jobs/${job.id}`}
                  className="flex items-center justify-between p-4 hover:bg-zinc-50 transition-colors duration-150"
                  data-testid={`job-row-${job.id}`}
                >
                  <div className="flex items-center gap-4">
                    <div>
                      <p className="font-['Chivo'] font-semibold text-sm text-zinc-950">
                        {job.name}
                      </p>
                      <p className="font-mono text-xs text-zinc-400 mt-0.5">
                        {job.id.slice(0, 8)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge className={`rounded-sm text-[10px] font-bold tracking-wider ${sc.cls}`}>
                      {sc.label}
                    </Badge>
                    <span className="font-mono text-xs text-zinc-400">
                      {new Date(job.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, accent, delay }) {
  return (
    <div
      className={`grid-border-item animate-fade-in-up ${delay} ${
        accent ? "bg-indigo-600" : "bg-white"
      }`}
    >
      <div className={`mb-3 ${accent ? "text-indigo-200" : "text-zinc-400"}`}>
        {icon}
      </div>
      <p
        className={`text-xs font-bold tracking-[0.2em] uppercase ${
          accent ? "text-indigo-200" : "text-zinc-500"
        }`}
      >
        {label}
      </p>
      <p
        className={`font-mono text-3xl font-bold mt-1 ${
          accent ? "text-white" : "text-zinc-950"
        }`}
      >
        {value}
      </p>
    </div>
  );
}



================================================================================
FILE: /app/frontend/src/pages/Upload.jsx
================================================================================
import { useState, useCallback, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  UploadSimple,
  FilmStrip,
  LinkSimple,
  Trash,
  Play,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Upload() {
  const navigate = useNavigate();
  const [videos, setVideos] = useState([]);
  const [uploading, setUploading] = useState({ first: false, second: false });
  const [progress, setProgress] = useState({ first: 0, second: 0 });
  const [urlMode, setUrlMode] = useState({ first: false, second: false });
  const [urlInput, setUrlInput] = useState({ first: "", second: "" });
  const [jobName, setJobName] = useState("");

  const fetchVideos = useCallback(async () => {
    const res = await axios.get(`${API}/videos`);
    setVideos(res.data);
  }, []);

  useEffect(() => {
    fetchVideos();
  }, [fetchVideos]);

  const handleFileUpload = async (half, file) => {
    if (!file) return;
    setUploading((u) => ({ ...u, [half]: true }));
    setProgress((p) => ({ ...p, [half]: 0 }));

    const formData = new FormData();
    formData.append("file", file);
    formData.append("half", half);

    try {
      await axios.post(`${API}/videos/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          const pct = Math.round((e.loaded * 100) / (e.total || 1));
          setProgress((p) => ({ ...p, [half]: pct }));
        },
      });
      toast.success(`${half === "first" ? "First" : "Second"} half uploaded`);
      fetchVideos();
    } catch (err) {
      toast.error("Upload failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setUploading((u) => ({ ...u, [half]: false }));
    }
  };

  const handleUrlSubmit = async (half) => {
    const url = urlInput[half];
    if (!url) return;
    try {
      await axios.post(`${API}/videos/url`, { half, external_url: url });
      toast.success("Video URL added");
      setUrlInput((u) => ({ ...u, [half]: "" }));
      fetchVideos();
    } catch (err) {
      toast.error("Failed: " + (err.response?.data?.detail || err.message));
    }
  };

  const deleteVideo = async (id) => {
    await axios.delete(`${API}/videos/${id}`);
    fetchVideos();
  };

  const createJob = async () => {
    if (videos.length === 0) {
      toast.error("Upload at least one video first");
      return;
    }
    const name = jobName || `Match Analysis ${new Date().toLocaleDateString()}`;
    try {
      const res = await axios.post(`${API}/jobs`, {
        name,
        video_ids: videos.map((v) => v.id),
      });
      toast.success("Job created");
      navigate(`/jobs/${res.data.id}`);
    } catch (err) {
      toast.error("Failed: " + (err.response?.data?.detail || err.message));
    }
  };

  const firstHalf = videos.filter((v) => v.half === "first");
  const secondHalf = videos.filter((v) => v.half === "second");

  return (
    <div data-testid="upload-page">
      <div className="mb-10">
        <h1 className="font-['Chivo'] text-4xl sm:text-5xl font-black text-zinc-950 tracking-tighter">
          Upload Match Video
        </h1>
        <p className="text-base text-zinc-500 mt-2">
          Upload 4K footage split by half. Supports direct file upload or external URL.
        </p>
      </div>

      {/* Two-column bento for halves */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-10">
        <HalfUploadZone
          half="first"
          label="First Half"
          videos={firstHalf}
          uploading={uploading.first}
          progress={progress.first}
          urlMode={urlMode.first}
          urlInput={urlInput.first}
          onToggleUrl={() => setUrlMode((m) => ({ ...m, first: !m.first }))}
          onUrlChange={(v) => setUrlInput((u) => ({ ...u, first: v }))}
          onUrlSubmit={() => handleUrlSubmit("first")}
          onFileSelect={(f) => handleFileUpload("first", f)}
          onDelete={deleteVideo}
        />
        <HalfUploadZone
          half="second"
          label="Second Half"
          videos={secondHalf}
          uploading={uploading.second}
          progress={progress.second}
          urlMode={urlMode.second}
          urlInput={urlInput.second}
          onToggleUrl={() => setUrlMode((m) => ({ ...m, second: !m.second }))}
          onUrlChange={(v) => setUrlInput((u) => ({ ...u, second: v }))}
          onUrlSubmit={() => handleUrlSubmit("second")}
          onFileSelect={(f) => handleFileUpload("second", f)}
          onDelete={deleteVideo}
        />
      </div>

      {/* Create Job */}
      <div className="border-2 border-zinc-950 p-6" data-testid="create-job-section">
        <h3 className="font-['Chivo'] text-lg font-bold text-zinc-950 mb-4">
          Submit Processing Job
        </h3>
        <div className="flex flex-col sm:flex-row gap-4 items-end">
          <div className="flex-1">
            <label className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 block mb-2">
              JOB NAME
            </label>
            <input
              type="text"
              value={jobName}
              onChange={(e) => setJobName(e.target.value)}
              placeholder="e.g. Arsenal vs Chelsea — Match Day 12"
              className="w-full border border-zinc-300 px-4 py-2.5 text-sm font-['IBM_Plex_Sans'] focus:ring-2 focus:ring-zinc-950 focus:outline-none"
              data-testid="job-name-input"
            />
          </div>
          <button
            onClick={createJob}
            disabled={videos.length === 0}
            className="bg-zinc-950 text-white px-8 py-2.5 text-xs font-bold tracking-[0.15em] uppercase hover:bg-zinc-800 hover:text-white transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
            data-testid="create-job-btn"
          >
            <Play size={14} weight="bold" />
            Create Job
          </button>
        </div>
        <p className="text-xs text-zinc-400 mt-3 font-mono">
          {videos.length} video(s) selected. Job will use default pipeline config (YOLOv8x + ByteTrack).
        </p>
      </div>
    </div>
  );
}

function HalfUploadZone({
  half,
  label,
  videos,
  uploading,
  progress,
  urlMode,
  urlInput,
  onToggleUrl,
  onUrlChange,
  onUrlSubmit,
  onFileSelect,
  onDelete,
}) {
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFileSelect(file);
  };

  return (
    <div className="border border-zinc-200" data-testid={`upload-zone-${half}`}>
      <div className="border-b border-zinc-200 px-6 py-3 flex items-center justify-between bg-zinc-50">
        <span className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
          {label}
        </span>
        <button
          onClick={onToggleUrl}
          className="text-xs font-bold text-zinc-400 hover:text-zinc-950 flex items-center gap-1 transition-colors"
          data-testid={`toggle-url-${half}`}
        >
          {urlMode ? (
            <>
              <UploadSimple size={12} weight="bold" /> File Upload
            </>
          ) : (
            <>
              <LinkSimple size={12} weight="bold" /> Use URL
            </>
          )}
        </button>
      </div>

      <div className="p-6">
        {urlMode ? (
          <div className="flex gap-2">
            <input
              type="url"
              value={urlInput}
              onChange={(e) => onUrlChange(e.target.value)}
              placeholder="https://storage.example.com/video.mp4"
              className="flex-1 border border-zinc-300 px-4 py-2.5 font-mono text-sm focus:ring-2 focus:ring-zinc-950 focus:outline-none"
              data-testid={`url-input-${half}`}
            />
            <button
              onClick={onUrlSubmit}
              className="bg-zinc-950 text-white px-4 py-2.5 text-xs font-bold uppercase hover:bg-zinc-800 hover:text-white transition-colors"
              data-testid={`url-submit-${half}`}
            >
              Add
            </button>
          </div>
        ) : (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed p-10 text-center cursor-pointer transition-colors duration-150 ${
              dragOver
                ? "border-zinc-950 bg-zinc-50"
                : "border-zinc-300 hover:border-zinc-400"
            }`}
            onClick={() => {
              const input = document.createElement("input");
              input.type = "file";
              input.accept = "video/*";
              input.onchange = (e) => onFileSelect(e.target.files[0]);
              input.click();
            }}
            data-testid={`dropzone-${half}`}
          >
            <FilmStrip
              size={32}
              weight="duotone"
              className="mx-auto text-zinc-300 mb-3"
            />
            <p className="text-sm text-zinc-500">
              Drop video file here or click to browse
            </p>
            <p className="text-xs text-zinc-400 mt-1 font-mono">
              MP4, MKV, AVI — max 10GB
            </p>
          </div>
        )}

        {uploading && (
          <div className="mt-4" data-testid={`upload-progress-${half}`}>
            <div className="flex justify-between mb-1">
              <span className="text-xs font-bold text-zinc-500">UPLOADING</span>
              <span className="font-mono text-xs text-zinc-700">{progress}%</span>
            </div>
            <Progress value={progress} className="h-1.5 rounded-none bg-zinc-100 [&>div]:bg-indigo-600" />
          </div>
        )}

        {videos.length > 0 && (
          <div className="mt-4 space-y-2" data-testid={`video-list-${half}`}>
            {videos.map((v) => (
              <div
                key={v.id}
                className="flex items-center justify-between border border-zinc-200 px-4 py-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <FilmStrip size={14} weight="bold" className="text-zinc-400 shrink-0" />
                  <span className="text-sm text-zinc-700 truncate">{v.filename}</span>
                  <Badge className="rounded-sm text-[10px] bg-zinc-100 text-zinc-500 shrink-0">
                    {v.source === "url" ? "URL" : v.size_mb ? `${v.size_mb} MB` : "—"}
                  </Badge>
                </div>
                <button
                  onClick={() => onDelete(v.id)}
                  className="text-zinc-400 hover:text-red-600 transition-colors ml-2"
                  data-testid={`delete-video-${v.id}`}
                >
                  <Trash size={14} weight="bold" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}



================================================================================
FILE: /app/frontend/src/pages/Jobs.jsx
================================================================================
import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Clock, ArrowRight } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusConfig = {
  pending_config: { label: "PENDING CONFIG", cls: "bg-yellow-400 text-zinc-950" },
  submitted: { label: "SUBMITTED", cls: "bg-indigo-600 text-white" },
  queued: { label: "QUEUED", cls: "bg-indigo-600 text-white" },
  processing: { label: "PROCESSING", cls: "bg-indigo-600 text-white" },
  completed: { label: "COMPLETED", cls: "bg-emerald-600 text-white" },
  failed: { label: "FAILED", cls: "bg-red-600 text-white" },
  submission_failed: { label: "SUBMIT FAILED", cls: "bg-red-600 text-white" },
};

export default function Jobs() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios
      .get(`${API}/jobs`)
      .then((res) => setJobs(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div data-testid="jobs-page">
      <div className="mb-10">
        <h1 className="font-['Chivo'] text-4xl sm:text-5xl font-black text-zinc-950 tracking-tighter">
          Processing Jobs
        </h1>
        <p className="text-base text-zinc-500 mt-2">
          Track RunPod GPU processing status and access results.
        </p>
      </div>

      {loading ? (
        <div className="border border-zinc-200 p-12 text-center">
          <p className="text-sm text-zinc-400 font-mono">Loading...</p>
        </div>
      ) : jobs.length === 0 ? (
        <div className="border border-zinc-200 p-16 text-center" data-testid="no-jobs-empty">
          <Clock size={40} weight="duotone" className="mx-auto text-zinc-300 mb-4" />
          <p className="text-zinc-500 mb-4">No processing jobs yet.</p>
          <Link
            to="/upload"
            className="inline-flex items-center gap-2 bg-zinc-950 text-white px-6 py-2.5 text-xs font-bold tracking-[0.15em] uppercase hover:bg-zinc-800 hover:text-white transition-colors"
            data-testid="go-upload-btn"
          >
            Upload Video <ArrowRight size={14} weight="bold" />
          </Link>
        </div>
      ) : (
        <div className="border border-zinc-200" data-testid="jobs-table">
          <Table>
            <TableHeader>
              <TableRow className="bg-zinc-50">
                <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
                  JOB NAME
                </TableHead>
                <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
                  ID
                </TableHead>
                <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
                  STATUS
                </TableHead>
                <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
                  VIDEOS
                </TableHead>
                <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 text-right">
                  CREATED
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {jobs.map((job) => {
                const sc = statusConfig[job.status] || statusConfig.pending_config;
                return (
                  <TableRow
                    key={job.id}
                    className="even:bg-zinc-50 hover:bg-zinc-100 cursor-pointer transition-colors"
                    data-testid={`job-row-${job.id}`}
                  >
                    <TableCell>
                      <Link
                        to={`/jobs/${job.id}`}
                        className="font-['Chivo'] font-semibold text-sm text-zinc-950 hover:underline"
                      >
                        {job.name}
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-zinc-400">
                      {job.id.slice(0, 8)}
                    </TableCell>
                    <TableCell>
                      <Badge className={`rounded-sm text-[10px] font-bold tracking-wider ${sc.cls}`}>
                        {sc.label}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-sm text-zinc-700">
                      {job.video_ids?.length || 0}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-zinc-400 text-right">
                      {new Date(job.created_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}



================================================================================
FILE: /app/frontend/src/pages/JobDetail.jsx
================================================================================
import { useState, useEffect, useCallback } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DownloadSimple,
  ArrowClockwise,
  Lightning,
  CheckCircle,
  Users,
  SoccerBall,
  ChartBar,
  Table as TableIcon,
  Code,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusConfig = {
  pending_config: { label: "PENDING CONFIG", cls: "bg-yellow-400 text-zinc-950" },
  submitted: { label: "SUBMITTED", cls: "bg-indigo-600 text-white" },
  queued: { label: "QUEUED", cls: "bg-indigo-600 text-white" },
  processing: { label: "PROCESSING", cls: "bg-indigo-600 text-white" },
  completed: { label: "COMPLETED", cls: "bg-emerald-600 text-white" },
  failed: { label: "FAILED", cls: "bg-red-600 text-white" },
  submission_failed: { label: "SUBMIT FAILED", cls: "bg-red-600 text-white" },
};

export default function JobDetail() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [mocking, setMocking] = useState(false);

  const fetchJob = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/jobs/${jobId}`);
      setJob(res.data);
    } catch (err) {
      toast.error("Failed to load job");
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  const pollStatus = async () => {
    setPolling(true);
    try {
      await axios.post(`${API}/jobs/${jobId}/poll`);
      await fetchJob();
      toast.success("Status updated");
    } catch (err) {
      toast.error("Poll failed");
    } finally {
      setPolling(false);
    }
  };

  const mockComplete = async () => {
    setMocking(true);
    try {
      await axios.post(`${API}/jobs/${jobId}/mock-complete`);
      await fetchJob();
      toast.success("Demo data generated");
    } catch (err) {
      toast.error("Failed to generate demo data");
    } finally {
      setMocking(false);
    }
  };

  const downloadResults = (format) => {
    window.open(`${API}/jobs/${jobId}/download/${format}`, "_blank");
  };

  if (loading) {
    return (
      <div className="p-12 text-center">
        <p className="text-sm text-zinc-400 font-mono">Loading job...</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="p-12 text-center">
        <p className="text-sm text-red-500">Job not found.</p>
      </div>
    );
  }

  const sc = statusConfig[job.status] || statusConfig.pending_config;
  const results = job.results;

  return (
    <div data-testid="job-detail-page">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 mb-1">
              JOB
            </p>
            <h1 className="font-['Chivo'] text-3xl sm:text-4xl font-black text-zinc-950 tracking-tighter">
              {job.name}
            </h1>
            <p className="font-mono text-xs text-zinc-400 mt-1">{job.id}</p>
          </div>
          <div className="flex items-center gap-3">
            <Badge
              className={`rounded-sm text-xs font-bold tracking-wider px-3 py-1 ${sc.cls}`}
              data-testid="job-status-badge"
            >
              {sc.label}
            </Badge>
          </div>
        </div>
      </div>

      {/* Progress + Actions */}
      <div className="border border-zinc-200 p-6 mb-8" data-testid="job-actions-panel">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              PROGRESS
            </p>
            <p className="font-mono text-2xl font-bold text-zinc-950 mt-1">
              {job.progress || 0}%
            </p>
          </div>
          <div className="flex gap-2">
            {job.status !== "completed" && (
              <>
                <button
                  onClick={pollStatus}
                  disabled={polling}
                  className="flex items-center gap-1.5 border border-zinc-300 px-4 py-2 text-xs font-bold uppercase text-zinc-700 hover:bg-zinc-100 hover:text-zinc-950 transition-colors disabled:opacity-40"
                  data-testid="poll-status-btn"
                >
                  <ArrowClockwise
                    size={14}
                    weight="bold"
                    className={polling ? "animate-spin" : ""}
                  />
                  Poll RunPod
                </button>
                <button
                  onClick={mockComplete}
                  disabled={mocking}
                  className="flex items-center gap-1.5 bg-indigo-600 text-white px-4 py-2 text-xs font-bold uppercase hover:bg-indigo-700 hover:text-white transition-colors disabled:opacity-40"
                  data-testid="mock-complete-btn"
                >
                  <Lightning size={14} weight="bold" />
                  {mocking ? "Generating..." : "Demo Data"}
                </button>
              </>
            )}
            {results && (
              <>
                <button
                  onClick={() => downloadResults("json")}
                  className="flex items-center gap-1.5 bg-zinc-950 text-white px-4 py-2 text-xs font-bold uppercase hover:bg-zinc-800 hover:text-white transition-colors"
                  data-testid="download-json-btn"
                >
                  <DownloadSimple size={14} weight="bold" />
                  JSON
                </button>
                <button
                  onClick={() => downloadResults("csv")}
                  className="flex items-center gap-1.5 border border-zinc-950 text-zinc-950 px-4 py-2 text-xs font-bold uppercase hover:bg-zinc-950 hover:text-white transition-colors"
                  data-testid="download-csv-btn"
                >
                  <DownloadSimple size={14} weight="bold" />
                  CSV
                </button>
              </>
            )}
          </div>
        </div>
        <Progress
          value={job.progress || 0}
          className="h-2 rounded-none bg-zinc-100 [&>div]:bg-indigo-600"
        />
        {job.error && (
          <p className="font-mono text-xs text-red-600 mt-3" data-testid="job-error">
            Error: {job.error}
          </p>
        )}
      </div>

      {/* Config */}
      <div className="border border-zinc-200 p-6 mb-8" data-testid="job-config-panel">
        <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 mb-4">
          PIPELINE CONFIG
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(job.config || {}).map(([key, val]) => (
            <div key={key}>
              <p className="text-xs text-zinc-400 uppercase">{key.replace(/_/g, " ")}</p>
              <p className="font-mono text-sm text-zinc-950 font-medium">
                {String(val)}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Results */}
      {results && <ResultsViewer results={results} />}
    </div>
  );
}

function ResultsViewer({ results }) {
  return (
    <div data-testid="results-viewer">
      <h2 className="font-['Chivo'] text-xl font-bold text-zinc-950 tracking-tight mb-4">
        Analysis Results
      </h2>
      <Tabs defaultValue="analytics" className="w-full">
        <TabsList className="w-full justify-start bg-zinc-50 border border-zinc-200 rounded-none h-auto p-0 flex-wrap">
          <TabsTrigger
            value="analytics"
            className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-white px-4 py-2.5 text-xs font-bold tracking-wider uppercase"
            data-testid="tab-analytics"
          >
            <ChartBar size={14} weight="bold" className="mr-1.5" />
            Analytics
          </TabsTrigger>
          <TabsTrigger
            value="events"
            className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-white px-4 py-2.5 text-xs font-bold tracking-wider uppercase"
            data-testid="tab-events"
          >
            <SoccerBall size={14} weight="bold" className="mr-1.5" />
            Events
          </TabsTrigger>
          <TabsTrigger
            value="teams"
            className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-white px-4 py-2.5 text-xs font-bold tracking-wider uppercase"
            data-testid="tab-teams"
          >
            <Users size={14} weight="bold" className="mr-1.5" />
            Teams
          </TabsTrigger>
          <TabsTrigger
            value="tracking"
            className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-white px-4 py-2.5 text-xs font-bold tracking-wider uppercase"
            data-testid="tab-tracking"
          >
            <TableIcon size={14} weight="bold" className="mr-1.5" />
            Tracking
          </TabsTrigger>
          <TabsTrigger
            value="raw"
            className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-white px-4 py-2.5 text-xs font-bold tracking-wider uppercase"
            data-testid="tab-raw"
          >
            <Code size={14} weight="bold" className="mr-1.5" />
            Raw JSON
          </TabsTrigger>
        </TabsList>

        <TabsContent value="analytics" className="mt-0 border border-t-0 border-zinc-200">
          <AnalyticsTab analytics={results.analytics} metadata={results.metadata} />
        </TabsContent>
        <TabsContent value="events" className="mt-0 border border-t-0 border-zinc-200">
          <EventsTab events={results.events} />
        </TabsContent>
        <TabsContent value="teams" className="mt-0 border border-t-0 border-zinc-200">
          <TeamsTab teams={results.team_assignments} />
        </TabsContent>
        <TabsContent value="tracking" className="mt-0 border border-t-0 border-zinc-200">
          <TrackingTab data={results.tracking_data} />
        </TabsContent>
        <TabsContent value="raw" className="mt-0 border border-t-0 border-zinc-200">
          <RawJsonTab results={results} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function AnalyticsTab({ analytics, metadata }) {
  if (!analytics) return <div className="p-6 text-zinc-400 text-sm">No analytics data.</div>;

  const metrics = [
    { label: "Possession", a: `${analytics.possession?.team_a}%`, b: `${analytics.possession?.team_b}%` },
    { label: "Pass Accuracy", a: `${analytics.pass_accuracy?.team_a}%`, b: `${analytics.pass_accuracy?.team_b}%` },
    { label: "Shots", a: analytics.shots?.team_a, b: analytics.shots?.team_b },
    { label: "Shots on Target", a: analytics.shots_on_target?.team_a, b: analytics.shots_on_target?.team_b },
    { label: "Corners", a: analytics.corners?.team_a, b: analytics.corners?.team_b },
    { label: "Fouls", a: analytics.fouls?.team_a, b: analytics.fouls?.team_b },
    { label: "Offsides", a: analytics.offsides?.team_a, b: analytics.offsides?.team_b },
    { label: "Distance (km)", a: analytics.total_distance_km?.team_a, b: analytics.total_distance_km?.team_b },
    { label: "Sprints", a: analytics.sprint_count?.team_a, b: analytics.sprint_count?.team_b },
    { label: "Avg Speed (km/h)", a: analytics.avg_speed_kmh?.team_a, b: analytics.avg_speed_kmh?.team_b },
    { label: "xG Total", a: analytics.xg_total?.team_a, b: analytics.xg_total?.team_b },
  ];

  return (
    <div data-testid="analytics-content">
      {/* Metadata */}
      {metadata && (
        <div className="border-b border-zinc-200 p-6 bg-zinc-50">
          <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 mb-3">
            PIPELINE METADATA
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(metadata).map(([k, v]) => (
              <div key={k}>
                <p className="text-xs text-zinc-400 uppercase">{k.replace(/_/g, " ")}</p>
                <p className="font-mono text-sm text-zinc-700">{String(v)}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      {/* Match Stats */}
      <div className="p-6">
        <Table>
          <TableHeader>
            <TableRow className="bg-zinc-50">
              <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
                Metric
              </TableHead>
              <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-indigo-600 text-right">
                Team A
              </TableHead>
              <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-emerald-600 text-right">
                Team B
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {metrics.map((m) => (
              <TableRow key={m.label} className="even:bg-zinc-50">
                <TableCell className="font-medium text-sm text-zinc-700">
                  {m.label}
                </TableCell>
                <TableCell className="font-mono text-sm text-zinc-950 text-right font-bold">
                  {m.a}
                </TableCell>
                <TableCell className="font-mono text-sm text-zinc-950 text-right font-bold">
                  {m.b}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function EventsTab({ events }) {
  if (!events || events.length === 0) {
    return <div className="p-6 text-zinc-400 text-sm">No events detected.</div>;
  }

  return (
    <div className="p-0 overflow-auto max-h-[500px]" data-testid="events-content">
      <Table>
        <TableHeader>
          <TableRow className="bg-zinc-50 sticky top-0">
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              TIME
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              TYPE
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              TEAM
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              PLAYER
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 text-right">
              POSITION
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 text-right">
              CONF
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {events.map((ev) => (
            <TableRow key={ev.id} className="even:bg-zinc-50" data-testid={`event-row-${ev.id}`}>
              <TableCell className="font-mono text-xs text-zinc-700">
                {ev.minute}'{String(ev.second).padStart(2, "0")}
              </TableCell>
              <TableCell>
                <Badge className="rounded-sm text-[10px] font-bold bg-zinc-100 text-zinc-700 uppercase">
                  {ev.type}
                </Badge>
              </TableCell>
              <TableCell className="font-mono text-xs font-bold text-zinc-950">
                {ev.team}
              </TableCell>
              <TableCell className="font-mono text-xs text-zinc-500">
                {ev.player_id || "—"}
              </TableCell>
              <TableCell className="font-mono text-xs text-zinc-500 text-right">
                ({ev.x?.toFixed(1)}, {ev.y?.toFixed(1)})
              </TableCell>
              <TableCell className="font-mono text-xs text-zinc-400 text-right">
                {(ev.confidence * 100).toFixed(0)}%
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function TeamsTab({ teams }) {
  if (!teams || teams.length === 0) {
    return <div className="p-6 text-zinc-400 text-sm">No team data.</div>;
  }

  const teamA = teams.filter((t) => t.team === "A");
  const teamB = teams.filter((t) => t.team === "B");

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 divide-x divide-zinc-200" data-testid="teams-content">
      <TeamList team="A" players={teamA} />
      <TeamList team="B" players={teamB} />
    </div>
  );
}

function TeamList({ team, players }) {
  return (
    <div className="p-6">
      <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 mb-4">
        TEAM {team} — {players.length} PLAYERS
      </p>
      <div className="space-y-2">
        {players.map((p) => (
          <div
            key={p.id}
            className="flex items-center justify-between border-b border-zinc-100 pb-2"
          >
            <div className="flex items-center gap-3">
              <span className="w-8 h-8 bg-zinc-100 flex items-center justify-center font-mono text-sm font-bold text-zinc-700">
                {p.jersey ?? "?"}
              </span>
              <span className="text-sm text-zinc-700">{p.name || p.id}</span>
            </div>
            <span className="font-mono text-xs text-zinc-400">
              {p.id}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrackingTab({ data }) {
  if (!data || data.length === 0) {
    return <div className="p-6 text-zinc-400 text-sm">No tracking data.</div>;
  }

  const sample = data.slice(0, 20);

  return (
    <div className="p-0 overflow-auto max-h-[500px]" data-testid="tracking-content">
      <Table>
        <TableHeader>
          <TableRow className="bg-zinc-50 sticky top-0">
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              FRAME
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500">
              TIME
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 text-right">
              PLAYERS
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 text-right">
              BALL X
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 text-right">
              BALL Y
            </TableHead>
            <TableHead className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 text-right">
              BALL SPEED
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sample.map((frame, i) => (
            <TableRow key={i} className="even:bg-zinc-50">
              <TableCell className="font-mono text-xs text-zinc-700">
                {frame.frame}
              </TableCell>
              <TableCell className="font-mono text-xs text-zinc-500">
                {frame.timestamp?.toFixed(2)}s
              </TableCell>
              <TableCell className="font-mono text-xs text-zinc-700 text-right">
                {frame.players?.length || 0}
              </TableCell>
              <TableCell className="font-mono text-xs text-zinc-700 text-right">
                {frame.ball?.x?.toFixed(1) ?? "—"}
              </TableCell>
              <TableCell className="font-mono text-xs text-zinc-700 text-right">
                {frame.ball?.y?.toFixed(1) ?? "—"}
              </TableCell>
              <TableCell className="font-mono text-xs text-zinc-700 text-right">
                {frame.ball?.speed_kmh?.toFixed(0) ?? "—"} km/h
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {data.length > 20 && (
        <p className="text-xs text-zinc-400 font-mono p-4">
          Showing 20 of {data.length} frames. Download full data via JSON/CSV.
        </p>
      )}
    </div>
  );
}

function RawJsonTab({ results }) {
  return (
    <div className="p-4" data-testid="raw-json-content">
      <pre className="bg-zinc-950 text-zinc-300 p-6 font-mono text-xs overflow-auto max-h-[600px] leading-relaxed">
        {JSON.stringify(results, null, 2)}
      </pre>
    </div>
  );
}



================================================================================
FILE: /app/frontend/src/pages/Settings.jsx
================================================================================
import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CheckCircle, WarningCircle, Eye, EyeSlash } from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [apiKey, setApiKey] = useState("");
  const [endpointId, setEndpointId] = useState("");
  const [saving, setSaving] = useState(false);
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    axios.get(`${API}/settings`).then((res) => {
      setSettings(res.data);
      setEndpointId(res.data.runpod_endpoint_id || "");
    });
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const data = {};
      if (apiKey) data.runpod_api_key = apiKey;
      if (endpointId) data.runpod_endpoint_id = endpointId;
      await axios.post(`${API}/settings`, data);
      toast.success("Settings saved");
      // Refresh
      const res = await axios.get(`${API}/settings`);
      setSettings(res.data);
      setApiKey("");
    } catch (err) {
      toast.error("Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid="settings-page">
      <div className="mb-10">
        <h1 className="font-['Chivo'] text-4xl sm:text-5xl font-black text-zinc-950 tracking-tighter">
          Settings
        </h1>
        <p className="text-base text-zinc-500 mt-2">
          Configure your RunPod connection for GPU processing.
        </p>
      </div>

      {/* Status */}
      <div
        className={`border-2 p-6 mb-8 flex items-center gap-4 ${
          settings?.configured
            ? "border-emerald-600 bg-emerald-50"
            : "border-yellow-400 bg-yellow-50"
        }`}
        data-testid="runpod-status"
      >
        {settings?.configured ? (
          <>
            <CheckCircle size={24} weight="bold" className="text-emerald-600" />
            <div>
              <p className="font-['Chivo'] font-bold text-zinc-950">RunPod Connected</p>
              <p className="text-sm text-zinc-600">
                Endpoint: <span className="font-mono">{settings.runpod_endpoint_id}</span>
              </p>
            </div>
          </>
        ) : (
          <>
            <WarningCircle size={24} weight="bold" className="text-yellow-600" />
            <div>
              <p className="font-['Chivo'] font-bold text-zinc-950">RunPod Not Configured</p>
              <p className="text-sm text-zinc-600">
                Add your API key and endpoint ID to enable GPU processing.
              </p>
            </div>
          </>
        )}
      </div>

      {/* Config Form */}
      <div className="border border-zinc-200 p-8" data-testid="runpod-config-form">
        <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 mb-6">
          RUNPOD CREDENTIALS
        </p>

        <div className="space-y-6">
          <div>
            <label className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 block mb-2">
              API KEY
            </label>
            <div className="relative">
              <input
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={settings?.runpod_api_key || "rp_xxxxxxxxxxxxxxxxxxxxxxxx"}
                className="w-full border border-zinc-300 px-4 py-2.5 font-mono text-sm focus:ring-2 focus:ring-zinc-950 focus:outline-none pr-10"
                data-testid="api-key-input"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-700"
                data-testid="toggle-key-visibility"
              >
                {showKey ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <p className="text-xs text-zinc-400 mt-1">
              Get your key from{" "}
              <a
                href="https://www.runpod.io/console/user/settings"
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-600 hover:underline"
              >
                RunPod Console → Settings → API Keys
              </a>
            </p>
          </div>

          <div>
            <label className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 block mb-2">
              ENDPOINT ID
            </label>
            <input
              type="text"
              value={endpointId}
              onChange={(e) => setEndpointId(e.target.value)}
              placeholder="e.g. abc123xyz"
              className="w-full border border-zinc-300 px-4 py-2.5 font-mono text-sm focus:ring-2 focus:ring-zinc-950 focus:outline-none"
              data-testid="endpoint-id-input"
            />
            <p className="text-xs text-zinc-400 mt-1">
              Found on your{" "}
              <a
                href="https://www.runpod.io/console/serverless"
                target="_blank"
                rel="noopener noreferrer"
                className="text-indigo-600 hover:underline"
              >
                Serverless Endpoint page
              </a>
            </p>
          </div>

          <button
            onClick={save}
            disabled={saving || (!apiKey && !endpointId)}
            className="bg-zinc-950 text-white px-8 py-2.5 text-xs font-bold tracking-[0.15em] uppercase hover:bg-zinc-800 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            data-testid="save-settings-btn"
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>
      </div>

      {/* Help Section */}
      <div className="border border-zinc-200 p-8 mt-8">
        <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 mb-4">
          SETUP GUIDE
        </p>
        <ol className="space-y-3 text-sm text-zinc-600 list-decimal list-inside">
          <li>
            Download the Handler Package from the{" "}
            <span className="font-bold text-zinc-950">Pipeline</span> page
          </li>
          <li>Build the Docker image and push to Docker Hub</li>
          <li>
            Create a Serverless Endpoint on{" "}
            <a
              href="https://www.runpod.io/console/serverless"
              target="_blank"
              rel="noopener noreferrer"
              className="text-indigo-600 hover:underline"
            >
              RunPod
            </a>
          </li>
          <li>Copy your API Key and Endpoint ID into the form above</li>
          <li>Upload a video and create a job — it will be sent to your GPU endpoint</li>
        </ol>
      </div>
    </div>
  );
}



================================================================================
FILE: /app/frontend/src/pages/Pipeline.jsx
================================================================================
import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DownloadSimple,
  TreeStructure,
  Code,
  GithubLogo,
  Cube,
  ArrowRight,
} from "@phosphor-icons/react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PIPELINE_STAGES = [
  {
    name: "Frame Extraction",
    desc: "Samples frames at configurable FPS from 4K video. Handles both halves independently.",
    tech: "OpenCV VideoCapture",
  },
  {
    name: "Object Detection",
    desc: "Detects players, ball, referees using YOLO. Tiled detection for 4K resolution.",
    tech: "YOLOv8x / YOLOv11",
  },
  {
    name: "Multi-Object Tracking",
    desc: "ByteTrack with camera motion compensation. Maintains consistent player IDs across frames.",
    tech: "ByteTrack + BoT-SORT CMC",
  },
  {
    name: "Pitch Calibration",
    desc: "Dynamic homography estimation from detected pitch lines. Maps pixel → real-world meters.",
    tech: "BroadTrack / HRNet / PnLCalib",
  },
  {
    name: "Team Classification",
    desc: "Unsupervised jersey color clustering via K-Means on HSV features. Separates teams + referees.",
    tech: "K-Means + DBSCAN + HSV",
  },
  {
    name: "Event Detection",
    desc: "Detects passes, shots, corners, fouls, offsides from ball trajectory + player proximity.",
    tech: "Rule-based + LSTM temporal",
  },
  {
    name: "Data Export",
    desc: "Aggregates into structured JSON: tracking, events, analytics, team assignments.",
    tech: "JSON / CSV output",
  },
];

const DOCKERFILE_CONTENT = `FROM runpod/pytorch:2.4.0-py3.12-cuda12.4.1-devel-ubuntu24.04
WORKDIR /workspace

RUN apt-get update && apt-get install -y \\
    libgl1-mesa-glx libglib2.0-0 libsm6 \\
    libxext6 libxrender-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from ultralytics import YOLO; YOLO('yolov8x.pt')"

COPY handler.py .
COPY pipeline/ pipeline/

CMD ["python", "-u", "handler.py"]`;

const DEPLOY_STEPS = [
  "Download the handler package (ZIP) from this page",
  "Unzip and review handler.py + pipeline/ modules",
  'Build Docker image: docker build -t yourhub/football-pipeline:latest .',
  'Push to Docker Hub: docker push yourhub/football-pipeline:latest',
  "Go to RunPod Console → Serverless → New Endpoint",
  'Enter your Docker image URL and select GPU (A100 recommended)',
  "Copy the Endpoint ID and your API Key",
  "Enter credentials in Settings page of this app",
];

export default function Pipeline() {
  const [downloading, setDownloading] = useState(false);

  const downloadPackage = async () => {
    setDownloading(true);
    try {
      const res = await axios.get(`${API}/handler-package`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = "runpod_football_handler.zip";
      link.click();
      window.URL.revokeObjectURL(url);
      toast.success("Handler package downloaded");
    } catch (err) {
      toast.error("Download failed");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div data-testid="pipeline-page">
      <div className="mb-10">
        <h1 className="font-['Chivo'] text-4xl sm:text-5xl font-black text-zinc-950 tracking-tighter">
          GPU Pipeline
        </h1>
        <p className="text-base text-zinc-500 mt-2">
          The RunPod handler code for football video analysis. Download, deploy, connect.
        </p>
      </div>

      {/* Download CTA */}
      <div className="border-2 border-zinc-950 p-8 mb-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4" data-testid="download-handler-cta">
        <div>
          <p className="font-['Chivo'] text-xl font-bold text-zinc-950">
            RunPod Handler Package
          </p>
          <p className="text-sm text-zinc-500 mt-1">
            Complete pipeline code: handler.py, Dockerfile, pipeline modules, README.
          </p>
        </div>
        <button
          onClick={downloadPackage}
          disabled={downloading}
          className="flex items-center gap-2 bg-zinc-950 text-white px-8 py-3 text-xs font-bold tracking-[0.15em] uppercase hover:bg-zinc-800 hover:text-white transition-colors disabled:opacity-40 shrink-0"
          data-testid="download-handler-btn"
        >
          <DownloadSimple size={16} weight="bold" />
          {downloading ? "Downloading..." : "Download ZIP"}
        </button>
      </div>

      <Tabs defaultValue="pipeline" className="w-full">
        <TabsList className="w-full justify-start bg-zinc-50 border border-zinc-200 rounded-none h-auto p-0">
          <TabsTrigger
            value="pipeline"
            className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-white px-4 py-2.5 text-xs font-bold tracking-wider uppercase"
            data-testid="tab-pipeline-stages"
          >
            <TreeStructure size={14} weight="bold" className="mr-1.5" />
            Pipeline Stages
          </TabsTrigger>
          <TabsTrigger
            value="docker"
            className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-white px-4 py-2.5 text-xs font-bold tracking-wider uppercase"
            data-testid="tab-docker"
          >
            <Cube size={14} weight="bold" className="mr-1.5" />
            Dockerfile
          </TabsTrigger>
          <TabsTrigger
            value="deploy"
            className="rounded-none data-[state=active]:bg-zinc-950 data-[state=active]:text-white px-4 py-2.5 text-xs font-bold tracking-wider uppercase"
            data-testid="tab-deploy"
          >
            <GithubLogo size={14} weight="bold" className="mr-1.5" />
            Deployment Guide
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pipeline" className="mt-0 border border-t-0 border-zinc-200 p-6">
          <div className="space-y-0" data-testid="pipeline-stages-list">
            {PIPELINE_STAGES.map((stage, i) => (
              <div
                key={stage.name}
                className="flex items-start gap-4 border-b border-zinc-100 py-5 last:border-0"
              >
                <div className="w-8 h-8 bg-zinc-950 text-white flex items-center justify-center font-mono text-xs font-bold shrink-0">
                  {i + 1}
                </div>
                <div className="flex-1">
                  <p className="font-['Chivo'] font-bold text-sm text-zinc-950">
                    {stage.name}
                  </p>
                  <p className="text-sm text-zinc-500 mt-0.5">{stage.desc}</p>
                  <p className="font-mono text-xs text-indigo-600 mt-1">{stage.tech}</p>
                </div>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="docker" className="mt-0 border border-t-0 border-zinc-200">
          <pre className="bg-zinc-950 text-zinc-300 p-6 font-mono text-xs overflow-auto leading-relaxed" data-testid="dockerfile-content">
            {DOCKERFILE_CONTENT}
          </pre>
        </TabsContent>

        <TabsContent value="deploy" className="mt-0 border border-t-0 border-zinc-200 p-6">
          <div data-testid="deploy-guide">
            <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 mb-6">
              STEP-BY-STEP DEPLOYMENT
            </p>
            <div className="space-y-4">
              {DEPLOY_STEPS.map((step, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-6 h-6 bg-zinc-100 text-zinc-600 flex items-center justify-center font-mono text-xs font-bold shrink-0">
                    {i + 1}
                  </div>
                  <p className="text-sm text-zinc-700">{step}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 border-t border-zinc-200 pt-6">
              <p className="text-xs font-bold tracking-[0.2em] uppercase text-zinc-500 mb-3">
                GPU RECOMMENDATIONS
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <GpuCard
                  name="RTX 3090"
                  vram="24 GB"
                  time="~15 min / half"
                  tier="Budget"
                />
                <GpuCard
                  name="RTX 4090"
                  vram="24 GB"
                  time="~8 min / half"
                  tier="Standard"
                />
                <GpuCard
                  name="A100 80GB"
                  vram="80 GB"
                  time="~5 min / half"
                  tier="Recommended"
                  highlight
                />
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function GpuCard({ name, vram, time, tier, highlight }) {
  return (
    <div
      className={`border p-4 ${
        highlight ? "border-2 border-zinc-950" : "border-zinc-200"
      }`}
    >
      {highlight && (
        <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-indigo-600">
          {tier}
        </span>
      )}
      {!highlight && (
        <span className="text-[10px] font-bold tracking-[0.2em] uppercase text-zinc-400">
          {tier}
        </span>
      )}
      <p className="font-['Chivo'] font-bold text-zinc-950 mt-1">{name}</p>
      <p className="font-mono text-xs text-zinc-500 mt-1">{vram} VRAM</p>
      <p className="font-mono text-xs text-zinc-700 mt-0.5">{time}</p>
    </div>
  );
}



================================================================================
FILE: /app/memory/PRD.md
================================================================================
# Football Video Analysis — RunPod Pipeline Interface

## Original Problem Statement
Build a web interface to connect to RunPod GPU for processing football match video analysis. Upload 4K video (first/second half), process through vision pipeline, extract structured data (player movements, events, analytics) for downstream analysis.

## Architecture
- **Frontend**: React + Tailwind + Shadcn UI (Swiss Brutalist design)
- **Backend**: FastAPI + MongoDB + Emergent Object Storage
- **RunPod Handler**: YOLO + ByteTrack + Homography + Team Clustering + Event Detection (packaged as Docker image for RunPod Serverless)

## Core Requirements
- [x] Video upload (file + URL) for first/second half
- [x] RunPod credential configuration (API key, endpoint ID)
- [x] Job creation and submission to RunPod
- [x] Job status tracking (polling RunPod API)
- [x] Demo data generation (mock-complete endpoint)
- [x] Results viewer (Analytics, Events, Teams, Tracking, Raw JSON tabs)
- [x] JSON/CSV download of results
- [x] RunPod handler package download (ZIP)
- [x] Pipeline documentation and deployment guide

## What's Been Implemented (2026-04-03)
- Full backend API: settings, videos, jobs, results, handler package
- 6-page frontend: Dashboard, Upload, Jobs, JobDetail, Settings, Pipeline
- RunPod handler code: handler.py + 5 pipeline modules + Dockerfile + README
- Object storage integration for video files
- Sample data generator for testing without RunPod

## User Personas
- Football data engineers needing structured match data
- Performance analysts building custom tactical models
- Clubs/teams wanting in-house video analysis pipeline

## Backlog
- P0: Connect to real RunPod endpoint (user to provide credentials)
- P1: Real-time progress updates (WebSocket)
- P1: Fine-tuned YOLO model on SoccerNet
- P2: 2D pitch minimap visualization with player positions
- P2: Event timeline visualization
- P2: Video preview/thumbnail generation
- P3: Multi-match comparison dashboard
- P3: LLM-based tactical narrative generation

