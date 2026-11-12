// src/utils/getOccupancy.js
import campusData from "../../../backend/database/campus_occupancy.json";

export function getCampusOccupancySummary() {
  let finalAvailableSeats = 0;

  // Process zones to calculate total vs available seats
  const summary = campusData.zones.map((zone) => {
    let totalSeats = 0;
    let availableSeats = 0;
    let spotHeldSeats = 0;

    const rooms = zone.rooms.map((room) => {
      let roomAvailable = 0;
      let roomSpotHeld = 0;
      let roomOccupied = 0;

      room.seats.forEach((seat) => {
        totalSeats++;
        if (seat.computed_state === "AVAILABLE") {
          availableSeats++;
          roomAvailable++;
        } else if (seat.computed_state === "SPOT_HELD") {
          spotHeldSeats++;
          roomSpotHeld++;
        } else {
          roomOccupied++;
        }
      });

      return {
        room_id: room.room_id,
        room_name: room.room_name,
        totalSeats: room.seats.length,
        availableSeats: roomAvailable,
        spotHeldSeats: roomSpotHeld,
        occupiedSeats: roomOccupied,
        seats: room.seats,
      };
    });

    finalAvailableSeats += availableSeats;

    return {
      name: zone.name, // e.g., "Hostel 1" or "Central Library"
      zone_type: zone.zone_type, // "hostel" or "library"
      totalSeats,
      availableSeats,
      spotHeldSeats,
      rooms,
      occupancyPercentage:
        totalSeats > 0
          ? Math.round(((totalSeats - availableSeats) / totalSeats) * 100)
          : 0,
    };
  });

  return { summary, finalAvailableSeats };
}
