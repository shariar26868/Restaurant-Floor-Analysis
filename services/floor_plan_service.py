# # services/floor_plan_service.py

# import cv2
# import numpy as np
# from typing import List, Dict, Tuple
# from bson import ObjectId
# from fastapi.concurrency import run_in_threadpool
# from ultralytics import YOLO
# import logging

# from database import get_database
# from services.s3_service import upload_to_s3

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Load YOLO model globally (loads once when server starts)
# try:
#     model = YOLO('yolov8n.pt')  # nano model for speed
#     logger.info("✅ YOLO model loaded successfully")
# except Exception as e:
#     logger.error(f"❌ Failed to load YOLO model: {e}")
#     model = None


# async def detect_tables_from_floor_plan(
#     floor_plan_content: bytes,
#     analysis_id: str,
#     room_dimensions: Dict
# ):
#     """
#     Detect tables from floor plan image using computer vision
#     """
#     db = get_database()
    
#     try:
#         logger.info(f"🔍 Starting floor plan analysis for {analysis_id}")
        
#         # Run detection in threadpool (OpenCV operations are blocking)
#         detected_tables, annotated_image = await run_in_threadpool(
#             _detect_tables_sync,
#             floor_plan_content,
#             room_dimensions
#         )
        
#         logger.info(f"✅ Detected {len(detected_tables)} tables")
        
#         # Encode annotated image
#         success, img_encoded = cv2.imencode('.jpg', annotated_image)
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


# def _detect_tables_sync(floor_plan_content: bytes, room_dimensions: Dict) -> Tuple[List[Dict], np.ndarray]:
#     """
#     Synchronous table detection using multiple methods
#     """
#     # Decode image
#     nparr = np.frombuffer(floor_plan_content, np.uint8)
#     img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
#     if img is None:
#         raise Exception("Failed to decode floor plan image")
    
#     height, width = img.shape[:2]
#     logger.info(f"📐 Image dimensions: {width}x{height}")
    
#     # Try YOLO detection first
#     detected_tables = []
    
#     if model is not None:
#         detected_tables = _detect_with_yolo(img, width, height, room_dimensions)
#         logger.info(f"🤖 YOLO detected {len(detected_tables)} tables")
    
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
#         results = model(img, conf=0.3, verbose=False)  # Lower confidence for floor plans
        
#         # Classes that might represent tables in floor plans
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
#     Detect tables using contour/shape detection
#     """
#     detected_tables = []
    
#     try:
#         # Convert to grayscale
#         gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
#         # Apply adaptive thresholding
#         thresh = cv2.adaptiveThreshold(
#             gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
#         )
        
#         # Find contours
#         contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
#         # Calculate minimum table size (5% of image dimensions)
#         min_area = (img_width * img_height) * 0.001
#         max_area = (img_width * img_height) * 0.1
        
#         for contour in contours:
#             area = cv2.contourArea(contour)
            
#             # Filter by area
#             if area < min_area or area > max_area:
#                 continue
            
#             # Get bounding rectangle
#             x, y, w, h = cv2.boundingRect(contour)
            
#             # Calculate aspect ratio
#             aspect_ratio = w / h if h > 0 else 0
            
#             # Filter table-like shapes (rectangles or squares)
#             if 0.3 < aspect_ratio < 3.0:  # Not too thin
#                 # Convert to real-world coordinates
#                 real_coords = _pixel_to_real_world(
#                     x, y, w, h,
#                     img_width, img_height,
#                     room_dimensions
#                 )
                
#                 detected_tables.append({
#                     "tableId": f"table_{len(detected_tables) + 1}",
#                     "detectionMethod": "shape",
#                     "pixelCoordinates": {
#                         "x": x,
#                         "y": y,
#                         "width": w,
#                         "height": h
#                     },
#                     "realWorldCoordinates": real_coords,
#                     "confidence": 0.70  # Lower confidence for shape detection
#                 })
    
#     except Exception as e:
#         logger.error(f"❌ Shape detection error: {e}")
    
#     return detected_tables


# def _pixel_to_real_world(x: int, y: int, w: int, h: int, 
#                           img_width: int, img_height: int, 
#                           room_dimensions: Dict) -> Dict:
#     """
#     Convert pixel coordinates to real-world measurements
#     """
#     # Room dimensions in meters (or specified unit)
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
#     for table in detected_tables:
#         pixel_coords = table['pixelCoordinates']
#         x = pixel_coords['x']
#         y = pixel_coords['y']
#         w = pixel_coords['width']
#         h = pixel_coords['height']
        
#         # Different colors based on detection method
#         if table.get('detectionMethod') == 'yolo':
#             color = (0, 255, 0)  # Green for YOLO
#         else:
#             color = (0, 165, 255)  # Orange for shape detection
        
#         # Draw rectangle
#         cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
        
#         # Add label
#         label = f"{table['tableId']} ({table['confidence']:.0%})"
        
#         # Label background
#         (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
#         cv2.rectangle(img, (x, y - label_h - 10), (x + label_w + 10, y), color, -1)
        
#         # Label text
#         cv2.putText(
#             img, label, (x + 5, y - 5),
#             cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
#         )
        
#         # Draw center point
#         real_coords = table['realWorldCoordinates']
#         center_text = f"({real_coords['centerPoint']['x']}, {real_coords['centerPoint']['y']})"
#         cv2.circle(img, (x + w//2, y + h//2), 5, (0, 0, 255), -1)
#         cv2.putText(
#             img, center_text, (x + w//2 + 10, y + h//2),
#             cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1
#         )
    
#     # Add summary info
#     summary = f"Detected Tables: {len(detected_tables)}"
#     cv2.putText(
#         img, summary, (10, 30),
#         cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2
#     )
    
#     return img





# # services/floor_plan_service.py

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
#     Detect tables using contour/shape detection
#     """
#     detected_tables = []
    
#     try:
#         # Convert to grayscale
#         gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
#         # Apply adaptive thresholding
#         thresh = cv2.adaptiveThreshold(
#             gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
#         )
        
#         # Find contours
#         contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
#         # Calculate area thresholds (0.1% to 10% of image)
#         min_area = (img_width * img_height) * 0.001
#         max_area = (img_width * img_height) * 0.1
        
#         logger.info(f"🔍 Found {len(contours)} contours, filtering by area {min_area:.0f} - {max_area:.0f}")
        
#         for contour in contours:
#             area = cv2.contourArea(contour)
            
#             # Filter by area
#             if area < min_area or area > max_area:
#                 continue
            
#             # Get bounding rectangle
#             x, y, w, h = cv2.boundingRect(contour)
            
#             # Calculate aspect ratio
#             aspect_ratio = w / h if h > 0 else 0
            
#             # Filter table-like shapes (not too thin)
#             if 0.3 < aspect_ratio < 3.0:
#                 # Convert to real-world coordinates
#                 real_coords = _pixel_to_real_world(
#                     x, y, w, h,
#                     img_width, img_height,
#                     room_dimensions
#                 )
                
#                 detected_tables.append({
#                     "tableId": f"table_{len(detected_tables) + 1}",
#                     "detectionMethod": "shape",
#                     "pixelCoordinates": {
#                         "x": x,
#                         "y": y,
#                         "width": w,
#                         "height": h
#                     },
#                     "realWorldCoordinates": real_coords,
#                     "confidence": 0.70
#                 })
    
#     except Exception as e:
#         logger.error(f"❌ Shape detection error: {e}")
    
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
#     for table in detected_tables:
#         pixel_coords = table['pixelCoordinates']
#         x = pixel_coords['x']
#         y = pixel_coords['y']
#         w = pixel_coords['width']
#         h = pixel_coords['height']
        
#         # Different colors based on detection method
#         if table.get('detectionMethod') == 'yolo':
#             color = (0, 255, 0)  # Green for YOLO
#         else:
#             color = (0, 165, 255)  # Orange for shape detection
        
#         # Draw rectangle
#         cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
        
#         # Add label
#         label = f"{table['tableId']} ({table['confidence']:.0%})"
        
#         # Label background
#         (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
#         cv2.rectangle(img, (x, y - label_h - 10), (x + label_w + 10, y), color, -1)
        
#         # Label text
#         cv2.putText(
#             img, label, (x + 5, y - 5),
#             cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
#         )
        
#         # Draw center point
#         real_coords = table['realWorldCoordinates']
#         center_text = f"({real_coords['centerPoint']['x']}, {real_coords['centerPoint']['y']})"
#         cv2.circle(img, (x + w//2, y + h//2), 5, (0, 0, 255), -1)
#         cv2.putText(
#             img, center_text, (x + w//2 + 10, y + h//2),
#             cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1
#         )
    
#     # Add summary info
#     summary = f"Detected Tables: {len(detected_tables)}"
#     cv2.putText(
#         img, summary, (10, 30),
#         cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2
#     )
    
#     return img









# services/floor_plan_service.py

import cv2
from urllib.parse import urlparse, unquote
import numpy as np
from typing import List, Dict, Tuple
from bson import ObjectId
from fastapi.concurrency import run_in_threadpool
import logging
import io
from PIL import Image
import boto3
from config import settings

from database import get_database
from services.s3_service import upload_to_s3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enable AVIF support
try:
    import pillow_avif
    logger.info("✅ pillow-avif-plugin loaded successfully")
except ImportError:
    logger.error("❌ pillow-avif-plugin not installed! Run: pip install pillow-avif-plugin")

# YOLO model (optional - will try to load, fallback to shape detection)
model = None
try:
    from ultralytics import YOLO
    model = YOLO('yolov8n.pt')
    logger.info("✅ YOLO model loaded successfully")
except Exception as e:
    logger.warning(f"⚠️ YOLO not available, will use shape detection: {e}")


async def detect_tables_from_floor_plan_url(
    floor_plan_url: str,
    analysis_id: str,
    room_dimensions: Dict
):
    """
    Download floor plan from S3 and detect tables
    """
    db = get_database()
    
    try:
        logger.info(f"🔍 Starting floor plan analysis for {analysis_id}")
        logger.info(f"📥 Downloading from S3: {floor_plan_url}")
        
        # Download image from S3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # Extract S3 key properly - remove query parameters
        parsed_url = urlparse(floor_plan_url)
        # Remove leading '/' from path
        s3_key = parsed_url.path.lstrip('/')
        # Decode URL encoding if any
        s3_key = unquote(s3_key)
        
        logger.info(f"📂 S3 Key: {s3_key}")
        
        # Download image
        response = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
        image_content = response['Body'].read()
        
        logger.info(f"✅ Downloaded {len(image_content)} bytes from S3")
        
        # Debug file info
        file_type = _detect_file_type(image_content)
        logger.info(f"🔍 Detected file type: {file_type}")
        logger.info(f"🔍 S3 Content-Type: {response.get('ContentType', 'Not set')}")
        
        # Run detection in threadpool
        detected_tables, annotated_image = await run_in_threadpool(
            _detect_tables_sync,
            image_content,
            room_dimensions
        )
        
        logger.info(f"✅ Detected {len(detected_tables)} tables")
        
        # Encode annotated image
        success, img_encoded = cv2.imencode('.jpg', annotated_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not success:
            raise Exception("Failed to encode annotated image")
        
        img_bytes = img_encoded.tobytes()
        
        # Upload annotated floor plan to S3
        annotated_url = await upload_to_s3(
            img_bytes,
            f"floor_plans/annotated_{analysis_id}.jpg"
        )
        
        logger.info(f"📤 Uploaded annotated image: {annotated_url}")
        
        # Update database
        await db.floor_plan_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {
                "$set": {
                    "analysisStatus": "completed",
                    "detectedTables": detected_tables,
                    "annotatedFloorPlanUrl": annotated_url,
                    "tableCount": len(detected_tables)
                }
            }
        )
        
        logger.info(f"✅ Floor plan analysis completed for {analysis_id}")
        
    except Exception as e:
        logger.error(f"❌ Floor plan analysis error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Update database with error
        await db.floor_plan_analysis.update_one(
            {"_id": ObjectId(analysis_id)},
            {
                "$set": {
                    "analysisStatus": "failed",
                    "error": str(e)
                }
            }
        )


def _detect_file_type(data: bytes) -> str:
    """
    Detect file type from magic bytes (file signature)
    """
    if len(data) < 12:
        return "Unknown (file too small)"
    
    # Check magic bytes
    if data[:2] == b'\xff\xd8':
        return "JPEG"
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        return "PNG"
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return "WEBP"
    elif data[4:12] == b'ftypavif' or data[4:12] == b'ftypavis':
        return "AVIF"
    elif data[:2] == b'BM':
        return "BMP"
    elif data[:4] == b'GIF8':
        return "GIF"
    else:
        return f"Unknown (magic: {data[:12].hex()})"


def _detect_tables_sync(floor_plan_content: bytes, room_dimensions: Dict) -> Tuple[List[Dict], np.ndarray]:
    """
    Synchronous table detection - supports all image formats including AVIF
    """
    img = None
    file_type = _detect_file_type(floor_plan_content)
    
    try:
        logger.info(f"🔄 Loading {file_type} image with PIL...")
        
        # Open image with PIL (supports AVIF if pillow-avif-plugin is installed)
        img_pil = Image.open(io.BytesIO(floor_plan_content))
        
        logger.info(f"✅ PIL loaded image - Format: {img_pil.format}, Mode: {img_pil.mode}, Size: {img_pil.size}")
        
        # Convert to RGB (handles all formats including AVIF, RGBA, LA, P)
        if img_pil.mode in ('RGBA', 'LA'):
            # Create white background for transparency
            logger.info(f"🔄 Converting {img_pil.mode} to RGB with white background")
            background = Image.new('RGB', img_pil.size, (255, 255, 255))
            background.paste(img_pil, mask=img_pil.split()[-1])
            img_pil = background
        elif img_pil.mode == 'P':
            # Palette mode - convert to RGBA first, then RGB
            logger.info(f"🔄 Converting palette mode to RGB")
            img_pil = img_pil.convert('RGBA')
            background = Image.new('RGB', img_pil.size, (255, 255, 255))
            background.paste(img_pil, mask=img_pil.split()[-1])
            img_pil = background
        elif img_pil.mode != 'RGB':
            logger.info(f"🔄 Converting {img_pil.mode} to RGB")
            img_pil = img_pil.convert('RGB')
        
        # Convert PIL (RGB) to OpenCV (BGR)
        img_array = np.array(img_pil)
        img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        logger.info(f"✅ Successfully converted to OpenCV format")
        
    except Exception as e:
        logger.error(f"❌ PIL failed to load image: {e}")
        
        # Fallback to OpenCV (won't work for AVIF but try anyway)
        try:
            logger.info("🔄 Attempting OpenCV fallback...")
            nparr = np.frombuffer(floor_plan_content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                raise Exception("OpenCV decode returned None")
            
            logger.info(f"✅ OpenCV loaded image successfully")
            
        except Exception as cv_error:
            logger.error(f"❌ OpenCV also failed: {cv_error}")
            
            # Provide helpful error message
            if file_type == "AVIF":
                error_msg = (
                    f"Failed to decode AVIF image. "
                    f"Please install pillow-avif-plugin: pip install pillow-avif-plugin"
                )
            else:
                error_msg = (
                    f"Failed to decode {file_type} image. "
                    f"PIL error: {str(e)}, OpenCV error: {str(cv_error)}"
                )
            
            raise Exception(error_msg)
    
    if img is None:
        raise Exception(f"Failed to load {file_type} image - result is None")
    
    height, width = img.shape[:2]
    logger.info(f"📐 Image dimensions: {width}x{height}")
    
    # Try YOLO detection first
    detected_tables = []
    
    if model is not None:
        try:
            detected_tables = _detect_with_yolo(img, width, height, room_dimensions)
            logger.info(f"🤖 YOLO detected {len(detected_tables)} tables")
        except Exception as e:
            logger.warning(f"⚠️ YOLO detection failed: {e}")
    
    # If YOLO doesn't find tables, use shape detection
    if len(detected_tables) == 0:
        detected_tables = _detect_with_shapes(img, width, height, room_dimensions)
        logger.info(f"🔶 Shape detection found {len(detected_tables)} tables")
    
    # Draw annotations on image
    annotated_img = _draw_annotations(img.copy(), detected_tables)
    
    return detected_tables, annotated_img


def _detect_with_yolo(img: np.ndarray, img_width: int, img_height: int, room_dimensions: Dict) -> List[Dict]:
    """
    Detect tables using YOLO model
    """
    detected_tables = []
    
    try:
        # Run YOLO detection
        results = model(img, conf=0.3, verbose=False)
        
        # Classes that might represent tables
        table_classes = ['dining table', 'table', 'desk', 'couch', 'chair']
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                class_id = int(box.cls[0])
                class_name = model.names[class_id]
                
                # Filter only table-like objects
                if any(tc in class_name.lower() for tc in table_classes):
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = float(box.conf[0])
                    
                    # Pixel coordinates
                    x, y, w, h = int(x1), int(y1), int(x2-x1), int(y2-y1)
                    
                    # Convert to real-world coordinates
                    real_coords = _pixel_to_real_world(
                        x, y, w, h,
                        img_width, img_height,
                        room_dimensions
                    )
                    
                    detected_tables.append({
                        "tableId": f"table_{len(detected_tables) + 1}",
                        "detectionMethod": "yolo",
                        "detectedClass": class_name,
                        "pixelCoordinates": {
                            "x": x,
                            "y": y,
                            "width": w,
                            "height": h
                        },
                        "realWorldCoordinates": real_coords,
                        "confidence": round(confidence, 2)
                    })
    
    except Exception as e:
        logger.warning(f"⚠️ YOLO detection failed: {e}")
    
    return detected_tables


def _detect_with_shapes(img: np.ndarray, img_width: int, img_height: int, room_dimensions: Dict) -> List[Dict]:
    """
    Detect tables using multi-method contour detection
    Detects both indoor and outdoor tables (circular and rectangular)
    """
    detected_tables = []
    
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Method 1: Detect dark/gray table shapes (for filled tables)
        logger.info("🔍 Method 1: Detecting filled shapes...")
        _, binary1 = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
        contours1, _ = cv2.findContours(binary1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Method 2: Detect edges/outlines (for outlined tables)
        logger.info("🔍 Method 2: Detecting edge-based shapes...")
        edges = cv2.Canny(gray, 50, 150)
        # Dilate to connect nearby edges
        kernel = np.ones((3,3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)
        contours2, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Method 3: Adaptive threshold for varying lighting
        logger.info("🔍 Method 3: Detecting with adaptive threshold...")
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )
        contours3, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Combine all contours
        all_contours = contours1 + contours2 + contours3
        logger.info(f"🔍 Total contours found: {len(all_contours)}")
        
        # Calculate area thresholds - more lenient for small outdoor tables
        min_area = (img_width * img_height) * 0.0005  # 0.05% (smaller threshold)
        max_area = (img_width * img_height) * 0.15    # 15% (larger threshold)
        
        logger.info(f"🔍 Filtering by area {min_area:.0f} - {max_area:.0f}")
        
        detected_boxes = []  # To avoid duplicates
        
        for contour in all_contours:
            area = cv2.contourArea(contour)
            
            # Filter by area
            if area < min_area or area > max_area:
                continue
            
            # Get bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # Calculate aspect ratio
            aspect_ratio = w / h if h > 0 else 0
            
            # Check circularity for round tables
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = 4 * np.pi * area / (perimeter * perimeter)
            else:
                circularity = 0
            
            # Detect both rectangular and circular tables
            is_table = False
            table_type = "unknown"
            
            # Circular tables (like outdoor seating)
            if circularity > 0.6:  # Circle-like shape
                is_table = True
                table_type = "circular"
            
            # Rectangular tables (dining area)
            elif 0.2 < aspect_ratio < 5.0:  # Allow wider range
                is_table = True
                table_type = "rectangular"
            
            if is_table:
                # Check for duplicates (same position)
                is_duplicate = False
                for existing_box in detected_boxes:
                    ex, ey, ew, eh = existing_box
                    # If centers are very close, it's a duplicate
                    center_dist = np.sqrt((x + w/2 - ex - ew/2)**2 + (y + h/2 - ey - eh/2)**2)
                    if center_dist < 20:  # pixels threshold
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    detected_boxes.append((x, y, w, h))
                    
                    # Convert to real-world coordinates
                    real_coords = _pixel_to_real_world(
                        x, y, w, h,
                        img_width, img_height,
                        room_dimensions
                    )
                    
                    # Higher confidence for circular tables
                    confidence = 0.80 if table_type == "circular" else 0.70
                    
                    detected_tables.append({
                        "tableId": f"table_{len(detected_tables) + 1}",
                        "detectionMethod": "shape",
                        "tableType": table_type,
                        "circularity": round(circularity, 2),
                        "pixelCoordinates": {
                            "x": x,
                            "y": y,
                            "width": w,
                            "height": h
                        },
                        "realWorldCoordinates": real_coords,
                        "confidence": confidence
                    })
        
        logger.info(f"✅ Detected {len(detected_tables)} unique tables")
        logger.info(f"📊 Breakdown: {sum(1 for t in detected_tables if t.get('tableType') == 'circular')} circular, "
                   f"{sum(1 for t in detected_tables if t.get('tableType') == 'rectangular')} rectangular")
    
    except Exception as e:
        logger.error(f"❌ Shape detection error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return detected_tables


def _pixel_to_real_world(x: int, y: int, w: int, h: int, 
                          img_width: int, img_height: int, 
                          room_dimensions: Dict) -> Dict:
    """
    Convert pixel coordinates to real-world measurements
    """
    # Room dimensions
    room_length = room_dimensions['length']
    room_width = room_dimensions['width']
    unit = room_dimensions.get('unit', 'meters')
    
    # Calculate scale factors
    scale_x = room_length / img_width
    scale_y = room_width / img_height
    
    # Convert to real-world coordinates
    real_x = x * scale_x
    real_y = y * scale_y
    real_width = w * scale_x
    real_height = h * scale_y
    
    # Calculate center point
    center_x = real_x + (real_width / 2)
    center_y = real_y + (real_height / 2)
    
    return {
        "x": round(real_x, 2),
        "y": round(real_y, 2),
        "width": round(real_width, 2),
        "height": round(real_height, 2),
        "unit": unit,
        "centerPoint": {
            "x": round(center_x, 2),
            "y": round(center_y, 2)
        },
        "area": round(real_width * real_height, 2)
    }


def _draw_annotations(img: np.ndarray, detected_tables: List[Dict]) -> np.ndarray:
    """
    Draw bounding boxes and labels on the floor plan
    """
    circular_count = 0
    rectangular_count = 0
    
    for table in detected_tables:
        pixel_coords = table['pixelCoordinates']
        x = pixel_coords['x']
        y = pixel_coords['y']
        w = pixel_coords['width']
        h = pixel_coords['height']
        
        # Different colors based on detection method and table type
        if table.get('detectionMethod') == 'yolo':
            color = (0, 255, 0)  # Green for YOLO
            label_prefix = "YOLO"
        elif table.get('tableType') == 'circular':
            color = (255, 0, 255)  # Magenta for circular tables (outdoor)
            label_prefix = "Circular"
            circular_count += 1
        elif table.get('tableType') == 'rectangular':
            color = (0, 165, 255)  # Orange for rectangular tables (indoor)
            label_prefix = "Rect"
            rectangular_count += 1
        else:
            color = (128, 128, 128)  # Gray for unknown
            label_prefix = "Table"
        
        # Draw rectangle or circle based on type
        if table.get('tableType') == 'circular':
            # Draw circle for circular tables
            center_x = x + w // 2
            center_y = y + h // 2
            radius = max(w, h) // 2
            cv2.circle(img, (center_x, center_y), radius, color, 3)
        else:
            # Draw rectangle for rectangular tables
            cv2.rectangle(img, (x, y), (x + w, y + h), color, 3)
        
        # Add label
        label = f"{table['tableId']} ({table['confidence']:.0%})"
        
        # Label background
        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
        cv2.rectangle(img, (x, y - label_h - 10), (x + label_w + 10, y), color, -1)
        
        # Label text
        cv2.putText(
            img, label, (x + 5, y - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2
        )
        
        # Draw center point
        real_coords = table['realWorldCoordinates']
        center_x = x + w // 2
        center_y = y + h // 2
        cv2.circle(img, (center_x, center_y), 4, (0, 0, 255), -1)
    
    # Add summary info with breakdown
    y_offset = 30
    summary = f"Total Tables: {len(detected_tables)}"
    cv2.putText(img, summary, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    
    if circular_count > 0:
        y_offset += 30
        cv2.putText(img, f"Circular: {circular_count}", (10, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
    
    if rectangular_count > 0:
        y_offset += 30
        cv2.putText(img, f"Rectangular: {rectangular_count}", (10, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
    
    return img




