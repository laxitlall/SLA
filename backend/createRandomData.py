import json
import random
from datetime import datetime

def generate_campus_occupancy_data():
    campus_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "zones": []
    }
    
    # 1. Generate 21 Hostels with 2-4 rooms each
    for h_id in range(1, 22):
        hostel_name = f"Hostel {h_id}"
        num_rooms = random.randint(2, 4)
        rooms = []
        
        for r_id in range(1, num_rooms + 1):
            room_name = f"Study Room {r_id}"
            num_seats = random.randint(5, 15)  # 5-15 seats per hostel room
            seats = generate_seats(num_seats, prefix=f"H{h_id}-R{r_id}")
            rooms.append({
                "room_id": f"h{h_id}-room-{r_id}",
                "room_name": room_name,
                "seats": seats
            })
            
        campus_data["zones"].append({
            "zone_type": "hostel",
            "name": hostel_name,
            "rooms": rooms
        })
        
    # 2. Generate Central Library with 10 rooms
    lib_rooms = []
    for r_id in range(1, 11):
        room_name = f"Reading Hall {r_id}"
        num_seats = random.randint(20, 40)  # 20-40 seats per library room
        seats = generate_seats(num_seats, prefix=f"LIB-R{r_id}")
        lib_rooms.append({
            "room_id": f"central-lib-room-{r_id}",
            "room_name": room_name,
            "seats": seats
        })
        
    campus_data["zones"].append({
        "zone_type": "library",
        "name": "Central Library",
        "rooms": lib_rooms
    })
    
    return campus_data

def generate_seats(num_seats, prefix):
    seats = []
    for s_idx in range(1, num_seats + 1):
        seat_id = f"{prefix}-S{s_idx:02d}"
        
        # Simulate realistic probabilities for detections
        has_person = random.random() < 0.45  # 45% chance a person is sitting there
        has_laptop = random.random() < (0.70 if has_person else 0.20)  # Laptops likely if person present, or left behind
        has_bag = random.random() < 0.15     # 15% chance a bag is left on the chair
        
        # Apply your decision hierarchy
        if has_person:
            state = "OCCUPIED"
        elif has_laptop or has_bag:
            state = "SPOT_HELD"
        else:
            state = "AVAILABLE"
            
        seats.append({
            "seat_id": seat_id,
            "detections": {
                "person": has_person,
                "laptop": has_laptop,
                "bag": has_bag
            },
            "computed_state": state,
            "confidence_score": round(random.uniform(0.88, 0.99), 2)
        })
    return seats

if __name__ == "__main__":
    data = generate_campus_occupancy_data()
    
    # Save the output to a JSON file
    filename = "./backend/database/campus_occupancy.json"
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
        
    print(f"Successfully generated mock data! Saved to {filename}.")
    print(f"Total Zones: {len(data['zones'])} (21 Hostels + 1 Central Library)")