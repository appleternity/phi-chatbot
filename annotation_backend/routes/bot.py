import json
from fastapi import APIRouter

from core.config import settings

router = APIRouter()

@router.get("/bots")
async def get_bots():
    """Fetch the list of available bots from the JSON file."""
    try:
        with open(settings.BOT_INFO_PATH, "r", encoding="utf-8") as f:
            bots = json.load(f)
        print("Fetched bots:", bots)
        return {"bots": bots}
    except Exception as e:
        print("Error fetching bots:", e)
        return {"bots": []}
