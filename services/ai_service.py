from typing import List, Dict
import json
from config import settings
from openai import OpenAI

client = OpenAI(api_key=settings.OPENAI_API_KEY)

async def get_ai_suggestions(
    guest_name: str,
    guest_id: str,
    dining_history: List[Dict]
) -> Dict:
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

    prompt = f"""
You are an AI assistant for a restaurant management system.

Guest Name: {guest_name}
Guest ID: {guest_id}

Dining History:
{history_text}

Return ONLY valid JSON in this format:
{{
  "suggestedTable": "T-X",
  "suggestedPartySize": 2,
  "suggestedFoods": ["food1", "food2"],
  "reasoning": "short explanation"
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
        return json.loads(response_text)

    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return {
            "suggestedTable": dining_history[0].get("tableName") if dining_history else "T-1",
            "suggestedPartySize": dining_history[0].get("partySize") if dining_history else 2,
            "suggestedFoods": ["Ask for recommendations"],
            "reasoning": "Unable to generate AI suggestions at this time"
        }
