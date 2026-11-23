"""Optional demo data for local development.

Enabled only with SEED_DEMO_DATA=true, and never in production. The demo accounts
share the password from DEMO_USER_PASSWORD - there is no built-in default password.
"""

import json
import logging
from pathlib import Path

from fastapi.concurrency import run_in_threadpool

from config import get_settings
from core.security import hash_password
from core.timeutils import utc_now
from database.db import OCCUPANCY_DOC_ID

logger = logging.getLogger("studyspot.seed")

OCCUPANCY_FILE = Path(__file__).resolve().parent / "campus_occupancy.json"

DEMO_USERS = [
    {
        "roll_number": "26M0821",
        "full_name": "Laxit Lall",
        "email": "26m0821@iitb.ac.in",
        "branch": "Computer Science",
        "hostel": "Hostel 15",
        "bio": "Ghare jaake sutti babu",
    },
    {
        "roll_number": "26M0829",
        "full_name": "Ayush Raj",
        "email": "26m0829@iitb.ac.in",
        "branch": "Computer Science",
        "hostel": "Hostel 15",
        "bio": "Ghare jaake sutti babu",
    },
    {
        "roll_number": "26M0828",
        "full_name": "sushil kumar",
        "email": "26m0828@iitb.ac.in",
        "branch": "Computer Science",
        "hostel": "Hostel 10",
        "bio": "Ghare jaake sutti babu",
    },
]


async def seed_demo_data(database) -> None:
    settings = get_settings()
    if settings.is_production:
        logger.error("Refusing to seed demo data in production.")
        return

    if not settings.demo_user_password:
        logger.warning("SEED_DEMO_DATA is on but DEMO_USER_PASSWORD is not set; skipping demo users.")
    else:
        password_hash = await run_in_threadpool(hash_password, settings.demo_user_password)
        for user in DEMO_USERS:
            await database.db.users.update_one(
                {"roll_number": user["roll_number"]},
                {
                    "$setOnInsert": {
                        **user,
                        "password_hash": password_hash,
                        "role": "student",
                        "token_version": 0,
                        "failed_login_count": 0,
                        "locked_until": None,
                        "created_at": utc_now(),
                    }
                },
                upsert=True,
            )
        logger.info("Demo users ensured (%d).", len(DEMO_USERS))

        
        if OCCUPANCY_FILE.exists():
            with open(OCCUPANCY_FILE, "r", encoding="utf-8") as f:
                occupancy = json.load(f)

            occupancy["_id"] = OCCUPANCY_DOC_ID
            await database.db.occupancy.replace_one(
                {"_id": OCCUPANCY_DOC_ID},
                occupancy,
                upsert=True,
            )
            logger.info("Seeded campus occupancy from %s", OCCUPANCY_FILE.name)
        else:
            logger.warning("Occupancy file not found at %s", OCCUPANCY_FILE)