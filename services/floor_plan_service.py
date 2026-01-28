# services/floor_plan_service.py

# import cv2
# from urllib.parse import urlparse, unquote
# import numpy as np
# from typing import List, Dict, Tuple
# from bson import ObjectId
# from fastapi.concurrency import run_in_threadpool
# import logging
# import io
# from PIL import Image
# import boto3
# from config import settings

# from database import get_database
# from services.s3_service import upload_to_s3

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Enable AVIF support
# try:
#     import pillow_avif
#     logger.info("✅ pillow-avif-plugin loaded successfully")
# except ImportError:
#     logger.error("❌ pillow-avif-plugin not installed! Run: pip install pillow-avif-plugin")

# # YOLO model (optional - will try to load, fallback to shape detection)
# model = None
# try:
#     from ultralytics import YOLO
#     model = YOLO('yolov8n.pt')
#     logger.info("✅ YOLO model loaded successfully")
# except Exception as e:
#     logger.warning(f"⚠️ YOLO not available, will use shape detection: {e}")


# async def detect_tables_from_floor_plan_url(
#     floor_plan_url: str,
#     analysis_id: str,
#     room_dimensions: Dict
# ):
#     """
#     Download floor plan from S3 and detect tables
#     """
#     db = get_database()
    
#     try:
#         logger.info(f"🔍 Starting floor plan analysis for {analysis_id}")
#         logger.info(f"📥 Downloading from S3: {floor_plan_url}")
        
#         # Download image from S3
#         s3_client = boto3.client(
#             's3',
#             aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
#             aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
#             region_name=settings.AWS_REGION
#         )
        
#         # Extract S3 key properly - remove query parameters
#         parsed_url = urlparse(floor_plan_url)
#         # Remove leading '/' from path
#         s3_key = parsed_url.path.lstrip('/')
#         # Decode URL encoding if any
#         s3_key = unquote(s3_key)
        
#         logger.info(f"📂 S3 Key: {s3_key}")
        
#         # Download image
#         response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
#         image_content = response['Body'].read()
        
#         logger.info(f"✅ Downloaded {len(image_content)} bytes from S3")
        
#         # Debug file info
#         file_type = _detect_file_type(image_content)
#         logger.info(f"🔍 Detected file type: {file_type}")
#         logger.info(f"🔍 S3 Content-Type: {response.get('ContentType', 'Not set')}")
        
#         # Run detection in threadpool
#         detected_tables, annotated_image = await run_in_threadpool(
#             _detect_tables_sync,
#             image_content,
#             room_dimensions
#         )
        
#         logger.info(f"✅ Detected {len(detected_tables)} tables")
        
#         # Encode annotated image
#         success, img_encoded = cv2.imencode('.jpg', annotated_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
#         if not success:
#             raise Exception("Failed to encode annotated image")
        
#         img_bytes = img_encoded.tobytes()
        
#         # Upload annotated floor plan to S3
#         annotated_url = await upload_to_s3(
#             img_bytes,
#             f"floor_plans/annotated_{analysis_id}.jpg"
#         )
        
#         logger.info(f"📤 Uploaded annotated image: {annotated_url}")
        
#         # Update database
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {
#                 "$set": {
#                     "analysisStatus": "completed",
#                     "detectedTables": detected_tables,
#                     "annotatedFloorPlanUrl": annotated_url,
#                     "tableCount": len(detected_tables)
#                 }
#             }
#         )
        
#         logger.info(f"✅ Floor plan analysis completed for {analysis_id}")
        
#     except Exception as e:
#         logger.error(f"❌ Floor plan analysis error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
        
#         # Update database with error
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {
#                 "$set": {
#                     "analysisStatus": "failed",
#                     "error": str(e)
#                 }
#             }
#         )


# def _detect_file_type(data: bytes) -> str:
#     """
#     Detect file type from magic bytes (file signature)
#     """
#     if len(data) < 12:
#         return "Unknown (file too small)"
    
#     # Check magic bytes
#     if data[:2] == b'\xff\xd8':
#         return "JPEG"
#     elif data[:8] == b'\x89PNG\r\n\x1a\n':
#         return "PNG"
#     elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
#         return "WEBP"
#     elif data[4:12] == b'ftypavif' or data[4:12] == b'ftypavis':
#         return "AVIF"
#     elif data[:2] == b'BM':
#         return "BMP"
#     elif data[:4] == b'GIF8':
#         return "GIF"
#     else:
#         return f"Unknown (magic: {data[:12].hex()})"


# def _detect_tables_sync(floor_plan_content: bytes, room_dimensions: Dict) -> Tuple[List[Dict], np.ndarray]:
#     """
#     Synchronous table detection - supports all image formats including AVIF
#     """
#     img = None
#     file_type = _detect_file_type(floor_plan_content)
    
#     try:
#         logger.info(f"🔄 Loading {file_type} image with PIL...")
        
#         # Open image with PIL (supports AVIF if pillow-avif-plugin is installed)
#         img_pil = Image.open(io.BytesIO(floor_plan_content))
        
#         logger.info(f"✅ PIL loaded image - Format: {img_pil.format}, Mode: {img_pil.mode}, Size: {img_pil.size}")
        
#         # Convert to RGB (handles all formats including AVIF, RGBA, LA, P)
#         if img_pil.mode in ('RGBA', 'LA'):
#             # Create white background for transparency
#             logger.info(f"🔄 Converting {img_pil.mode} to RGB with white background")
#             background = Image.new('RGB', img_pil.size, (255, 255, 255))
#             background.paste(img_pil, mask=img_pil.split()[-1])
#             img_pil = background
#         elif img_pil.mode == 'P':
#             # Palette mode - convert to RGBA first, then RGB
#             logger.info(f"🔄 Converting palette mode to RGB")
#             img_pil = img_pil.convert('RGBA')
#             background = Image.new('RGB', img_pil.size, (255, 255, 255))
#             background.paste(img_pil, mask=img_pil.split()[-1])
#             img_pil = background
#         elif img_pil.mode != 'RGB':
#             logger.info(f"🔄 Converting {img_pil.mode} to RGB")
#             img_pil = img_pil.convert('RGB')
        
#         # Convert PIL (RGB) to OpenCV (BGR)
#         img_array = np.array(img_pil)
#         img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
#         logger.info(f"✅ Successfully converted to OpenCV format")
        
#     except Exception as e:
#         logger.error(f"❌ PIL failed to load image: {e}")
        
#         # Fallback to OpenCV (won't work for AVIF but try anyway)
#         try:
#             logger.info("🔄 Attempting OpenCV fallback...")
#             nparr = np.frombuffer(floor_plan_content, np.uint8)
#             img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
#             if img is None:
#                 raise Exception("OpenCV decode returned None")
            
#             logger.info(f"✅ OpenCV loaded image successfully")
            
#         except Exception as cv_error:
#             logger.error(f"❌ OpenCV also failed: {cv_error}")
            
#             # Provide helpful error message
#             if file_type == "AVIF":
#                 error_msg = (
#                     f"Failed to decode AVIF image. "
#                     f"Please install pillow-avif-plugin: pip install pillow-avif-plugin"
#                 )
#             else:
#                 error_msg = (
#                     f"Failed to decode {file_type} image. "
#                     f"PIL error: {str(e)}, OpenCV error: {str(cv_error)}"
#                 )
            
#             raise Exception(error_msg)
    
#     if img is None:
#         raise Exception(f"Failed to load {file_type} image - result is None")
    
#     height, width = img.shape[:2]
#     logger.info(f"📐 Image dimensions: {width}x{height}")
    
#     # Try YOLO detection first
#     detected_tables = []
    
#     if model is not None:
#         try:
#             detected_tables = _detect_with_yolo(img, width, height, room_dimensions)
#             logger.info(f"🤖 YOLO detected {len(detected_tables)} tables")
#         except Exception as e:
#             logger.warning(f"⚠️ YOLO detection failed: {e}")
    
#     # If YOLO doesn't find tables, use shape detection
#     if len(detected_tables) == 0:
#         detected_tables = _detect_with_shapes(img, width, height, room_dimensions)
#         logger.info(f"🔶 Shape detection found {len(detected_tables)} tables")
    
#     # Draw annotations on image
#     annotated_img = _draw_annotations(img.copy(), detected_tables)
    
#     return detected_tables, annotated_img


# def _detect_with_yolo(img: np.ndarray, img_width: int, img_height: int, room_dimensions: Dict) -> List[Dict]:
#     """
#     Detect tables using YOLO model
#     """
#     detected_tables = []
    
#     try:
#         # Run YOLO detection
#         results = model(img, conf=0.3, verbose=False)
        
#         # Classes that might represent tables
#         table_classes = ['dining table', 'table', 'desk', 'couch', 'chair']
        
#         for result in results:
#             boxes = result.boxes
#             for box in boxes:
#                 class_id = int(box.cls[0])
#                 class_name = model.names[class_id]
                
#                 # Filter only table-like objects
#                 if any(tc in class_name.lower() for tc in table_classes):
#                     x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
#                     confidence = float(box.conf[0])
                    
#                     # Pixel coordinates
#                     x, y, w, h = int(x1), int(y1), int(x2-x1), int(y2-y1)
                    
#                     # Convert to real-world coordinates
#                     real_coords = _pixel_to_real_world(
#                         x, y, w, h,
#                         img_width, img_height,
#                         room_dimensions
#                     )
                    
#                     detected_tables.append({
#                         "tableId": f"table_{len(detected_tables) + 1}",
#                         "detectionMethod": "yolo",
#                         "detectedClass": class_name,
#                         "pixelCoordinates": {
#                             "x": x,
#                             "y": y,
#                             "width": w,
#                             "height": h
#                         },
#                         "realWorldCoordinates": real_coords,
#                         "confidence": round(confidence, 2)
#                     })
    
#     except Exception as e:
#         logger.warning(f"⚠️ YOLO detection failed: {e}")
    
#     return detected_tables


# def _detect_with_shapes(img: np.ndarray, img_width: int, img_height: int, room_dimensions: Dict) -> List[Dict]:
#     """
#     Detect tables using multi-method contour detection
#     Detects both indoor and outdoor tables (circular and rectangular)
#     """
#     detected_tables = []
    
#     try:
#         # Convert to grayscale
#         gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
#         # Method 1: Detect dark/gray table shapes (for filled tables)
#         logger.info("🔍 Method 1: Detecting filled shapes...")
#         _, binary1 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
#         contours1, _ = cv2.findContours(binary1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
#         # Method 2: Detect edges/outlines (for outlined tables)
#         logger.info("🔍 Method 2: Detecting edge-based shapes...")
#         edges = cv2.Canny(gray, 50, 150)
#         # Dilate to connect nearby edges
#         kernel = np.ones((3,3), np.uint8)
#         dilated = cv2.dilate(edges, kernel, iterations=2)
#         contours2, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
#         # Method 3: Adaptive threshold for varying lighting
#         logger.info("🔍 Method 3: Detecting with adaptive threshold...")
#         thresh = cv2.adaptiveThreshold(
#             gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
#         )
#         contours3, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
#         # Combine all contours
#         all_contours = contours1 + contours2 + contours3
#         logger.info(f"🔍 Total contours found: {len(all_contours)}")
        
#         # Calculate area thresholds - more lenient for small outdoor tables
#         min_area = (img_width * img_height) * 0.0005  # 0.05% (smaller threshold)
#         max_area = (img_width * img_height) * 0.15    # 15% (larger threshold)
        
#         logger.info(f"🔍 Filtering by area {min_area:.0f} - {max_area:.0f}")
        
#         detected_boxes = []  # To avoid duplicates
        
#         for contour in all_contours:
#             area = cv2.contourArea(contour)
            
#             # Filter by area
#             if area < min_area or area > max_area:
#                 continue
            
#             # Get bounding rectangle
#             x, y, w, h = cv2.boundingRect(contour)
            
#             # Calculate aspect ratio
#             aspect_ratio = w / h if h > 0 else 0
            
#             # Check circularity for round tables
#             perimeter = cv2.arcLength(contour, True)
#             if perimeter > 0:
#                 circularity = 4 * np.pi * area / (perimeter * perimeter)
#             else:
#                 circularity = 0
            
#             # Detect both rectangular and circular tables
#             is_table = False
#             table_type = "unknown"
            
#             # Circular tables (like outdoor seating)
#             if circularity > 0.6:  # Circle-like shape
#                 is_table = True
#                 table_type = "circular"
            
#             # Rectangular tables (dining area)
#             elif 0.2 < aspect_ratio < 5.0:  # Allow wider range
#                 is_table = True
#                 table_type = "rectangular"
            
#             if is_table:
#                 # Check for duplicates (same position)
#                 is_duplicate = False
#                 for existing_box in detected_boxes:
#                     ex, ey, ew, eh = existing_box
#                     # If centers are very close, it's a duplicate
#                     center_dist = np.sqrt((x + w/2 - ex - ew/2)**2 + (y + h/2 - ey - eh/2)**2)
#                     if center_dist < 20:  # pixels threshold
#                         is_duplicate = True
#                         break
                
#                 if not is_duplicate:
#                     detected_boxes.append((x, y, w, h))
                    
#                     # Convert to real-world coordinates
#                     real_coords = _pixel_to_real_world(
#                         x, y, w, h,
#                         img_width, img_height,
#                         room_dimensions
#                     )
                    
#                     # Higher confidence for circular tables
#                     confidence = 0.80 if table_type == "circular" else 0.70
                    
#                     detected_tables.append({
#                         "tableId": f"table_{len(detected_tables) + 1}",
#                         "detectionMethod": "shape",
#                         "tableType": table_type,
#                         "circularity": round(circularity, 2),
#                         "pixelCoordinates": {
#                             "x": x,
#                             "y": y,
#                             "width": w,
#                             "height": h
#                         },
#                         "realWorldCoordinates": real_coords,
#                         "confidence": confidence
#                     })
        
#         logger.info(f"✅ Detected {len(detected_tables)} unique tables")
#         logger.info(f"📊 Breakdown: {sum(1 for t in detected_tables if t.get('tableType') == 'circular')} circular, "
#                    f"{sum(1 for t in detected_tables if t.get('tableType') == 'rectangular')} rectangular")
    
#     except Exception as e:
#         logger.error(f"❌ Shape detection error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
    
#     return detected_tables


# def _pixel_to_real_world(x: int, y: int, w: int, h: int, 
#                           img_width: int, img_height: int, 
#                           room_dimensions: Dict) -> Dict:
#     """
#     Convert pixel coordinates to real-world measurements
#     """
#     # Room dimensions
#     room_length = room_dimensions['length']
#     room_width = room_dimensions['width']
#     unit = room_dimensions.get('unit', 'meters')
    
#     # Calculate scale factors
#     scale_x = room_length / img_width
#     scale_y = room_width / img_height
    
#     # Convert to real-world coordinates
#     real_x = x * scale_x
#     real_y = y * scale_y
#     real_width = w * scale_x
#     real_height = h * scale_y
    
#     # Calculate center point
#     center_x = real_x + (real_width / 2)
#     center_y = real_y + (real_height / 2)
    
#     return {
#         "x": round(real_x, 2),
#         "y": round(real_y, 2),
#         "width": round(real_width, 2),
#         "height": round(real_height, 2),
#         "unit": unit,
#         "centerPoint": {
#             "x": round(center_x, 2),
#             "y": round(center_y, 2)
#         },
#         "area": round(real_width * real_height, 2)
#     }


# def _draw_annotations(img: np.ndarray, detected_tables: List[Dict]) -> np.ndarray:
#     """
#     Draw bounding boxes and labels on the floor plan
#     """
#     circular_count = 0
#     rectangular_count = 0
    
#     for table in detected_tables:
#         pixel_coords = table['pixelCoordinates']
#         x = pixel_coords['x']
#         y = pixel_coords['y']
#         w = pixel_coords['width']
#         h = pixel_coords['height']
        
#         # Different colors based on detection method and table type
#         if table.get('detectionMethod') == 'yolo':
#             color = (0, 255, 0)  # Green for YOLO
#             label_prefix = "YOLO"
#         elif table.get('tableType') == 'circular':
#             color = (255, 0, 255)  # Magenta for circular tables (outdoor)
#             label_prefix = "Circular"
#             circular_count += 1
#         elif table.get('tableType') == 'rectangular':
#             color = (0, 165, 255)  # Orange for rectangular tables (indoor)
#             label_prefix = "Rect"
#             rectangular_count += 1
#         else:
#             color = (128, 128, 128)  # Gray for unknown
#             label_prefix = "Table"
        
#         # Draw rectangle or circle based on type
#         if table.get('tableType') == 'circular':
#             # Draw circle for circular tables
#             center_x = x + w // 2
#             center_y = y + h // 2
#             radius = max(w, h) // 2
#             cv2.circle(img, (center_x, center_y), radius, color, 3)
#         else:
#             # Draw rectangle for rectangular tables
#             cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
        
#         # Add label
#         label = f"{table['tableId']} ({table['confidence']:.0%})"
        
#         # Label background
#         (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
#         cv2.rectangle(img, (x, y - label_h - 10), (x + label_w + 10, y), color, -1)
        
#         # Label text
#         cv2.putText(
#             img, label, (x + 5, y - 5),
#             cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2
#         )
        
#         # Draw center point
#         real_coords = table['realWorldCoordinates']
#         center_x = x + w // 2
#         center_y = y + h // 2
#         cv2.circle(img, (center_x, center_y), 4, (0, 0, 255), -1)
    
#     # Add summary info with breakdown
#     y_offset = 30
#     summary = f"Total Tables: {len(detected_tables)}"
#     cv2.putText(img, summary, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    
#     if circular_count > 0:
#         y_offset += 30
#         cv2.putText(img, f"Circular: {circular_count}", (10, y_offset), 
#                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
    
#     if rectangular_count > 0:
#         y_offset += 30
#         cv2.putText(img, f"Rectangular: {rectangular_count}", (10, y_offset), 
#                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
    
#     return img











# # services/floor_plan_service.py
# """
# Smart Table Detection Service
# ==============================
# Detects tables by identifying chair clusters around central shapes
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
#     Smart table detection using chair clustering approach
#     """
#     db = get_database()
    
#     try:
#         logger.info(f"🔍 Starting SMART floor plan analysis for {analysis_id}")
        
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
        
#         # Run smart detection
#         detected_tables, annotated_image, detection_metadata = await run_in_threadpool(
#             _smart_detect_tables,
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
        
#         logger.info(f"✅ Smart analysis completed for {analysis_id}")
        
#     except Exception as e:
#         logger.error(f"❌ Smart analysis error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
        
#         await db.floor_plan_analysis.update_one(
#             {"_id": ObjectId(analysis_id)},
#             {"$set": {"analysisStatus": "failed", "error": str(e)}}
#         )


# def _smart_detect_tables(
#     image_content: bytes,
#     room_dimensions: Dict
# ) -> Tuple[List[Dict], np.ndarray, Dict]:
#     """
#     Smart detection: Find tables by detecting chair clusters
#     """
    
#     # Load image
#     img = _load_image(image_content)
#     height, width = img.shape[:2]
    
#     logger.info(f"📐 Image: {width}x{height}")
    
#     # Method 1: OpenAI Vision (Primary - most accurate)
#     logger.info("🤖 Step 1: Analyzing with OpenAI Vision...")
#     openai_tables = _detect_with_openai_vision(image_content, room_dimensions, width, height)
#     logger.info(f"✅ OpenAI found {len(openai_tables)} tables")
    
#     # Method 2: Chair-based CV detection (Fallback)
#     logger.info("🪑 Step 2: Chair-based CV detection...")
#     cv_tables = _detect_tables_by_chairs(img, width, height, room_dimensions)
#     logger.info(f"✅ CV found {len(cv_tables)} table clusters")
    
#     # Merge results
#     logger.info("🔀 Step 3: Merging results...")
#     final_tables = _merge_smart_detections(openai_tables, cv_tables, width, height)
#     logger.info(f"✅ Final count: {len(final_tables)} tables")
    
#     # Metadata
#     metadata = {
#         "openai_count": len(openai_tables),
#         "cv_count": len(cv_tables),
#         "final_count": len(final_tables),
#         "detection_method": "openai_vision" if len(openai_tables) > 0 else "chair_clustering",
#         "table_shapes_detected": list(set([t.get('tableType', 'unknown') for t in final_tables]))
#     }
    
#     # Draw annotations
#     annotated = _draw_smart_annotations(img.copy(), final_tables)
    
#     return final_tables, annotated, metadata


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


# def _detect_with_openai_vision(
#     image_content: bytes,
#     room_dimensions: Dict,
#     img_width: int,
#     img_height: int
# ) -> List[Dict]:
#     """
#     Use OpenAI Vision with chair-aware prompting
#     """
#     try:
#         base64_image = base64.b64encode(image_content).decode('utf-8')
        
#         prompt = f"""You are analyzing a restaurant floor plan. Your ONLY job: COUNT EVERY TABLE.

# Room: {room_dimensions['length']} x {room_dimensions['width']} {room_dimensions['unit']}

# ⚠️ CRITICAL SCANNING PROCEDURE:
# You MUST scan the ENTIRE image systematically. Do NOT skip any area!

# STEP 1: DIVIDE THE IMAGE INTO ZONES
# - Far Left zone (0-20% from left edge) - CHECK CAREFULLY! 
# - Left zone (20-40% from left)
# - Center zone (40-60%)
# - Right zone (60-80% from left)
# - Far Right zone (80-100%)

# STEP 2: IN EACH ZONE, FIND TABLE PATTERNS
# A TABLE = Small circles (chairs) surrounding a central space/shape

# Common patterns:
# • 4 chairs in square around center = 1 table
# • 4-6 chairs around rectangle = 1 table  
# • Chairs in circle pattern = 1 round table
# • Chairs along one side = 1 booth/bench table

# STEP 3: COUNT SYSTEMATICALLY
# Go zone by zone, TOP to BOTTOM:
# - Far Left: How many chair groups? __
# - Left: How many chair groups? __
# - Center: How many chair groups? __
# - Right: How many chair groups? __
# - Far Right: How many chair groups? __

# TOTAL = Sum of ALL zones

# ⚠️ COMMON MISTAKES TO AVOID:
# ❌ Missing tables on far left/right edges
# ❌ Counting individual chairs as separate tables
# ❌ Missing small/partially visible tables
# ❌ Counting same table twice

# ✅ WHAT TO COUNT:
# - Large rectangles with chairs = table
# - Small rectangles with chairs = table
# - Any rectangle/square on LEFT side with chairs = table (don't miss these!)
# - Circles with chairs around them = table
# - Kitchen/bar area tables if they have chairs

# Return JSON with EVERY table found:
# [
#   {{
#     "table_number": 1,
#     "type": "rectangular",
#     "zone": "far_left" or "left" or "center" or "right" or "far_right",
#     "center_x_percent": 0.15,
#     "center_y_percent": 0.20,
#     "width_percent": 0.08,
#     "height_percent": 0.06,
#     "chair_count": 4,
#     "confidence": 0.95
#   }}
# ]

# BEFORE RETURNING:
# 1. Count your JSON objects
# 2. Re-scan far left and far right edges - did you miss any?
# 3. Verify total makes sense (typical: 8-15 tables for small restaurant)

# Return ONLY the JSON array, nothing else."""

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
#             temperature=0.1
#         )
        
#         content = response.choices[0].message.content.strip()
        
#         # Extract JSON
#         if content.startswith("```json"):
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif content.startswith("```"):
#             content = content.split("```")[1].split("```")[0].strip()
        
#         tables_data = json.loads(content)
        
#         detected_tables = []
#         for table in tables_data:
#             detected_tables.append({
#                 "source": "openai",
#                 "tableId": f"table_{table['table_number']}",
#                 "type": table.get('type', 'rectangular'),
#                 "location": table.get('location', 'unknown'),
#                 "chair_count": table.get('chair_count', 0),
#                 "center_x_percent": table['center_x_percent'],
#                 "center_y_percent": table['center_y_percent'],
#                 "width_percent": table.get('width_percent', 0.05),
#                 "height_percent": table.get('height_percent', 0.05),
#                 "confidence": table.get('confidence', 0.9)
#             })
        
#         logger.info(f"🤖 OpenAI Vision: {len(detected_tables)} tables")
#         return detected_tables
        
#     except json.JSONDecodeError as e:
#         logger.error(f"❌ OpenAI JSON parse error: {e}")
#         if 'content' in locals():
#             logger.error(f"Response was: {content}")
#         return []
#     except Exception as e:
#         logger.error(f"❌ OpenAI Vision error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         return []


# def _detect_tables_by_chairs(
#     img: np.ndarray,
#     img_width: int,
#     img_height: int,
#     room_dimensions: Dict
# ) -> List[Dict]:
#     """
#     Detect tables by finding chair clusters using CV
    
#     Strategy:
#     1. Find all small circular objects (chairs)
#     2. Group them into clusters
#     3. Find center of each cluster = table location
#     """
#     try:
#         gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
#         # Detect circular objects (chairs)
#         logger.info("🔍 Detecting circular objects (chairs)...")
        
#         # Use Hough Circle detection
#         circles = cv2.HoughCircles(
#             gray,
#             cv2.HOUGH_GRADIENT,
#             dp=1,
#             minDist=10,  # Chairs are close together
#             param1=50,
#             param2=30,
#             minRadius=3,   # Small circles
#             maxRadius=20   # Not too big
#         )
        
#         if circles is None:
#             logger.warning("⚠️ No circles detected, trying contour method")
#             return _detect_tables_by_contours(img, img_width, img_height, room_dimensions)
        
#         circles = np.uint16(np.around(circles))
#         chair_positions = []
        
#         for circle in circles[0, :]:
#             x, y, r = circle
#             chair_positions.append((int(x), int(y), int(r)))
        
#         logger.info(f"🪑 Found {len(chair_positions)} potential chairs")
        
#         # Cluster chairs into table groups
#         table_clusters = _cluster_chairs(chair_positions, img_width, img_height)
#         logger.info(f"📊 Formed {len(table_clusters)} chair clusters")
        
#         # Convert clusters to table detections
#         detected_tables = []
        
#         for idx, cluster in enumerate(table_clusters):
#             if len(cluster) < 2:  # Need at least 2 chairs for a table
#                 continue
            
#             # Calculate cluster center and bounds
#             cluster_x = [c[0] for c in cluster]
#             cluster_y = [c[1] for c in cluster]
            
#             center_x = int(np.mean(cluster_x))
#             center_y = int(np.mean(cluster_y))
            
#             min_x, max_x = min(cluster_x), max(cluster_x)
#             min_y, max_y = min(cluster_y), max(cluster_y)
            
#             width = max_x - min_x
#             height = max_y - min_y
            
#             # Determine table shape based on chair arrangement
#             table_type = _determine_table_shape(cluster)
            
#             detected_tables.append({
#                 "source": "cv",
#                 "tableId": f"cv_table_{idx + 1}",
#                 "type": table_type,
#                 "chair_count": len(cluster),
#                 "center_x_percent": center_x / img_width,
#                 "center_y_percent": center_y / img_height,
#                 "width_percent": width / img_width,
#                 "height_percent": height / img_height,
#                 "confidence": min(0.7 + len(cluster) * 0.05, 0.95)  # More chairs = higher confidence
#             })
        
#         return detected_tables
        
#     except Exception as e:
#         logger.error(f"❌ Chair detection error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         return []


# def _cluster_chairs(chair_positions: List[Tuple], img_width: int, img_height: int) -> List[List[Tuple]]:
#     """
#     Group chairs into clusters (each cluster = one table)
#     Uses DBSCAN-like clustering
#     """
#     if len(chair_positions) == 0:
#         return []
    
#     # Distance threshold for clustering (chairs around same table are close)
#     cluster_distance = min(img_width, img_height) * 0.08  # 8% of image size
    
#     clusters = []
#     used = set()
    
#     for i, chair in enumerate(chair_positions):
#         if i in used:
#             continue
        
#         # Start new cluster
#         cluster = [chair]
#         used.add(i)
        
#         # Find all nearby chairs
#         for j, other_chair in enumerate(chair_positions):
#             if j in used:
#                 continue
            
#             # Check distance to any chair in current cluster
#             min_dist = float('inf')
#             for cluster_chair in cluster:
#                 dist = np.sqrt((chair[0] - other_chair[0])**2 + (chair[1] - other_chair[1])**2)
#                 min_dist = min(min_dist, dist)
            
#             if min_dist < cluster_distance:
#                 cluster.append(other_chair)
#                 used.add(j)
        
#         clusters.append(cluster)
    
#     return clusters


# def _determine_table_shape(chair_cluster: List[Tuple]) -> str:
#     """
#     Determine table shape based on chair arrangement
#     """
#     if len(chair_cluster) < 2:
#         return "unknown"
    
#     # Get chair positions
#     positions = np.array([(c[0], c[1]) for c in chair_cluster])
    
#     # Calculate convex hull
#     try:
#         from scipy.spatial import ConvexHull
#         hull = ConvexHull(positions)
#         hull_area = hull.volume  # In 2D, volume = area
        
#         # Calculate bounding rectangle
#         min_x, min_y = positions.min(axis=0)
#         max_x, max_y = positions.max(axis=0)
#         rect_area = (max_x - min_x) * (max_y - min_y)
        
#         if rect_area == 0:
#             return "circular"
        
#         # If hull area is close to rectangle area, it's rectangular
#         fill_ratio = hull_area / rect_area
        
#         if fill_ratio > 0.8:
#             return "rectangular"
#         elif 0.6 < fill_ratio <= 0.8:
#             return "L-shaped"
#         elif 0.4 < fill_ratio <= 0.6:
#             return "U-shaped"
#         else:
#             return "circular"
            
#     except:
#         # Fallback: check if chairs form a circle
#         center = positions.mean(axis=0)
#         distances = np.sqrt(((positions - center) ** 2).sum(axis=1))
        
#         # If distances are similar, it's circular
#         if distances.std() / distances.mean() < 0.3:
#             return "circular"
#         else:
#             return "rectangular"


# def _detect_tables_by_contours(
#     img: np.ndarray,
#     img_width: int,
#     img_height: int,
#     room_dimensions: Dict
# ) -> List[Dict]:
#     """
#     Improved contour detection with strict filtering
#     """
#     try:
#         gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
#         # Use multiple threshold methods and combine
#         detected_objects = []
        
#         # Method 1: Adaptive threshold
#         thresh1 = cv2.adaptiveThreshold(
#             gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
#         )
#         contours1, _ = cv2.findContours(thresh1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
#         # Method 2: Binary threshold
#         _, thresh2 = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)
#         contours2, _ = cv2.findContours(thresh2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
#         # Combine contours
#         all_contours = list(contours1) + list(contours2)
        
#         # Strict area thresholds - ONLY table-sized objects
#         total_area = img_width * img_height
#         min_table_area = total_area * 0.003   # Minimum 0.3% of image
#         max_table_area = total_area * 0.10    # Maximum 10% of image
        
#         logger.info(f"🔍 Area range: {min_table_area:.0f} - {max_table_area:.0f} px²")
        
#         potential_tables = []
        
#         for contour in all_contours:
#             area = cv2.contourArea(contour)
            
#             # Strict area filtering
#             if not (min_table_area < area < max_table_area):
#                 continue
            
#             x, y, w, h = cv2.boundingRect(contour)
            
#             # Aspect ratio check
#             aspect_ratio = w / h if h > 0 else 0
            
#             # Circularity check
#             perimeter = cv2.arcLength(contour, True)
#             circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
            
#             # STRICT shape requirements
#             is_valid_shape = False
#             table_type = "unknown"
            
#             # Circle (high circularity)
#             if circularity > 0.65:
#                 is_valid_shape = True
#                 table_type = "circular"
            
#             # Rectangle (reasonable aspect ratio + not too circular)
#             elif 0.3 < aspect_ratio < 4.0 and circularity < 0.85:
#                 is_valid_shape = True
#                 table_type = "rectangular"
            
#             if is_valid_shape:
#                 potential_tables.append({
#                     "x": x, "y": y, "w": w, "h": h,
#                     "area": area,
#                     "circularity": circularity,
#                     "aspect_ratio": aspect_ratio,
#                     "type": table_type
#                 })
        
#         logger.info(f"🔍 Found {len(potential_tables)} potential table shapes")
        
#         # Remove duplicates (same position)
#         unique_tables = []
#         seen_positions = []
#         threshold = min(img_width, img_height) * 0.05
        
#         for obj in potential_tables:
#             center_x = obj['x'] + obj['w'] / 2
#             center_y = obj['y'] + obj['h'] / 2
            
#             is_duplicate = False
#             for seen_x, seen_y in seen_positions:
#                 dist = np.sqrt((center_x - seen_x)**2 + (center_y - seen_y)**2)
#                 if dist < threshold:
#                     is_duplicate = True
#                     break
            
#             if not is_duplicate:
#                 seen_positions.append((center_x, center_y))
#                 unique_tables.append(obj)
        
#         logger.info(f"✅ After deduplication: {len(unique_tables)} tables")
        
#         # Convert to standard format
#         detected_tables = []
#         for idx, obj in enumerate(unique_tables):
#             detected_tables.append({
#                 "source": "cv",
#                 "tableId": f"cv_table_{idx + 1}",
#                 "type": obj['type'],
#                 "center_x_percent": (obj['x'] + obj['w']/2) / img_width,
#                 "center_y_percent": (obj['y'] + obj['h']/2) / img_height,
#                 "width_percent": obj['w'] / img_width,
#                 "height_percent": obj['h'] / img_height,
#                 "confidence": 0.65
#             })
        
#         return detected_tables
        
#     except Exception as e:
#         logger.error(f"❌ Contour detection error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         return []


# def _merge_smart_detections(
#     openai_tables: List[Dict],
#     cv_tables: List[Dict],
#     img_width: int,
#     img_height: int
# ) -> List[Dict]:
#     """
#     Intelligent merging with cross-validation
#     """
    
#     logger.info(f"📊 OpenAI: {len(openai_tables)} | CV: {len(cv_tables)}")
    
#     # If counts are very different, something is wrong - need validation
#     count_diff = abs(len(openai_tables) - len(cv_tables))
    
#     if count_diff > 3:
#         logger.warning(f"⚠️ Large discrepancy detected! OpenAI: {len(openai_tables)}, CV: {len(cv_tables)}")
#         logger.info("🔍 Using hybrid approach with validation...")
        
#         # Use both methods and merge intelligently
#         all_detections = openai_tables + cv_tables
        
#         # Remove duplicates and keep high-confidence ones
#         final_tables = []
#         seen_positions = []
        
#         # Sort by confidence
#         all_detections.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
#         threshold = min(img_width, img_height) * 0.08
        
#         for detection in all_detections:
#             center_x = detection['center_x_percent'] * img_width
#             center_y = detection['center_y_percent'] * img_height
            
#             # Check if we already have a table near this position
#             is_duplicate = False
#             for seen_x, seen_y in seen_positions:
#                 dist = np.sqrt((center_x - seen_x)**2 + (center_y - seen_y)**2)
#                 if dist < threshold:
#                     is_duplicate = True
#                     break
            
#             if not is_duplicate:
#                 seen_positions.append((center_x, center_y))
#                 final_tables.append(detection)
        
#         logger.info(f"✅ After merging and deduplication: {len(final_tables)} tables")
#         primary_source = "hybrid"
        
#     else:
#         # Counts are close, prefer OpenAI
#         if len(openai_tables) > 0:
#             final_tables = openai_tables
#             primary_source = "openai"
#             logger.info("✅ Using OpenAI Vision (counts match)")
#         else:
#             final_tables = cv_tables
#             primary_source = "cv"
#             logger.info("✅ Using CV detection")
    
#     # Convert to final format
#     formatted_tables = []
    
#     for idx, table in enumerate(final_tables):
#         center_x = int(table['center_x_percent'] * img_width)
#         center_y = int(table['center_y_percent'] * img_height)
#         width = int(table.get('width_percent', 0.05) * img_width)
#         height = int(table.get('height_percent', 0.05) * img_height)
        
#         # Ensure minimum size
#         width = max(width, 20)
#         height = max(height, 20)
        
#         x = max(0, center_x - width // 2)
#         y = max(0, center_y - height // 2)
        
#         formatted_tables.append({
#             "tableId": f"table_{idx + 1}",
#             "detectionMethod": table.get('source', primary_source),
#             "tableType": table.get('type', 'rectangular'),
#             "chairCount": table.get('chair_count', 0),
#             "location": table.get('location', table.get('zone', 'unknown')),
#             "pixelCoordinates": {
#                 "x": x,
#                 "y": y,
#                 "width": width,
#                 "height": height
#             },
#             "confidence": table.get('confidence', 0.7)
#         })
    
#     # Sort by position (left to right, top to bottom)
#     formatted_tables.sort(key=lambda t: (
#         t['pixelCoordinates']['x'],  # Left to right first
#         t['pixelCoordinates']['y']   # Then top to bottom
#     ))
    
#     # Renumber after sorting
#     for idx, table in enumerate(formatted_tables):
#         table['tableId'] = f"table_{idx + 1}"
    
#     logger.info(f"✅ Final: {len(formatted_tables)} tables (source: {primary_source})")
    
#     return formatted_tables


# def _draw_smart_annotations(img: np.ndarray, tables: List[Dict]) -> np.ndarray:
#     """Draw annotations showing detected tables"""
    
#     shape_colors = {
#         'circular': (255, 0, 255),      # Magenta
#         'rectangular': (0, 165, 255),   # Orange
#         'L-shaped': (0, 255, 255),      # Yellow
#         'U-shaped': (255, 255, 0),      # Cyan
#     }
    
#     for table in tables:
#         px = table['pixelCoordinates']
#         x, y, w, h = px['x'], px['y'], px['width'], px['height']
        
#         table_type = table.get('tableType', 'rectangular')
#         color = shape_colors.get(table_type, (128, 128, 128))
        
#         # Draw shape
#         if table_type == 'circular':
#             center = (x + w // 2, y + h // 2)
#             radius = max(w, h) // 2
#             cv2.circle(img, center, radius, color, 3)
#         else:
#             cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
        
#         # Label with chair count
#         chair_count = table.get('chairCount', 0)
#         if chair_count > 0:
#             label = f"{table['tableId']} ({chair_count} chairs)"
#         else:
#             label = f"{table['tableId']}"
        
#         cv2.putText(img, label, (x + 5, y - 5),
#                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
#         # Draw center
#         cv2.circle(img, (x + w // 2, y + h // 2), 4, (0, 0, 255), -1)
    
#     # Summary
#     y_offset = 30
#     cv2.putText(img, f"Total Tables: {len(tables)}", (10, y_offset),
#                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    
#     # Shape breakdown
#     shapes = {}
#     for table in tables:
#         shape = table.get('tableType', 'unknown')
#         shapes[shape] = shapes.get(shape, 0) + 1
    
#     y_offset += 30
#     for shape, count in shapes.items():
#         color = shape_colors.get(shape, (128, 128, 128))
#         cv2.putText(img, f"{shape}: {count}", (10, y_offset),
#                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
#         y_offset += 25
    
#     return img





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
    
#     logger.info(f"📐 Image: {width}x{height}")
    
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
#             x = int(table['center_x_percent'] * width - (table.get('width_percent', 0.05) * width / 2))
#             y = int(table['center_y_percent'] * height - (table.get('height_percent', 0.05) * height / 2))
#             w = int(table.get('width_percent', 0.05) * width)
#             h = int(table.get('height_percent', 0.05) * height)
            
#             # Ensure values are within bounds
#             x = max(0, min(x, width - 1))
#             y = max(0, min(y, height - 1))
#             w = max(20, min(w, width - x))
#             h = max(20, min(h, height - y))
            
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
#                 "confidence": 0.90  # OpenAI is quite reliable
#             })
        
#         # Draw annotations
#         annotated = _draw_annotations(img.copy(), detected_tables)
        
#         # Metadata
#         metadata = {
#             "detection_method": "openai_vision",
#             "table_count": len(detected_tables),
#             "table_types": list(set([t['tableType'] for t in detected_tables])),
#             "total_estimated_seats": sum([t['chairCount'] for t in detected_tables])
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
        
#         # Label
#         seats = table.get('chairCount', 0)
#         label = f"{table['tableId']}"
#         if seats > 0:
#             label += f" ({seats})"
        
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









# services/floor_plan_service.py
"""
Simple Table Detection Service
===============================
Uses ONLY OpenAI Vision API - no CV hallucinations!
"""

import cv2
from urllib.parse import urlparse, unquote
import numpy as np
from typing import List, Dict, Tuple
from bson import ObjectId
from fastapi.concurrency import run_in_threadpool
import logging
import io
import json
import base64
from PIL import Image
import boto3
from openai import OpenAI
from config import settings
from database import get_database
from services.s3_service import upload_to_s3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)


async def detect_tables_from_floor_plan_url(
    floor_plan_url: str,
    analysis_id: str,
    room_dimensions: Dict
):
    """
    Table detection using OpenAI Vision API only
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
        
        # Run detection
        detected_tables, annotated_image, detection_metadata = await run_in_threadpool(
            _detect_with_openai_vision,
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


def _detect_with_openai_vision(
    image_content: bytes,
    room_dimensions: Dict
) -> Tuple[List[Dict], np.ndarray, Dict]:
    """
    Use OpenAI Vision to detect tables
    """
    # Load image
    img = _load_image(image_content)
    height, width = img.shape[:2]
    
    # 🆕 Calculate pixel-to-meter scale
    scale_x = room_dimensions['length'] / width
    scale_y = room_dimensions['width'] / height
    
    logger.info(f"📐 Image: {width}x{height}")
    logger.info(f"🔢 Scale: {scale_x:.4f}m/px (X), {scale_y:.4f}m/px (Y)")
    
    try:
        base64_image = base64.b64encode(image_content).decode('utf-8')
        
        # IMPROVED PROMPT - very specific instructions
        prompt = f"""You are analyzing a restaurant floor plan image to detect dining tables.

**Room Dimensions:** {room_dimensions['length']} x {room_dimensions['width']} {room_dimensions['unit']}
**Image Size:** {width} x {height} pixels

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
- width_percent: table width as % of image width
- height_percent: table height as % of image height
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

        logger.info("🤖 Calling OpenAI Vision API...")
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.1  # Low temperature for consistency
        )
        
        content = response.choices[0].message.content.strip()
        logger.info(f"📥 OpenAI Response received ({len(content)} chars)")
        
        # Parse JSON
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        tables_data = json.loads(content)
        
        logger.info(f"✅ OpenAI detected {len(tables_data)} tables")
        
        # Convert to standard format
        detected_tables = []
        
        for table in tables_data:
            # Calculate pixel coordinates
            x = int(table['center_x_percent'] * width - (table.get('width_percent', 0.05) * width / 2))
            y = int(table['center_y_percent'] * height - (table.get('height_percent', 0.05) * height / 2))
            w = int(table.get('width_percent', 0.05) * width)
            h = int(table.get('height_percent', 0.05) * height)
            
            # Ensure values are within bounds
            x = max(0, min(x, width - 1))
            y = max(0, min(y, height - 1))
            w = max(20, min(w, width - x))
            h = max(20, min(h, height - y))
            
            # 🆕 Calculate real-world coordinates
            real_x = x * scale_x
            real_y = y * scale_y
            real_width = w * scale_x
            real_height = h * scale_y
            
            detected_tables.append({
                "tableId": f"table_{table['table_number']}",
                "detectionMethod": "openai_vision",
                "tableType": table.get('type', 'rectangular'),
                "chairCount": table.get('estimated_seats', 0),
                "pixelCoordinates": {
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h
                },
                # 🆕 Added real-world coordinates
                "realWorldCoordinates": {
                    "x": round(real_x, 2),
                    "y": round(real_y, 2),
                    "width": round(real_width, 2),
                    "height": round(real_height, 2),
                    "unit": room_dimensions['unit']
                },
                "confidence": 0.90  # OpenAI is quite reliable
            })
        
        # Draw annotations
        annotated = _draw_annotations(img.copy(), detected_tables)
        
        # Metadata
        metadata = {
            "detection_method": "openai_vision",
            "table_count": len(detected_tables),
            "table_types": list(set([t['tableType'] for t in detected_tables])),
            "total_estimated_seats": sum([t['chairCount'] for t in detected_tables]),
            "scale_factor": {
                "x": round(scale_x, 4),
                "y": round(scale_y, 4),
                "unit": f"{room_dimensions['unit']}/pixel"
            }
        }
        
        return detected_tables, annotated, metadata
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        if 'content' in locals():
            logger.error(f"Response was: {content}")
        # Return empty on error
        return [], img, {"error": str(e)}
        
    except Exception as e:
        logger.error(f"❌ OpenAI Vision error: {e}")
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
    
    # Summary
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