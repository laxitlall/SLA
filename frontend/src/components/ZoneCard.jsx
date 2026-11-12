import { useState } from "react";

export default function ZoneCard({ zone }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      onClick={() => setIsExpanded((prev) => !prev)}
      className="border rounded-xl p-5 shadow-sm bg-white hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="text-xl font-semibold text-greenfont">{zone.name}</h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {zone.rooms?.length || 0} {zone.rooms?.length === 1 ? "room" : "rooms"} • Click to{" "}
            {isExpanded ? "hide" : "view"} rooms
          </p>
        </div>
        <span
          className={`px-2 py-1 text-xs rounded-full font-medium bg-roomgreen ${
            zone.availableSeats > 0
              ? "bg-green-100 text-green-700"
              : "bg-red-100 text-red-700"
          }`}
        >
          {zone.availableSeats > 0 ? "Open Spaces" : "Full"}
        </span>
      </div>

      {/* Availability Stats */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-gray-600">
          <p>
            Available Seats:{" "}
            <strong className="text-black">{zone.availableSeats}</strong> /{" "}
            {zone.totalSeats}
          </p>
          {zone.spotHeldSeats > 0 && (
            <span className="text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full font-medium">
              {zone.spotHeldSeats} spot held
            </span>
          )}
        </div>

        {/* Progress Bar */}
        <div className="w-full bg-gray-200 h-2 rounded-full overflow-hidden">
          <div
            className={`h-full ${
              zone.occupancyPercentage > 80 ? "bg-red-500" : "bg-lightgreenfont"
            }`}
            style={{ width: `${zone.occupancyPercentage}%` }}
          />
        </div>
        <p className="text-xs text-right text-gray-500">
          {zone.occupancyPercentage}% Occupied
        </p>
      </div>

      {/* Expandable Room Breakdown */}
      {isExpanded && zone.rooms && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="mt-4 pt-4 border-t border-[#e3e8e5] space-y-3 cursor-default"
        >
          {zone.rooms.map((room) => (
            <div
              key={room.room_id}
              className="rounded-lg bg-roomgreen p-3 flex flex-col gap-2"
            >
              <div className="flex justify-between items-center">
                <span className="font-medium text-sm text-greenfont">
                  {room.room_name}
                </span>
                <span className="text-xs text-gray-600">
                  <strong className="text-greenfont">{room.availableSeats}</strong> /{" "}
                  {room.totalSeats} free
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {room.seats.map((seat) => {
                  const stateStyles =
                    seat.computed_state === "AVAILABLE"
                      ? "bg-green-100 text-green-800 border-green-200"
                      : seat.computed_state === "SPOT_HELD"
                      ? "bg-amber-100 text-amber-800 border-amber-200"
                      : "bg-red-100 text-red-800 border-red-200";
                  return (
                    <span
                      key={seat.seat_id}
                      title={`${seat.seat_id}: ${seat.computed_state.replace("_", " ")}`}
                      className={`text-[11px] px-2 py-0.5 rounded border font-medium ${stateStyles}`}
                    >
                      {seat.seat_id.split("-").pop()}
                    </span>
                  );
                })}
              </div>
            </div>
          ))}
          <div className="flex gap-4 text-xs text-gray-500 pt-1">
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-green-200 inline-block" />{" "}
              Available
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-amber-200 inline-block" />{" "}
              Spot Held (Bag/Laptop)
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-red-200 inline-block" />{" "}
              Occupied
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
