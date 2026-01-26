# routes/reservation_extract.py
"""
Reservation Data Extraction Router
===================================
Upload image/file → Extract reservation details using OpenAI Vision
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import Dict
import logging
import base64
import json
from openai import OpenAI
from config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Create router
router = APIRouter(prefix="/api/reservation", tags=["Reservation Extract"])


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
        "data": {
            "name": "Naayeem",
            "phone": "1712345678",
            "partySize": 4,
            "arrivalTime": "18:30",
            "estimatedWait": 20
        }
    }
    """
    try:
        logger.info(f"📤 Received file: {file.filename} ({file.content_type})")
        
        # Read file content
        file_content = await file.read()
        
        # Validate file size (max 10MB)
        if len(file_content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Max 10MB allowed.")
        
        # Extract reservation data using OpenAI Vision
        extracted_data = await _extract_with_openai_vision(file_content, file.content_type)
        
        logger.info(f"✅ Extraction successful: {extracted_data}")
        
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


async def _extract_with_openai_vision(
    file_content: bytes,
    content_type: str
) -> Dict:
    """
    Use OpenAI Vision to extract reservation details from image
    """
    
    # Convert to base64
    base64_file = base64.b64encode(file_content).decode('utf-8')
    
    # Determine media type
    if content_type.startswith('image/'):
        media_type = content_type
    else:
        # Default to jpeg for unknown types
        media_type = "image/jpeg"
    
    # Prompt for OpenAI
    prompt = """You are analyzing an image that contains reservation information for a restaurant.

**YOUR TASK:** Extract the following reservation details from this image:

1. **name** - Customer's name (string)
2. **phone** - Customer's phone number (string, digits only, no spaces/dashes)
3. **partySize** - Number of people in the party (integer)
4. **arrivalTime** - Arrival/reservation time in 24-hour format HH:MM (string, e.g., "18:30")
5. **estimatedWait** - Estimated wait time in minutes (integer)

**IMPORTANT RULES:**
- If a field is NOT found in the image, use these defaults:
  - name: "Unknown"
  - phone: "0000000000"
  - partySize: 0
  - arrivalTime: "00:00"
  - estimatedWait: 0
- Phone numbers: Remove all spaces, dashes, and formatting. Just digits.
- Time format: Always use 24-hour format (HH:MM). Convert from 12-hour if needed.
  - Example: "6:30 PM" → "18:30"
  - Example: "10:15 AM" → "10:15"
- Wait time: If given in hours, convert to minutes (e.g., "1.5 hours" → 90)

**OUTPUT FORMAT:**
Return ONLY a JSON object with these exact fields, nothing else:

{
  "name": "string",
  "phone": "string",
  "partySize": number,
  "arrivalTime": "HH:MM",
  "estimatedWait": number
}

**EXAMPLES:**

Image shows: "Reservation for John Doe, party of 4, 7:30 PM, phone: 017-1234-5678"
Output:
{
  "name": "John Doe",
  "phone": "01712345678",
  "partySize": 4,
  "arrivalTime": "19:30",
  "estimatedWait": 0
}

Image shows: "Walk-in: Sarah, 2 people, wait time 30 min, contact: +880 1812345678"
Output:
{
  "name": "Sarah",
  "phone": "01812345678",
  "partySize": 2,
  "arrivalTime": "00:00",
  "estimatedWait": 30
}

Now analyze the provided image and extract the reservation data."""

    try:
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
                                "url": f"data:{media_type};base64,{base64_file}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.1  # Low temperature for consistent extraction
        )
        
        content = response.choices[0].message.content.strip()
        logger.info(f"📥 OpenAI Response: {content}")
        
        # Parse JSON response
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        extracted_data = json.loads(content)
        
        # Validate required fields
        required_fields = ["name", "phone", "partySize", "arrivalTime", "estimatedWait"]
        for field in required_fields:
            if field not in extracted_data:
                logger.warning(f"⚠️ Missing field '{field}', using default")
                # Set defaults
                if field == "name":
                    extracted_data[field] = "Unknown"
                elif field == "phone":
                    extracted_data[field] = "0000000000"
                elif field in ["partySize", "estimatedWait"]:
                    extracted_data[field] = 0
                elif field == "arrivalTime":
                    extracted_data[field] = "00:00"
        
        # Clean phone number (remove non-digits)
        if isinstance(extracted_data.get("phone"), str):
            extracted_data["phone"] = ''.join(filter(str.isdigit, extracted_data["phone"]))
        
        # Ensure correct types
        extracted_data["partySize"] = int(extracted_data.get("partySize", 0))
        extracted_data["estimatedWait"] = int(extracted_data.get("estimatedWait", 0))
        
        return extracted_data
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        logger.error(f"Response was: {content}")
        raise Exception(f"Failed to parse OpenAI response: {e}")
    
    except Exception as e:
        logger.error(f"❌ OpenAI Vision error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise Exception(f"OpenAI Vision extraction failed: {e}")