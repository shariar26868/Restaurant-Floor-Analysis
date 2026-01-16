import cv2
import numpy as np
from typing import List, Dict
import tempfile
import os
from bson import ObjectId
from fastapi.concurrency import run_in_threadpool

from database import get_database
from services.s3_service import upload_to_s3


async def process_restaurant_video(video_content: bytes, analysis_id: str):
    """
    Process restaurant video to detect tables, doors, pillars.
    Heavy OpenCV work is executed in a threadpool to avoid blocking FastAPI.
    """
    db = get_database()
    temp_path = None

    try:
        # 1️⃣ Save video temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
            temp_video.write(video_content)
            temp_path = temp_video.name

        # 2️⃣ Run blocking OpenCV logic in threadpool
        detected_objects, frame = await run_in_threadpool(
            _process_video_sync,
            temp_path,
        )

        # 3️⃣ Encode static image
        success, img_encoded = cv2.imencode(".jpg", frame)
        if not success:
            raise Exception("Failed to encode frame")

        img_bytes = img_encoded.tobytes()

        # 4️⃣ Upload static image to S3
        static_image_url = await upload_to_s3(
            img_bytes,
            f"static_images/{analysis_id}.jpg",
        )

        # 5️⃣ Update database
        await db.video_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {
                "$set": {
                    "analysisStatus": "completed",
                    "detectedObjects": detected_objects,
                    "staticImageUrl": static_image_url,
                }
            },
        )

        print(f"✅ Video analysis completed for {analysis_id}")

    except Exception as e:
        print(f"❌ Video processing error: {e}")

        await db.video_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": {"analysisStatus": "failed"}},
        )

    finally:
        # 6️⃣ Cleanup temporary file
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


# -------------------------------------------------------------------
# SYNC FUNCTIONS (run inside threadpool)
# -------------------------------------------------------------------

def _process_video_sync(video_path: str):
    """
    Blocking OpenCV logic (SYNC).
    This function is executed inside a threadpool.
    """
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise Exception("Could not open video")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    middle_frame_index = max(total_frames // 2, 0)

    cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame_index)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise Exception("Could not read frame")

    detected_objects = detect_objects_simple_sync(frame)

    return detected_objects, frame


def detect_objects_simple_sync(frame: np.ndarray) -> List[Dict]:
    """
    Simple contour-based object detection (SYNC).
    For demo purposes only. Replace with YOLO for production.
    """
    detected: List[Dict] = []

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Threshold
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

    # Find contours
    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    for contour in contours:
        area = cv2.contourArea(contour)

        # Filter small objects
        if area < 5000:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / h if h else 0

        # Very naive classification
        obj_type = "table"
        if aspect_ratio > 3 or aspect_ratio < 0.3:
            obj_type = "pillar"
        elif area < 10000:
            obj_type = "door"

        detected.append(
            {
                "type": obj_type,
                "coordinates": {
                    "x": int(x),
                    "y": int(y),
                    "width": int(w),
                    "height": int(h),
                },
                "confidence": 0.75,  # placeholder confidence
            }
        )

    # Limit number of returned objects
    return detected[:20]
