"""
Video-Based Table Detection Service
====================================
Detects tables and their coordinates from restaurant walkthrough videos
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple
from bson import ObjectId
from fastapi.concurrency import run_in_threadpool
import logging
import json
import base64
from openai import OpenAI
from config import settings
from database import get_database
from services.s3_service import upload_to_s3
import tempfile
import os
from urllib.parse import urlparse, unquote
import boto3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


async def detect_tables_from_video_url(
    video_url: str,
    analysis_id: str,
    room_dimensions: Dict
):
    """
    Main function: Detect tables from video URL
    """
    db = get_database()
    
    try:
        logger.info(f"🎥 Starting VIDEO table detection for {analysis_id}")
        
        # Download video from S3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        parsed_url = urlparse(video_url)
        s3_key = unquote(parsed_url.path.lstrip('/'))
        
        logger.info(f"📂 Downloading video: {s3_key}")
        
        response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        video_content = response['Body'].read()
        
        logger.info(f"✅ Downloaded {len(video_content)} bytes")
        
        # Process video
        detected_tables, sample_frame, detection_metadata = await run_in_threadpool(
            _process_video_sync,
            video_content,
            room_dimensions
        )
        
        logger.info(f"✅ Detected {len(detected_tables)} tables from video")
        
        # Upload sample frame
        if sample_frame is not None:
            success, img_encoded = cv2.imencode('.jpg', sample_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
            if success:
                annotated_url = await upload_to_s3(
                    img_encoded.tobytes(),
                    f"video_analysis/annotated_{analysis_id}.jpg"
                )
            else:
                annotated_url = None
        else:
            annotated_url = None
        
        # Update database
        await db.floor_plan_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {
                "$set": {
                    "analysisStatus": "completed",
                    "detectedTables": detected_tables,
                    "annotatedFloorPlanUrl": annotated_url,
                    "tableCount": len(detected_tables),
                    "detectionMetadata": detection_metadata,
                    "sourceType": "video"
                }
            }
        )
        
        logger.info(f"✅ Video analysis completed")
        
    except Exception as e:
        logger.error(f"❌ Video analysis error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        await db.floor_plan_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": {"analysisStatus": "failed", "error": str(e)}}
        )


def _process_video_sync(
    video_content: bytes,
    room_dimensions: Dict
) -> Tuple[List[Dict], np.ndarray, Dict]:
    """
    Process video synchronously
    """
    
    # Save video to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        tmp_file.write(video_content)
        video_path = tmp_file.name
    
    try:
        # Extract frames
        logger.info("📸 Extracting frames from video...")
        frames = _extract_frames(video_path, num_frames=6)
        logger.info(f"✅ Extracted {len(frames)} frames")
        
        if len(frames) == 0:
            raise Exception("No frames could be extracted from video")
        
        # Analyze with OpenAI Vision
        logger.info("🤖 Analyzing video with OpenAI Vision...")
        detected_tables = _analyze_video_with_openai(frames, room_dimensions)
        logger.info(f"✅ Found {len(detected_tables)} tables")
        
        # 🆕 FALLBACK: If OpenAI found 0 tables, try basic CV detection
        if len(detected_tables) == 0:
            logger.warning("⚠️ OpenAI found 0 tables, trying CV fallback...")
            try:
                # Use middle frame (usually best view)
                best_frame = frames[len(frames) // 2]
                height, width = best_frame.shape[:2]
                
                # Simple CV-based table detection
                cv_tables = _detect_tables_with_cv_fallback(best_frame, room_dimensions)
                
                if len(cv_tables) > 0:
                    logger.info(f"✅ CV fallback found {len(cv_tables)} tables")
                    detected_tables = cv_tables
                else:
                    logger.warning("⚠️ CV fallback also found 0 tables")
            except Exception as e:
                logger.error(f"❌ CV fallback failed: {e}")
        
        # Draw on first frame
        sample_frame = _draw_annotations(frames[0].copy(), detected_tables)
        
        # Metadata
        metadata = {
            "detection_method": "openai_video_analysis" if detected_tables and detected_tables[0].get('detectionMethod') == 'openai_video' else "cv_fallback",
            "table_count": len(detected_tables),
            "frames_analyzed": len(frames),
            "table_types": list(set([t.get('tableType', 'unknown') for t in detected_tables])),
            "total_estimated_seats": sum([t.get('chairCount', 0) for t in detected_tables])
        }
        
        return detected_tables, sample_frame, metadata
        
    finally:
        # Clean up
        try:
            os.unlink(video_path)
        except:
            pass


def _extract_frames(video_path: str, num_frames: int = 6) -> List[np.ndarray]:
    """
    Extract evenly-spaced frames from video
    """
    frames = []
    
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        logger.error("Failed to open video")
        return frames
    
    # Get video properties
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    logger.info(f"📹 Video: {total_frames} frames, {fps:.1f} FPS")
    
    # Calculate frame indices to extract
    if total_frames < num_frames:
        frame_indices = list(range(total_frames))
    else:
        step = total_frames // num_frames
        frame_indices = [i * step for i in range(num_frames)]
    
    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if ret:
            # Resize if too large
            height, width = frame.shape[:2]
            if width > 1920:
                scale = 1920 / width
                new_width = 1920
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))
            
            frames.append(frame)
            logger.info(f"  ✅ Extracted frame {frame_idx}")
    
    cap.release()
    
    return frames


def _analyze_video_with_openai(
    frames: List[np.ndarray],
    room_dimensions: Dict
) -> List[Dict]:
    """
    Analyze video frames with OpenAI Vision API - IMPROVED PROMPT
    """
    
    try:
        # Convert frames to base64
        frame_data = []
        for idx, frame in enumerate(frames[:4]):  # Max 4 frames
            # Resize frame if too large
            height, width = frame.shape[:2]
            if width > 1280:
                scale = 1280 / width
                new_width = 1280
                new_height = int(height * scale)
                resized_frame = cv2.resize(frame, (new_width, new_height))
            else:
                resized_frame = frame
            
            success, buffer = cv2.imencode('.jpg', resized_frame, [
                cv2.IMWRITE_JPEG_QUALITY, 85  # Slightly higher quality
            ])
            
            if success:
                b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
                frame_data.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64}",
                        "detail": "high"
                    }
                })
                logger.info(f"  📸 Prepared frame {idx + 1} ({resized_frame.shape[1]}x{resized_frame.shape[0]})")
        
        if len(frame_data) == 0:
            logger.error("❌ No frames could be encoded")
            return []
        
        # Get first frame dimensions
        img_height, img_width = frames[0].shape[:2]
        
        # IMPROVED PROMPT - More explicit and forgiving
        prompt = f"""Analyze these {len(frame_data)} video frames from a restaurant/dining space.

🎯 TASK: Count ALL tables where people can sit and eat.

WHAT COUNTS AS A TABLE:
✅ Dining tables (any size, any shape)
✅ Bar tables / high-top tables
✅ Booth seating with tables
✅ Cafe tables / bistro tables
✅ Outdoor patio tables
✅ Counter seating with surface

CRITICAL RULES:
1. Count EVERY table you see, even if partially visible
2. If the SAME table appears in multiple frames, count it ONLY ONCE
3. Even if you're not 100% sure, include it (better to overcount slightly than miss tables)
4. Look carefully - tables might be in corners, against walls, or partially obscured

ANALYSIS STEPS:
1. Scan each frame systematically (left to right, front to back)
2. Mark each unique table you identify
3. For each table, estimate its approximate location in the room
4. Count total unique tables across all frames

OUTPUT FORMAT (JSON array):
[
  {{
    "table_number": 1,
    "type": "rectangular",
    "approximate_position": "front-left corner",
    "center_x_percent": 0.25,
    "center_y_percent": 0.30,
    "chair_count": 4,
    "confidence": 0.85
  }},
  {{
    "table_number": 2,
    "type": "circular",
    "approximate_position": "center of room",
    "center_x_percent": 0.50,
    "center_y_percent": 0.50,
    "chair_count": 6,
    "confidence": 0.90
  }}
]

POSITIONING GUIDE:
- center_x_percent: 0.0 = far left, 0.5 = center, 1.0 = far right
- center_y_percent: 0.0 = top/front, 0.5 = middle, 1.0 = bottom/back
- type: "rectangular", "circular", or "square"
- chair_count: number of chairs you can see or estimate

If you see NO tables at all (empty room), return: []

⚠️ IMPORTANT: Return ONLY valid JSON (the array), no explanations or markdown formatting."""

        # Build messages
        content = [{"type": "text", "text": prompt}]
        content.extend(frame_data)
        
        # Call OpenAI with adjusted parameters
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            max_tokens=2500,
            temperature=0.2  # Slightly higher for more creative detection
        )
        
        # Parse response
        result = response.choices[0].message.content.strip()
        
        logger.info(f"📝 OpenAI raw response: {result[:300]}...")
        
        # Extract JSON - robust parsing
        if result.startswith("```json"):
            result = result.split("```json")[1].split("```")[0].strip()
        elif result.startswith("```"):
            result = result.split("```")[1].split("```")[0].strip()
        elif not (result.startswith("[") or result.startswith("{")):
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                result = json_match.group(0)
            else:
                logger.error(f"❌ No JSON array found in response")
                logger.error(f"Full response: {result}")
                return []
        
        # Handle empty/invalid responses
        if not result or result.strip() == "" or result.strip() == "[]":
            logger.warning("⚠️ OpenAI returned empty array or no tables detected")
            return []
        
        # Parse JSON
        tables_data = json.loads(result)
        
        # Validate it's a list
        if not isinstance(tables_data, list):
            logger.error(f"❌ Expected array, got {type(tables_data)}")
            return []
        
        # Convert to standard format
        detected_tables = []
        
        for table in tables_data:
            try:
                center_x = int(table['center_x_percent'] * img_width)
                center_y = int(table['center_y_percent'] * img_height)
                
                # Estimate size based on chair count
                chair_count = table.get('chair_count', 4)
                if chair_count <= 2:
                    size_factor = 0.06
                elif chair_count <= 4:
                    size_factor = 0.08
                else:
                    size_factor = 0.10
                
                estimated_width = int(img_width * size_factor)
                estimated_height = int(img_height * size_factor)
                
                detected_tables.append({
                    "tableId": f"table_{table['table_number']}",
                    "detectionMethod": "openai_video",
                    "tableType": table.get('type', 'rectangular'),
                    "chairCount": chair_count,
                    "approximatePosition": table.get('approximate_position', 'unknown'),
                    "pixelCoordinates": {
                        "x": max(0, center_x - estimated_width // 2),
                        "y": max(0, center_y - estimated_height // 2),
                        "width": estimated_width,
                        "height": estimated_height
                    },
                    "confidence": table.get('confidence', 0.80)
                })
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"⚠️ Skipping malformed table data: {table} - Error: {e}")
                continue
        
        logger.info(f"🤖 OpenAI detected {len(detected_tables)} tables")
        return detected_tables
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        if 'result' in locals():
            logger.error(f"Response was: {result}")
        return []
    except Exception as e:
        logger.error(f"❌ OpenAI analysis error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def _detect_tables_with_cv_fallback(frame: np.ndarray, room_dimensions: Dict) -> List[Dict]:
    """
    Simple CV-based table detection fallback using contour detection
    """
    try:
        height, width = frame.shape[:2]
        
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while keeping edges
        filtered = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Edge detection
        edges = cv2.Canny(filtered, 50, 150)
        
        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours for table-like shapes
        detected_tables = []
        min_area = (width * height) * 0.01  # At least 1% of frame
        max_area = (width * height) * 0.25  # At most 25% of frame
        
        table_id = 1
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if min_area < area < max_area:
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Check aspect ratio (tables are roughly square-ish)
                aspect_ratio = float(w) / h if h > 0 else 0
                
                if 0.3 < aspect_ratio < 3.0:  # Reasonable aspect ratio
                    detected_tables.append({
                        "tableId": f"table_{table_id}",
                        "detectionMethod": "cv_fallback",
                        "tableType": "rectangular",
                        "chairCount": 0,
                        "approximatePosition": f"detected_at_x{x}_y{y}",
                        "pixelCoordinates": {
                            "x": x,
                            "y": y,
                            "width": w,
                            "height": h
                        },
                        "confidence": 0.5
                    })
                    table_id += 1
        
        # Limit to top 20 tables by area
        if len(detected_tables) > 20:
            detected_tables.sort(key=lambda t: t['pixelCoordinates']['width'] * t['pixelCoordinates']['height'], reverse=True)
            detected_tables = detected_tables[:20]
        
        return detected_tables
        
    except Exception as e:
        logger.error(f"❌ CV fallback detection error: {e}")
        return []


def _draw_annotations(frame: np.ndarray, tables: List[Dict]) -> np.ndarray:
    """
    Draw table annotations on frame
    """
    
    colors = {
        'circular': (255, 0, 255),     # Magenta
        'rectangular': (0, 165, 255),  # Orange
        'square': (0, 255, 255),       # Yellow
    }
    
    for table in tables:
        px = table['pixelCoordinates']
        x, y, w, h = px['x'], px['y'], px['width'], px['height']
        
        table_type = table.get('tableType', 'rectangular')
        color = colors.get(table_type, (0, 255, 0))
        
        # Draw bounding box
        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 3)
        
        # Label
        chair_count = table.get('chairCount', 0)
        label = f"{table['tableId']}"
        if chair_count > 0:
            label += f" ({chair_count} chairs)"
        
        # Background for text
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x, y - th - 10), (x + tw + 10, y), color, -1)
        
        # Text
        cv2.putText(frame, label, (x + 5, y - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Center point
        cv2.circle(frame, (x + w // 2, y + h // 2), 5, (0, 0, 255), -1)
    
    # Summary
    cv2.putText(frame, f"Total Tables: {len(tables)}", (10, 40),
               cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
    
    return frame




# """
# Video-Based Table Detection Service - ADVANCED VERSION
# =======================================================
# Multi-strategy approach for robust table detection
# """

# import cv2
# import numpy as np
# from typing import List, Dict, Tuple, Optional
# from bson import ObjectId
# from fastapi.concurrency import run_in_threadpool
# import logging
# import json
# import base64
# from openai import OpenAI
# from config import settings
# from database import get_database
# from services.s3_service import upload_to_s3
# import tempfile
# import os
# from urllib.parse import urlparse, unquote
# import boto3
# from collections import defaultdict

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Initialize OpenAI client
# openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


# async def detect_tables_from_video_url(
#     video_url: str,
#     analysis_id: str,
#     room_dimensions: Dict
# ):
#     """
#     Main function: Detect tables from video URL with advanced processing
#     """
#     db = get_database()
    
#     try:
#         logger.info(f"🎥 Starting ADVANCED VIDEO table detection for {analysis_id}")
        
#         # Download video from S3
#         s3_client = boto3.client(
#             's3',
#             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
#             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
#             region_name=settings.AWS_REGION
#         )
        
#         parsed_url = urlparse(video_url)
#         s3_key = unquote(parsed_url.path.lstrip('/'))
        
#         logger.info(f"📂 Downloading video: {s3_key}")
        
#         response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
#         video_content = response['Body'].read()
        
#         logger.info(f"✅ Downloaded {len(video_content)} bytes")
        
#         # Process video with advanced detection
#         detected_tables, sample_frame, detection_metadata = await run_in_threadpool(
#             _process_video_advanced,
#             video_content,
#             room_dimensions
#         )
        
#         logger.info(f"✅ Detected {len(detected_tables)} tables from video")
        
#         # Upload sample frame
#         if sample_frame is not None:
#             success, img_encoded = cv2.imencode('.jpg', sample_frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            
#             if success:
#                 annotated_url = await upload_to_s3(
#                     img_encoded.tobytes(),
#                     f"video_analysis/annotated_{analysis_id}.jpg"
#                 )
#             else:
#                 annotated_url = None
#         else:
#             annotated_url = None
        
#         # Update database
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {
#                 "$set": {
#                     "analysisStatus": "completed",
#                     "detectedTables": detected_tables,
#                     "annotatedFloorPlanUrl": annotated_url,
#                     "tableCount": len(detected_tables),
#                     "detectionMetadata": detection_metadata,
#                     "sourceType": "video"
#                 }
#             }
#         )
        
#         logger.info(f"✅ Advanced video analysis completed successfully")
        
#     except Exception as e:
#         logger.error(f"❌ Video analysis error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
        
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {"$set": {"analysisStatus": "failed", "error": str(e)}}
#         )


# def _process_video_advanced(
#     video_content: bytes,
#     room_dimensions: Dict
# ) -> Tuple[List[Dict], np.ndarray, Dict]:
#     """
#     Advanced video processing with multi-strategy detection
#     """
    
#     # Save video to temp file
#     with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
#         tmp_file.write(video_content)
#         video_path = tmp_file.name
    
#     try:
#         # Step 1: Extract more frames for better coverage
#         logger.info("📸 Extracting frames from video...")
#         frames = _extract_smart_frames(video_path, num_frames=8)
#         logger.info(f"✅ Extracted {len(frames)} frames")
        
#         if len(frames) == 0:
#             raise Exception("No frames could be extracted from video")
        
#         # Step 2: Pre-process frames for better detection
#         logger.info("🔧 Pre-processing frames...")
#         enhanced_frames = [_enhance_frame(f) for f in frames]
        
#         # Step 3: Multi-strategy detection
#         all_detections = []
        
#         # Strategy 1: OpenAI Vision (primary)
#         logger.info("🤖 Strategy 1: OpenAI Vision Analysis...")
#         openai_tables = _analyze_with_openai_advanced(enhanced_frames, room_dimensions)
#         if openai_tables:
#             all_detections.append(("openai", openai_tables))
#             logger.info(f"  ✅ OpenAI found {len(openai_tables)} tables")
        
#         # Strategy 2: CV-based detection (backup)
#         logger.info("🔍 Strategy 2: Computer Vision Detection...")
#         cv_tables = _detect_with_advanced_cv(enhanced_frames, room_dimensions)
#         if cv_tables:
#             all_detections.append(("cv", cv_tables))
#             logger.info(f"  ✅ CV found {len(cv_tables)} tables")
        
#         # Strategy 3: Color-based segmentation
#         logger.info("🎨 Strategy 3: Color-based Segmentation...")
#         color_tables = _detect_with_color_segmentation(enhanced_frames[len(frames)//2], room_dimensions)
#         if color_tables:
#             all_detections.append(("color", color_tables))
#             logger.info(f"  ✅ Color segmentation found {len(color_tables)} tables")
        
#         # Step 4: Merge and validate detections
#         logger.info("🔀 Merging detection results...")
#         final_tables = _merge_detections(all_detections, frames[0].shape)
#         logger.info(f"✅ Final count: {len(final_tables)} tables after merging")
        
#         # Step 5: Post-process and refine
#         final_tables = _refine_detections(final_tables, frames[0].shape, room_dimensions)
        
#         # Step 6: Create visualization
#         sample_frame = _draw_advanced_annotations(frames[0].copy(), final_tables)
        
#         # Metadata
#         metadata = {
#             "detection_methods_used": [m for m, _ in all_detections],
#             "raw_detections": {m: len(t) for m, t in all_detections},
#             "final_table_count": len(final_tables),
#             "frames_analyzed": len(frames),
#             "table_types": list(set([t.get('tableType', 'unknown') for t in final_tables])),
#             "total_estimated_seats": sum([t.get('chairCount', 0) for t in final_tables]),
#             "confidence_distribution": {
#                 "high": len([t for t in final_tables if t.get('confidence', 0) >= 0.8]),
#                 "medium": len([t for t in final_tables if 0.6 <= t.get('confidence', 0) < 0.8]),
#                 "low": len([t for t in final_tables if t.get('confidence', 0) < 0.6])
#             }
#         }
        
#         return final_tables, sample_frame, metadata
        
#     finally:
#         # Clean up
#         try:
#             os.unlink(video_path)
#         except:
#             pass


# def _extract_smart_frames(video_path: str, num_frames: int = 8) -> List[np.ndarray]:
#     """
#     Smart frame extraction - picks frames with most motion/changes
#     """
#     frames = []
#     cap = cv2.VideoCapture(video_path)
    
#     if not cap.isOpened():
#         logger.error("Failed to open video")
#         return frames
    
#     total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
#     fps = cap.get(cv2.CAP_PROP_FPS)
    
#     logger.info(f"📹 Video: {total_frames} frames, {fps:.1f} FPS")
    
#     # Extract candidate frames
#     if total_frames < num_frames:
#         frame_indices = list(range(total_frames))
#     else:
#         # Sample more frames than needed
#         step = total_frames // (num_frames * 2)
#         candidate_indices = [i * step for i in range(num_frames * 2)]
        
#         # Score frames based on content variance (brightness, edges)
#         scored_frames = []
#         for idx in candidate_indices:
#             cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
#             ret, frame = cap.read()
#             if ret:
#                 gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
#                 variance = cv2.Laplacian(gray, cv2.CV_64F).var()
#                 scored_frames.append((idx, variance, frame))
        
#         # Pick top frames with highest variance (most detail)
#         scored_frames.sort(key=lambda x: x[1], reverse=True)
#         frame_indices = [x[0] for x in scored_frames[:num_frames]]
#         frame_indices.sort()
    
#     # Extract selected frames
#     for frame_idx in frame_indices:
#         cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
#         ret, frame = cap.read()
        
#         if ret:
#             height, width = frame.shape[:2]
#             if width > 1920:
#                 scale = 1920 / width
#                 new_width = 1920
#                 new_height = int(height * scale)
#                 frame = cv2.resize(frame, (new_width, new_height))
            
#             frames.append(frame)
    
#     cap.release()
#     return frames


# def _enhance_frame(frame: np.ndarray) -> np.ndarray:
#     """
#     Enhance frame quality for better detection
#     """
#     # CLAHE for better contrast
#     lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
#     l, a, b = cv2.split(lab)
#     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
#     l = clahe.apply(l)
#     enhanced = cv2.merge([l, a, b])
#     enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
    
#     # Denoise
#     enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)
    
#     return enhanced


# def _analyze_with_openai_advanced(
#     frames: List[np.ndarray],
#     room_dimensions: Dict
# ) -> List[Dict]:
#     """
#     Advanced OpenAI analysis with better prompting
#     """
#     try:
#         # Prepare frames
#         frame_data = []
#         for idx, frame in enumerate(frames[:5]):  # Use 5 best frames
#             height, width = frame.shape[:2]
#             if width > 1280:
#                 scale = 1280 / width
#                 new_width = 1280
#                 new_height = int(height * scale)
#                 resized_frame = cv2.resize(frame, (new_width, new_height))
#             else:
#                 resized_frame = frame
            
#             success, buffer = cv2.imencode('.jpg', resized_frame, [
#                 cv2.IMWRITE_JPEG_QUALITY, 90
#             ])
            
#             if success:
#                 b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
#                 frame_data.append({
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{b64}",
#                         "detail": "high"
#                     }
#                 })
        
#         if not frame_data:
#             return []
        
#         img_height, img_width = frames[0].shape[:2]
        
#         # Advanced multi-stage prompt
#         prompt = f"""You are an expert restaurant layout analyst. Analyze these {len(frame_data)} frames from a restaurant video.

# ROOM DIMENSIONS: {room_dimensions.get('length', 'unknown')}m × {room_dimensions.get('width', 'unknown')}m

# 🎯 PRIMARY TASK: Identify ALL dining tables in this restaurant space.

# ═══════════════════════════════════════════════════════
# WHAT IS A DINING TABLE?
# ═══════════════════════════════════════════════════════
# ✅ ANY surface where customers sit to dine
# ✅ Tables with chairs (2-20 chairs)
# ✅ All shapes: round, square, rectangular, oval
# ✅ All types: dining tables, bar tables, booths, cafe tables
# ✅ All locations: main dining, bar area, patio, corners

# ═══════════════════════════════════════════════════════
# DETECTION INSTRUCTIONS:
# ═══════════════════════════════════════════════════════
# 1. Scan EACH frame carefully from multiple angles
# 2. Look in ALL areas: center, corners, walls, background
# 3. Count UNIQUE tables (same table in multiple frames = count once)
# 4. Include partially visible tables
# 5. When uncertain, INCLUDE the table (better to detect more)

# ═══════════════════════════════════════════════════════
# COORDINATE SYSTEM:
# ═══════════════════════════════════════════════════════
# - X-axis (horizontal): 0.0 = left edge → 1.0 = right edge
# - Y-axis (vertical): 0.0 = top/front → 1.0 = bottom/back
# - Give PRECISE decimal positions (e.g., 0.23, 0.67)

# ═══════════════════════════════════════════════════════
# OUTPUT FORMAT (JSON ARRAY):
# ═══════════════════════════════════════════════════════
# [
#   {{
#     "table_number": 1,
#     "type": "rectangular",
#     "approximate_position": "front-left near window",
#     "center_x_percent": 0.23,
#     "center_y_percent": 0.15,
#     "chair_count": 4,
#     "confidence": 0.95,
#     "notes": "clearly visible in frame 1 and 2"
#   }},
#   {{
#     "table_number": 2,
#     "type": "circular",
#     "approximate_position": "center area",
#     "center_x_percent": 0.52,
#     "center_y_percent": 0.48,
#     "chair_count": 6,
#     "confidence": 0.90,
#     "notes": "prominent in center of room"
#   }}
# ]

# EXAMPLES OF GOOD DETECTION:
# - Table with 2 chairs in corner → YES, include it
# - Bar table with high chairs → YES, include it
# - Booth seating with table → YES, include it
# - Partially visible table edge → YES, include it
# - Table in background/blurry → YES, try to include it

# ⚠️ RETURN ONLY THE JSON ARRAY - NO MARKDOWN, NO EXPLANATIONS
# ⚠️ BE THOROUGH - restaurants usually have 5-30 tables
# ⚠️ CONFIDENCE: 0.9-1.0 = clearly visible, 0.7-0.89 = somewhat visible, 0.6-0.69 = barely visible"""

#         # Call OpenAI
#         content = [{"type": "text", "text": prompt}]
#         content.extend(frame_data)
        
#         response = openai_client.chat.completions.create(
#             model="gpt-4o",
#             messages=[{"role": "user", "content": content}],
#             max_tokens=3000,
#             temperature=0.15
#         )
        
#         result = response.choices[0].message.content.strip()
#         logger.info(f"📝 OpenAI response length: {len(result)} chars")
        
#         # Parse JSON
#         if result.startswith("```json"):
#             result = result.split("```json")[1].split("```")[0].strip()
#         elif result.startswith("```"):
#             result = result.split("```")[1].split("```")[0].strip()
        
#         if not result or result == "[]":
#             return []
        
#         tables_data = json.loads(result)
        
#         if not isinstance(tables_data, list):
#             return []
        
#         # Convert to standard format
#         detected_tables = []
#         for table in tables_data:
#             try:
#                 center_x = int(table['center_x_percent'] * img_width)
#                 center_y = int(table['center_y_percent'] * img_height)
                
#                 chair_count = table.get('chair_count', 4)
#                 size_factor = 0.06 + (chair_count * 0.01)  # Larger tables for more chairs
                
#                 estimated_width = int(img_width * size_factor)
#                 estimated_height = int(img_height * size_factor)
                
#                 detected_tables.append({
#                     "tableId": f"table_{table['table_number']}",
#                     "detectionMethod": "openai_vision",
#                     "tableType": table.get('type', 'rectangular'),
#                     "chairCount": chair_count,
#                     "approximatePosition": table.get('approximate_position', ''),
#                     "pixelCoordinates": {
#                         "x": max(0, center_x - estimated_width // 2),
#                         "y": max(0, center_y - estimated_height // 2),
#                         "width": estimated_width,
#                         "height": estimated_height
#                     },
#                     "confidence": table.get('confidence', 0.85),
#                     "notes": table.get('notes', '')
#                 })
#             except (KeyError, TypeError, ValueError) as e:
#                 logger.warning(f"⚠️ Skipping malformed table: {e}")
#                 continue
        
#         return detected_tables
        
#     except Exception as e:
#         logger.error(f"❌ OpenAI error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         return []


# def _detect_with_advanced_cv(frames: List[np.ndarray], room_dimensions: Dict) -> List[Dict]:
#     """
#     Advanced CV detection using multiple techniques
#     """
#     try:
#         # Use middle frame (usually best view)
#         frame = frames[len(frames) // 2]
#         height, width = frame.shape[:2]
        
#         gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
#         # Multiple edge detection methods
#         edges1 = cv2.Canny(gray, 30, 100)
#         edges2 = cv2.Canny(gray, 50, 150)
#         edges = cv2.bitwise_or(edges1, edges2)
        
#         # Morphological operations to connect edges
#         kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
#         closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        
#         # Find contours
#         contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
#         detected_tables = []
#         min_area = (width * height) * 0.005  # 0.5% of frame
#         max_area = (width * height) * 0.20   # 20% of frame
        
#         table_id = 1
#         for contour in contours:
#             area = cv2.contourArea(contour)
            
#             if min_area < area < max_area:
#                 x, y, w, h = cv2.boundingRect(contour)
#                 aspect_ratio = float(w) / h if h > 0 else 0
                
#                 # More lenient aspect ratio
#                 if 0.25 < aspect_ratio < 4.0:
#                     # Estimate chair count based on size
#                     relative_size = area / (width * height)
#                     if relative_size < 0.02:
#                         chairs = 2
#                     elif relative_size < 0.05:
#                         chairs = 4
#                     else:
#                         chairs = 6
                    
#                     detected_tables.append({
#                         "tableId": f"cv_table_{table_id}",
#                         "detectionMethod": "computer_vision",
#                         "tableType": "circular" if 0.8 < aspect_ratio < 1.2 else "rectangular",
#                         "chairCount": chairs,
#                         "approximatePosition": f"area_{int((x/width)*10)}_{int((y/height)*10)}",
#                         "pixelCoordinates": {
#                             "x": x,
#                             "y": y,
#                             "width": w,
#                             "height": h
#                         },
#                         "confidence": 0.65
#                     })
#                     table_id += 1
        
#         # Limit to top 25 by area
#         if len(detected_tables) > 25:
#             detected_tables.sort(key=lambda t: t['pixelCoordinates']['width'] * t['pixelCoordinates']['height'], reverse=True)
#             detected_tables = detected_tables[:25]
        
#         return detected_tables
        
#     except Exception as e:
#         logger.error(f"❌ CV detection error: {e}")
#         return []


# def _detect_with_color_segmentation(frame: np.ndarray, room_dimensions: Dict) -> List[Dict]:
#     """
#     Detect tables using color-based segmentation
#     """
#     try:
#         height, width = frame.shape[:2]
        
#         # Convert to HSV for better color detection
#         hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
#         # Define color ranges for typical table colors (wood, white, black)
#         lower_wood = np.array([10, 50, 50])
#         upper_wood = np.array([30, 255, 255])
        
#         lower_white = np.array([0, 0, 180])
#         upper_white = np.array([180, 30, 255])
        
#         lower_black = np.array([0, 0, 0])
#         upper_black = np.array([180, 255, 50])
        
#         # Create masks
#         mask_wood = cv2.inRange(hsv, lower_wood, upper_wood)
#         mask_white = cv2.inRange(hsv, lower_white, upper_white)
#         mask_black = cv2.inRange(hsv, lower_black, upper_black)
        
#         # Combine masks
#         combined_mask = cv2.bitwise_or(mask_wood, cv2.bitwise_or(mask_white, mask_black))
        
#         # Clean up mask
#         kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
#         cleaned_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
#         cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_OPEN, kernel)
        
#         # Find contours
#         contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
#         detected_tables = []
#         min_area = (width * height) * 0.01
#         max_area = (width * height) * 0.15
        
#         table_id = 1
#         for contour in contours:
#             area = cv2.contourArea(contour)
            
#             if min_area < area < max_area:
#                 x, y, w, h = cv2.boundingRect(contour)
#                 aspect_ratio = float(w) / h if h > 0 else 0
                
#                 if 0.3 < aspect_ratio < 3.0:
#                     detected_tables.append({
#                         "tableId": f"color_table_{table_id}",
#                         "detectionMethod": "color_segmentation",
#                         "tableType": "circular" if 0.75 < aspect_ratio < 1.25 else "rectangular",
#                         "chairCount": 4,
#                         "approximatePosition": f"color_detected",
#                         "pixelCoordinates": {
#                             "x": x,
#                             "y": y,
#                             "width": w,
#                             "height": h
#                         },
#                         "confidence": 0.60
#                     })
#                     table_id += 1
        
#         return detected_tables[:15]  # Limit to 15 tables
        
#     except Exception as e:
#         logger.error(f"❌ Color segmentation error: {e}")
#         return []


# def _merge_detections(all_detections: List[Tuple[str, List[Dict]]], frame_shape: Tuple) -> List[Dict]:
#     """
#     Intelligently merge detections from multiple methods
#     """
#     if not all_detections:
#         return []
    
#     # Priority: OpenAI > CV > Color
#     method_priority = {"openai": 3, "cv": 2, "color": 1}
    
#     # If OpenAI found tables, use them as primary
#     openai_results = [tables for method, tables in all_detections if method == "openai"]
#     if openai_results and len(openai_results[0]) > 0:
#         logger.info(f"✅ Using OpenAI results as primary ({len(openai_results[0])} tables)")
#         return openai_results[0]
    
#     # Otherwise merge all results
#     all_tables = []
#     for method, tables in all_detections:
#         all_tables.extend(tables)
    
#     if not all_tables:
#         return []
    
#     # Remove duplicates using spatial clustering
#     height, width = frame_shape[:2]
#     merged = []
#     used = set()
    
#     for i, table1 in enumerate(all_tables):
#         if i in used:
#             continue
        
#         # Find all tables at similar position
#         cluster = [table1]
#         px1 = table1['pixelCoordinates']
#         center1_x = px1['x'] + px1['width'] // 2
#         center1_y = px1['y'] + px1['height'] // 2
        
#         for j, table2 in enumerate(all_tables):
#             if i == j or j in used:
#                 continue
            
#             px2 = table2['pixelCoordinates']
#             center2_x = px2['x'] + px2['width'] // 2
#             center2_y = px2['y'] + px2['height'] // 2
            
#             # If centers are close (within 15% of frame size)
#             distance = np.sqrt((center1_x - center2_x)**2 + (center1_y - center2_y)**2)
#             threshold = max(width, height) * 0.15
            
#             if distance < threshold:
#                 cluster.append(table2)
#                 used.add(j)
        
#         # Pick best from cluster (highest priority method + confidence)
#         best_table = max(cluster, key=lambda t: (
#             method_priority.get(t.get('detectionMethod', '').split('_')[0], 0),
#             t.get('confidence', 0)
#         ))
        
#         merged.append(best_table)
#         used.add(i)
    
#     logger.info(f"🔀 Merged {len(all_tables)} detections → {len(merged)} unique tables")
#     return merged


# def _refine_detections(tables: List[Dict], frame_shape: Tuple, room_dimensions: Dict) -> List[Dict]:
#     """
#     Post-process and refine detected tables
#     """
#     if not tables:
#         return tables
    
#     height, width = frame_shape[:2]
    
#     # Re-number tables sequentially
#     for idx, table in enumerate(tables, 1):
#         table['tableId'] = f"table_{idx}"
    
#     # Sort by position (top-to-bottom, left-to-right)
#     tables.sort(key=lambda t: (
#         t['pixelCoordinates']['y'] + t['pixelCoordinates']['height']//2,
#         t['pixelCoordinates']['x'] + t['pixelCoordinates']['width']//2
#     ))
    
#     # Re-assign IDs after sorting
#     for idx, table in enumerate(tables, 1):
#         table['tableId'] = f"table_{idx}"
    
#     return tables


# def _draw_advanced_annotations(frame: np.ndarray, tables: List[Dict]) -> np.ndarray:
#     """
#     Draw beautiful annotations with confidence indicators
#     """
#     colors = {
#         'circular': (255, 100, 255),    # Magenta
#         'rectangular': (50, 180, 255),  # Orange
#         'square': (100, 255, 255),      # Yellow
#     }
    
#     overlay = frame.copy()
    
#     for table in tables:
#         px = table['pixelCoordinates']
#         x, y, w, h = px['x'], px['y'], px['width'], px['height']
        
#         table_type = table.get('tableType', 'rectangular')
#         base_color = colors.get(table_type, (0, 255, 0))
        
#         # Adjust color intensity based on confidence
#         confidence = table.get('confidence', 0.8)
#         color = tuple(int(c * confidence) for c in base_color)
        
#         # Draw semi-transparent fill
#         cv2.rectangle(overlay, (x, y), (x + w, y + h), base_color, -1)
        
#         # Draw border
#         thickness = 3 if confidence >= 0.8 else 2
#         cv2.rectangle(frame, (x, y), (x + w, y + h), color, thickness)
        
#         # Label with more info
#         chair_count = table.get('chairCount', 0)
#         method = table.get('detectionMethod', 'unknown')[:2].upper()
        
#         label = f"{table['tableId']}"
#         if chair_count > 0:
#             label += f" [{chair_count}👤]"
#         label += f" {int(confidence*100)}%"
        
#         # Background for text
#         (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
#         cv2.rectangle(frame, (x, y - th - 8), (x + tw + 8, y), color, -1)
        
#         # Text
#         cv2.putText(frame, label, (x + 4, y - 4),
#                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
#         # Center marker
#         center_x, center_y = x + w // 2, y + h // 2
#         cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)
    
#     # Blend overlay
#     cv2.addWeighted(overlay, 0.2, frame, 0.8, 0, frame)
    
#     # Summary box
#     summary_height = 120
#     cv2.rectangle(frame, (10, 10), (400, summary_height), (0, 0, 0), -1)
#     cv2.rectangle(frame, (10, 10), (400, summary_height), (0, 255, 0), 2)
    
#     cv2.putText(frame, f"Total Tables: {len(tables)}", (20, 35),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    
#     total_seats = sum([t.get('chairCount', 0) for t in tables])
#     cv2.putText(frame, f"Total Seats: {total_seats}", (20, 65),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
#     # Confidence breakdown
#     high_conf = len([t for t in tables if t.get('confidence', 0) >= 0.8])
#     cv2.putText(frame, f"High Confidence: {high_conf}/{len(tables)}", (20, 95),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 2)
    
#     return frame