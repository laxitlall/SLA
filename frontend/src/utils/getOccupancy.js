// src/utils/getOccupancy.js
import campusData from '../../../backend/database/campus_occupancy.json';

export function getCampusOccupancySummary() {
  let finalAvailableSeats = 0;

  // Process zones to calculate total vs available seats
  const summary = campusData.zones.map(zone => {
    let totalSeats = 0;
    let availableSeats = 0;

    zone.rooms.forEach(room => {
      room.seats.forEach(seat => {
        totalSeats++;
        if (seat.computed_state === "AVAILABLE") {
          availableSeats++;
        }
      });
    });
    finalAvailableSeats += availableSeats;

    return {
      name: zone.name,               // e.g., "Hostel 1" or "Central Library"
      zone_type: zone.zone_type,     // "hostel" or "library"
      totalSeats,
      availableSeats,
      occupancyPercentage: totalSeats > 0 ? Math.round(((totalSeats - availableSeats) / totalSeats) * 100) : 0
    };
  });

  return { summary, finalAvailableSeats };
}