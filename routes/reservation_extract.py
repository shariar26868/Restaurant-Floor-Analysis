# """
# Reservation Data Extraction Router - GEMINI (AUTO-DETECT VERSION)
# ==================================================================
# Automatically detects and uses the correct Gemini model
# """

# from fastapi import APIRouter, UploadFile, File, HTTPException
# from typing import Dict, List, Optional
# import logging
# import json
# import google.generativeai as genai
# from config import settings

# # Configure logging
# logger = logging.getLogger(__name__)

# # Initialize Gemini
# genai.configure(api_key=settings.GEMINI_API_KEY)

# # Create router
# router = APIRouter(prefix="/api/reservation", tags=["Reservation Extract"])

# # Cache for detected model
# _vision_model_cache: Optional[str] = None


# def _get_vision_model_name() -> str:
#     """
#     Auto-detect the correct Gemini vision model name
    
#     Returns: Model name that supports vision
#     """
#     global _vision_model_cache
    
#     # Return cached if available
#     if _vision_model_cache:
#         return _vision_model_cache
    
#     logger.info("🔍 Auto-detecting Gemini vision model...")
    
#     try:
#         # Priority list of possible model names (newest first)
#         possible_models = [
#             'gemini-1.5-pro-latest',
#             'gemini-1.5-pro',
#             'gemini-1.5-flash-latest',
#             'gemini-1.5-flash',
#             'gemini-pro-vision',
#             'models/gemini-1.5-pro-latest',
#             'models/gemini-1.5-pro',
#             'models/gemini-1.5-flash-latest',
#             'models/gemini-1.5-flash',
#             'models/gemini-pro-vision',
#         ]
        
#         # Get list of available models
#         available_models = {}
#         for model in genai.list_models():
#             if 'generateContent' in model.supported_generation_methods:
#                 available_models[model.name] = model
#                 # Also add without 'models/' prefix
#                 short_name = model.name.replace('models/', '')
#                 available_models[short_name] = model
        
#         logger.info(f"📋 Found {len(available_models)} available models")
        
#         # Try each possible model in priority order
#         for model_name in possible_models:
#             if model_name in available_models:
#                 _vision_model_cache = model_name
#                 logger.info(f"✅ Using vision model: {model_name}")
#                 return model_name
        
#         # If no known model found, use the first available one
#         if available_models:
#             first_model = list(available_models.keys())[0]
#             _vision_model_cache = first_model
#             logger.warning(f"⚠️ Using fallback model: {first_model}")
#             return first_model
        
#         # No models available at all
#         raise Exception("No Gemini models available for your API key")
        
#     except Exception as e:
#         logger.error(f"❌ Model detection failed: {e}")
#         # Last resort fallback
#         return 'gemini-1.5-pro-latest'


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
#         "data": [...]
#     }
#     """
#     try:
#         logger.info(f"📤 Received file: {file.filename} ({file.content_type})")
        
#         # Read file content
#         file_content = await file.read()
        
#         # Validate file size (max 10MB)
#         if len(file_content) > 10 * 1024 * 1024:
#             raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
        
#         # Extract reservation data
#         extracted_data = await _extract_with_gemini_vision(file_content, file.content_type)
        
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


# async def _extract_with_gemini_vision(
#     file_content: bytes,
#     content_type: str
# ) -> List[Dict]:
#     """
#     Use Google Gemini Vision to extract reservation details
    
#     Auto-detects correct model and handles the extraction
#     """
    
#     try:
#         # Get correct vision model
#         model_name = _get_vision_model_name()
#         model = genai.GenerativeModel(model_name)
        
#         # Prepare image
#         import io
#         from PIL import Image
#         image = Image.open(io.BytesIO(file_content))
        
#         logger.info(f"🤖 Using Gemini model: {model_name}")
        
#         # === COMBINED APPROACH: Single-step extraction ===
#         # (More reliable than 2-step for some models)
        
#         extraction_prompt = """Analyze this image which contains a restaurant reservation table.

# Extract ALL reservations you see and return them as a JSON array.

# **FIELD MAPPING:**
# - name: Customer name
# - phone: Phone number (digits only, no spaces/dashes)
# - partySize: Number of people (integer)
# - arrivalTime: Time in HH:MM format (24-hour, e.g. "18:30")
# - estimatedWait: Wait time in minutes (integer)

# **RULES:**
# 1. Extract EVERY row you see
# 2. Copy numbers EXACTLY - don't change digits
# 3. Remove spaces/dashes from phone numbers
# 4. Convert times to 24-hour format:
#    - "6:30 PM" → "18:30"
#    - "10:15 AM" → "10:15"
# 5. Convert wait times to minutes (e.g., "1.5 hours" → 90)

# **OUTPUT (JSON array only, no explanation):**
# [
#   {
#     "name": "string",
#     "phone": "string (digits only)",
#     "partySize": number,
#     "arrivalTime": "HH:MM",
#     "estimatedWait": number
#   }
# ]

# **EXAMPLE:**
# If image shows:
# Row 1: Rajib | 017-1234-5678 | 6:30 PM | 20 min | 4 people
# Row 2: Monhob | 018 9876 5432 | 6:45 PM | 15 | 2

# Output:
# [
#   {"name": "Rajib", "phone": "01712345678", "partySize": 4, "arrivalTime": "18:30", "estimatedWait": 20},
#   {"name": "Monhob", "phone": "01898765432", "partySize": 2, "arrivalTime": "18:45", "estimatedWait": 15}
# ]

# Now analyze the image and extract the reservations."""

#         response = model.generate_content([extraction_prompt, image])
#         content = response.text.strip()
        
#         logger.info(f"📥 Gemini Response:\n{content[:500]}...")
        
#         # Clean response
#         if content.startswith("```json"):
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif content.startswith("```"):
#             content = content.split("```")[1].split("```")[0].strip()
        
#         # Parse JSON
#         extracted_data = json.loads(content)
        
#         # Ensure it's a list
#         if not isinstance(extracted_data, list):
#             extracted_data = [extracted_data]
        
#         # Validate and clean each reservation
#         for idx, reservation in enumerate(extracted_data, 1):
#             logger.info(f"📋 Processing reservation {idx}: {reservation.get('name', 'Unknown')}")
            
#             # Required fields with defaults
#             required_fields = {
#                 "name": "Unknown",
#                 "phone": "0000000000",
#                 "partySize": 0,
#                 "arrivalTime": "00:00",
#                 "estimatedWait": 0
#             }
            
#             for field, default in required_fields.items():
#                 if field not in reservation or reservation[field] is None:
#                     logger.warning(f"⚠️ Missing field '{field}', using default: {default}")
#                     reservation[field] = default
            
#             # Clean phone number (digits only)
#             if isinstance(reservation.get("phone"), str):
#                 reservation["phone"] = ''.join(filter(str.isdigit, reservation["phone"]))
            
#             # Ensure correct types
#             try:
#                 reservation["partySize"] = int(reservation.get("partySize", 0))
#                 reservation["estimatedWait"] = int(reservation.get("estimatedWait", 0))
#             except (ValueError, TypeError) as e:
#                 logger.warning(f"⚠️ Type conversion error: {e}")
#                 reservation["partySize"] = 0
#                 reservation["estimatedWait"] = 0
            
#             # Validate time format
#             arrival_time = str(reservation.get("arrivalTime", "00:00"))
#             if not _is_valid_time_format(arrival_time):
#                 logger.warning(f"⚠️ Invalid time '{arrival_time}', using '00:00'")
#                 reservation["arrivalTime"] = "00:00"
        
#         logger.info(f"✅ Extracted {len(extracted_data)} reservation(s)")
#         return extracted_data
        
#     except json.JSONDecodeError as e:
#         logger.error(f"❌ JSON parse error: {e}")
#         logger.error(f"Content was: {content}")
#         raise Exception(f"Failed to parse response as JSON: {e}")
    
#     except Exception as e:
#         logger.error(f"❌ Gemini error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         raise Exception(f"Gemini extraction failed: {e}")


# def _is_valid_time_format(time_str: str) -> bool:
#     """Validate HH:MM time format"""
#     if not isinstance(time_str, str):
#         return False
    
#     parts = time_str.split(":")
#     if len(parts) != 2:
#         return False
    
#     try:
#         hour, minute = int(parts[0]), int(parts[1])
#         return 0 <= hour <= 23 and 0 <= minute <= 59
#     except ValueError:
#         return False







"""
Reservation Data Extraction Router - GEMINI (CIRCLE DETECTION + DYNAMIC COLUMNS)
================================================================================
Features:
- Detects circles around names (any color) for meal type classification
- Accepts dynamic column headers from any uploaded file
- Auto-detects correct Gemini model
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict, List, Optional, Any
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
    
    Features:
    - Detects circles around names (any color) → marks as "halfboard"
    - Names without circles → marks as "breakfast"
    - Accepts ANY column headers dynamically
    
    Accepts: Images (jpg, png, pdf) or documents
    
    Returns:
    {
        "success": true,
        "columns": ["name", "phone", "arrivalTime", ...],
        "data": [
            {
                "name": "John Doe",
                "phone": "1234567890",
                "mealType": "halfboard",  // if circled
                ...other dynamic fields
            }
        ]
    }
    """
    try:
        logger.info(f"📤 Received file: {file.filename} ({file.content_type})")
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size (max 10MB)
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
        
        # Extract reservation data with circle detection
        result = await _extract_with_gemini_vision(file_content, file.content_type)
        
        logger.info(f"✅ Extraction successful: Found {len(result['data'])} reservation(s)")
        logger.info(f"📋 Detected columns: {result['columns']}")
        
        return {
            "success": True,
            "columns": result["columns"],
            "data": result["data"]
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
) -> Dict[str, Any]:
    """
    Use Google Gemini Vision to extract reservation details with circle detection
    
    Returns:
    {
        "columns": [...],
        "data": [...]
    }
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
        
        # === ENHANCED PROMPT: Circle Detection + Dynamic Columns ===
        
        extraction_prompt = """Analyze this restaurant reservation table image carefully.

**TASK 1: Detect Column Headers**
First, identify ALL column headers in the table (e.g., name, phone, arrivalTime, partySize, etc.)
The columns can have ANY names - extract them exactly as they appear.

**TASK 2: Detect Visual Markers (CRITICAL)**
Look for circles, highlights, or marks around customer names:
- ✅ If a name has a CIRCLE (red, black, blue, or ANY color) → mealType: "halfboard"
- ❌ If a name has NO circle → mealType: "breakfast"

**TASK 3: Extract Data**
For each row, extract all column values AND add the mealType field.

**DATA CLEANING RULES:**
1. Phone numbers: Remove all spaces, dashes, brackets (keep digits only)
2. Times: Convert to 24-hour HH:MM format
   - "6:30 PM" → "18:30"
   - "10:15 AM" → "10:15"
3. Wait times: Convert to minutes (integer)
   - "1.5 hours" → 90
   - "30 min" → 30
4. Party size: Convert to integer
5. Copy all other fields exactly as they appear

**OUTPUT FORMAT (JSON only, no explanation):**
{
  "columns": ["column1", "column2", ...],  // All detected columns
  "data": [
    {
      "column1": "value1",
      "column2": "value2",
      "mealType": "halfboard" or "breakfast",  // ALWAYS include this
      ...
    }
  ]
}

**EXAMPLE INPUT:**
Table with columns: name, phone, time, wait, guests
- Row 1: "John Doe" (circled in red) | 017-1234-5678 | 6:30 PM | 20 min | 4
- Row 2: "Jane Smith" (no circle) | 018 9876 5432 | 7:00 PM | 15 min | 2

**EXAMPLE OUTPUT:**
{
  "columns": ["name", "phone", "time", "wait", "guests"],
  "data": [
    {
      "name": "John Doe",
      "phone": "01712345678",
      "time": "18:30",
      "wait": 20,
      "guests": 4,
      "mealType": "halfboard"
    },
    {
      "name": "Jane Smith",
      "phone": "01898765432",
      "time": "19:00",
      "wait": 15,
      "guests": 2,
      "mealType": "breakfast"
    }
  ]
}

**IMPORTANT:**
- Look VERY carefully for circles/marks around names
- Even faint or partial circles count
- Circle color doesn't matter (red, black, blue, any color)
- If uncertain, default to "breakfast"
- Extract ALL rows you see
- Include mealType for EVERY reservation

Now analyze the image and extract the reservations with meal types."""

        response = model.generate_content([extraction_prompt, image])
        content = response.text.strip()
        
        logger.info(f"📥 Gemini Response (first 500 chars):\n{content[:500]}...")
        
        # Clean response (remove markdown code blocks)
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        result = json.loads(content)
        
        # Validate structure
        if not isinstance(result, dict):
            raise ValueError("Response must be a JSON object with 'columns' and 'data'")
        
        if "columns" not in result or "data" not in result:
            raise ValueError("Response must contain 'columns' and 'data' keys")
        
        if not isinstance(result["data"], list):
            raise ValueError("'data' must be a list")
        
        columns = result["columns"]
        reservations = result["data"]
        
        logger.info(f"📊 Detected {len(columns)} columns: {columns}")
        logger.info(f"📋 Found {len(reservations)} reservations")
        
        # Process and validate each reservation
        for idx, reservation in enumerate(reservations, 1):
            name = reservation.get("name") or reservation.get(columns[0]) if columns else "Unknown"
            logger.info(f"🔍 Processing reservation {idx}: {name}")
            
            # Ensure mealType exists
            if "mealType" not in reservation:
                logger.warning(f"⚠️ No mealType detected for {name}, defaulting to 'breakfast'")
                reservation["mealType"] = "breakfast"
            
            # Validate mealType value
            if reservation["mealType"] not in ["halfboard", "breakfast"]:
                logger.warning(f"⚠️ Invalid mealType '{reservation['mealType']}' for {name}, defaulting to 'breakfast'")
                reservation["mealType"] = "breakfast"
            
            # Clean phone number if present
            for key in reservation.keys():
                if "phone" in key.lower() and isinstance(reservation[key], str):
                    reservation[key] = ''.join(filter(str.isdigit, reservation[key]))
                    logger.debug(f"  📞 Cleaned phone: {reservation[key]}")
            
            # Log meal type
            meal_emoji = "🍽️" if reservation["mealType"] == "halfboard" else "🥐"
            logger.info(f"  {meal_emoji} Meal type: {reservation['mealType']}")
        
        # Count meal types
        halfboard_count = sum(1 for r in reservations if r.get("mealType") == "halfboard")
        breakfast_count = sum(1 for r in reservations if r.get("mealType") == "breakfast")
        
        logger.info(f"✅ Extraction complete:")
        logger.info(f"   🍽️  Halfboard (circled): {halfboard_count}")
        logger.info(f"   🥐 Breakfast (no circle): {breakfast_count}")
        
        return {
            "columns": columns,
            "data": reservations
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        logger.error(f"Raw content:\n{content}")
        raise Exception(f"Failed to parse Gemini response as JSON: {e}")
    
    except Exception as e:
        logger.error(f"❌ Gemini extraction error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise Exception(f"Gemini extraction failed: {e}")


# Optional: Endpoint to get extraction statistics
@router.get("/stats")
async def get_extraction_stats():
    """
    Get information about the extraction service
    """
    model_name = _get_vision_model_name()
    
    return {
        "service": "Reservation Data Extraction",
        "model": model_name,
        "features": [
            "Circle detection for meal type classification",
            "Dynamic column header detection",
            "Multi-color circle support (red, black, blue, any color)",
            "Automatic phone number cleaning",
            "Time format normalization"
        ],
        "meal_types": {
            "halfboard": "Names with circles (any color) - for dinner table management",
            "breakfast": "Names without circles - for setting tables after dinner"
        }
    }