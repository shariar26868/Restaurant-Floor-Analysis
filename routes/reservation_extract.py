

# #####eta khub valu##able file#####

# """
# Reservation Data Extraction Router - GEMINI (CIRCLE DETECTION + DYNAMIC COLUMNS)
# ================================================================================
# Features:
# - Detects circles around names (any color) for meal type classification
# - Accepts dynamic column headers from any uploaded file
# - Auto-detects correct Gemini model
# """

# from fastapi import APIRouter, UploadFile, File, HTTPException
# from typing import Dict, List, Optional, Any
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
    
#     Features:
#     - Detects circles around names (any color) → marks as "halfboard"
#     - Names without circles → marks as "breakfast"
#     - Accepts ANY column headers dynamically
    
#     Accepts: Images (jpg, png, pdf) or documents
    
#     Returns:
#     {
#         "success": true,
#         "columns": ["name", "phone", "arrivalTime", ...],
#         "data": [
#             {
#                 "name": "John Doe",
#                 "phone": "1234567890",
#                 "mealType": "halfboard",  // if circled
#                 ...other dynamic fields
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
        
#         # Extract reservation data with circle detection
#         result = await _extract_with_gemini_vision(file_content, file.content_type)
        
#         logger.info(f"✅ Extraction successful: Found {len(result['data'])} reservation(s)")
#         logger.info(f"📋 Detected columns: {result['columns']}")
        
#         return {
#             "success": True,
#             "columns": result["columns"],
#             "data": result["data"]
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
# ) -> Dict[str, Any]:
#     """
#     Use Google Gemini Vision to extract reservation details with circle detection
    
#     Returns:
#     {
#         "columns": [...],
#         "data": [...]
#     }
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
        
#         # === ENHANCED PROMPT: Circle Detection + Dynamic Columns ===
        
#         extraction_prompt = """Analyze this restaurant reservation table image carefully.

# **TASK 1: Detect Column Headers**
# First, identify ALL column headers in the table (e.g., name, phone, arrivalTime, partySize, etc.)
# The columns can have ANY names - extract them exactly as they appear.

# **TASK 2: Detect Visual Markers (CRITICAL)**
# Look for circles, highlights, or marks around customer names:
# - ✅ If a name has a CIRCLE (red, black, blue, or ANY color) → mealType: "halfboard"
# - ❌ If a name has NO circle → mealType: "breakfast"

# **TASK 3: Extract Data**
# For each row, extract all column values AND add the mealType field.

# **DATA CLEANING RULES:**
# 1. Phone numbers: Remove all spaces, dashes, brackets (keep digits only)
# 2. Times: Convert to 24-hour HH:MM format
#    - "6:30 PM" → "18:30"
#    - "10:15 AM" → "10:15"
# 3. Wait times: Convert to minutes (integer)
#    - "1.5 hours" → 90
#    - "30 min" → 30
# 4. Party size: Convert to integer
# 5. Copy all other fields exactly as they appear

# **OUTPUT FORMAT (JSON only, no explanation):**
# {
#   "columns": ["column1", "column2", ...],  // All detected columns
#   "data": [
#     {
#       "column1": "value1",
#       "column2": "value2",
#       "mealType": "halfboard" or "breakfast",  // ALWAYS include this
#       ...
#     }
#   ]
# }

# **EXAMPLE INPUT:**
# Table with columns: name, phone, time, wait, guests
# - Row 1: "John Doe" (circled in red) | 017-1234-5678 | 6:30 PM | 20 min | 4
# - Row 2: "Jane Smith" (no circle) | 018 9876 5432 | 7:00 PM | 15 min | 2

# **EXAMPLE OUTPUT:**
# {
#   "columns": ["name", "phone", "time", "wait", "guests"],
#   "data": [
#     {
#       "name": "John Doe",
#       "phone": "01712345678",
#       "time": "18:30",
#       "wait": 20,
#       "guests": 4,
#       "mealType": "halfboard"
#     },
#     {
#       "name": "Jane Smith",
#       "phone": "01898765432",
#       "time": "19:00",
#       "wait": 15,
#       "guests": 2,
#       "mealType": "breakfast"
#     }
#   ]
# }

# **IMPORTANT:**
# - Look VERY carefully for circles/marks around names
# - Even faint or partial circles count
# - Circle color doesn't matter (red, black, blue, any color)
# - If uncertain, default to "breakfast"
# - Extract ALL rows you see
# - Include mealType for EVERY reservation

# Now analyze the image and extract the reservations with meal types."""

#         response = model.generate_content([extraction_prompt, image])
#         content = response.text.strip()
        
#         logger.info(f"📥 Gemini Response (first 500 chars):\n{content[:500]}...")
        
#         # Clean response (remove markdown code blocks)
#         if content.startswith("```json"):
#             content = content.split("```json")[1].split("```")[0].strip()
#         elif content.startswith("```"):
#             content = content.split("```")[1].split("```")[0].strip()
        
#         # Parse JSON
#         result = json.loads(content)
        
#         # Validate structure
#         if not isinstance(result, dict):
#             raise ValueError("Response must be a JSON object with 'columns' and 'data'")
        
#         if "columns" not in result or "data" not in result:
#             raise ValueError("Response must contain 'columns' and 'data' keys")
        
#         if not isinstance(result["data"], list):
#             raise ValueError("'data' must be a list")
        
#         columns = result["columns"]
#         reservations = result["data"]
        
#         logger.info(f"📊 Detected {len(columns)} columns: {columns}")
#         logger.info(f"📋 Found {len(reservations)} reservations")
        
#         # Process and validate each reservation
#         for idx, reservation in enumerate(reservations, 1):
#             name = reservation.get("name") or reservation.get(columns[0]) if columns else "Unknown"
#             logger.info(f"🔍 Processing reservation {idx}: {name}")
            
#             # Ensure mealType exists
#             if "mealType" not in reservation:
#                 logger.warning(f"⚠️ No mealType detected for {name}, defaulting to 'breakfast'")
#                 reservation["mealType"] = "breakfast"
            
#             # Validate mealType value
#             if reservation["mealType"] not in ["halfboard", "breakfast"]:
#                 logger.warning(f"⚠️ Invalid mealType '{reservation['mealType']}' for {name}, defaulting to 'breakfast'")
#                 reservation["mealType"] = "breakfast"
            
#             # Clean phone number if present
#             for key in reservation.keys():
#                 if "phone" in key.lower() and isinstance(reservation[key], str):
#                     reservation[key] = ''.join(filter(str.isdigit, reservation[key]))
#                     logger.debug(f"  📞 Cleaned phone: {reservation[key]}")
            
#             # Log meal type
#             meal_emoji = "🍽️" if reservation["mealType"] == "halfboard" else "🥐"
#             logger.info(f"  {meal_emoji} Meal type: {reservation['mealType']}")
        
#         # Count meal types
#         halfboard_count = sum(1 for r in reservations if r.get("mealType") == "halfboard")
#         breakfast_count = sum(1 for r in reservations if r.get("mealType") == "breakfast")
        
#         logger.info(f"✅ Extraction complete:")
#         logger.info(f"   🍽️  Halfboard (circled): {halfboard_count}")
#         logger.info(f"   🥐 Breakfast (no circle): {breakfast_count}")
        
#         return {
#             "columns": columns,
#             "data": reservations
#         }
        
#     except json.JSONDecodeError as e:
#         logger.error(f"❌ JSON parse error: {e}")
#         logger.error(f"Raw content:\n{content}")
#         raise Exception(f"Failed to parse Gemini response as JSON: {e}")
    
#     except Exception as e:
#         logger.error(f"❌ Gemini extraction error: {e}")
#         import traceback
#         logger.error(traceback.format_exc())
#         raise Exception(f"Gemini extraction failed: {e}")


# # Optional: Endpoint to get extraction statistics
# @router.get("/stats")
# async def get_extraction_stats():
#     """
#     Get information about the extraction service
#     """
#     model_name = _get_vision_model_name()
    
#     return {
#         "service": "Reservation Data Extraction",
#         "model": model_name,
#         "features": [
#             "Circle detection for meal type classification",
#             "Dynamic column header detection",
#             "Multi-color circle support (red, black, blue, any color)",
#             "Automatic phone number cleaning",
#             "Time format normalization"
#         ],
#         "meal_types": {
#             "halfboard": "Names with circles (any color) - for dinner table management",
#             "breakfast": "Names without circles - for setting tables after dinner"
#         }
#     }









"""
Reservation Data Extraction Router - OPTIMIZED FOR ACTUAL FORMAT
================================================================================
Based on client's actual reservation list format:

Columns: Breakf. | Lunch | Dinner | Rn.# | Guest name | Schuld (Group) | Rooms

Features:
- Extracts breakfast/lunch/dinner counts from separate columns
- Identifies guest groups from "Schuld" column (right side)
- Separates dinner vs breakfast reservations
- Groups guests that belong together for seating
- Handles room assignments

Example from actual list:
2  0  0  14  Wongsilar, Christine            Chindm 04.09-11.09
1  0  1  231 Spängler, Christina, Frau       
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
    """Auto-detect the correct Gemini vision model name"""
    global _vision_model_cache
    
    if _vision_model_cache:
        return _vision_model_cache
    
    logger.info("🔍 Auto-detecting Gemini vision model...")
    
    try:
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
        
        available_models = {}
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                available_models[model.name] = model
                short_name = model.name.replace('models/', '')
                available_models[short_name] = model
        
        for model_name in possible_models:
            if model_name in available_models:
                _vision_model_cache = model_name
                logger.info(f"✅ Using vision model: {model_name}")
                return model_name
        
        if available_models:
            first_model = list(available_models.keys())[0]
            _vision_model_cache = first_model
            return first_model
        
        raise Exception("No Gemini models available")
        
    except Exception as e:
        logger.error(f"❌ Model detection failed: {e}")
        return 'gemini-1.5-pro-latest'


@router.post("/extract-details")
async def extract_reservation_details(file: UploadFile = File(...)) -> Dict:
    """
    Extract reservation details from uploaded hotel/restaurant list
    
    Expected format: Table with columns
    - Breakf. (breakfast count)
    - Lunch (lunch count)  
    - Dinner (dinner count)
    - Rn.# (room number)
    - Guest name
    - Schuld/Group (group information on right side)
    - Rooms (room assignment)
    
    Returns organized data for breakfast planning and seating arrangement
    """
    try:
        logger.info(f"📤 Received file: {file.filename} ({file.content_type})")
        
        file_content = await file.read()
        
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
        
        result = await _extract_with_gemini_vision(file_content, file.content_type)
        
        logger.info(f"✅ Extraction successful")
        logger.info(f"🍽️  Guests needing dinner: {result['summary']['total_dinner_guests']}")
        logger.info(f"🥐 Guests needing breakfast: {result['summary']['total_breakfast_guests']}")
        logger.info(f"👥 Groups detected: {len(result['groups'])}")
        
        return {
            "success": True,
            **result
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
    """Extract reservation data using Gemini Vision"""
    
    try:
        model_name = _get_vision_model_name()
        model = genai.GenerativeModel(model_name)
        
        import io
        from PIL import Image
        image = Image.open(io.BytesIO(file_content))
        
        logger.info(f"🤖 Using Gemini model: {model_name}")
        
        # ENHANCED PROMPT FOR ACTUAL TABLE FORMAT
        extraction_prompt = """Analyze this hotel/restaurant reservation list carefully.

**TABLE FORMAT UNDERSTANDING:**

The table has these columns (left to right):
1. **Breakf.** - Number of breakfast guests (0, 1, 2, etc.)
2. **Lunch** - Number of lunch guests
3. **Dinner** - Number of dinner guests  
4. **Rn.#** - Room number
5. **Guest name** - Full name of guest
6. **Schuld/Group** - Group/organization name (on the RIGHT SIDE)
7. **Rooms** - Room assignment details

**EXTRACTION RULES:**

1. **Read ALL rows in the table**
2. **Extract numbers from Breakf., Lunch, Dinner columns**
3. **Pay attention to the RIGHT SIDE for group information**
   - Column may be labeled "Schuld", "Group", or similar
   - Examples: "Chindm 04.09-11.09", "Kafathm Gerhardl31", etc.
4. **Guest Classification:**
   - If Dinner > 0 → needs dinner table NOW
   - If Breakf. > 0 but Dinner = 0 → only breakfast setup (after dinner)
   - If Lunch > 0 → lunch planning

**GROUP DETECTION:**
- Same group name on right side = must sit together
- Examples from image:
  • "Chindm 04.09-11.09" - all guests with this are one group
  • "Kafathm Gerhardl31" - another group
  • Empty/"-" = individual guest (no group)

**OUTPUT FORMAT (JSON only, no markdown):**
{
  "reservations": [
    {
      "guest_name": "Wongsilar, Christine",
      "room_number": "14",
      "breakfast_count": 2,
      "lunch_count": 0,
      "dinner_count": 0,
      "group": "Chindm 04.09-11.09",
      "room_assignment": "Chindm 04.09-11.09",
      "meal_type": "breakfast_only"
    },
    {
      "guest_name": "Spängler, Christina, Frau",
      "room_number": "231",
      "breakfast_count": 1,
      "lunch_count": 0,
      "dinner_count": 1,
      "group": null,
      "room_assignment": "",
      "meal_type": "halfboard"
    }
  ],
  "dinner_reservations": [
    {
      "guest_name": "Spängler, Christina, Frau",
      "total_guests": 1,
      "dinner_count": 1,
      "breakfast_count": 1,
      "group": null,
      "needs_table_now": true
    }
  ],
  "breakfast_reservations": [
    {
      "guest_name": "Wongsilar, Christine",
      "total_guests": 2,
      "breakfast_count": 2,
      "group": "Chindm 04.09-11.09",
      "setup_after_dinner": true
    }
  ],
  "groups": {
    "Chindm 04.09-11.09": {
      "members": ["Wongsilar, Christine", "..."],
      "total_breakfast": 10,
      "total_dinner": 5,
      "total_lunch": 0
    },
    "Kafathm Gerhardl31": {
      "members": ["Guest1", "Guest2"],
      "total_breakfast": 4,
      "total_dinner": 4,
      "total_lunch": 0
    }
  },
  "summary": {
    "total_reservations": 50,
    "total_breakfast_guests": 45,
    "total_dinner_guests": 30,
    "total_lunch_guests": 5,
    "total_groups": 5,
    "individual_guests": 10
  }
}

**CRITICAL INSTRUCTIONS:**
1. Read EVERY row in the table - don't skip any
2. Numbers from Breakf/Lunch/Dinner columns are EXACT counts
3. Group name is on the FAR RIGHT side
4. Empty group field = null (individual guest)
5. meal_type:
   - "halfboard" if dinner_count > 0
   - "breakfast_only" if dinner_count = 0 but breakfast_count > 0
   - "lunch_only" if only lunch_count > 0
6. For dinner_reservations: only include guests with dinner_count > 0
7. For breakfast_reservations: include ALL guests with breakfast_count > 0
8. Calculate group totals by summing all members' counts

**EXAMPLE FROM IMAGE:**

Row: 2  0  0  14  Wongsilar, Christine            Chindm 04.09-11.09

Extracts as:
{
  "guest_name": "Wongsilar, Christine",
  "room_number": "14",
  "breakfast_count": 2,
  "lunch_count": 0,
  "dinner_count": 0,
  "group": "Chindm 04.09-11.09",
  "meal_type": "breakfast_only"
}

Now analyze the entire table and extract ALL reservations with proper grouping."""

        response = model.generate_content([extraction_prompt, image])
        content = response.text.strip()
        
        logger.info(f"📥 Gemini Response received (length: {len(content)})")
        
        # Clean markdown
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        result = json.loads(content)
        
        # Validate
        if "reservations" not in result:
            raise ValueError("Response must contain 'reservations' key")
        
        # Log detailed info
        logger.info(f"📊 EXTRACTION RESULTS:")
        logger.info(f"   Total reservations: {len(result.get('reservations', []))}")
        logger.info(f"   Dinner reservations: {len(result.get('dinner_reservations', []))}")
        logger.info(f"   Breakfast reservations: {len(result.get('breakfast_reservations', []))}")
        logger.info(f"   Groups detected: {len(result.get('groups', {}))}")
        
        # Log group details
        for group_name, group_data in result.get('groups', {}).items():
            logger.info(f"   👥 {group_name}:")
            logger.info(f"      Members: {len(group_data.get('members', []))}")
            logger.info(f"      Breakfast: {group_data.get('total_breakfast', 0)}")
            logger.info(f"      Dinner: {group_data.get('total_dinner', 0)}")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        logger.error(f"Raw content (first 1000 chars):\n{content[:1000]}")
        raise Exception(f"Failed to parse Gemini response: {e}")
    
    except Exception as e:
        logger.error(f"❌ Extraction error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise Exception(f"Gemini extraction failed: {e}")


@router.post("/generate-seating-plan")
async def generate_seating_plan(file: UploadFile = File(...)) -> Dict:
    """
    Generate optimal seating arrangement for breakfast/dinner
    
    Features:
    - Groups same group members together
    - Separates dinner vs breakfast setup timing
    - Provides table size recommendations
    - Room-wise allocation if multiple rooms
    
    Returns complete seating plan with table assignments
    """
    try:
        file_content = await file.read()
        extraction_result = await _extract_with_gemini_vision(file_content, "image")
        
        seating_plan = _generate_optimal_seating(extraction_result)
        
        return {
            "success": True,
            "seating_plan": seating_plan,
            "extraction_summary": extraction_result.get('summary', {})
        }
        
    except Exception as e:
        logger.error(f"❌ Seating plan error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate seating plan: {str(e)}")


def _generate_optimal_seating(extraction_data: Dict) -> Dict:
    """
    Generate optimal seating arrangement based on extracted data
    
    Logic:
    1. Group guests with same group name together
    2. Create table assignments for dinner (immediate)
    3. Create table assignments for breakfast (after dinner)
    4. Suggest table sizes based on guest counts
    """
    groups = extraction_data.get('groups', {})
    dinner_reservations = extraction_data.get('dinner_reservations', [])
    breakfast_reservations = extraction_data.get('breakfast_reservations', [])
    
    seating_plan = {
        "dinner_seating": {
            "group_tables": [],
            "individual_tables": [],
            "setup_timing": "NOW - before dinner service"
        },
        "breakfast_seating": {
            "group_tables": [],
            "individual_tables": [],
            "setup_timing": "AFTER dinner service"
        },
        "notes": []
    }
    
    # === DINNER SEATING (Priority: Set Now) ===
    processed_dinner_groups = set()
    
    for group_name, group_data in groups.items():
        dinner_count = group_data.get('total_dinner', 0)
        if dinner_count > 0 and group_name not in processed_dinner_groups:
            seating_plan["dinner_seating"]["group_tables"].append({
                "group_name": group_name,
                "members": group_data.get('members', []),
                "total_guests": dinner_count,
                "suggested_table": _suggest_table_size(dinner_count),
                "priority": "HIGH - Group must sit together"
            })
            processed_dinner_groups.add(group_name)
    
    # Individual dinner guests (no group)
    for reservation in dinner_reservations:
        if not reservation.get('group'):
            seating_plan["dinner_seating"]["individual_tables"].append({
                "guest_name": reservation['guest_name'],
                "guests": reservation['dinner_count'],
                "suggested_table": _suggest_table_size(reservation['dinner_count'])
            })
    
    # === BREAKFAST SEATING (Set After Dinner) ===
    processed_breakfast_groups = set()
    
    for group_name, group_data in groups.items():
        breakfast_count = group_data.get('total_breakfast', 0)
        if breakfast_count > 0 and group_name not in processed_breakfast_groups:
            seating_plan["breakfast_seating"]["group_tables"].append({
                "group_name": group_name,
                "members": group_data.get('members', []),
                "total_guests": breakfast_count,
                "suggested_table": _suggest_table_size(breakfast_count),
                "priority": "Group must sit together"
            })
            processed_breakfast_groups.add(group_name)
    
    # Individual breakfast guests
    for reservation in breakfast_reservations:
        if not reservation.get('group'):
            seating_plan["breakfast_seating"]["individual_tables"].append({
                "guest_name": reservation['guest_name'],
                "guests": reservation['total_guests'],
                "suggested_table": _suggest_table_size(reservation['total_guests'])
            })
    
    # Add summary notes
    total_dinner_tables = (
        len(seating_plan["dinner_seating"]["group_tables"]) +
        len(seating_plan["dinner_seating"]["individual_tables"])
    )
    total_breakfast_tables = (
        len(seating_plan["breakfast_seating"]["group_tables"]) +
        len(seating_plan["breakfast_seating"]["individual_tables"])
    )
    
    seating_plan["notes"] = [
        f"Total dinner tables to set NOW: {total_dinner_tables}",
        f"Total breakfast tables to set AFTER dinner: {total_breakfast_tables}",
        f"Groups requiring special seating: {len(groups)}",
        "Remember: Same group members MUST sit together"
    ]
    
    return seating_plan


def _suggest_table_size(guest_count: int) -> str:
    """Suggest appropriate table size based on guest count"""
    if guest_count <= 2:
        return f"2-person table (guests: {guest_count})"
    elif guest_count <= 4:
        return f"4-person table (guests: {guest_count})"
    elif guest_count <= 6:
        return f"6-person table (guests: {guest_count})"
    elif guest_count <= 8:
        return f"8-person table (guests: {guest_count})"
    else:
        # Large groups may need multiple tables pushed together
        tables_needed = (guest_count + 7) // 8  # Round up, 8 per table
        return f"{tables_needed} tables (8-person each) for {guest_count} guests"


@router.get("/stats")
async def get_extraction_stats():
    """Service information and capabilities"""
    model_name = _get_vision_model_name()
    
    return {
        "service": "Hotel/Restaurant Reservation Extraction & Seating Planner",
        "model": model_name,
        "supported_formats": [
            "Table with Breakfast/Lunch/Dinner columns",
            "Group information on right side (Schuld column)",
            "Room numbers and assignments"
        ],
        "features": [
            "Extract breakfast/lunch/dinner counts from table columns",
            "Identify guest groups from right side of list",
            "Separate dinner vs breakfast reservations",
            "Generate seating plans with group arrangements",
            "Calculate total guests per meal type",
            "Suggest appropriate table sizes"
        ],
        "classification": {
            "halfboard": "Guests with dinner_count > 0 - need table NOW",
            "breakfast_only": "Guests with breakfast_count > 0, dinner_count = 0 - set after dinner",
            "groups": "Same group name = must sit together"
        }
    }