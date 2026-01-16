# routes/video.py
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from database import get_database
from services.video_service import process_restaurant_video
from services.s3_service import upload_to_s3
from bson import ObjectId
import uuid

router = APIRouter()

@router.post("/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...)
):
    """Upload restaurant video for analysis"""
    
    # Validate video file
    if not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")
    
    db = get_database()
    
    # Generate unique filename
    video_id = str(uuid.uuid4())
    filename = f"videos/{video_id}.mp4"
    
    # Read video content
    video_content = await video.read()
    
    # Upload to S3
    video_url = await upload_to_s3(video_content, filename)
    
    # Create video analysis record
    analysis_record = {
        "videoUrl": video_url,
        "analysisStatus": "processing",
        "detectedObjects": [],
        "staticImageUrl": None
    }
    
    result = await db.video_analysis.insert_one(analysis_record)
    analysis_id = str(result.inserted_id)
    
    # Process video in background
    background_tasks.add_task(
        process_restaurant_video,
        video_content,
        analysis_id
    )
    
    return {
        "statusCode": 200,
        "success": True,
        "message": "Video uploaded successfully. Analysis in progress.",
        "data": {
            "analysisId": analysis_id,
            "videoUrl": video_url,
            "status": "processing"
        }
    }

@router.get("/analysis/{analysis_id}")
async def get_analysis_result(analysis_id: str):
    """Get video analysis result"""
    db = get_database()
    
    analysis = await db.video_analysis.find_one({"_id": ObjectId(analysis_id)})
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    analysis["id"] = str(analysis["_id"])
    del analysis["_id"]
    
    return {
        "statusCode": 200,
        "success": True,
        "data": analysis
    }

@router.get("/all")
async def get_all_analyses():
    """Get all video analyses"""
    db = get_database()
    
    analyses = await db.video_analysis.find().to_list(100)
    
    for a in analyses:
        a["id"] = str(a["_id"])
        del a["_id"]
    
    return {
        "statusCode": 200,
        "success": True,
        "data": analyses
    }