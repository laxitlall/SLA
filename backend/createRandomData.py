import json
import random
from datetime import datetime, timezone
from pathlib import Path


def generate_campus_occupancy_data():
    campus_data = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "zones": [],
    }

    # 1. Generate h
    for h_id in range(1, 22):
        hostel_name = f"Hostel {h_id}"
        num_rooms = random.randint(2, 4)
        rooms = []

        for r_id in range(1, num_rooms + 1):
            room_name = f"Study Room {r_id}"
            num_seats = random.randint(5, 15)  # 5-15 seats per hostel room
            seats = generate_seats(num_seats, prefix=f"H{h_id}-R{r_id}")
            rooms.append(
                {
                    "room_id": f"h{h_id}-room-{r_id}",
                    "room_name": room_name,
                    "seats": seats,
                }
            )

        campus_data["zones"].append(
            {"zone_type": "hostel", "name": hostel_name, "rooms": rooms}
        )

    
    lib_rooms = []
    for r_id in range(1, 11):
        room_name = f"Reading Hall {r_id}"
        num_seats = random.randint(20, 40)  # 20-40 seats per library room
        seats = generate_seats(num_seats, prefix=f"LIB-R{r_id}")
        lib_rooms.append(
            {
                "room_id": f"central-lib-room-{r_id}",
                "room_name": room_name,
                "seats": seats,
            }
        )

    campus_data["zones"].append(
        {"zone_type": "library", "name": "Central Library", "rooms": lib_rooms}
    )

    return campus_data


def generate_seats(num_seats, prefix):
    seats = []
    for s_idx in range(1, num_seats + 1):
        seat_id = f"{prefix}-S{s_idx:02d}"

        # S
        has_person = random.random() < 0.45 
        has_laptop = random.random() < (
            0.70 if has_person else 0.20
        )  #
        has_bag = random.random() < 0.15  

        # Apply your decision hierarchy
        if has_person:
            state = "OCCUPIED"
        elif has_laptop or has_bag:
            state = "SPOT_HELD"
        else:
            state = "AVAILABLE"

        seats.append(
            {
                "seat_id": seat_id,
                "detections": {
                    "person": has_person,
                    "laptop": has_laptop,
                    "bag": has_bag,
                },
                "computed_state": state,
                "confidence_score": round(random.uniform(0.88, 0.99), 2),
            }
        )
    return seats


if __name__ == "__main__":
    from database.db import db_instance

    data = generate_campus_occupancy_data()
    db_instance.save_occupancy(data)
    filename = Path(__file__).resolve().parent / "database" / "campus_occupancy.json"
    print(f"Successfully generated & synced mock data! Saved to {filename}.")
    print(f"MongoDB Cloud Connected: {db_instance.using_cloud}")
    print(f"Total Zones: {len(data['zones'])} (21 Hostels + 1 Central Library)")
