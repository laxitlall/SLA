import { Link, useLocation } from "react-router";
import reactLogo from "../assets/react.svg";

export function getInitials(name = "") {
  return (
    name
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((w) => w[0].toUpperCase())
      .slice(0, 2)
      .join("") || "U"
  );
}

export default function Navbar({
  user,
  searchQuery,
  onSearchChange,
  searchPlaceholder = "Search for libraries and study rooms",
  showSearch = false,
  activeHand = null,
  onConfirmHand,
  onLowerHand,
  pendingRequestsCount = 0,
}) {
  const location = useLocation();
  const abbrName = user ? getInitials(user.full_name) : "";

  return (
    <header className="sticky top-0 z-30 bg-white border-[#e3e8e5] border-b-[1px]">
      <div className="px-5 lg:px-10 py-4 flex justify-between items-center gap-4">
        <div className="flex items-center gap-6">
          <Link to="/room" className="flex items-center gap-3">
            <img className="w-10 h-10" src={reactLogo} alt="logo" />
            <span className="text-xl font-medium text-greenfont">Study Spot</span>
          </Link>

          {user && (
            <nav className="hidden sm:flex items-center gap-1 bg-roomgreen p-1 rounded-xl">
              <Link
                to="/room"
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                  location.pathname === "/room" ||
                  location.pathname === "/personal-room"
                    ? "bg-white text-greenfont shadow-sm"
                    : "text-[#63706b] hover:text-greenfont"
                }`}
              >
                Spaces
              </Link>
              <Link
                to="/friends"
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
                  location.pathname === "/friends"
                    ? "bg-white text-greenfont shadow-sm"
                    : "text-[#63706b] hover:text-greenfont"
                }`}
              >
                <span>Friends</span>
                {pendingRequestsCount > 0 && (
                  <span className="px-1.5 py-0.5 text-[10px] rounded-full bg-greenfont text-white">
                    {pendingRequestsCount}
                  </span>
                )}
              </Link>
              <Link
                to="/profile"
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition ${
                  location.pathname.startsWith("/profile")
                    ? "bg-white text-greenfont shadow-sm"
                    : "text-[#63706b] hover:text-greenfont"
                }`}
              >
                Profile
              </Link>
</nav>
          )}
        </div>

        {showSearch && (
          <div className="hidden gap-3 bg-roomgreen rounded-[10px] px-3 py-2 items-center w-full max-w-xs md:flex">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => onSearchChange?.(e.target.value)}
              placeholder={searchPlaceholder}
              className="w-full bg-transparent py-1 px-2 text-greenfont placeholder:text-grayfont font-medium text-sm outline-none"
            />
          </div>
        )}

        {user ? (
          <div className="flex items-center gap-3">
            {activeHand && (
              <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 rounded-xl bg-green-50 border border-green-200 text-xs font-medium text-green-800">
                <span>✋ {activeHand.zone_name}</span>
                <span className="text-green-600">
                  ({activeHand.remaining_minutes}m left)
                </span>
              </div>
            )}
            <Link
              to="/profile"
              className="flex gap-3 items-center p-2 rounded-lg hover:bg-[#F0F4F2] transition"
            >
              <div className="px-2.5 py-1.5 rounded-[10px] bg-[#dcebe5] text-[#36594f] font-bold text-sm">
                {abbrName}
              </div>
              <div className="hidden flex-col sm:flex">
                <span className="text-sm text-greenfont font-bold">
                  {user.full_name}
                </span>
                <span className="text-xs text-gray-500">
                  {user.branch || user.roll_number}
                </span>
              </div>
            </Link>
          </div>
        ) : (
          <div className="flex gap-4 items-center">
            <div className="hidden p-2 rounded-[10px] bg-roomgreen text-[#36594f] font-medium text-xs sm:block">
              Guest mode
            </div>
            <Link
              to="/login"
              className="py-2 px-3 rounded-[10px] font-bold text-white bg-greenfont"
            >
              Log in
            </Link>
          </div>
        )}
      </div>

      {/* Auto-Unraise Check-in Notification Banner */}
      {user && activeHand && activeHand.needs_confirmation && (
        <div className="bg-amber-50 border-t border-amber-200 px-5 lg:px-10 py-2.5 flex flex-col sm:flex-row justify-between items-center gap-3">
          <div className="text-xs sm:text-sm text-amber-900 font-medium">
            ⏰ <strong>Check-in Confirmation:</strong> Your raised hand at{" "}
            <strong>
              {activeHand.zone_name} ({activeHand.room_name})
            </strong>{" "}
            will auto-unraise in{" "}
            <strong>{activeHand.remaining_minutes} min</strong>. Are you still
            studying there?
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={onConfirmHand}
              className="px-3 py-1.5 rounded-lg bg-greenfont text-white text-xs font-bold hover:opacity-95"
            >
              Yes, still here (+1 hr)
            </button>
            <button
              type="button"
              onClick={onLowerHand}
              className="px-3 py-1.5 rounded-lg bg-white border border-amber-300 text-amber-900 text-xs font-bold hover:bg-amber-100"
            >
              No, unraise hand
            </button>
          </div>
        </div>
      )}
    </header>
  );
}
