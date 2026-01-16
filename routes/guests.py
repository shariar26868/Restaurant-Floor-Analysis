from fastapi import APIRouter, HTTPException
from typing import List, Any, Dict
from models import Guest
from database import get_database
from bson import ObjectId

router = APIRouter()


def convert_objectid_to_str(data: Any) -> Any:
    """
    Recursively convert all ObjectId instances to strings in a data structure
    """
    if isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, dict):
        return {key: convert_objectid_to_str(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_objectid_to_str(item) for item in data]
    else:
        return data


@router.get("/", response_model=List[Guest])
async def get_guests():
    """Get all guests"""
    db = get_database()
    guests_collection = db["guests"]
    tables_collection = db["tables"]  # Assuming you have a tables collection
    
    # Fetch guests from MongoDB
    guests_cursor = guests_collection.find()
    guests = await guests_cursor.to_list(length=None)
    
    # Convert MongoDB documents to Pydantic models
    result = []
    for guest_doc in guests:
        try:
            # Convert ALL ObjectIds to strings recursively
            guest_doc = convert_objectid_to_str(guest_doc)
            
            # If guest has tableId, fetch the table data
            if guest_doc.get('tableId') and guest_doc['tableId']:
                try:
                    table_doc = await tables_collection.find_one({"_id": ObjectId(guest_doc['tableId'])})
                    if table_doc:
                        # Convert table ObjectIds to strings
                        table_doc = convert_objectid_to_str(table_doc)
                        # Add table data to guest
                        guest_doc['table'] = table_doc
                except Exception as e:
                    print(f"⚠️ Could not fetch table for guest {guest_doc.get('_id')}: {e}")
                    guest_doc['table'] = None
            
            # Create Pydantic model instance
            guest = Guest(**guest_doc)
            result.append(guest)
        except Exception as e:
            # Log the error and skip invalid guests
            print(f"⚠️ Skipping invalid guest: {guest_doc.get('_id', 'unknown')} - Error: {e}")
            continue
    
    return result


@router.post("/", response_model=Guest)
async def create_guest(guest: Guest):
    """Create a new guest"""
    db = get_database()
    guests_collection = db["guests"]
    
    # Convert to dict, excluding the id field
    guest_dict = guest.model_dump(by_alias=True, exclude_unset=True, exclude={"id"})
    
    # Insert into MongoDB
    result = await guests_collection.insert_one(guest_dict)
    
    # Fetch the created guest
    created_guest = await guests_collection.find_one({"_id": result.inserted_id})
    
    # Convert all ObjectIds to strings
    created_guest = convert_objectid_to_str(created_guest)
    
    return Guest(**created_guest)


@router.get("/{guest_id}/suggestions")
async def get_guest_ai_suggestions(guest_id: str):
    """Get AI suggestions for a guest based on their history and preferences"""
    db = get_database()
    guests_collection = db["guests"]
    
    # Validate ObjectId
    if not ObjectId.is_valid(guest_id):
        raise HTTPException(status_code=400, detail="Invalid guest ID format")
    
    # Find guest
    guest_doc = await guests_collection.find_one({"_id": ObjectId(guest_id)})
    
    if not guest_doc:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    # Convert all ObjectIds to strings
    guest_doc = convert_objectid_to_str(guest_doc)
    
    # Generate simple AI suggestions based on guest data
    suggestions = {
        "name": guest_doc.get("name"),
        "guests": guest_doc.get("partySize"),
        "dietaryPreference": guest_doc.get("dietaryPreferences", []),
        "preferredTable": f"T-{guest_doc.get('partySize', 2)}" if guest_doc.get("partySize") else "T-2",
        "stayInformation": None,
        "notes": guest_doc.get("notes")
    }
    
    # Add stay information if available
    if guest_doc.get("stayFrom") and guest_doc.get("stayTo"):
        from datetime import datetime
        stay_from = guest_doc.get("stayFrom")
        stay_to = guest_doc.get("stayTo")
        
        # Format dates
        if isinstance(stay_from, str):
            stay_from = datetime.fromisoformat(stay_from.replace('Z', '+00:00'))
        if isinstance(stay_to, str):
            stay_to = datetime.fromisoformat(stay_to.replace('Z', '+00:00'))
            
        suggestions["stayInformation"] = f"{stay_from.strftime('%b %d')} - {stay_to.strftime('%b %d')}"
    
    return suggestions


@router.get("/{guest_id}", response_model=Guest)
async def get_guest(guest_id: str):
    """Get a single guest by ID"""
    db = get_database()
    guests_collection = db["guests"]
    tables_collection = db["tables"]
    
    # Validate ObjectId
    if not ObjectId.is_valid(guest_id):
        raise HTTPException(status_code=400, detail="Invalid guest ID format")
    
    # Find guest
    guest_doc = await guests_collection.find_one({"_id": ObjectId(guest_id)})
    
    if not guest_doc:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    # Convert all ObjectIds to strings
    guest_doc = convert_objectid_to_str(guest_doc)
    
    # If guest has tableId, fetch the table data
    if guest_doc.get('tableId') and guest_doc['tableId']:
        try:
            table_doc = await tables_collection.find_one({"_id": ObjectId(guest_doc['tableId'])})
            if table_doc:
                table_doc = convert_objectid_to_str(table_doc)
                guest_doc['table'] = table_doc
        except Exception as e:
            print(f"⚠️ Could not fetch table for guest {guest_doc.get('_id')}: {e}")
    
    return Guest(**guest_doc)


@router.put("/{guest_id}", response_model=Guest)
async def update_guest(guest_id: str, guest: Guest):
    """Update a guest"""
    db = get_database()
    guests_collection = db["guests"]
    
    # Validate ObjectId
    if not ObjectId.is_valid(guest_id):
        raise HTTPException(status_code=400, detail="Invalid guest ID format")
    
    # Convert to dict, excluding the id field
    guest_dict = guest.model_dump(by_alias=True, exclude_unset=True, exclude={"id"})
    
    # Update in MongoDB
    result = await guests_collection.update_one(
        {"_id": ObjectId(guest_id)},
        {"$set": guest_dict}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    # Fetch updated guest
    updated_guest = await guests_collection.find_one({"_id": ObjectId(guest_id)})
    
    # Convert all ObjectIds to strings
    updated_guest = convert_objectid_to_str(updated_guest)
    
    return Guest(**updated_guest)


@router.delete("/{guest_id}")
async def delete_guest(guest_id: str):
    """Delete a guest"""
    db = get_database()
    guests_collection = db["guests"]
    
    # Validate ObjectId
    if not ObjectId.is_valid(guest_id):
        raise HTTPException(status_code=400, detail="Invalid guest ID format")
    
    # Delete from MongoDB
    result = await guests_collection.delete_one({"_id": ObjectId(guest_id)})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Guest not found")
    
    return {"message": "Guest deleted successfully"}