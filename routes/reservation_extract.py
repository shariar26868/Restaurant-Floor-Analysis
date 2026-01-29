# # # routes/reservation_extract.py
# # """
# # Reservation Data Extraction Router
# # ===================================
# # Upload image/file → Extract reservation details using OpenAI Vision
# # """

# # from fastapi import APIRouter, UploadFile, File, HTTPException
# # from typing import Dict
# # import logging
# # import base64
# # import json
# # from openai import OpenAI
# # from config import settings

# # # Configure logging
# # logger = logging.getLogger(__name__)

# # # Initialize OpenAI client
# # openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# # # Create router
# # router = APIRouter(prefix="/api/reservation", tags=["Reservation Extract"])


# # @router.post("/extract-details")
# # async def extract_reservation_details(
# #     file: UploadFile = File(...)
# # ) -> Dict:
# #     """
# #     Extract reservation details from uploaded image/document
    
# #     Accepts: Images (jpg, png, pdf) or documents
    
# #     Returns:
# #     {
# #         "success": true,
# #         "data": {
# #             "name": "Naayeem",
# #             "phone": "1712345678",
# #             "partySize": 4,
# #             "arrivalTime": "18:30",
# #             "estimatedWait": 20
# #         }
# #     }
# #     """
# #     try:
# #         logger.info(f"📤 Received file: {file.filename} ({file.content_type})")
        
# #         # Read file content
# #         file_content = await file.read()
        
# #         # Validate file size (max 10MB)
# #         if len(file_content) > 10 * 1024 * 1024:
# #             raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
        
# #         # Extract reservation data using OpenAI Vision
# #         extracted_data = await _extract_with_openai_vision(file_content, file.content_type)
        
# #         logger.info(f"✅ Extraction successful: {extracted_data}")
        
# #         return {
# #             "success": True,
# #             "data": extracted_data
# #         }
        
# #     except HTTPException as e:
# #         raise e
# #     except Exception as e:
# #         logger.error(f"❌ Extraction error: {e}")
# #         import traceback
# #         logger.error(traceback.format_exc())
# #         raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


# # async def _extract_with_openai_vision(
# #     file_content: bytes,
# #     content_type: str
# # ) -> Dict:
# #     """
# #     Use OpenAI Vision to extract reservation details from image
# #     """
    
# #     # Convert to base64
# #     base64_file = base64.b64encode(file_content).decode('utf-8')
    
# #     # Determine media type
# #     if content_type.startswith('image/'):
# #         media_type = content_type
# #     else:
# #         # Default to jpeg for unknown types
# #         media_type = "image/jpeg"
    
# #     # Prompt for OpenAI
# #     prompt = """You are analyzing an image that contains reservation information for a restaurant.

# # **YOUR TASK:** Extract the following reservation details from this image:

# # 1. **name** - Customer's name (string)
# # 2. **phone** - Customer's phone number (string, digits only, no spaces/dashes)
# # 3. **partySize** - Number of people in the party (integer)
# # 4. **arrivalTime** - Arrival/reservation time in 24-hour format HH:MM (string, e.g., "18:30")
# # 5. **estimatedWait** - Estimated wait time in minutes (integer)

# # **IMPORTANT RULES:**
# # - If a field is NOT found in the image, use these defaults:
# #   - name: "Unknown"
# #   - phone: "0000000000"
# #   - partySize: 0
# #   - arrivalTime: "00:00"
# #   - estimatedWait: 0
# # - Phone numbers: Remove all spaces, dashes, and formatting. Just digits.
# # - Time format: Always use 24-hour format (HH:MM). Convert from 12-hour if needed.
# #   - Example: "6:30 PM" → "18:30"
# #   - Example: "10:15 AM" → "10:15"
# # - Wait time: If given in hours, convert to minutes (e.g., "1.5 hours" → 90)

# # **OUTPUT FORMAT:**
# # Return ONLY a JSON object with these exact fields, nothing else:

# # {
# #   "name": "string",
# #   "phone": "string",
# #   "partySize": number,
# #   "arrivalTime": "HH:MM",
# #   "estimatedWait": number
# # }

# # **EXAMPLES:**

# # Image shows: "Reservation for John Doe, party of 4, 7:30 PM, phone: 017-1234-5678"
# # Output:
# # {
# #   "name": "John Doe",
# #   "phone": "01712345678",
# #   "partySize": 4,
# #   "arrivalTime": "19:30",
# #   "estimatedWait": 0
# # }

# # Image shows: "Walk-in: Sarah, 2 people, wait time 30 min, contact: +880 1812345678"
# # Output:
# # {
# #   "name": "Sarah",
# #   "phone": "01812345678",
# #   "partySize": 2,
# #   "arrivalTime": "00:00",
# #   "estimatedWait": 30
# # }

# # Now analyze the provided image and extract the reservation data."""

# #     try:
# #         logger.info("🤖 Calling OpenAI Vision API...")
        
# #         response = openai_client.chat.completions.create(
# #             model="gpt-4o",
# #             messages=[
# #                 {
# #                     "role": "user",
# #                     "content": [
# #                         {"type": "text", "text": prompt},
# #                         {
# #                             "type": "image_url",
# #                             "image_url": {
# #                                 "url": f"data:{media_type};base64,{base64_file}"
# #                             }
# #                         }
# #                     ]
# #                 }
# #             ],
# #             max_tokens=500,
# #             temperature=0.1  # Low temperature for consistent extraction
# #         )
        
# #         content = response.choices[0].message.content.strip()
# #         logger.info(f"📥 OpenAI Response: {content}")
        
# #         # Parse JSON response
# #         if content.startswith("```json"):
# #             content = content.split("```json")[1].split("```")[0].strip()
# #         elif content.startswith("```"):
# #             content = content.split("```")[1].split("```")[0].strip()
        
# #         extracted_data = json.loads(content)
        
# #         # Validate required fields
# #         required_fields = ["name", "phone", "partySize", "arrivalTime", "estimatedWait"]
# #         for field in required_fields:
# #             if field not in extracted_data:
# #                 logger.warning(f"⚠️ Missing field '{field}', using default")
# #                 # Set defaults
# #                 if field == "name":
# #                     extracted_data[field] = "Unknown"
# #                 elif field == "phone":
# #                     extracted_data[field] = "0000000000"
# #                 elif field in ["partySize", "estimatedWait"]:
# #                     extracted_data[field] = 0
# #                 elif field == "arrivalTime":
# #                     extracted_data[field] = "00:00"
        
# #         # Clean phone number (remove non-digits)
# #         if isinstance(extracted_data.get("phone"), str):
# #             extracted_data["phone"] = ''.join(filter(str.isdigit, extracted_data["phone"]))
        
# #         # Ensure correct types
# #         extracted_data["partySize"] = int(extracted_data.get("partySize", 0))
# #         extracted_data["estimatedWait"] = int(extracted_data.get("estimatedWait", 0))
        
# #         return extracted_data
        
# #     except json.JSONDecodeError as e:
# #         logger.error(f"❌ JSON parse error: {e}")
# #         logger.error(f"Response was: {content}")
# #         raise Exception(f"Failed to parse OpenAI response: {e}")
    
# #     except Exception as e:
# #         logger.error(f"❌ OpenAI Vision error: {e}")
# #         import traceback
# #         logger.error(traceback.format_exc())
# #         raise Exception(f"OpenAI Vision extraction failed: {e}")




# """
# Reservation Data Extraction Router
# ===================================
# Upload image/file → Extract reservation details using OpenAI Vision
# """

# from fastapi import APIRouter, UploadFile, File, HTTPException
# from typing import Dict, List
# import logging
# import base64
# import json
# from openai import OpenAI
# from config import settings

# # Configure logging
# logger = logging.getLogger(__name__)

# # Initialize OpenAI client
# openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# # Create router
# router = APIRouter(prefix="/api/reservation", tags=["Reservation Extract"])


# @router.post("/extract-details")
# async def extract_reservation_details(
#     file: UploadFile = File(...)
# ) -> Dict:
#     """
#     Extract reservation details from uploaded image/document
    
#     Accepts: Images (jpg, png, pdf) or documents
    
#     Returns:
#     {
#         "success": true,
#         "data": [
#             {
#                 "name": "Rajib",
#                 "phone": "1712345678",
#                 "partySize": 4,
#                 "arrivalTime": "18:30",
#                 "estimatedWait": 20
#             },
#             {
#                 "name": "Monhob",
#                 "phone": "1898765432",
#                 "partySize": 2,
#                 "arrivalTime": "18:45",
#                 "estimatedWait": 15
#             }
#         ]
#     }
#     """
#     try:
#         logger.info(f"📤 Received file: {file.filename} ({file.content_type})")
        
#         # Read file content
#         file_content = await file.read()
        
#         # Validate file size (max 10MB)
#         if len(file_content) > 10 * 1024 * 1024:
#             raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
        
#         # Extract reservation data using OpenAI Vision
#         extracted_data = await _extract_with_openai_vision(file_content, file.content_type)
        
#         logger.info(f"✅ Extraction successful: Found {len(extracted_data)} reservation(s)")
        
#         return {
#             "success": True,
#             "data": extracted_data
#         }
        
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.error(f"❌ Extraction error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


# async def _extract_with_openai_vision(
#     file_content: bytes,
#     content_type: str
# ) -> List[Dict]:
#     """
#     Use OpenAI Vision to extract reservation details from image
#     Returns a list of reservations (supports multiple reservations in one image)
    
#     Strategy: Two-step process for better accuracy:
#     1. First call: Detailed OCR to extract exact text
#     2. Second call: Parse the OCR text into structured JSON
#     """
    
#     # Convert to base64
#     base64_file = base64.b64encode(file_content).decode('utf-8')
    
#     # Determine media type
#     if content_type.startswith('image/'):
#         media_type = content_type
#     else:
#         # Default to jpeg for unknown types
#         media_type = "image/jpeg"
    
#     # STEP 1: OCR Prompt - Extract exact text from image
#     ocr_prompt = """Look at this image and transcribe EXACTLY what you see.

# If this is a TABLE, output it in this format:
# ```
# ROW 1: [value1] | [value2] | [value3] | [value4] | [value5]
# ROW 2: [value1] | [value2] | [value3] | [value4] | [value5]
# ```

# Read each cell VERY CAREFULLY. Don't skip any rows.
# Focus on getting numbers and digits EXACTLY correct."""

#     try:
#         # === STEP 1: Perform OCR ===
#         logger.info("🤖 Step 1: Performing detailed OCR...")
        
#         ocr_response = openai_client.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": ocr_prompt},
#                         {
#                             "type": "image_url",
#                             "image_url": {
#                                 "url": f"data:{media_type};base64,{base64_file}"
#                             }
#                         }
#                     ]
#                 }
#             ],
#             max_tokens=800,
#             temperature=0.0  # Zero temperature for exact OCR
#         )
        
#         ocr_text = ocr_response.choices[0].message.content.strip()
#         logger.info(f"📝 OCR Result:\n{ocr_text}")
        
#         # === STEP 2: Parse OCR text into structured data ===
#         logger.info("🤖 Step 2: Parsing structured data from OCR...")
        
#         # STEP 2 Prompt - Parse the OCR text
#         parsing_prompt = f"""You are analyzing reservation data that was extracted from an image.

# Here is the EXACT TEXT from the image (OCR result):
# {ocr_text}

# **YOUR TASK:** Parse this text and extract ALL reservations with PERFECT ACCURACY.

# **FIELD MAPPING (common column orders):**
# - Column 1: name
# - Column 2: phone
# - Column 3: arrivalTime (HH:MM format)
# - Column 4: estimatedWait (minutes)
# - Column 5: partySize (number of people)

# **CRITICAL RULES:**
# - Extract EVERY row you see in the OCR text
# - Copy numbers EXACTLY as shown - do NOT change any digits
# - For phone: remove spaces/dashes but keep all digits
# - For time: keep in HH:MM format (e.g., "18:30")
# - For wait time and party size: convert to integers

# **OUTPUT FORMAT (JSON array only):**
# [
#   {{
#     "name": "string",
#     "phone": "string",
#     "partySize": number,
#     "arrivalTime": "HH:MM",
#     "estimatedWait": number
#   }}
# ]

# **EXAMPLE:**
# If OCR shows:
# ```
# ROW 1: Rajib | 1712345678 | 18:30 | 20 | 4
# ROW 2: Monhob | 1898765432 | 18:45 | 15 | 2
# ```

# Output:
# [
#   {{"name": "Rajib", "phone": "1712345678", "partySize": 4, "arrivalTime": "18:30", "estimatedWait": 20}},
#   {{"name": "Monhob", "phone": "1898765432", "partySize": 2, "arrivalTime": "18:45", "estimatedWait": 15}}
# ]

# Now parse the OCR text above and output the JSON array."""
        
#         parsing_response = openai_client.chat.completions.create(
#             model="gpt-4o",
#             messages=[
#                 {
#                     "role": "user",
#                     "content": parsing_prompt
#                 }
#             ],
#             max_tokens=1000,
#             temperature=0.1
#         )
        
#         content = parsing_response.choices[0].message.content.strip()
#         logger.info(f"📥 Structured Response: {content}")
        
#         # Parse JSON response
#         if content.startswith("```json"):
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif content.startswith("```"):
#             content = content.split("```")[1].split("```")[0].strip()
        
#         extracted_data = json.loads(content)
        
#         # Ensure it's a list
#         if not isinstance(extracted_data, list):
#             # If OpenAI returned a single object instead of array, wrap it
#             extracted_data = [extracted_data]
        
#         # Validate and clean each reservation
#         for reservation in extracted_data:
#             # Validate required fields
#             required_fields = ["name", "phone", "partySize", "arrivalTime", "estimatedWait"]
#             for field in required_fields:
#                 if field not in reservation:
#                     logger.warning(f"⚠️ Missing field '{field}', using default")
#                     # Set defaults
#                     if field == "name":
#                         reservation[field] = "Unknown"
#                     elif field == "phone":
#                         reservation[field] = "0000000000"
#                     elif field in ["partySize", "estimatedWait"]:
#                         reservation[field] = 0
#                     elif field == "arrivalTime":
#                         reservation[field] = "00:00"
            
#             # Clean phone number (remove non-digits)
#             if isinstance(reservation.get("phone"), str):
#                 reservation["phone"] = ''.join(filter(str.isdigit, reservation["phone"]))
            
#             # Ensure correct types
#             reservation["partySize"] = int(reservation.get("partySize", 0))
#             reservation["estimatedWait"] = int(reservation.get("estimatedWait", 0))
        
#         logger.info(f"✅ Successfully extracted {len(extracted_data)} reservation(s)")
#         return extracted_data
        
#     except json.JSONDecodeError as e:
#         logger.error(f"❌ JSON parse error: {e}")
#         logger.error(f"Response was: {content}")
#         raise Exception(f"Failed to parse OpenAI response: {e}")
    
#     except Exception as e:
#         logger.error(f"❌ OpenAI Vision error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         raise Exception(f"OpenAI Vision extraction failed: {e}")








# """
# Reservation Data Extraction Router - With Structured Outputs
# ============================================================
# Upload image/file → Extract reservation details using OpenAI Vision + Structured Outputs
# """

# from fastapi import APIRouter, UploadFile, File, HTTPException
# from typing import Dict, List
# import logging
# import base64
# import json
# from openai import OpenAI
# from config import settings
# from pydantic import BaseModel

# # Configure logging
# logger = logging.getLogger(__name__)

# # Initialize OpenAI client
# openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# # Create router
# router = APIRouter(prefix="/api/reservation", tags=["Reservation Extract"])


# # Pydantic model for structured output
# class ReservationItem(BaseModel):
#     name: str
#     phone: str
#     arrivalTime: str
#     estimatedWait: int
#     partySize: int


# class ReservationList(BaseModel):
#     reservations: List[ReservationItem]


# @router.post("/extract-details")
# async def extract_reservation_details(
#     file: UploadFile = File(...)
# ) -> Dict:
#     """
#     Extract reservation details from uploaded image/document
    
#     Uses OpenAI structured outputs for guaranteed correct field mapping
#     """
#     try:
#         logger.info(f"📤 Received file: {file.filename} ({file.content_type})")
        
#         # Read file content
#         file_content = await file.read()
        
#         # Validate file size (max 10MB)
#         if len(file_content) > 10 * 1024 * 1024:
#             raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
        
#         # Extract reservation data
#         extracted_data = await _extract_with_structured_output(file_content, file.content_type)
        
#         logger.info(f"✅ Extraction successful: Found {len(extracted_data)} reservation(s)")
        
#         return {
#             "success": True,
#             "data": extracted_data
#         }
        
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.error(f"❌ Extraction error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


# async def _extract_with_structured_output(
#     file_content: bytes,
#     content_type: str
# ) -> List[Dict]:
#     """
#     Extract using structured outputs - most reliable method
#     """
    
#     # Convert to base64
#     base64_file = base64.b64encode(file_content).decode('utf-8')
    
#     # Determine media type
#     if content_type.startswith('image/'):
#         media_type = content_type
#     else:
#         media_type = "image/jpeg"
    
#     extraction_prompt = """Extract ALL reservation data from this table image.

# **CRITICAL INSTRUCTIONS:**

# 1. **READ THE TABLE HEADERS FIRST** to understand column order
#    - Common orders: name | phone | arrivalTime | estimatedWait | partySize
#    - OR: name | phone | arrivalTime | partySize | estimatedWait

# 2. **FOR EACH ROW:**
#    - Read values from LEFT to RIGHT
#    - Match each value to its column header position
#    - Extract EXACTLY what you see

# 3. **FIELD IDENTIFICATION:**
#    - name: Person's full name
#    - phone: 10-digit number
#    - arrivalTime: Time in HH:MM format (e.g., "20:35")
#    - estimatedWait: Wait time in minutes (usually 10-60)
#    - partySize: Number of people (usually 1-10)

# 4. **CRITICAL: DO NOT GUESS COLUMN ORDER**
#    - If header says "estimatedWait" is column 4, then column 4 value IS estimatedWait
#    - If header says "partySize" is column 5, then column 5 value IS partySize
#    - Read headers → Map values → Extract

# 5. **EXAMPLES:**

# If table shows:
# ```
# Headers: name | phone | arrivalTime | estimatedWait | partySize
# Row:     Isabella White | 1812398765 | 20:35 | 15 | 3
# ```

# Then extract:
# - name: "Isabella White"
# - phone: "1812398765"
# - arrivalTime: "20:35"
# - estimatedWait: 15
# - partySize: 3

# If table shows:
# ```
# Headers: name | phone | arrivalTime | estimatedWait | partySize
# Row:     Alexander Young | 1912765438 | 21:45 | 20 | 4
# ```

# Then extract:
# - name: "Alexander Young"
# - phone: "1912765438"
# - arrivalTime: "21:45"
# - estimatedWait: 20
# - partySize: 4

# Extract ALL rows and return them in the structured format."""

#     try:
#         logger.info("🤖 Using structured output extraction...")
        
#         # Using beta parse method for structured outputs
#         completion = openai_client.beta.chat.completions.parse(
#             model="gpt-4o",
#             messages=[
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": extraction_prompt},
#                         {
#                             "type": "image_url",
#                             "image_url": {
#                                 "url": f"data:{media_type};base64,{base64_file}"
#                             }
#                         }
#                     ]
#                 }
#             ],
#             response_format=ReservationList,
#             temperature=0.0
#         )
        
#         # Get structured output
#         reservation_list = completion.choices[0].message.parsed
        
#         # Convert to list of dicts
#         extracted_data = []
#         for res in reservation_list.reservations:
#             data = {
#                 "name": res.name,
#                 "phone": ''.join(filter(str.isdigit, res.phone)),  # Clean phone
#                 "arrivalTime": res.arrivalTime,
#                 "estimatedWait": res.estimatedWait,
#                 "partySize": res.partySize
#             }
            
#             logger.info(f"✓ {data['name']}: party={data['partySize']}, wait={data['estimatedWait']}")
            
#             # Apply light validation (only for extreme errors)
#             if data["partySize"] > 30 or data["estimatedWait"] <= 3:
#                 logger.warning(f"⚠️ Possible swap detected for {data['name']}, swapping values")
#                 data["partySize"], data["estimatedWait"] = data["estimatedWait"], data["partySize"]
            
#             # Bounds check
#             if data["partySize"] < 1:
#                 data["partySize"] = 1
#             if data["partySize"] > 20:
#                 data["partySize"] = 20
#             if data["estimatedWait"] < 5:
#                 data["estimatedWait"] = 10
#             if data["estimatedWait"] > 120:
#                 data["estimatedWait"] = 60
            
#             extracted_data.append(data)
        
#         logger.info(f"✅ Extracted {len(extracted_data)} reservations with structured output")
#         return extracted_data
        
#     except Exception as e:
#         logger.error(f"❌ Structured extraction failed, falling back to JSON mode")
#         logger.error(f"Error: {e}")
        
#         # Fallback to regular JSON extraction
#         return await _extract_fallback(file_content, media_type)


# async def _extract_fallback(file_content: bytes, media_type: str) -> List[Dict]:
#     """Fallback extraction using regular JSON mode"""
    
#     base64_file = base64.b64encode(file_content).decode('utf-8')
    
#     prompt = """Extract reservation data. Return JSON array:
# [{"name":"...", "phone":"...", "arrivalTime":"HH:MM", "estimatedWait":number, "partySize":number}]

# Read table LEFT TO RIGHT. Match values to column headers exactly."""
    
#     response = openai_client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {
#                 "role": "user",
#                 "content": [
#                     {"type": "text", "text": prompt},
#                     {
#                         "type": "image_url",
#                         "image_url": {
#                             "url": f"data:{media_type};base64,{base64_file}"
#                         }
#                     }
#                 ]
#             }
#         ],
#         max_tokens=2000,
#         temperature=0.0
#     )
    
#     content = response.choices[0].message.content.strip()
    
#     # Clean JSON
#     if "```json" in content:
#         content = content.split("```json")[1].split("```")[0].strip()
#     elif "```" in content:
#         content = content.split("```")[1].split("```")[0].strip()
    
#     data = json.loads(content)
    
#     if not isinstance(data, list):
#         data = [data]
    
#     # Clean up
#     for item in data:
#         if "phone" in item:
#             item["phone"] = ''.join(filter(str.isdigit, str(item["phone"])))
#         if "partySize" not in item:
#             item["partySize"] = 2
#         if "estimatedWait" not in item:
#             item["estimatedWait"] = 15
        
#         item["partySize"] = int(item.get("partySize", 2))
#         item["estimatedWait"] = int(item.get("estimatedWait", 15))
    
#     return data






"""
Reservation Data Extraction Router - GEMINI (AUTO-DETECT VERSION)
==================================================================
Automatically detects and uses the correct Gemini model
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict, List, Optional
import logging
import json
import google.generativeai as genai
from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

# Create router
router = APIRouter(prefix="/api/reservation", tags=["Reservation Extract"])

# Cache for detected model
_vision_model_cache: Optional[str] = None


def _get_vision_model_name() -> str:
    """
    Auto-detect the correct Gemini vision model name
    
    Returns: Model name that supports vision
    """
    global _vision_model_cache
    
    # Return cached if available
    if _vision_model_cache:
        return _vision_model_cache
    
    logger.info("🔍 Auto-detecting Gemini vision model...")
    
    try:
        # Priority list of possible model names (newest first)
        possible_models = [
            'gemini-1.5-pro-latest',
            'gemini-1.5-pro',
            'gemini-1.5-flash-latest',
            'gemini-1.5-flash',
            'gemini-pro-vision',
            'models/gemini-1.5-pro-latest',
            'models/gemini-1.5-pro',
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-flash',
            'models/gemini-pro-vision',
        ]
        
        # Get list of available models
        available_models = {}
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                available_models[model.name] = model
                # Also add without 'models/' prefix
                short_name = model.name.replace('models/', '')
                available_models[short_name] = model
        
        logger.info(f"📋 Found {len(available_models)} available models")
        
        # Try each possible model in priority order
        for model_name in possible_models:
            if model_name in available_models:
                _vision_model_cache = model_name
                logger.info(f"✅ Using vision model: {model_name}")
                return model_name
        
        # If no known model found, use the first available one
        if available_models:
            first_model = list(available_models.keys())[0]
            _vision_model_cache = first_model
            logger.warning(f"⚠️ Using fallback model: {first_model}")
            return first_model
        
        # No models available at all
        raise Exception("No Gemini models available for your API key")
        
    except Exception as e:
        logger.error(f"❌ Model detection failed: {e}")
        # Last resort fallback
        return 'gemini-1.5-pro-latest'


@router.post("/extract-details")
async def extract_reservation_details(
    file: UploadFile = File(...)
) -> Dict:
    """
    Extract reservation details from uploaded image/document
    
    Accepts: Images (jpg, png, pdf) or documents
    
    Returns:
    {
        "success": true,
        "data": [...]
    }
    """
    try:
        logger.info(f"📤 Received file: {file.filename} ({file.content_type})")
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size (max 10MB)
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
        
        # Extract reservation data
        extracted_data = await _extract_with_gemini_vision(file_content, file.content_type)
        
        logger.info(f"✅ Extraction successful: Found {len(extracted_data)} reservation(s)")
        
        return {
            "success": True,
            "data": extracted_data
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Extraction error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


async def _extract_with_gemini_vision(
    file_content: bytes,
    content_type: str
) -> List[Dict]:
    """
    Use Google Gemini Vision to extract reservation details
    
    Auto-detects correct model and handles the extraction
    """
    
    try:
        # Get correct vision model
        model_name = _get_vision_model_name()
        model = genai.GenerativeModel(model_name)
        
        # Prepare image
        import io
        from PIL import Image
        image = Image.open(io.BytesIO(file_content))
        
        logger.info(f"🤖 Using Gemini model: {model_name}")
        
        # === COMBINED APPROACH: Single-step extraction ===
        # (More reliable than 2-step for some models)
        
        extraction_prompt = """Analyze this image which contains a restaurant reservation table.

Extract ALL reservations you see and return them as a JSON array.

**FIELD MAPPING:**
- name: Customer name
- phone: Phone number (digits only, no spaces/dashes)
- partySize: Number of people (integer)
- arrivalTime: Time in HH:MM format (24-hour, e.g. "18:30")
- estimatedWait: Wait time in minutes (integer)

**RULES:**
1. Extract EVERY row you see
2. Copy numbers EXACTLY - don't change digits
3. Remove spaces/dashes from phone numbers
4. Convert times to 24-hour format:
   - "6:30 PM" → "18:30"
   - "10:15 AM" → "10:15"
5. Convert wait times to minutes (e.g., "1.5 hours" → 90)

**OUTPUT (JSON array only, no explanation):**
[
  {
    "name": "string",
    "phone": "string (digits only)",
    "partySize": number,
    "arrivalTime": "HH:MM",
    "estimatedWait": number
  }
]

**EXAMPLE:**
If image shows:
Row 1: Rajib | 017-1234-5678 | 6:30 PM | 20 min | 4 people
Row 2: Monhob | 018 9876 5432 | 6:45 PM | 15 | 2

Output:
[
  {"name": "Rajib", "phone": "01712345678", "partySize": 4, "arrivalTime": "18:30", "estimatedWait": 20},
  {"name": "Monhob", "phone": "01898765432", "partySize": 2, "arrivalTime": "18:45", "estimatedWait": 15}
]

Now analyze the image and extract the reservations."""

        response = model.generate_content([extraction_prompt, image])
        content = response.text.strip()
        
        logger.info(f"📥 Gemini Response:\n{content[:500]}...")
        
        # Clean response
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        extracted_data = json.loads(content)
        
        # Ensure it's a list
        if not isinstance(extracted_data, list):
            extracted_data = [extracted_data]
        
        # Validate and clean each reservation
        for idx, reservation in enumerate(extracted_data, 1):
            logger.info(f"📋 Processing reservation {idx}: {reservation.get('name', 'Unknown')}")
            
            # Required fields with defaults
            required_fields = {
                "name": "Unknown",
                "phone": "0000000000",
                "partySize": 0,
                "arrivalTime": "00:00",
                "estimatedWait": 0
            }
            
            for field, default in required_fields.items():
                if field not in reservation or reservation[field] is None:
                    logger.warning(f"⚠️ Missing field '{field}', using default: {default}")
                    reservation[field] = default
            
            # Clean phone number (digits only)
            if isinstance(reservation.get("phone"), str):
                reservation["phone"] = ''.join(filter(str.isdigit, reservation["phone"]))
            
            # Ensure correct types
            try:
                reservation["partySize"] = int(reservation.get("partySize", 0))
                reservation["estimatedWait"] = int(reservation.get("estimatedWait", 0))
            except (ValueError, TypeError) as e:
                logger.warning(f"⚠️ Type conversion error: {e}")
                reservation["partySize"] = 0
                reservation["estimatedWait"] = 0
            
            # Validate time format
            arrival_time = str(reservation.get("arrivalTime", "00:00"))
            if not _is_valid_time_format(arrival_time):
                logger.warning(f"⚠️ Invalid time '{arrival_time}', using '00:00'")
                reservation["arrivalTime"] = "00:00"
        
        logger.info(f"✅ Extracted {len(extracted_data)} reservation(s)")
        return extracted_data
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        logger.error(f"Content was: {content}")
        raise Exception(f"Failed to parse response as JSON: {e}")
    
    except Exception as e:
        logger.error(f"❌ Gemini error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise Exception(f"Gemini extraction failed: {e}")


def _is_valid_time_format(time_str: str) -> bool:
    """Validate HH:MM time format"""
    if not isinstance(time_str, str):
        return False
    
    parts = time_str.split(":")
    if len(parts) != 2:
        return False
    
    try:
        hour, minute = int(parts[0]), int(parts[1])
        return 0 <= hour <= 23 and 0 <= minute <= 59
    except ValueError:
        return False