import { useState } from "react";
import { Link } from "react-router";

export default function ZoneCard({
  zone,
  user = null,
  activeHand = null,
  friendsInZone = [],
  onRaiseHand,
  onLowerHand,
  onOpenRSVPModal,
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div
      onClick={() => setIsExpanded((prev) => !prev)}
      className="border border-[#e3e8e5] rounded-xl p-5 shadow-sm bg-white hover:shadow-md transition-shadow cursor-pointer"
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-xl font-semibold text-greenfont">{zone.name}</h2>
            {friendsInZone.length > 0 && (
              <span className="px-2.5 py-0.5 text-xs rounded-full font-bold bg-[#dcebe5] text-[#285446]">
                ✋ {friendsInZone.length}{" "}
                {friendsInZone.length === 1 ? "friend" : "friends"} here
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5">
            {zone.rooms?.length || 0}{" "}
            {zone.rooms?.length === 1 ? "room" : "rooms"} • Click to{" "}
            {isExpanded ? "hide" : "view"} rooms & seats
          </p>
        </div>
        <span
          className={`px-2.5 py-1 text-xs rounded-full font-medium ${
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
          {zone.rooms.map((room) => {
            const isMyHandHere =
              activeHand &&
              activeHand.zone_name === zone.name &&
              activeHand.room_id === room.room_id;

            const friendsInRoom = friendsInZone.filter(
              (f) => f.active_hand?.room_id === room.room_id
            );

            return (
              <div
                key={room.room_id}
                className="rounded-lg bg-roomgreen p-3.5 flex flex-col gap-2.5"
              >
                <div className="flex flex-wrap justify-between items-center gap-2">
                  <div>
                    <span className="font-semibold text-sm text-greenfont">
                      {room.room_name}
                    </span>
                    <span className="ml-2 text-xs text-gray-600">
                      (<strong className="text-greenfont">{room.availableSeats}</strong>{" "}
                      / {room.totalSeats} free)
                    </span>
                  </div>

                  {user && (
                    <div className="flex items-center gap-2">
                      {isMyHandHere ? (
                        <button
                          type="button"
                          onClick={() => onLowerHand?.()}
                          className="px-2.5 py-1 rounded-lg bg-greenfont text-white text-xs font-bold hover:opacity-90"
                        >
                          ✋ Hand Raised ✓ (Lower)
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() =>
                            onRaiseHand?.({
                              zone_name: zone.name,
                              room_id: room.room_id,
                              room_name: room.room_name,
                            })
                          }
                          className="px-2.5 py-1 rounded-lg bg-white border border-[#cdd8d3] text-greenfont text-xs font-bold hover:bg-[#dcebe5]"
                        >
                          ✋ Raise Hand Here
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() =>
                          onOpenRSVPModal?.({
                            zone_name: zone.name,
                            room_id: room.room_id,
                            room_name: room.room_name,
                          })
                        }
                        className="px-2.5 py-1 rounded-lg bg-white border border-[#cdd8d3] text-[#36594f] text-xs font-bold hover:bg-[#dcebe5]"
                      >
                        📅 + RSVP
                      </button>
                    </div>
                  )}
                </div>

                {/* Friends currently studying in this specific room */}
                {friendsInRoom.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 text-xs bg-white/80 px-2.5 py-1.5 rounded-md border border-[#dcebe5]">
                    <span className="font-semibold text-greenfont">
                      Studying here now:
                    </span>
                    {friendsInRoom.map((friend) => (
                      <Link
                        key={friend.roll_number}
                        to={`/profile/${friend.roll_number}`}
                        className="underline font-medium text-lightgreenfont hover:text-greenfont"
                      >
                        {friend.full_name} ({friend.active_hand?.note || "Studying"})
                      </Link>
                    ))}
                  </div>
                )}

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
                        title={`${seat.seat_id}: ${seat.computed_state.replace(
                          "_",
                          " "
                        )}`}
                        className={`text-[11px] px-2 py-0.5 rounded border font-medium ${stateStyles}`}
                      >
                        {seat.seat_id.split("-").pop()}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
          <div className="flex flex-wrap gap-4 text-xs text-gray-500 pt-1">
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
