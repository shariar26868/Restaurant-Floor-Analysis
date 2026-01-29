# from typing import List, Dict
# import json
# from config import settings
# from openai import OpenAI

# client = OpenAI(api_key=settings.OPENAI_API_KEY)

# async def get_ai_suggestions(
#     guest_name: str,
#     guest_id: str,
#     dining_history: List[Dict]
# ) -> Dict:
#     # Prepare history summary
#     if dining_history:
#         history_text = "\n".join([
#             f"- Visit on {h.get('visitDate')}: Table {h.get('tableName')}, "
#             f"Party size: {h.get('partySize')}, "
#             f"Ordered: {', '.join(h.get('foodOrdered', []))}, "
#             f"Preferences: {', '.join(h.get('preferences', []))}"
#             for h in dining_history
#         ])
#     else:
#         history_text = "No previous dining history (First time guest)"

#     prompt = f"""
# You are an AI assistant for a restaurant management system.

# Guest Name: {guest_name}
# Guest ID: {guest_id}

# Dining History:
# {history_text}

# Return ONLY valid JSON in this format:
# {{
#   "suggestedTable": "T-X",
#   "suggestedPartySize": 2,
#   "suggestedFoods": ["food1", "food2"],
#   "reasoning": "short explanation"
# }}
# """

#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o-mini",  # fast + cheap
#             messages=[
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.4
#         )

#         response_text = response.choices[0].message.content.strip()
#         return json.loads(response_text)

#     except Exception as e:
#         print(f"❌ OpenAI API Error: {e}")
#         return {
#             "suggestedTable": dining_history[0].get("tableName") if dining_history else "T-1",
#             "suggestedPartySize": dining_history[0].get("partySize") if dining_history else 2,
#             "suggestedFoods": ["Ask for recommendations"],
#             "reasoning": "Unable to generate AI suggestions at this time"
#         }





from typing import List, Dict, Optional
import json
from config import settings
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)

async def get_ai_suggestions(
    guest_name: str,
    guest_id: str,
    dining_history: List[Dict],
    current_table: Optional[str] = None
) -> Dict:
    """
    Get AI-powered suggestions for a guest
    
    Args:
        guest_name: Name of the guest
        guest_id: Guest ID
        dining_history: List of previous dining experiences
        current_table: Previously assigned table (if any)
    
    Returns:
        Dictionary with AI suggestions
    """
    
    # Check if guest has previous table assignment
    has_previous_table = current_table is not None
    
    # Prepare history summary
    if dining_history:
        history_text = "\n".join([
            f"- Visit on {h.get('visitDate')}: Table {h.get('tableName')}, "
            f"Party size: {h.get('partySize')}, "
            f"Ordered: {', '.join(h.get('foodOrdered', []))}, "
            f"Preferences: {', '.join(h.get('preferences', []))}"
            for h in dining_history
        ])
    else:
        history_text = "No previous dining history (First time guest)"
    
    # Build prompt with table information
    table_context = f"Previous table assignment: {current_table}" if has_previous_table else "No previous table assignment - NEW GUEST"
    
    prompt = f"""
You are an AI assistant for a restaurant management system.

Guest Name: {guest_name}
Guest ID: {guest_id}
{table_context}

Dining History:
{history_text}

Instructions:
- If the guest has a previous table assignment, recommend the same table
- If no previous table, leave suggestedTable as null (do NOT suggest any table)
- Mark guest as "returning" or "new"

Return ONLY valid JSON in this format:
{{
    "suggestedTable": "{current_table if has_previous_table else 'null'}",
    "suggestedPartySize": 2,
    "suggestedFoods": ["food1", "food2"],
    "guestType": "returning" or "new",
    "reasoning": "short explanation mentioning if returning guest with previous table or new guest"
}}
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # fast + cheap
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )
        
        response_text = response.choices[0].message.content.strip()
        result = json.loads(response_text)
        
        # Ensure suggestedTable is None for new guests
        if not has_previous_table:
            result["suggestedTable"] = None
        
        return result
        
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        
        # Fallback logic
        if has_previous_table:
            return {
                "suggestedTable": current_table,
                "suggestedPartySize": dining_history[0].get("partySize") if dining_history else None,
                "suggestedFoods": ["Ask for recommendations"],
                "guestType": "returning",
                "reasoning": "Returning guest - recommending previous table"
            }
        else:
            return {
                "suggestedTable": None,  # Null/empty for new guests
                "suggestedPartySize": None,
                "suggestedFoods": ["Ask for recommendations"],
                "guestType": "new",
                "reasoning": "New guest - no previous table history"
            }