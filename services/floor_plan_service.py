
# # services/floor_plan_service.py
# """
# Simple Table Detection Service
# ===============================
# Uses ONLY OpenAI Vision API - no CV hallucinations!
# """

# import cv2
# from urllib.parse import urlparse, unquote
# import numpy as np
# from typing import List, Dict, Tuple
# from bson import ObjectId
# from fastapi.concurrency import run_in_threadpool
# import logging
# import io
# import json
# import base64
# from PIL import Image
# import boto3
# from openai import OpenAI
# from config import settings
# from database import get_database
# from services.s3_service import upload_to_s3

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Initialize OpenAI client
# openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


# async def detect_tables_from_floor_plan_url(
#     floor_plan_url: str,
#     analysis_id: str,
#     room_dimensions: Dict
# ):
#     """
#     Table detection using OpenAI Vision API only
#     """
#     db = get_database()
    
#     try:
#         logger.info(f"🔍 Starting floor plan analysis for {analysis_id}")
        
#         # Download image from S3
#         s3_client = boto3.client(
#             's3',
#             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
#             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
#             region_name=settings.AWS_REGION
#         )
        
#         parsed_url = urlparse(floor_plan_url)
#         s3_key = unquote(parsed_url.path.lstrip('/'))
        
#         logger.info(f"📂 S3 Key: {s3_key}")
        
#         response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
#         image_content = response['Body'].read()
        
#         logger.info(f"✅ Downloaded {len(image_content)} bytes")
        
#         # Run detection
#         detected_tables, annotated_image, detection_metadata = await run_in_threadpool(
#             _detect_with_openai_vision,
#             image_content,
#             room_dimensions
#         )
        
#         logger.info(f"✅ Detected {len(detected_tables)} tables")
        
#         # Encode and upload annotated image
#         success, img_encoded = cv2.imencode('.jpg', annotated_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
#         if not success:
#             raise Exception("Failed to encode annotated image")
        
#         annotated_url = await upload_to_s3(
#             img_encoded.tobytes(),
#             f"floor_plans/annotated_{analysis_id}.jpg"
#         )
        
#         # Update database
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {
#                 "$set": {
#                     "analysisStatus": "completed",
#                     "detectedTables": detected_tables,
#                     "annotatedFloorPlanUrl": annotated_url,
#                     "tableCount": len(detected_tables),
#                     "detectionMetadata": detection_metadata
#                 }
#             }
#         )
        
#         logger.info(f"✅ Analysis completed for {analysis_id}")
        
#     except Exception as e:
#         logger.error(f"❌ Analysis error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
        
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {"$set": {"analysisStatus": "failed", "error": str(e)}}
#         )


# def _detect_with_openai_vision(
#     image_content: bytes,
#     room_dimensions: Dict
# ) -> Tuple[List[Dict], np.ndarray, Dict]:
#     """
#     Use OpenAI Vision to detect tables
#     """
#     # Load image
#     img = _load_image(image_content)
#     height, width = img.shape[:2]
    
#     # 🆕 Calculate pixel-to-meter scale
#     scale_x = room_dimensions['length'] / width
#     scale_y = room_dimensions['width'] / height
    
#     logger.info(f"📐 Image: {width}x{height}")
#     logger.info(f"🔢 Scale: {scale_x:.4f}m/px (X), {scale_y:.4f}m/px (Y)")
    
#     try:
#         base64_image = base64.b64encode(image_content).decode('utf-8')
        
#         # IMPROVED PROMPT - very specific instructions
#         prompt = f"""You are analyzing a restaurant floor plan image to detect dining tables.

# **Room Dimensions:** {room_dimensions['length']} x {room_dimensions['width']} {room_dimensions['unit']}
# **Image Size:** {width} x {height} pixels

# **YOUR TASK:** Identify EVERY dining table in this floor plan.

# **What is a TABLE:**
# - A table is where customers sit to eat
# - Tables can be: circular (round), rectangular (square/oblong), or irregular shapes
# - Tables usually have chairs around them (but chairs might not always be visible)
# - Look for table shapes in the dining area, NOT in kitchen/storage areas

# **SCANNING PROCEDURE:**
# 1. Divide the image into 5 vertical sections: Far Left, Left, Center, Right, Far Right
# 2. In EACH section, scan from top to bottom
# 3. Mark every table-like shape you see
# 4. DO NOT miss tables on the edges of the image!

# **IMPORTANT RULES:**
# ✅ Count all tables, even small ones
# ✅ Count tables near walls/edges
# ✅ If you see a group of chairs, there's likely a table there
# ❌ Do NOT count kitchen counters, bars (unless they have seating)
# ❌ Do NOT count the same table twice
# ❌ Do NOT invent tables that don't exist

# **OUTPUT FORMAT:**
# Return a JSON array with each table. For each table provide:
# - table_number: sequential number (1, 2, 3...)
# - type: "rectangular" or "circular" or "irregular"
# - center_x_percent: X position of table center as % of image width (0.0 to 1.0)
# - center_y_percent: Y position of table center as % of image height (0.0 to 1.0)
# - width_percent: table width as % of image width
# - height_percent: table height as % of image height
# - estimated_seats: estimated number of seats (2, 4, 6, 8, etc.)

# **Example:**
# [
#   {{
#     "table_number": 1,
#     "type": "rectangular",
#     "center_x_percent": 0.25,
#     "center_y_percent": 0.30,
#     "width_percent": 0.08,
#     "height_percent": 0.06,
#     "estimated_seats": 4
#   }},
#   {{
#     "table_number": 2,
#     "type": "circular",
#     "center_x_percent": 0.65,
#     "center_y_percent": 0.45,
#     "width_percent": 0.07,
#     "height_percent": 0.07,
#     "estimated_seats": 4
#   }}
# ]

# Return ONLY the JSON array, nothing else. Be thorough and don't miss any tables!"""

#         logger.info("🤖 Calling OpenAI Vision API...")
        
#         response = openai_client.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": prompt},
#                         {
#                             "type": "image_url",
#                             "image_url": {
#                                 "url": f"data:image/jpeg;base64,{base64_image}"
#                             }
#                         }
#                     ]
#                 }
#             ],
#             max_tokens=2000,
#             temperature=0.1  # Low temperature for consistency
#         )
        
#         content = response.choices[0].message.content.strip()
#         logger.info(f"📥 OpenAI Response received ({len(content)} chars)")
        
#         # Parse JSON
#         if content.startswith("```json"):
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif content.startswith("```"):
#             content = content.split("```")[1].split("```")[0].strip()
        
#         tables_data = json.loads(content)
        
#         logger.info(f"✅ OpenAI detected {len(tables_data)} tables")
        
#         # Convert to standard format
#         detected_tables = []
        
#         for table in tables_data:
#             # Calculate pixel coordinates
#             x = int(table['center_x_percent'] * width - (table.get('width_percent', 0.05) * width / 2))
#             y = int(table['center_y_percent'] * height - (table.get('height_percent', 0.05) * height / 2))
#             w = int(table.get('width_percent', 0.05) * width)
#             h = int(table.get('height_percent', 0.05) * height)
            
#             # Ensure values are within bounds
#             x = max(0, min(x, width - 1))
#             y = max(0, min(y, height - 1))
#             w = max(20, min(w, width - x))
#             h = max(20, min(h, height - y))
            
#             # 🆕 Calculate real-world coordinates
#             real_x = x * scale_x
#             real_y = y * scale_y
#             real_width = w * scale_x
#             real_height = h * scale_y
            
#             detected_tables.append({
#                 "tableId": f"table_{table['table_number']}",
#                 "detectionMethod": "openai_vision",
#                 "tableType": table.get('type', 'rectangular'),
#                 "chairCount": table.get('estimated_seats', 0),
#                 "pixelCoordinates": {
#                     "x": x,
#                     "y": y,
#                     "width": w,
#                     "height": h
#                 },
#                 # 🆕 Added real-world coordinates
#                 "realWorldCoordinates": {
#                     "x": round(real_x, 2),
#                     "y": round(real_y, 2),
#                     "width": round(real_width, 2),
#                     "height": round(real_height, 2),
#                     "unit": room_dimensions['unit']
#                 },
#                 "confidence": 0.90  # OpenAI is quite reliable
#             })
        
#         # Draw annotations
#         annotated = _draw_annotations(img.copy(), detected_tables)
        
#         # Metadata
#         metadata = {
#             "detection_method": "openai_vision",
#             "table_count": len(detected_tables),
#             "table_types": list(set([t['tableType'] for t in detected_tables])),
#             "total_estimated_seats": sum([t['chairCount'] for t in detected_tables]),
#             "scale_factor": {
#                 "x": round(scale_x, 4),
#                 "y": round(scale_y, 4),
#                 "unit": f"{room_dimensions['unit']}/pixel"
#             }
#         }
        
#         return detected_tables, annotated, metadata
        
#     except json.JSONDecodeError as e:
#         logger.error(f"❌ JSON parse error: {e}")
#         if 'content' in locals():
#             logger.error(f"Response was: {content}")
#         # Return empty on error
#         return [], img, {"error": str(e)}
        
#     except Exception as e:
#         logger.error(f"❌ OpenAI Vision error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         return [], img, {"error": str(e)}


# def _load_image(image_content: bytes) -> np.ndarray:
#     """Load image from bytes"""
#     try:
#         import pillow_avif
#     except ImportError:
#         pass
    
#     img_pil = Image.open(io.BytesIO(image_content))
    
#     if img_pil.mode != 'RGB':
#         img_pil = img_pil.convert('RGB')
    
#     img_array = np.array(img_pil)
#     return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)


# def _draw_annotations(img: np.ndarray, tables: List[Dict]) -> np.ndarray:
#     """Draw clean annotations on the image"""
    
#     colors = {
#         'circular': (255, 0, 255),      # Magenta
#         'rectangular': (0, 165, 255),   # Orange
#         'irregular': (0, 255, 255)      # Yellow
#     }
    
#     for table in tables:
#         px = table['pixelCoordinates']
#         x, y, w, h = px['x'], px['y'], px['width'], px['height']
        
#         table_type = table.get('tableType', 'rectangular')
#         color = colors.get(table_type, (0, 255, 0))
        
#         # Draw shape
#         if table_type == 'circular':
#             center = (x + w // 2, y + h // 2)
#             radius = max(w, h) // 2
#             cv2.circle(img, center, radius, color, 2)
#         else:
#             cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        
#         # Label with real-world dimensions
#         seats = table.get('chairCount', 0)
#         real_coords = table.get('realWorldCoordinates', {})
#         real_w = real_coords.get('width', 0)
#         real_h = real_coords.get('height', 0)
        
#         label = f"{table['tableId']}"
#         if seats > 0:
#             label += f" ({seats})"
#         if real_w > 0 and real_h > 0:
#             label += f" {real_w:.1f}x{real_h:.1f}m"
        
#         # Draw label with background
#         font = cv2.FONT_HERSHEY_SIMPLEX
#         font_scale = 0.4
#         thickness = 1
#         (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
        
#         cv2.rectangle(img, (x, y - text_h - 6), (x + text_w + 4, y - 2), color, -1)
#         cv2.putText(img, label, (x + 2, y - 4), font, font_scale, (255, 255, 255), thickness)
        
#         # Center dot
#         cv2.circle(img, (x + w // 2, y + h // 2), 3, (0, 0, 255), -1)
    
#     # Summary
#     summary_h = 100
#     cv2.rectangle(img, (5, 5), (250, summary_h), (0, 0, 0), -1)
#     cv2.rectangle(img, (5, 5), (250, summary_h), (255, 255, 255), 2)
    
#     y_pos = 25
#     cv2.putText(img, f"Tables: {len(tables)}", (15, y_pos),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
#     # Type breakdown
#     type_counts = {}
#     total_seats = 0
#     for t in tables:
#         type_counts[t['tableType']] = type_counts.get(t['tableType'], 0) + 1
#         total_seats += t.get('chairCount', 0)
    
#     y_pos += 25
#     for t_type, count in type_counts.items():
#         color = colors.get(t_type, (128, 128, 128))
#         cv2.putText(img, f"{t_type}: {count}", (15, y_pos),
#                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
#         y_pos += 20
    
#     cv2.putText(img, f"Seats: {total_seats}", (15, y_pos),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
#     return img










# """
# Simple Table Detection Service - GEMINI VERSION (ROBUST FIX)
# ================================================
# Uses Google Gemini Vision API with proper API version handling
# """

# import cv2
# from urllib.parse import urlparse, unquote
# import numpy as np
# from typing import List, Dict, Tuple, Optional
# from bson import ObjectId
# from fastapi.concurrency import run_in_threadpool
# import logging
# import io
# import json
# import base64
# from PIL import Image
# import boto3
# import google.generativeai as genai
# from config import settings
# from database import get_database
# from services.s3_service import upload_to_s3

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Initialize Gemini
# genai.configure(api_key=settings.GEMINI_API_KEY)

# # Cache for detected model
# _vision_model_cache: Optional[str] = None


# def _list_available_models() -> List[str]:
#     """List all available vision models from Gemini API"""
#     available = []
#     try:
#         for model in genai.list_models():
#             if 'generateContent' in model.supported_generation_methods:
#                 name = model.name.replace('models/', '')
#                 available.append(name)
#                 logger.debug(f"✅ Available: {name}")
#         return available
#     except Exception as e:
#         logger.error(f"❌ Could not list models: {e}")
#         return []


# def _get_vision_model() -> genai.GenerativeModel:
#     """Get the correct Gemini vision model (auto-detect from available models)"""
#     global _vision_model_cache
    
#     if not _vision_model_cache:
#         logger.info("🔍 Auto-detecting Gemini model...")
        
#         # Get actually available models from API
#         available_models = _list_available_models()
        
#         if not available_models:
#             raise Exception(
#                 "No Gemini models available. Please check your API key and permissions. "
#                 "Visit https://aistudio.google.com/app/apikey to verify your API key."
#             )
        
#         logger.info(f"📋 Found {len(available_models)} available models")
        
#         # Preferred models in order (check which ones are actually available)
#         preferred_models = [
#             'gemini-2.0-flash-exp',     # Latest experimental
#             'gemini-1.5-pro',
#             'gemini-1.5-flash', 
#             'gemini-1.5-flash-8b',
#             'gemini-pro-vision',
#             'gemini-exp-1206',          # Another experimental
#         ]
        
#         # Find first preferred model that's available
#         for preferred in preferred_models:
#             if preferred in available_models:
#                 _vision_model_cache = preferred
#                 logger.info(f"✅ Selected model: {preferred}")
#                 return genai.GenerativeModel(_vision_model_cache)
        
#         # If no preferred model found, use the first available one
#         _vision_model_cache = available_models[0]
#         logger.warning(f"⚠️ Using first available model: {_vision_model_cache}")
#         logger.info(f"💡 Available models were: {', '.join(available_models)}")
    
#     return genai.GenerativeModel(_vision_model_cache)


# async def detect_tables_from_floor_plan_url(
#     floor_plan_url: str,
#     analysis_id: str,
#     room_dimensions: Dict
# ):
#     """
#     Table detection using Gemini Vision API
#     """
#     db = get_database()
    
#     try:
#         logger.info(f"🔍 Starting floor plan analysis for {analysis_id}")
        
#         # Download image from S3
#         s3_client = boto3.client(
#             's3',
#             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
#             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
#             region_name=settings.AWS_REGION
#         )
        
#         parsed_url = urlparse(floor_plan_url)
#         s3_key = unquote(parsed_url.path.lstrip('/'))
        
#         logger.info(f"📂 S3 Key: {s3_key}")
        
#         response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
#         image_content = response['Body'].read()
        
#         logger.info(f"✅ Downloaded {len(image_content)} bytes")
        
#         # Run detection with Gemini
#         detected_tables, annotated_image, detection_metadata = await run_in_threadpool(
#             _detect_with_gemini_vision,
#             image_content,
#             room_dimensions
#         )
        
#         logger.info(f"✅ Detected {len(detected_tables)} tables")
        
#         # Encode and upload annotated image
#         success, img_encoded = cv2.imencode('.jpg', annotated_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
#         if not success:
#             raise Exception("Failed to encode annotated image")
        
#         annotated_url = await upload_to_s3(
#             img_encoded.tobytes(),
#             f"floor_plans/annotated_{analysis_id}.jpg"
#         )
        
#         # Update database
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {
#                 "$set": {
#                     "analysisStatus": "completed",
#                     "detectedTables": detected_tables,
#                     "annotatedFloorPlanUrl": annotated_url,
#                     "tableCount": len(detected_tables),
#                     "detectionMetadata": detection_metadata
#                 }
#             }
#         )
        
#         logger.info(f"✅ Analysis completed for {analysis_id}")
        
#     except Exception as e:
#         logger.error(f"❌ Analysis error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
        
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {"$set": {"analysisStatus": "failed", "error": str(e)}}
#         )


# def _detect_with_gemini_vision(
#     image_content: bytes,
#     room_dimensions: Dict
# ) -> Tuple[List[Dict], np.ndarray, Dict]:
#     """
#     Use Gemini Vision to detect tables
#     """
#     # Load image
#     img = _load_image(image_content)
#     height, width = img.shape[:2]
    
#     # Calculate pixel-to-meter scale
#     scale_x = room_dimensions['length'] / width
#     scale_y = room_dimensions['width'] / height
    
#     logger.info(f"📐 Image: {width}x{height}")
#     logger.info(f"🔢 Scale: {scale_x:.4f}m/px (X), {scale_y:.4f}m/px (Y)")
    
#     try:
#         # Get Gemini model (with auto-detection)
#         model = _get_vision_model()
        
#         # Load PIL image for Gemini
#         pil_image = Image.open(io.BytesIO(image_content))
        
#         # IMPROVED PROMPT - very specific instructions
#         prompt = f"""You are analyzing a restaurant floor plan image to detect dining tables.

# **Room Dimensions:** {room_dimensions['length']} x {room_dimensions['width']} {room_dimensions['unit']}
# **Image Size:** {width} x {height} pixels

# **YOUR TASK:** Identify EVERY dining table in this floor plan.

# **What is a TABLE:**
# - A table is where customers sit to eat
# - Tables can be: circular (round), rectangular (square/oblong), or irregular shapes
# - Tables usually have chairs around them (but chairs might not always be visible)
# - Look for table shapes in the dining area, NOT in kitchen/storage areas

# **SCANNING PROCEDURE:**
# 1. Divide the image into 5 vertical sections: Far Left, Left, Center, Right, Far Right
# 2. In EACH section, scan from top to bottom
# 3. Mark every table-like shape you see
# 4. DO NOT miss tables on the edges of the image!

# **IMPORTANT RULES:**
# ✅ Count all tables, even small ones
# ✅ Count tables near walls/edges
# ✅ If you see a group of chairs, there's likely a table there
# ❌ Do NOT count kitchen counters, bars (unless they have seating)
# ❌ Do NOT count the same table twice
# ❌ Do NOT invent tables that don't exist

# **OUTPUT FORMAT:**
# Return a JSON array with each table. For each table provide:
# - table_number: sequential number (1, 2, 3...)
# - type: "rectangular" or "circular" or "irregular"
# - center_x_percent: X position of table center as % of image width (0.0 to 1.0)
# - center_y_percent: Y position of table center as % of image height (0.0 to 1.0)
# - width_percent: table width as % of image width
# - height_percent: table height as % of image height
# - estimated_seats: estimated number of seats (2, 4, 6, 8, etc.)

# **Example:**
# [
#   {{
#     "table_number": 1,
#     "type": "rectangular",
#     "center_x_percent": 0.25,
#     "center_y_percent": 0.30,
#     "width_percent": 0.08,
#     "height_percent": 0.06,
#     "estimated_seats": 4
#   }},
#   {{
#     "table_number": 2,
#     "type": "circular",
#     "center_x_percent": 0.65,
#     "center_y_percent": 0.45,
#     "width_percent": 0.07,
#     "height_percent": 0.07,
#     "estimated_seats": 4
#   }}
# ]

# Return ONLY the JSON array, nothing else. Be thorough and don't miss any tables!"""

#         logger.info(f"🤖 Calling Gemini Vision API (model: {_vision_model_cache})...")
        
#         # Generate content with Gemini
#         response = model.generate_content([prompt, pil_image])
#         content = response.text.strip()
        
#         logger.info(f"📥 Gemini Response received ({len(content)} chars)")
#         logger.debug(f"Response preview: {content[:200]}...")
        
#         # Parse JSON
#         if content.startswith("```json"):
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif content.startswith("```"):
#             content = content.split("```")[1].split("```")[0].strip()
        
#         tables_data = json.loads(content)
        
#         logger.info(f"✅ Gemini detected {len(tables_data)} tables")
        
#         # Convert to standard format
#         detected_tables = []
        
#         for table in tables_data:
#             # Calculate pixel coordinates
#             x = int(table['center_x_percent'] * width - (table.get('width_percent', 0.05) * width / 2))
#             y = int(table['center_y_percent'] * height - (table.get('height_percent', 0.05) * height / 2))
#             w = int(table.get('width_percent', 0.05) * width)
#             h = int(table.get('height_percent', 0.05) * height)
            
#             # Ensure values are within bounds
#             x = max(0, min(x, width - 1))
#             y = max(0, min(y, height - 1))
#             w = max(20, min(w, width - x))
#             h = max(20, min(h, height - y))
            
#             # Calculate real-world coordinates
#             real_x = x * scale_x
#             real_y = y * scale_y
#             real_width = w * scale_x
#             real_height = h * scale_y
            
#             detected_tables.append({
#                 "tableId": f"table_{table['table_number']}",
#                 "detectionMethod": "gemini_vision",
#                 "tableType": table.get('type', 'rectangular'),
#                 "chairCount": table.get('estimated_seats', 0),
#                 "pixelCoordinates": {
#                     "x": x,
#                     "y": y,
#                     "width": w,
#                     "height": h
#                 },
#                 "realWorldCoordinates": {
#                     "x": round(real_x, 2),
#                     "y": round(real_y, 2),
#                     "width": round(real_width, 2),
#                     "height": round(real_height, 2),
#                     "unit": room_dimensions['unit']
#                 },
#                 "confidence": 0.90
#             })
        
#         # Draw annotations
#         annotated = _draw_annotations(img.copy(), detected_tables)
        
#         # Metadata
#         metadata = {
#             "detection_method": "gemini_vision",
#             "model_used": _vision_model_cache or "gemini-unknown",
#             "table_count": len(detected_tables),
#             "table_types": list(set([t['tableType'] for t in detected_tables])),
#             "total_estimated_seats": sum([t['chairCount'] for t in detected_tables]),
#             "scale_factor": {
#                 "x": round(scale_x, 4),
#                 "y": round(scale_y, 4),
#                 "unit": f"{room_dimensions['unit']}/pixel"
#             }
#         }
        
#         return detected_tables, annotated, metadata
        
#     except json.JSONDecodeError as e:
#         logger.error(f"❌ JSON parse error: {e}")
#         if 'content' in locals():
#             logger.error(f"Response was: {content}")
#         # Return empty on error
#         return [], img, {"error": str(e)}
        
#     except Exception as e:
#         logger.error(f"❌ Gemini Vision error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         return [], img, {"error": str(e)}


# def _load_image(image_content: bytes) -> np.ndarray:
#     """Load image from bytes"""
#     try:
#         import pillow_avif
#     except ImportError:
#         pass
    
#     img_pil = Image.open(io.BytesIO(image_content))
    
#     if img_pil.mode != 'RGB':
#         img_pil = img_pil.convert('RGB')
    
#     img_array = np.array(img_pil)
#     return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)


# def _draw_annotations(img: np.ndarray, tables: List[Dict]) -> np.ndarray:
#     """Draw clean annotations on the image"""
    
#     colors = {
#         'circular': (255, 0, 255),      # Magenta
#         'rectangular': (0, 165, 255),   # Orange
#         'irregular': (0, 255, 255)      # Yellow
#     }
    
#     for table in tables:
#         px = table['pixelCoordinates']
#         x, y, w, h = px['x'], px['y'], px['width'], px['height']
        
#         table_type = table.get('tableType', 'rectangular')
#         color = colors.get(table_type, (0, 255, 0))
        
#         # Draw shape
#         if table_type == 'circular':
#             center = (x + w // 2, y + h // 2)
#             radius = max(w, h) // 2
#             cv2.circle(img, center, radius, color, 2)
#         else:
#             cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        
#         # Label with real-world dimensions
#         seats = table.get('chairCount', 0)
#         real_coords = table.get('realWorldCoordinates', {})
#         real_w = real_coords.get('width', 0)
#         real_h = real_coords.get('height', 0)
        
#         label = f"{table['tableId']}"
#         if seats > 0:
#             label += f" ({seats})"
#         if real_w > 0 and real_h > 0:
#             label += f" {real_w:.1f}x{real_h:.1f}m"
        
#         # Draw label with background
#         font = cv2.FONT_HERSHEY_SIMPLEX
#         font_scale = 0.4
#         thickness = 1
#         (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
        
#         cv2.rectangle(img, (x, y - text_h - 6), (x + text_w + 4, y - 2), color, -1)
#         cv2.putText(img, label, (x + 2, y - 4), font, font_scale, (255, 255, 255), thickness)
        
#         # Center dot
#         cv2.circle(img, (x + w // 2, y + h // 2), 3, (0, 0, 255), -1)
    
#     # Summary box
#     summary_h = 100
#     cv2.rectangle(img, (5, 5), (250, summary_h), (0, 0, 0), -1)
#     cv2.rectangle(img, (5, 5), (250, summary_h), (255, 255, 255), 2)
    
#     y_pos = 25
#     cv2.putText(img, f"Tables: {len(tables)}", (15, y_pos),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
#     # Type breakdown
#     type_counts = {}
#     total_seats = 0
#     for t in tables:
#         type_counts[t['tableType']] = type_counts.get(t['tableType'], 0) + 1
#         total_seats += t.get('chairCount', 0)
    
#     y_pos += 25
#     for t_type, count in type_counts.items():
#         color = colors.get(t_type, (128, 128, 128))
#         cv2.putText(img, f"{t_type}: {count}", (15, y_pos),
#                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
#         y_pos += 20
    
#     cv2.putText(img, f"Seats: {total_seats}", (15, y_pos),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
#     return img





################final version#######################

# """
# Simple Table Detection Service - GEMINI VERSION (PRODUCTION READY)
# ================================================
# Uses Google Gemini Vision API with rate limit handling
# """

# import cv2
# from urllib.parse import urlparse, unquote
# import numpy as np
# from typing import List, Dict, Tuple, Optional
# from bson import ObjectId
# from fastapi.concurrency import run_in_threadpool
# import logging
# import io
# import json
# import time
# from PIL import Image
# import boto3
# import google.generativeai as genai
# from google.api_core import exceptions as google_exceptions
# from config import settings
# from database import get_database
# from services.s3_service import upload_to_s3

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Initialize Gemini
# genai.configure(api_key=settings.GEMINI_API_KEY)

# # Cache for detected model
# _vision_model_cache: Optional[str] = None


# def _list_available_models() -> List[str]:
#     """List all available vision models from Gemini API"""
#     available = []
#     try:
#         for model in genai.list_models():
#             if 'generateContent' in model.supported_generation_methods:
#                 name = model.name.replace('models/', '')
#                 available.append(name)
#         return available
#     except Exception as e:
#         logger.error(f"❌ Could not list models: {e}")
#         return []


# def _get_vision_model() -> genai.GenerativeModel:
#     """Get the correct Gemini vision model with quota-aware selection"""
#     global _vision_model_cache
    
#     if not _vision_model_cache:
#         logger.info("🔍 Auto-detecting Gemini model...")
        
#         # Get actually available models from API
#         available_models = _list_available_models()
        
#         if not available_models:
#             raise Exception(
#                 "No Gemini models available. Please check your API key and permissions. "
#                 "Visit https://aistudio.google.com/app/apikey to verify your API key."
#             )
        
#         logger.info(f"📋 Found {len(available_models)} available models")
        
#         # Preferred models in order (prioritizing models with better free-tier quotas)
#         preferred_models = [
#             # Free tier models with good quotas (prioritize these)
#             'gemini-2.0-flash-exp',      # Latest Flash with good quotas
#             'gemini-1.5-flash',           # Stable Flash model
#             'gemini-1.5-flash-8b',        # Lightweight Flash
#             'gemini-1.5-flash-002',       # Flash variant
#             'gemini-1.5-flash-latest',    # Latest Flash
            
#             # Pro models (might have stricter limits on free tier)
#             'gemini-2.5-pro',             # New recommended model
#             'gemini-1.5-pro',             # Stable Pro
#             'gemini-1.5-pro-002',         # Pro variant
#             'gemini-1.5-pro-latest',      # Latest Pro
            
#             # Experimental models (use with caution)
#             'gemini-exp-1206',            # Experimental
#             'gemini-2.0-pro-exp',         # Pro experimental
            
#             # Legacy
#             'gemini-pro-vision',          # Legacy fallback
#         ]
        
#         # Find first preferred model that's available
#         for preferred in preferred_models:
#             if preferred in available_models:
#                 _vision_model_cache = preferred
#                 logger.info(f"✅ Selected model: {preferred}")
#                 return genai.GenerativeModel(_vision_model_cache)
        
#         # If no preferred model found, use the first available one
#         _vision_model_cache = available_models[0]
#         logger.warning(f"⚠️ Using first available model: {_vision_model_cache}")
#         logger.info(f"💡 Available models were: {', '.join(available_models[:5])}...")
    
#     return genai.GenerativeModel(_vision_model_cache)


# async def detect_tables_from_floor_plan_url(
#     floor_plan_url: str,
#     analysis_id: str,
#     room_dimensions: Dict
# ):
#     """
#     Table detection using Gemini Vision API with retry logic
#     """
#     db = get_database()
    
#     try:
#         logger.info(f"🔍 Starting floor plan analysis for {analysis_id}")
        
#         # Download image from S3
#         s3_client = boto3.client(
#             's3',
#             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
#             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
#             region_name=settings.AWS_REGION
#         )
        
#         parsed_url = urlparse(floor_plan_url)
#         s3_key = unquote(parsed_url.path.lstrip('/'))
        
#         logger.info(f"📂 S3 Key: {s3_key}")
        
#         response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
#         image_content = response['Body'].read()
        
#         logger.info(f"✅ Downloaded {len(image_content)} bytes")
        
#         # Run detection with Gemini (with retry logic)
#         detected_tables, annotated_image, detection_metadata = await run_in_threadpool(
#             _detect_with_gemini_vision_with_retry,
#             image_content,
#             room_dimensions
#         )
        
#         logger.info(f"✅ Detected {len(detected_tables)} tables")
        
#         # Encode and upload annotated image
#         success, img_encoded = cv2.imencode('.jpg', annotated_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
#         if not success:
#             raise Exception("Failed to encode annotated image")
        
#         annotated_url = await upload_to_s3(
#             img_encoded.tobytes(),
#             f"floor_plans/annotated_{analysis_id}.jpg"
#         )
        
#         # Update database
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {
#                 "$set": {
#                     "analysisStatus": "completed",
#                     "detectedTables": detected_tables,
#                     "annotatedFloorPlanUrl": annotated_url,
#                     "tableCount": len(detected_tables),
#                     "detectionMetadata": detection_metadata
#                 }
#             }
#         )
        
#         logger.info(f"✅ Analysis completed for {analysis_id}")
        
#     except Exception as e:
#         logger.error(f"❌ Analysis error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
        
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {"$set": {"analysisStatus": "failed", "error": str(e)}}
#         )


# def _detect_with_gemini_vision_with_retry(
#     image_content: bytes,
#     room_dimensions: Dict,
#     max_retries: int = 3
# ) -> Tuple[List[Dict], np.ndarray, Dict]:
#     """
#     Wrapper with retry logic for rate limit errors
#     """
#     global _vision_model_cache
    
#     for attempt in range(max_retries):
#         try:
#             return _detect_with_gemini_vision(image_content, room_dimensions)
            
#         except google_exceptions.ResourceExhausted as e:
#             logger.warning(f"⚠️ Rate limit hit on attempt {attempt + 1}/{max_retries}")
            
#             # If we have retries left, try a different model
#             if attempt < max_retries - 1:
#                 # Clear cache to force model reselection
#                 old_model = _vision_model_cache
#                 _vision_model_cache = None
                
#                 # Get list of available models
#                 available = _list_available_models()
                
#                 # Try to find a different model (preferring Flash models)
#                 flash_models = [m for m in available if 'flash' in m.lower() and m != old_model]
#                 other_models = [m for m in available if m != old_model and m not in flash_models]
                
#                 if flash_models:
#                     _vision_model_cache = flash_models[0]
#                     logger.info(f"🔄 Retrying with different model: {_vision_model_cache}")
#                     time.sleep(2)  # Brief delay before retry
#                     continue
#                 elif other_models:
#                     _vision_model_cache = other_models[0]
#                     logger.info(f"🔄 Retrying with different model: {_vision_model_cache}")
#                     time.sleep(2)
#                     continue
#                 else:
#                     logger.error("❌ No alternative models available")
#                     raise
#             else:
#                 logger.error("❌ Max retries exceeded")
#                 raise
                
#         except Exception as e:
#             # For other errors, don't retry
#             raise
    
#     # Should not reach here
#     raise Exception("Unexpected retry loop exit")


# def _detect_with_gemini_vision(
#     image_content: bytes,
#     room_dimensions: Dict
# ) -> Tuple[List[Dict], np.ndarray, Dict]:
#     """
#     Use Gemini Vision to detect tables
#     """
#     # Load image
#     img = _load_image(image_content)
#     height, width = img.shape[:2]
    
#     # Calculate pixel-to-meter scale
#     scale_x = room_dimensions['length'] / width
#     scale_y = room_dimensions['width'] / height
    
#     logger.info(f"📐 Image: {width}x{height}")
#     logger.info(f"🔢 Scale: {scale_x:.4f}m/px (X), {scale_y:.4f}m/px (Y)")
    
#     try:
#         # Get Gemini model (with auto-detection)
#         model = _get_vision_model()
        
#         # Load PIL image for Gemini
#         pil_image = Image.open(io.BytesIO(image_content))
        
#         # IMPROVED PROMPT - very specific instructions
#         prompt = f"""You are analyzing a restaurant floor plan image to detect dining tables.

# **Room Dimensions:** {room_dimensions['length']} x {room_dimensions['width']} {room_dimensions['unit']}
# **Image Size:** {width} x {height} pixels

# **YOUR TASK:** Identify EVERY dining table in this floor plan.

# **What is a TABLE:**
# - A table is where customers sit to eat
# - Tables can be: circular (round), rectangular (square/oblong), or irregular shapes
# - Tables usually have chairs around them (but chairs might not always be visible)
# - Look for table shapes in the dining area, NOT in kitchen/storage areas

# **SCANNING PROCEDURE:**
# 1. Divide the image into 5 vertical sections: Far Left, Left, Center, Right, Far Right
# 2. In EACH section, scan from top to bottom
# 3. Mark every table-like shape you see
# 4. DO NOT miss tables on the edges of the image!

# **IMPORTANT RULES:**
# ✅ Count all tables, even small ones
# ✅ Count tables near walls/edges
# ✅ If you see a group of chairs, there's likely a table there
# ❌ Do NOT count kitchen counters, bars (unless they have seating)
# ❌ Do NOT count the same table twice
# ❌ Do NOT invent tables that don't exist

# **OUTPUT FORMAT:**
# Return a JSON array with each table. For each table provide:
# - table_number: sequential number (1, 2, 3...)
# - type: "rectangular" or "circular" or "irregular"
# - center_x_percent: X position of table center as % of image width (0.0 to 1.0)
# - center_y_percent: Y position of table center as % of image height (0.0 to 1.0)
# - width_percent: table width as % of image width
# - height_percent: table height as % of image height
# - estimated_seats: estimated number of seats (2, 4, 6, 8, etc.)

# **Example:**
# [
#   {{
#     "table_number": 1,
#     "type": "rectangular",
#     "center_x_percent": 0.25,
#     "center_y_percent": 0.30,
#     "width_percent": 0.08,
#     "height_percent": 0.06,
#     "estimated_seats": 4
#   }},
#   {{
#     "table_number": 2,
#     "type": "circular",
#     "center_x_percent": 0.65,
#     "center_y_percent": 0.45,
#     "width_percent": 0.07,
#     "height_percent": 0.07,
#     "estimated_seats": 4
#   }}
# ]

# Return ONLY the JSON array, nothing else. Be thorough and don't miss any tables!"""

#         logger.info(f"🤖 Calling Gemini Vision API (model: {_vision_model_cache})...")
        
#         # Generate content with Gemini
#         response = model.generate_content([prompt, pil_image])
#         content = response.text.strip()
        
#         logger.info(f"📥 Gemini Response received ({len(content)} chars)")
#         logger.debug(f"Response preview: {content[:200]}...")
        
#         # Parse JSON
#         if content.startswith("```json"):
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif content.startswith("```"):
#             content = content.split("```")[1].split("```")[0].strip()
        
#         tables_data = json.loads(content)
        
#         logger.info(f"✅ Gemini detected {len(tables_data)} tables")
        
#         # Convert to standard format
#         detected_tables = []
        
#         for table in tables_data:
#             # Calculate pixel coordinates
#             x = int(table['center_x_percent'] * width - (table.get('width_percent', 0.05) * width / 2))
#             y = int(table['center_y_percent'] * height - (table.get('height_percent', 0.05) * height / 2))
#             w = int(table.get('width_percent', 0.05) * width)
#             h = int(table.get('height_percent', 0.05) * height)
            
#             # Ensure values are within bounds
#             x = max(0, min(x, width - 1))
#             y = max(0, min(y, height - 1))
#             w = max(20, min(w, width - x))
#             h = max(20, min(h, height - y))
            
#             # Calculate real-world coordinates
#             real_x = x * scale_x
#             real_y = y * scale_y
#             real_width = w * scale_x
#             real_height = h * scale_y
            
#             detected_tables.append({
#                 "tableId": f"table_{table['table_number']}",
#                 "detectionMethod": "gemini_vision",
#                 "tableType": table.get('type', 'rectangular'),
#                 "chairCount": table.get('estimated_seats', 0),
#                 "pixelCoordinates": {
#                     "x": x,
#                     "y": y,
#                     "width": w,
#                     "height": h
#                 },
#                 "realWorldCoordinates": {
#                     "x": round(real_x, 2),
#                     "y": round(real_y, 2),
#                     "width": round(real_width, 2),
#                     "height": round(real_height, 2),
#                     "unit": room_dimensions['unit']
#                 },
#                 "confidence": 0.90
#             })
        
#         # Draw annotations
#         annotated = _draw_annotations(img.copy(), detected_tables)
        
#         # Metadata
#         metadata = {
#             "detection_method": "gemini_vision",
#             "model_used": _vision_model_cache or "gemini-unknown",
#             "table_count": len(detected_tables),
#             "table_types": list(set([t['tableType'] for t in detected_tables])),
#             "total_estimated_seats": sum([t['chairCount'] for t in detected_tables]),
#             "scale_factor": {
#                 "x": round(scale_x, 4),
#                 "y": round(scale_y, 4),
#                 "unit": f"{room_dimensions['unit']}/pixel"
#             }
#         }
        
#         return detected_tables, annotated, metadata
        
#     except json.JSONDecodeError as e:
#         logger.error(f"❌ JSON parse error: {e}")
#         if 'content' in locals():
#             logger.error(f"Response was: {content}")
#         # Return empty on error
#         return [], img, {"error": str(e)}
        
#     except google_exceptions.ResourceExhausted:
#         # Re-raise quota errors so retry logic can handle them
#         raise
        
#     except Exception as e:
#         logger.error(f"❌ Gemini Vision error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         return [], img, {"error": str(e)}


# def _load_image(image_content: bytes) -> np.ndarray:
#     """Load image from bytes"""
#     try:
#         import pillow_avif
#     except ImportError:
#         pass
    
#     img_pil = Image.open(io.BytesIO(image_content))
    
#     if img_pil.mode != 'RGB':
#         img_pil = img_pil.convert('RGB')
    
#     img_array = np.array(img_pil)
#     return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)


# def _draw_annotations(img: np.ndarray, tables: List[Dict]) -> np.ndarray:
#     """Draw clean annotations on the image"""
    
#     colors = {
#         'circular': (255, 0, 255),      # Magenta
#         'rectangular': (0, 165, 255),   # Orange
#         'irregular': (0, 255, 255)      # Yellow
#     }
    
#     for table in tables:
#         px = table['pixelCoordinates']
#         x, y, w, h = px['x'], px['y'], px['width'], px['height']
        
#         table_type = table.get('tableType', 'rectangular')
#         color = colors.get(table_type, (0, 255, 0))
        
#         # Draw shape
#         if table_type == 'circular':
#             center = (x + w // 2, y + h // 2)
#             radius = max(w, h) // 2
#             cv2.circle(img, center, radius, color, 2)
#         else:
#             cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        
#         # Label with real-world dimensions
#         seats = table.get('chairCount', 0)
#         real_coords = table.get('realWorldCoordinates', {})
#         real_w = real_coords.get('width', 0)
#         real_h = real_coords.get('height', 0)
        
#         label = f"{table['tableId']}"
#         if seats > 0:
#             label += f" ({seats})"
#         if real_w > 0 and real_h > 0:
#             label += f" {real_w:.1f}x{real_h:.1f}m"
        
#         # Draw label with background
#         font = cv2.FONT_HERSHEY_SIMPLEX
#         font_scale = 0.4
#         thickness = 1
#         (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
        
#         cv2.rectangle(img, (x, y - text_h - 6), (x + text_w + 4, y - 2), color, -1)
#         cv2.putText(img, label, (x + 2, y - 4), font, font_scale, (255, 255, 255), thickness)
        
#         # Center dot
#         cv2.circle(img, (x + w // 2, y + h // 2), 3, (0, 0, 255), -1)
    
#     # Summary box
#     summary_h = 100
#     cv2.rectangle(img, (5, 5), (250, summary_h), (0, 0, 0), -1)
#     cv2.rectangle(img, (5, 5), (250, summary_h), (255, 255, 255), 2)
    
#     y_pos = 25
#     cv2.putText(img, f"Tables: {len(tables)}", (15, y_pos),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
#     # Type breakdown
#     type_counts = {}
#     total_seats = 0
#     for t in tables:
#         type_counts[t['tableType']] = type_counts.get(t['tableType'], 0) + 1
#         total_seats += t.get('chairCount', 0)
    
#     y_pos += 25
#     for t_type, count in type_counts.items():
#         color = colors.get(t_type, (128, 128, 128))
#         cv2.putText(img, f"{t_type}: {count}", (15, y_pos),
#                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
#         y_pos += 20
    
#     cv2.putText(img, f"Seats: {total_seats}", (15, y_pos),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
#     return img








#############etaa khub valo kaj koree#######################


"""
Simple Table Detection Service - GEMINI VERSION (COORDINATE FIX)
================================================
Fixed coordinate system and dimension calculations
"""

import cv2
from urllib.parse import urlparse, unquote
import numpy as np
from typing import List, Dict, Tuple, Optional
from bson import ObjectId
from fastapi.concurrency import run_in_threadpool
import logging
import io
import json
import time
from PIL import Image
import boto3
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from config import settings
from database import get_database
from services.s3_service import upload_to_s3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

# Cache for detected model
_vision_model_cache: Optional[str] = None


def _list_available_models() -> List[str]:
    """List all available vision models from Gemini API"""
    available = []
    try:
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                name = model.name.replace('models/', '')
                available.append(name)
        return available
    except Exception as e:
        logger.error(f"❌ Could not list models: {e}")
        return []


def _get_vision_model() -> genai.GenerativeModel:
    """Get the correct Gemini vision model with quota-aware selection"""
    global _vision_model_cache
    
    if not _vision_model_cache:
        logger.info("🔍 Auto-detecting Gemini model...")
        
        # Get actually available models from API
        available_models = _list_available_models()
        
        if not available_models:
            raise Exception(
                "No Gemini models available. Please check your API key and permissions. "
                "Visit https://aistudio.google.com/app/apikey to verify your API key."
            )
        
        logger.info(f"📋 Found {len(available_models)} available models")
        
        # Preferred models in order (prioritizing models with better free-tier quotas)
        preferred_models = [
            # Free tier models with good quotas (prioritize these)
            'gemini-2.0-flash-exp',      # Latest Flash with good quotas
            'gemini-1.5-flash',           # Stable Flash model
            'gemini-1.5-flash-8b',        # Lightweight Flash
            'gemini-1.5-flash-002',       # Flash variant
            'gemini-1.5-flash-latest',    # Latest Flash
            
            # Pro models (might have stricter limits on free tier)
            'gemini-2.5-pro',             # New recommended model
            'gemini-1.5-pro',             # Stable Pro
            'gemini-1.5-pro-002',         # Pro variant
            'gemini-1.5-pro-latest',      # Latest Pro
            
            # Experimental models (use with caution)
            'gemini-exp-1206',            # Experimental
            'gemini-2.0-pro-exp',         # Pro experimental
            
            # Legacy
            'gemini-pro-vision',          # Legacy fallback
        ]
        
        # Find first preferred model that's available
        for preferred in preferred_models:
            if preferred in available_models:
                _vision_model_cache = preferred
                logger.info(f"✅ Selected model: {preferred}")
                return genai.GenerativeModel(_vision_model_cache)
        
        # If no preferred model found, use the first available one
        _vision_model_cache = available_models[0]
        logger.warning(f"⚠️ Using first available model: {_vision_model_cache}")
        logger.info(f"💡 Available models were: {', '.join(available_models[:5])}...")
    
    return genai.GenerativeModel(_vision_model_cache)


async def detect_tables_from_floor_plan_url(
    floor_plan_url: str,
    analysis_id: str,
    room_dimensions: Dict
):
    """
    Table detection using Gemini Vision API with retry logic
    """
    db = get_database()
    
    try:
        logger.info(f"🔍 Starting floor plan analysis for {analysis_id}")
        
        # Download image from S3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        parsed_url = urlparse(floor_plan_url)
        s3_key = unquote(parsed_url.path.lstrip('/'))
        
        logger.info(f"📂 S3 Key: {s3_key}")
        
        response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        image_content = response['Body'].read()
        
        logger.info(f"✅ Downloaded {len(image_content)} bytes")
        
        # Run detection with Gemini (with retry logic)
        detected_tables, annotated_image, detection_metadata = await run_in_threadpool(
            _detect_with_gemini_vision_with_retry,
            image_content,
            room_dimensions
        )
        
        logger.info(f"✅ Detected {len(detected_tables)} tables")
        
        # Encode and upload annotated image
        success, img_encoded = cv2.imencode('.jpg', annotated_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not success:
            raise Exception("Failed to encode annotated image")
        
        annotated_url = await upload_to_s3(
            img_encoded.tobytes(),
            f"floor_plans/annotated_{analysis_id}.jpg"
        )
        
        # Update database
        await db.floor_plan_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {
                "$set": {
                    "analysisStatus": "completed",
                    "detectedTables": detected_tables,
                    "annotatedFloorPlanUrl": annotated_url,
                    "tableCount": len(detected_tables),
                    "detectionMetadata": detection_metadata
                }
            }
        )
        
        logger.info(f"✅ Analysis completed for {analysis_id}")
        
    except Exception as e:
        logger.error(f"❌ Analysis error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        await db.floor_plan_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {"$set": {"analysisStatus": "failed", "error": str(e)}}
        )


def _detect_with_gemini_vision_with_retry(
    image_content: bytes,
    room_dimensions: Dict,
    max_retries: int = 3
) -> Tuple[List[Dict], np.ndarray, Dict]:
    """
    Wrapper with retry logic for rate limit errors
    """
    global _vision_model_cache
    
    for attempt in range(max_retries):
        try:
            return _detect_with_gemini_vision(image_content, room_dimensions)
            
        except google_exceptions.ResourceExhausted as e:
            logger.warning(f"⚠️ Rate limit hit on attempt {attempt + 1}/{max_retries}")
            
            # If we have retries left, try a different model
            if attempt < max_retries - 1:
                # Clear cache to force model reselection
                old_model = _vision_model_cache
                _vision_model_cache = None
                
                # Get list of available models
                available = _list_available_models()
                
                # Try to find a different model (preferring Flash models)
                flash_models = [m for m in available if 'flash' in m.lower() and m != old_model]
                other_models = [m for m in available if m != old_model and m not in flash_models]
                
                if flash_models:
                    _vision_model_cache = flash_models[0]
                    logger.info(f"🔄 Retrying with different model: {_vision_model_cache}")
                    time.sleep(2)  # Brief delay before retry
                    continue
                elif other_models:
                    _vision_model_cache = other_models[0]
                    logger.info(f"🔄 Retrying with different model: {_vision_model_cache}")
                    time.sleep(2)
                    continue
                else:
                    logger.error("❌ No alternative models available")
                    raise
            else:
                logger.error("❌ Max retries exceeded")
                raise
                
        except Exception as e:
            # For other errors, don't retry
            raise
    
    # Should not reach here
    raise Exception("Unexpected retry loop exit")


def _detect_with_gemini_vision(
    image_content: bytes,
    room_dimensions: Dict
) -> Tuple[List[Dict], np.ndarray, Dict]:
    """
    Use Gemini Vision to detect tables
    
    FIXED: Proper coordinate system mapping
    - Image width (pixels) → Room horizontal dimension
    - Image height (pixels) → Room vertical dimension
    """
    # Load image
    img = _load_image(image_content)
    img_height, img_width = img.shape[:2]
    
    # CRITICAL FIX: Determine which room dimension maps to which image axis
    # Standard convention: 
    # - "length" typically refers to the longer dimension
    # - "width" typically refers to the shorter dimension
    # - Floor plans usually show width horizontally
    
    # Check if room dimensions specify which is horizontal/vertical
    # If 'length' > 'width', assume width is horizontal (common in floor plans)
    room_length = room_dimensions['length']
    room_width = room_dimensions['width']
    
    # FIXED MAPPING:
    # For this floor plan: width=20m (horizontal), length=15m (vertical)
    # Image: 1004px wide × 528px tall
    # So: width → img_width, length → img_height
    
    # Use the room dimension labels correctly
    horizontal_meters = room_width    # 20m maps to image width
    vertical_meters = room_length     # 15m maps to image height
    
    # Calculate pixel-to-meter scale
    scale_x = horizontal_meters / img_width   # meters per pixel (horizontal)
    scale_y = vertical_meters / img_height    # meters per pixel (vertical)
    
    logger.info(f"📐 Image: {img_width}x{img_height} pixels")
    logger.info(f"📏 Room: {horizontal_meters}m (H) × {vertical_meters}m (V)")
    logger.info(f"🔢 Scale: {scale_x:.4f}m/px (X), {scale_y:.4f}m/px (Y)")
    
    try:
        # Get Gemini model (with auto-detection)
        model = _get_vision_model()
        
        # Load PIL image for Gemini
        pil_image = Image.open(io.BytesIO(image_content))
        
        # IMPROVED PROMPT - very specific instructions
        prompt = f"""You are analyzing a restaurant floor plan image to detect dining tables.

**Room Dimensions:** {horizontal_meters}m (width/horizontal) × {vertical_meters}m (length/vertical)
**Image Size:** {img_width} × {img_height} pixels

**YOUR TASK:** Identify EVERY dining table in this floor plan.

**What is a TABLE:**
- A table is where customers sit to eat
- Tables can be: circular (round), rectangular (square/oblong), or irregular shapes
- Tables usually have chairs around them (but chairs might not always be visible)
- Look for table shapes in the dining area, NOT in kitchen/storage areas

**SCANNING PROCEDURE:**
1. Divide the image into 5 vertical sections: Far Left, Left, Center, Right, Far Right
2. In EACH section, scan from top to bottom
3. Mark every table-like shape you see
4. DO NOT miss tables on the edges of the image!

**IMPORTANT RULES:**
✅ Count all tables, even small ones
✅ Count tables near walls/edges
✅ If you see a group of chairs, there's likely a table there
❌ Do NOT count kitchen counters, bars (unless they have seating)
❌ Do NOT count the same table twice
❌ Do NOT invent tables that don't exist

**OUTPUT FORMAT:**
Return a JSON array with each table. For each table provide:
- table_number: sequential number (1, 2, 3...)
- type: "rectangular" or "circular" or "irregular"
- center_x_percent: X position of table center as % of image width (0.0 to 1.0)
- center_y_percent: Y position of table center as % of image height (0.0 to 1.0)
- width_percent: table width as % of image width (horizontal size)
- height_percent: table height as % of image height (vertical size)
- estimated_seats: estimated number of seats (2, 4, 6, 8, etc.)

**Example:**
[
  {{
    "table_number": 1,
    "type": "rectangular",
    "center_x_percent": 0.25,
    "center_y_percent": 0.30,
    "width_percent": 0.08,
    "height_percent": 0.06,
    "estimated_seats": 4
  }},
  {{
    "table_number": 2,
    "type": "circular",
    "center_x_percent": 0.65,
    "center_y_percent": 0.45,
    "width_percent": 0.07,
    "height_percent": 0.07,
    "estimated_seats": 4
  }}
]

Return ONLY the JSON array, nothing else. Be thorough and don't miss any tables!"""

        logger.info(f"🤖 Calling Gemini Vision API (model: {_vision_model_cache})...")
        
        # Generate content with Gemini
        response = model.generate_content([prompt, pil_image])
        content = response.text.strip()
        
        logger.info(f"📥 Gemini Response received ({len(content)} chars)")
        logger.debug(f"Response preview: {content[:200]}...")
        
        # Parse JSON
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        tables_data = json.loads(content)
        
        logger.info(f"✅ Gemini detected {len(tables_data)} tables")
        
        # Convert to standard format
        detected_tables = []
        
        for table in tables_data:
            # Calculate pixel coordinates from percentages
            center_x_px = table['center_x_percent'] * img_width
            center_y_px = table['center_y_percent'] * img_height
            width_px = table.get('width_percent', 0.05) * img_width
            height_px = table.get('height_percent', 0.05) * img_height
            
            # Top-left corner coordinates
            x = int(center_x_px - width_px / 2)
            y = int(center_y_px - height_px / 2)
            w = int(width_px)
            h = int(height_px)
            
            # Ensure values are within bounds
            x = max(0, min(x, img_width - 1))
            y = max(0, min(y, img_height - 1))
            w = max(20, min(w, img_width - x))
            h = max(20, min(h, img_height - y))
            
            # FIXED: Calculate real-world coordinates using correct scale
            real_x = x * scale_x
            real_y = y * scale_y
            real_width = w * scale_x
            real_height = h * scale_y
            
            detected_tables.append({
                "tableId": f"table_{table['table_number']}",
                "detectionMethod": "gemini_vision",
                "tableType": table.get('type', 'rectangular'),
                "chairCount": table.get('estimated_seats', 0),
                "pixelCoordinates": {
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h
                },
                "realWorldCoordinates": {
                    "x": round(real_x, 2),
                    "y": round(real_y, 2),
                    "width": round(real_width, 2),
                    "height": round(real_height, 2),
                    "unit": room_dimensions['unit']
                },
                "confidence": 0.90
            })
        
        # Draw annotations
        annotated = _draw_annotations(img.copy(), detected_tables)
        
        # Metadata
        metadata = {
            "detection_method": "gemini_vision",
            "model_used": _vision_model_cache or "gemini-unknown",
            "table_count": len(detected_tables),
            "table_types": list(set([t['tableType'] for t in detected_tables])),
            "total_estimated_seats": sum([t['chairCount'] for t in detected_tables]),
            "scale_factor": {
                "x": round(scale_x, 4),
                "y": round(scale_y, 4),
                "unit": f"{room_dimensions['unit']}/pixel"
            },
            "room_mapping": {
                "horizontal_meters": horizontal_meters,
                "vertical_meters": vertical_meters,
                "image_width_px": img_width,
                "image_height_px": img_height
            }
        }
        
        return detected_tables, annotated, metadata
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        if 'content' in locals():
            logger.error(f"Response was: {content}")
        # Return empty on error
        return [], img, {"error": str(e)}
        
    except google_exceptions.ResourceExhausted:
        # Re-raise quota errors so retry logic can handle them
        raise
        
    except Exception as e:
        logger.error(f"❌ Gemini Vision error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return [], img, {"error": str(e)}


def _load_image(image_content: bytes) -> np.ndarray:
    """Load image from bytes"""
    try:
        import pillow_avif
    except ImportError:
        pass
    
    img_pil = Image.open(io.BytesIO(image_content))
    
    if img_pil.mode != 'RGB':
        img_pil = img_pil.convert('RGB')
    
    img_array = np.array(img_pil)
    return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)


def _draw_annotations(img: np.ndarray, tables: List[Dict]) -> np.ndarray:
    """Draw clean annotations on the image"""
    
    colors = {
        'circular': (255, 0, 255),      # Magenta
        'rectangular': (0, 165, 255),   # Orange
        'irregular': (0, 255, 255)      # Yellow
    }
    
    for table in tables:
        px = table['pixelCoordinates']
        x, y, w, h = px['x'], px['y'], px['width'], px['height']
        
        table_type = table.get('tableType', 'rectangular')
        color = colors.get(table_type, (0, 255, 0))
        
        # Draw shape
        if table_type == 'circular':
            center = (x + w // 2, y + h // 2)
            radius = max(w, h) // 2
            cv2.circle(img, center, radius, color, 2)
        else:
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        
        # Label with real-world dimensions
        seats = table.get('chairCount', 0)
        real_coords = table.get('realWorldCoordinates', {})
        real_w = real_coords.get('width', 0)
        real_h = real_coords.get('height', 0)
        
        label = f"{table['tableId']}"
        if seats > 0:
            label += f" ({seats})"
        if real_w > 0 and real_h > 0:
            label += f" {real_w:.1f}x{real_h:.1f}m"
        
        # Draw label with background
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.4
        thickness = 1
        (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
        
        cv2.rectangle(img, (x, y - text_h - 6), (x + text_w + 4, y - 2), color, -1)
        cv2.putText(img, label, (x + 2, y - 4), font, font_scale, (255, 255, 255), thickness)
        
        # Center dot
        cv2.circle(img, (x + w // 2, y + h // 2), 3, (0, 0, 255), -1)
    
    # Summary box
    summary_h = 100
    cv2.rectangle(img, (5, 5), (250, summary_h), (0, 0, 0), -1)
    cv2.rectangle(img, (5, 5), (250, summary_h), (255, 255, 255), 2)
    
    y_pos = 25
    cv2.putText(img, f"Tables: {len(tables)}", (15, y_pos),
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Type breakdown
    type_counts = {}
    total_seats = 0
    for t in tables:
        type_counts[t['tableType']] = type_counts.get(t['tableType'], 0) + 1
        total_seats += t.get('chairCount', 0)
    
    y_pos += 25
    for t_type, count in type_counts.items():
        color = colors.get(t_type, (128, 128, 128))
        cv2.putText(img, f"{t_type}: {count}", (15, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        y_pos += 20
    
    cv2.putText(img, f"Seats: {total_seats}", (15, y_pos),
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    return img





# #####################time error dekhay######


# # """
# # Simple Table Detection Service - GEMINI VERSION (COORDINATE FIX)
# # ================================================
# # STRICT visual dimensions + only circle/rectangle tables
# # """

# # import cv2
# # from urllib.parse import urlparse, unquote
# # import numpy as np
# # from typing import List, Dict, Tuple, Optional
# # from bson import ObjectId
# # from fastapi.concurrency import run_in_threadpool
# # import logging
# # import io
# # import json
# # import time
# # from PIL import Image
# # import boto3
# # import google.generativeai as genai
# # from google.api_core import exceptions as google_exceptions
# # from config import settings
# # from database import get_database
# # from services.s3_service import upload_to_s3

# # # --------------------------------------------------
# # # Logging
# # # --------------------------------------------------
# # logging.basicConfig(level=logging.INFO)
# # logger = logging.getLogger(__name__)

# # # --------------------------------------------------
# # # Gemini Init
# # # --------------------------------------------------
# # genai.configure(api_key=settings.GEMINI_API_KEY)
# # _vision_model_cache: Optional[str] = None


# # def _list_available_models() -> List[str]:
# #     try:
# #         return [
# #             m.name.replace("models/", "")
# #             for m in genai.list_models()
# #             if "generateContent" in m.supported_generation_methods
# #         ]
# #     except Exception as e:
# #         logger.error(f"❌ Model list failed: {e}")
# #         return []


# # def _get_vision_model() -> genai.GenerativeModel:
# #     global _vision_model_cache

# #     if not _vision_model_cache:
# #         available = _list_available_models()
# #         if not available:
# #             raise Exception("No Gemini models available")

# #         preferred = [
# #             "gemini-2.0-flash-exp",
# #             "gemini-1.5-flash",
# #             "gemini-1.5-flash-8b",
# #             "gemini-1.5-pro",
# #             "gemini-pro-vision",
# #         ]

# #         for p in preferred:
# #             if p in available:
# #                 _vision_model_cache = p
# #                 break
# #         else:
# #             _vision_model_cache = available[0]

# #         logger.info(f"✅ Gemini model selected: {_vision_model_cache}")

# #     return genai.GenerativeModel(_vision_model_cache)


# # # --------------------------------------------------
# # # Public API
# # # --------------------------------------------------
# # async def detect_tables_from_floor_plan_url(
# #     floor_plan_url: str,
# #     analysis_id: str,
# #     room_dimensions: Dict
# # ):
# #     db = get_database()

# #     try:
# #         logger.info(f"🔍 Starting analysis {analysis_id}")

# #         s3 = boto3.client(
# #             "s3",
# #             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
# #             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
# #             region_name=settings.AWS_REGION,
# #         )

# #         parsed = urlparse(floor_plan_url)
# #         s3_key = unquote(parsed.path.lstrip("/"))

# #         img_bytes = s3.get_object(
# #             Bucket=settings.S3_BUCKET_NAME,
# #             Key=s3_key
# #         )["Body"].read()

# #         tables, annotated, meta = await run_in_threadpool(
# #             _detect_with_gemini_vision_with_retry,
# #             img_bytes,
# #             room_dimensions
# #         )

# #         ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
# #         if not ok:
# #             raise Exception("Image encoding failed")

# #         annotated_url = await upload_to_s3(
# #             encoded.tobytes(),
# #             f"floor_plans/annotated_{analysis_id}.jpg"
# #         )

# #         await db.floor_plan_analysis.update_one(
# #             {"_id": ObjectId(analysis_id)},
# #             {"$set": {
# #                 "analysisStatus": "completed",
# #                 "detectedTables": tables,
# #                 "annotatedFloorPlanUrl": annotated_url,
# #                 "tableCount": len(tables),
# #                 "detectionMetadata": meta
# #             }}
# #         )

# #     except Exception as e:
# #         logger.error(e)
# #         await db.floor_plan_analysis.update_one(
# #             {"_id": ObjectId(analysis_id)},
# #             {"$set": {"analysisStatus": "failed", "error": str(e)}}
# #         )


# # # --------------------------------------------------
# # # Retry Wrapper
# # # --------------------------------------------------
# # def _detect_with_gemini_vision_with_retry(
# #     image_content: bytes,
# #     room_dimensions: Dict,
# #     max_retries: int = 3
# # ):
# #     global _vision_model_cache

# #     for i in range(max_retries):
# #         try:
# #             return _detect_with_gemini_vision(image_content, room_dimensions)
# #         except google_exceptions.ResourceExhausted:
# #             _vision_model_cache = None
# #             time.sleep(2)
# #     raise Exception("Gemini quota exceeded")


# # # --------------------------------------------------
# # # Core Detection
# # # --------------------------------------------------
# # def _detect_with_gemini_vision(
# #     image_content: bytes,
# #     room_dimensions: Dict
# # ):
# #     img = _load_image(image_content)
# #     h, w = img.shape[:2]

# #     horizontal_m = room_dimensions["width"]
# #     vertical_m = room_dimensions["length"]

# #     scale_x = horizontal_m / w
# #     scale_y = vertical_m / h

# #     model = _get_vision_model()
# #     pil_img = Image.open(io.BytesIO(image_content))

# #     prompt = f"""
# # You are analyzing a restaurant floor plan.

# # Room size: {horizontal_m}m (horizontal) × {vertical_m}m (vertical)
# # Image size: {w}px × {h}px

# # TASK:
# # Detect ALL dining tables.

# # RULES:
# # - Tables are ONLY rectangular or circular
# # - Use ONLY what is visible in the image
# # - Do NOT guess size
# # - Do NOT invent tables

# # OUTPUT JSON ARRAY ONLY:
# # [
# #   {{
# #     "table_number": 1,
# #     "type": "rectangular" OR "circular",
# #     "center_x_percent": 0.5,
# #     "center_y_percent": 0.5,
# #     "width_percent": 0.1,
# #     "height_percent": 0.08,
# #     "estimated_seats": 4
# #   }}
# # ]
# # """

# #     response = model.generate_content([prompt, pil_img])
# #     text = response.text.strip()

# #     if text.startswith("```"):
# #         text = text.split("```")[1].strip()

# #     data = json.loads(text)
# #     detected = []

# #     for t in data:
# #         if "width_percent" not in t or "height_percent" not in t:
# #             continue

# #         raw = t.get("type", "rectangular").lower()
# #         table_type = "circular" if raw in ["circle", "circular", "round"] else "rectangular"

# #         cx = t["center_x_percent"] * w
# #         cy = t["center_y_percent"] * h
# #         tw = t["width_percent"] * w
# #         th = t["height_percent"] * h

# #         x = int(cx - tw / 2)
# #         y = int(cy - th / 2)

# #         tw = max(20, int(tw))
# #         th = max(20, int(th))

# #         detected.append({
# #             "tableId": f"table_{t['table_number']}",
# #             "detectionMethod": "gemini_vision",
# #             "tableType": table_type,
# #             "chairCount": t.get("estimated_seats", 0),
# #             "pixelCoordinates": {
# #                 "x": x, "y": y, "width": tw, "height": th
# #             },
# #             "realWorldCoordinates": {
# #                 "x": round(x * scale_x, 2),
# #                 "y": round(y * scale_y, 2),
# #                 "width": round(tw * scale_x, 2),
# #                 "height": round(th * scale_y, 2),
# #                 "unit": room_dimensions["unit"]
# #             },
# #             "confidence": 0.9
# #         })

# #     annotated = _draw_annotations(img.copy(), detected)

# #     return detected, annotated, {
# #         "model": _vision_model_cache,
# #         "table_count": len(detected)
# #     }


# # # --------------------------------------------------
# # # Utils
# # # --------------------------------------------------
# # def _load_image(image_content: bytes) -> np.ndarray:
# #     img = Image.open(io.BytesIO(image_content)).convert("RGB")
# #     return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# # def _draw_annotations(img: np.ndarray, tables: List[Dict]) -> np.ndarray:
# #     for t in tables:
# #         p = t["pixelCoordinates"]
# #         x, y, w, h = p.values()

# #         if t["tableType"] == "circular":
# #             r = int(min(w, h) / 2)
# #             cv2.circle(img, (x + w // 2, y + h // 2), r, (255, 0, 255), 2)
# #         else:
# #             cv2.rectangle(img, (x, y), (x + w, y + h), (0, 165, 255), 2)

# #         cv2.circle(img, (x + w // 2, y + h // 2), 3, (0, 0, 255), -1)

# #     return img



# """
# Simple Table Detection Service - GEMINI VERSION (COORDINATE FIX + TIMEOUT FIX)
# ================================================
# STRICT visual dimensions + only circle/rectangle tables
# """

# import cv2
# from urllib.parse import urlparse, unquote
# import numpy as np
# from typing import List, Dict, Tuple, Optional
# from bson import ObjectId
# from fastapi.concurrency import run_in_threadpool
# import logging
# import io
# import json
# import time
# from PIL import Image
# import boto3
# import google.generativeai as genai
# from google.api_core import exceptions as google_exceptions
# from config import settings
# from database import get_database
# from services.s3_service import upload_to_s3
# import signal
# from contextlib import contextmanager

# # --------------------------------------------------
# # Logging
# # --------------------------------------------------
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # --------------------------------------------------
# # Configuration
# # --------------------------------------------------
# MAX_IMAGE_DIMENSION = 1024  # Reduce image size to speed up processing
# GEMINI_TIMEOUT_SECONDS = 60  # Explicit timeout for Gemini calls
# MAX_RETRIES = 3
# RETRY_DELAY_SECONDS = 2


# # --------------------------------------------------
# # Timeout Handler
# # --------------------------------------------------
# class TimeoutError(Exception):
#     pass


# @contextmanager
# def time_limit(seconds):
#     """
#     Context manager for timing out operations.
#     Works on Unix systems with signal-based timeout.
#     For Windows, falls back to basic timing check.
#     """
#     def signal_handler(signum, frame):
#         raise TimeoutError(f"Operation timed out after {seconds} seconds")
    
#     # Try signal-based timeout (Unix/Linux/Mac)
#     try:
#         old_handler = signal.signal(signal.SIGALRM, signal_handler)
#         signal.alarm(seconds)
#         try:
#             yield
#         finally:
#             signal.alarm(0)
#             signal.signal(signal.SIGALRM, old_handler)
#     except (AttributeError, ValueError):
#         # Windows doesn't support SIGALRM, use simple yield
#         # Timeout will be enforced by retry logic instead
#         yield

# # --------------------------------------------------
# # Gemini Init
# # --------------------------------------------------
# genai.configure(api_key=settings.GEMINI_API_KEY)
# _vision_model_cache: Optional[str] = None


# def _list_available_models() -> List[str]:
#     try:
#         return [
#             m.name.replace("models/", "")
#             for m in genai.list_models()
#             if "generateContent" in m.supported_generation_methods
#         ]
#     except Exception as e:
#         logger.error(f"❌ Model list failed: {e}")
#         return []


# def _get_vision_model() -> genai.GenerativeModel:
#     global _vision_model_cache

#     if not _vision_model_cache:
#         available = _list_available_models()
#         if not available:
#             raise Exception("No Gemini models available")

#         # Prefer faster models first
#         preferred = [
#             "gemini-2.0-flash-exp",
#             "gemini-1.5-flash-8b",  # Moved up - faster
#             "gemini-1.5-flash",
#             "gemini-1.5-pro",
#             "gemini-pro-vision",
#         ]

#         for p in preferred:
#             if p in available:
#                 _vision_model_cache = p
#                 break
#         else:
#             _vision_model_cache = available[0]

#         logger.info(f"✅ Gemini model selected: {_vision_model_cache}")

#     return genai.GenerativeModel(_vision_model_cache)


# # --------------------------------------------------
# # Public API
# # --------------------------------------------------
# async def detect_tables_from_floor_plan_url(
#     floor_plan_url: str,
#     analysis_id: str,
#     room_dimensions: Dict
# ):
#     db = get_database()

#     try:
#         logger.info(f"🔍 Starting analysis {analysis_id}")
#         start_time = time.time()

#         s3 = boto3.client(
#             "s3",
#             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
#             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
#             region_name=settings.AWS_REGION,
#         )

#         parsed = urlparse(floor_plan_url)
#         s3_key = unquote(parsed.path.lstrip("/"))

#         logger.info(f"📥 Downloading image from S3: {s3_key}")
#         img_bytes = s3.get_object(
#             Bucket=settings.S3_BUCKET_NAME,
#             Key=s3_key
#         )["Body"].read()
        
#         logger.info(f"✅ Image downloaded ({len(img_bytes)} bytes)")

#         # Run detection with explicit timeout handling
#         tables, annotated, meta = await run_in_threadpool(
#             _detect_with_gemini_vision_with_retry,
#             img_bytes,
#             room_dimensions
#         )

#         logger.info(f"✅ Detection completed: {len(tables)} tables found")

#         ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 95])
#         if not ok:
#             raise Exception("Image encoding failed")

#         logger.info(f"📤 Uploading annotated image")
#         annotated_url = await upload_to_s3(
#             encoded.tobytes(),
#             f"floor_plans/annotated_{analysis_id}.jpg"
#         )

#         elapsed = time.time() - start_time
#         logger.info(f"✅ Analysis completed in {elapsed:.2f}s")

#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {"$set": {
#                 "analysisStatus": "completed",
#                 "detectedTables": tables,
#                 "annotatedFloorPlanUrl": annotated_url,
#                 "tableCount": len(tables),
#                 "detectionMetadata": {
#                     **meta,
#                     "processingTimeSeconds": round(elapsed, 2)
#                 }
#             }}
#         )

#     except Exception as e:
#         error_msg = str(e)
#         logger.error(f"❌ Analysis failed: {error_msg}")
        
#         # Provide more helpful error messages
#         if "timed out" in error_msg.lower() or "504" in error_msg:
#             error_msg = "The request timed out. Please try again with a smaller image or simpler floor plan."
#         elif "quota" in error_msg.lower() or "ResourceExhausted" in error_msg:
#             error_msg = "API quota exceeded. Please try again in a few moments."
        
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {"$set": {
#                 "analysisStatus": "failed",
#                 "error": error_msg
#             }}
#         )


# # --------------------------------------------------
# # Image Preprocessing
# # --------------------------------------------------
# def _resize_image_if_needed(image_bytes: bytes, max_dimension: int = MAX_IMAGE_DIMENSION) -> Tuple[bytes, float]:
#     """
#     Resize image to reduce processing time while maintaining aspect ratio.
#     Returns resized image bytes and scale factor.
#     """
#     img = Image.open(io.BytesIO(image_bytes))
#     original_size = img.size
    
#     # Convert RGBA/P to RGB (handle transparency)
#     if img.mode in ('RGBA', 'LA', 'P'):
#         logger.info(f"🎨 Converting {img.mode} to RGB")
#         # Create white background
#         background = Image.new('RGB', img.size, (255, 255, 255))
#         if img.mode == 'P':
#             img = img.convert('RGBA')
#         background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
#         img = background
#     elif img.mode != 'RGB':
#         logger.info(f"🎨 Converting {img.mode} to RGB")
#         img = img.convert('RGB')
    
#     # Check if resize needed
#     max_current = max(img.size)
#     if max_current <= max_dimension:
#         # Still need to save as JPEG even if no resize
#         buffer = io.BytesIO()
#         img.save(buffer, format="JPEG", quality=85)
#         return buffer.getvalue(), 1.0
    
#     # Calculate new size maintaining aspect ratio
#     scale = max_dimension / max_current
#     new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
    
#     logger.info(f"📐 Resizing image from {original_size} to {new_size} (scale: {scale:.2f})")
    
#     # Resize with high quality
#     img = img.resize(new_size, Image.Resampling.LANCZOS)
    
#     # Convert back to bytes
#     buffer = io.BytesIO()
#     img.save(buffer, format="JPEG", quality=85)
#     return buffer.getvalue(), scale


# # --------------------------------------------------
# # Retry Wrapper
# # --------------------------------------------------
# def _detect_with_gemini_vision_with_retry(
#     image_content: bytes,
#     room_dimensions: Dict,
#     max_retries: int = MAX_RETRIES
# ):
#     global _vision_model_cache

#     # Resize image before processing
#     resized_image, resize_scale = _resize_image_if_needed(image_content)
    
#     last_error = None
#     for attempt in range(max_retries):
#         try:
#             logger.info(f"🔄 Detection attempt {attempt + 1}/{max_retries}")
#             result = _detect_with_gemini_vision(resized_image, room_dimensions, resize_scale)
#             logger.info(f"✅ Detection successful on attempt {attempt + 1}")
#             return result
            
#         except google_exceptions.ResourceExhausted as e:
#             last_error = e
#             logger.warning(f"⚠️ Quota exhausted on attempt {attempt + 1}, switching model")
#             _vision_model_cache = None  # Force model switch
#             if attempt < max_retries - 1:
#                 time.sleep(RETRY_DELAY_SECONDS)
                
#         except google_exceptions.DeadlineExceeded as e:
#             last_error = e
#             logger.warning(f"⏱️ Request timed out on attempt {attempt + 1}")
#             if attempt < max_retries - 1:
#                 time.sleep(RETRY_DELAY_SECONDS)
                
#         except google_exceptions.GoogleAPIError as e:
#             last_error = e
#             logger.warning(f"⚠️ API error on attempt {attempt + 1}: {e}")
#             if attempt < max_retries - 1:
#                 time.sleep(RETRY_DELAY_SECONDS)
                
#         except Exception as e:
#             last_error = e
#             logger.error(f"❌ Unexpected error on attempt {attempt + 1}: {e}")
#             if attempt < max_retries - 1:
#                 time.sleep(RETRY_DELAY_SECONDS)
    
#     # All retries failed
#     raise Exception(f"Detection failed after {max_retries} attempts. Last error: {last_error}")


# # --------------------------------------------------
# # Core Detection
# # --------------------------------------------------
# def _detect_with_gemini_vision(
#     image_content: bytes,
#     room_dimensions: Dict,
#     resize_scale: float = 1.0
# ):
#     img = _load_image(image_content)
#     h, w = img.shape[:2]

#     horizontal_m = room_dimensions["width"]
#     vertical_m = room_dimensions["length"]

#     scale_x = horizontal_m / w
#     scale_y = vertical_m / h

#     model = _get_vision_model()
#     pil_img = Image.open(io.BytesIO(image_content))

#     # Simplified, more focused prompt
#     prompt = f"""Analyze this restaurant floor plan and detect all dining tables.

# Image: {w}px × {h}px
# Room: {horizontal_m}m × {vertical_m}m

# Rules:
# - Only detect visible tables (rectangular or circular)
# - Provide center position and size as percentages (0-1)
# - Estimate seat count

# Return JSON array:
# [{{"table_number": 1, "type": "rectangular", "center_x_percent": 0.5, "center_y_percent": 0.5, "width_percent": 0.1, "height_percent": 0.08, "estimated_seats": 4}}]"""

#     try:
#         logger.info("🤖 Sending request to Gemini...")
        
#         # Configure generation with timeout handling
#         generation_config = genai.types.GenerationConfig(
#             temperature=0.1,  # Lower temperature for more consistent results
#             max_output_tokens=2048,
#         )
        
#         # Use timeout wrapper
#         with time_limit(GEMINI_TIMEOUT_SECONDS):
#             response = model.generate_content(
#                 [prompt, pil_img],
#                 generation_config=generation_config
#             )
        
#         logger.info("✅ Received response from Gemini")
#         text = response.text.strip()

#     except TimeoutError as e:
#         logger.error(f"⏱️ Gemini API call timed out: {e}")
#         raise google_exceptions.DeadlineExceeded(str(e))
#     except Exception as e:
#         logger.error(f"❌ Gemini API call failed: {e}")
#         raise

#     # Parse response
#     if text.startswith("```"):
#         lines = text.split("\n")
#         text = "\n".join([l for l in lines if not l.strip().startswith("```")])
#         text = text.strip()

#     try:
#         data = json.loads(text)
#     except json.JSONDecodeError as e:
#         logger.error(f"❌ Failed to parse JSON response: {text}")
#         raise Exception(f"Invalid JSON response from Gemini: {e}")

#     detected = []

#     for t in data:
#         if "width_percent" not in t or "height_percent" not in t:
#             logger.warning(f"⚠️ Skipping table with missing dimensions: {t}")
#             continue

#         raw = t.get("type", "rectangular").lower()
#         table_type = "circular" if raw in ["circle", "circular", "round"] else "rectangular"

#         cx = t["center_x_percent"] * w
#         cy = t["center_y_percent"] * h
#         tw = t["width_percent"] * w
#         th = t["height_percent"] * h

#         x = int(cx - tw / 2)
#         y = int(cy - th / 2)

#         tw = max(20, int(tw))
#         th = max(20, int(th))

#         detected.append({
#             "tableId": f"table_{t['table_number']}",
#             "detectionMethod": "gemini_vision",
#             "tableType": table_type,
#             "chairCount": t.get("estimated_seats", 0),
#             "pixelCoordinates": {
#                 "x": x, "y": y, "width": tw, "height": th
#             },
#             "realWorldCoordinates": {
#                 "x": round(x * scale_x, 2),
#                 "y": round(y * scale_y, 2),
#                 "width": round(tw * scale_x, 2),
#                 "height": round(th * scale_y, 2),
#                 "unit": room_dimensions["unit"]
#             },
#             "confidence": 0.9
#         })

#     annotated = _draw_annotations(img.copy(), detected)

#     return detected, annotated, {
#         "model": _vision_model_cache,
#         "table_count": len(detected),
#         "image_resized": resize_scale < 1.0,
#         "resize_scale": round(resize_scale, 2) if resize_scale < 1.0 else None
#     }


# # --------------------------------------------------
# # Utils
# # --------------------------------------------------
# def _load_image(image_content: bytes) -> np.ndarray:
#     img = Image.open(io.BytesIO(image_content)).convert("RGB")
#     return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# def _draw_annotations(img: np.ndarray, tables: List[Dict]) -> np.ndarray:
#     for t in tables:
#         p = t["pixelCoordinates"]
#         x, y, w, h = p["x"], p["y"], p["width"], p["height"]

#         if t["tableType"] == "circular":
#             r = int(min(w, h) / 2)
#             cv2.circle(img, (x + w // 2, y + h // 2), r, (255, 0, 255), 2)
#         else:
#             cv2.rectangle(img, (x, y), (x + w, y + h), (0, 165, 255), 2)

#         # Draw center point
#         cv2.circle(img, (x + w // 2, y + h // 2), 3, (0, 0, 255), -1)
        
#         # Add table ID label
#         label = t["tableId"]
#         cv2.putText(img, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 
#                    0.4, (0, 255, 0), 1, cv2.LINE_AA)

#     return img
