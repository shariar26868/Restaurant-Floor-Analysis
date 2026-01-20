# routes/floor_plan.py
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Form
from database import get_database
from services.floor_plan_service import detect_tables_from_floor_plan_url
from services.s3_service import upload_to_s3
from bson import ObjectId
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload")
async def upload_floor_plan(
    background_tasks: BackgroundTasks,
    floor_plan: UploadFile = File(...),
    room_length: float = Form(10.0),
    room_width: float = Form(8.0),
    unit: str = Form("meters")
):
    """
    Upload restaurant floor plan for automatic table detection
    """
    
    # Validate image file
    if not floor_plan.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, 
            detail="File must be an image (PNG, JPG, JPEG)"
        )
    
    db = get_database()
    
    # Generate unique ID
    analysis_id = str(uuid.uuid4())
    
    # Read image content
    image_content = await floor_plan.read()
    
    # Validate content
    if not image_content or len(image_content) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    
    logger.info(f"📦 Received image: {len(image_content)} bytes, type: {floor_plan.content_type}")
    
    # Upload original floor plan to S3
    original_filename = f"floor_plans/original_{analysis_id}.jpg"
    floor_plan_url = await upload_to_s3(image_content, original_filename)
    
    # Create analysis record in database
    analysis_record = {
        "floorPlanUrl": floor_plan_url,
        "analysisStatus": "processing",
        "detectedTables": [],
        "annotatedFloorPlanUrl": None,
        "roomDimensions": {
            "length": room_length,
            "width": room_width,
            "unit": unit
        },
        "createdAt": datetime.utcnow()
    }
    
    result = await db.floor_plan_analysis.insert_one(analysis_record)
    db_analysis_id = str(result.inserted_id)
    
    # Room dimensions for processing
    room_dimensions = {
        "length": room_length,
        "width": room_width,
        "unit": unit
    }
    
    # Process floor plan in background (downloads from S3)
    background_tasks.add_task(
        detect_tables_from_floor_plan_url,
        floor_plan_url,
        db_analysis_id,
        room_dimensions
    )
    
    return {
        "statusCode": 200,
        "success": True,
        "message": "Floor plan uploaded successfully. Table detection in progress.",
        "data": {
            "analysisId": db_analysis_id,
            "floorPlanUrl": floor_plan_url,
            "status": "processing",
            "roomDimensions": room_dimensions
        }
    }


@router.get("/analysis/{analysis_id}")
async def get_floor_plan_analysis(analysis_id: str):
    """Get floor plan analysis result"""
    db = get_database()
    
    try:
        analysis = await db.floor_plan_analysis.find_one({"_id": ObjectId(analysis_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid analysis ID")
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Convert ObjectId to string
    analysis["id"] = str(analysis["_id"])
    del analysis["_id"]
    
    # Format createdAt if exists
    if "createdAt" in analysis:
        analysis["createdAt"] = analysis["createdAt"].isoformat()
    
    return {
        "statusCode": 200,
        "success": True,
        "data": analysis
    }


@router.get("/all")
async def get_all_floor_plan_analyses():
    """Get all floor plan analyses"""
    db = get_database()
    
    analyses = await db.floor_plan_analysis.find().sort("createdAt", -1).to_list(100)
    
    for analysis in analyses:
        analysis["id"] = str(analysis["_id"])
        del analysis["_id"]
        
        if "createdAt" in analysis:
            analysis["createdAt"] = analysis["createdAt"].isoformat()
    
    return {
        "statusCode": 200,
        "success": True,
        "data": analyses,
        "count": len(analyses)
    }


@router.delete("/analysis/{analysis_id}")
async def delete_floor_plan_analysis(analysis_id: str):
    """Delete a floor plan analysis"""
    db = get_database()
    
    try:
        result = await db.floor_plan_analysis.delete_one({"_id": ObjectId(analysis_id)})
    except:
        raise HTTPException(status_code=400, detail="Invalid analysis ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return {
        "statusCode": 200,
        "success": True,
        "message": "Floor plan analysis deleted successfully"
    }