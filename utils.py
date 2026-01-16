from typing import Dict, Any
from copy import deepcopy

# ---------------------------
# Standard Success Response
# ---------------------------
def success_response(data: Any, message: str = "Success", status_code: int = 200) -> Dict:
    """Standard success response"""
    return {
        "statusCode": status_code,
        "success": True,
        "message": message,
        "data": data
    }

# ---------------------------
# Standard Error Response
# ---------------------------
def error_response(message: str, status_code: int = 400) -> Dict:
    """Standard error response"""
    return {
        "statusCode": status_code,
        "success": False,
        "message": message,
        "data": None
    }

# ---------------------------
# Format Guest Object for Response
# ---------------------------
def format_guest_response(guest: Dict) -> Dict:
    """
    Converts MongoDB '_id' to 'id' and returns a safe copy.
    Prevents mutating the original dictionary.
    """
    guest_copy = deepcopy(guest)
    if "_id" in guest_copy:
        guest_copy["id"] = str(guest_copy["_id"])
        del guest_copy["_id"]
    return guest_copy

# ---------------------------
# Format List of Guests
# ---------------------------
def format_guest_list(guests: list) -> list:
    """Format multiple guest objects"""
    return [format_guest_response(g) for g in guests]
