import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import Navbar, { getInitials } from "../components/Navbar";
import {
  apiConfirmHand,
  apiGetActiveHands,
  apiGetUserProfile,
  apiLowerHand,
  apiRaiseHand,
  apiRemoveFriend,
  apiRespondFriendRequest,
  apiSendFriendRequest,
  apiToggleRSVP,
  apiUpdateProfile,
  getCurrentUser,
  logoutUser,
} from "../utils/api";

export default function Profile() {
  const { rollNumber } = useParams();
  const navigate = useNavigate();
  const [currentUser, setCurrentUser] = useState(() => getCurrentUser());
  const targetRoll = rollNumber || currentUser?.roll_number;

  const [profile, setProfile] = useState(null);
  const [myActiveHand, setMyActiveHand] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [branch, setBranch] = useState("");
  const [hostel, setHostel] = useState("");
  const [bio, setBio] = useState("");
  const [error, setError] = useState("");

  const loadProfile = async () => {
    if (!targetRoll) {
      navigate("/login");
      return;
    }
    try {
      setError("");
      const [prof, hands] = await Promise.all([
        apiGetUserProfile(targetRoll, currentUser?.roll_number || ""),
        apiGetActiveHands(),
      ]);
      setProfile(prof);
      setBranch(prof.branch || "");
      setHostel(prof.hostel || "");
      setBio(prof.bio || "");

      if (currentUser) {
        const myHand = hands.find(
          (h) =>
            h.user_roll.toUpperCase() === currentUser.roll_number.toUpperCase()
        );
        setMyActiveHand(myHand || null);
      }
    } catch (err) {
      setError(err.message || "Could not load student profile.");
    }
  };

  useEffect(() => {
    loadProfile();
  }, [targetRoll]);

  const handleSaveProfile = async (e) => {
    e.preventDefault();
    if (!currentUser) return;
    const updated = await apiUpdateProfile(currentUser.roll_number, {
      branch,
      hostel,
      bio,
    });
    setCurrentUser(updated);
    setIsEditing(false);
    await loadProfile();
  };

  const handleLogout = () => {
    logoutUser();
    navigate("/");
  };

  if (error) {
    return (
      <div className="bg-roomgreen min-h-screen">
        <Navbar user={currentUser} activeHand={myActiveHand} />
        <main className="max-w-3xl mx-auto px-5 py-12">
          <div className="bg-white rounded-2xl p-8 border border-[#e3e8e5] text-center">
            <h1 className="text-2xl font-bold text-greenfont">{error}</h1>
            <Link
              to="/friends"
              className="mt-4 inline-block px-4 py-2 rounded-xl bg-greenfont text-white text-xs font-bold"
            >
              Back to Friends Search
            </Link>
          </div>
        </main>
      </div>
    );
  }

  if (!profile) return null;

  const isOwnProfile =
    currentUser &&
    currentUser.roll_number.toUpperCase() === profile.roll_number.toUpperCase();

  return (
    <div className="bg-roomgreen min-h-screen">
      <Navbar
        user={currentUser}
        activeHand={myActiveHand}
        onConfirmHand={async () => {
          if (!currentUser) return;
          const updated = await apiConfirmHand(currentUser.roll_number, 60);
          setMyActiveHand(updated);
          await loadProfile();
        }}
        onLowerHand={async () => {
          if (!currentUser) return;
          await apiLowerHand(currentUser.roll_number);
          setMyActiveHand(null);
          await loadProfile();
        }}
      />

      <main className="max-w-4xl mx-auto px-5 py-8 lg:py-10">
        {/* Top Profile Card */}
        <section className="bg-white rounded-2xl p-6 sm:p-8 border border-[#e3e8e5] shadow-sm">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-[#dcebe5] text-[#36594f] font-bold text-2xl flex items-center justify-center">
                {getInitials(profile.full_name)}
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h1 className="text-2xl font-bold text-greenfont">
                    {profile.full_name}
                  </h1>
                  <span className="px-2.5 py-0.5 rounded-full bg-roomgreen text-[#36594f] text-xs font-bold">
                    {profile.roll_number}
                  </span>
                </div>
                <div className="text-sm text-gray-600 mt-1">
                  {profile.branch} • {profile.hostel}
                </div>
                <div className="text-xs text-gray-400 mt-0.5">
                  {profile.email} • {profile.friends_count || 0} campus friends
                </div>
              </div>
            </div>

            {/* Action buttons: Own profile vs Another Student's profile */}
            {isOwnProfile ? (
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsEditing((prev) => !prev)}
                  className="px-4 py-2 rounded-xl bg-roomgreen text-greenfont text-xs font-bold hover:bg-[#dcebe5]"
                >
                  {isEditing ? "Cancel Edit" : "Edit Profile"}
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="px-4 py-2 rounded-xl bg-red-50 text-red-700 border border-red-200 text-xs font-bold hover:bg-red-100"
                >
                  Log out
                </button>
              </div>
            ) : (
              currentUser && (
                <div className="flex items-center gap-2">
                  {profile.relationship === "NONE" && (
                    <button
                      type="button"
                      onClick={async () => {
                        await apiSendFriendRequest(
                          currentUser.roll_number,
                          profile.roll_number
                        );
                        await loadProfile();
                      }}
                      className="px-4 py-2.5 rounded-xl bg-greenfont text-white text-xs font-bold hover:opacity-95"
                    >
                      + Send Friend Request
                    </button>
                  )}
                  {profile.relationship === "OUTGOING_PENDING" && (
                    <span className="px-4 py-2 rounded-xl bg-gray-100 text-gray-600 text-xs font-bold">
                      Friend Request Sent
                    </span>
                  )}
                  {profile.relationship === "INCOMING_PENDING" && (
                    <div className="flex gap-2">
                      <button
                        type="button"
                        onClick={async () => {
                          await apiRespondFriendRequest(
                            profile.roll_number,
                            currentUser.roll_number,
                            "ACCEPT"
                          );
                          await loadProfile();
                        }}
                        className="px-4 py-2 rounded-xl bg-greenfont text-white text-xs font-bold"
                      >
                        Accept Friend Request
                      </button>
                      <button
                        type="button"
                        onClick={async () => {
                          await apiRespondFriendRequest(
                            profile.roll_number,
                            currentUser.roll_number,
                            "DECLINE"
                          );
                          await loadProfile();
                        }}
                        className="px-3 py-2 rounded-xl bg-gray-100 text-gray-700 text-xs font-bold"
                      >
                        Decline
                      </button>
                    </div>
                  )}
                  {profile.relationship === "FRIENDS" && (
                    <div className="flex items-center gap-2">
                      <span className="px-3 py-2 rounded-xl bg-[#dcebe5] text-greenfont text-xs font-bold">
                        Friends ✓
                      </span>
                      <button
                        type="button"
                        onClick={async () => {
                          await apiRemoveFriend(
                            currentUser.roll_number,
                            profile.roll_number
                          );
                          await loadProfile();
                        }}
                        className="px-3 py-2 rounded-xl bg-white border border-gray-200 text-gray-500 text-xs font-medium hover:text-red-600"
                      >
                        Remove
                      </button>
                    </div>
                  )}
                </div>
              )
            )}
          </div>

          <p className="mt-5 text-sm text-gray-600 bg-roomgreen rounded-xl p-4">
            {profile.bio || "No study bio added yet."}
          </p>

          {/* Edit Own Profile Form */}
          {isOwnProfile && isEditing && (
            <form
              onSubmit={handleSaveProfile}
              className="mt-6 pt-6 border-t border-[#e3e8e5] grid grid-cols-1 sm:grid-cols-2 gap-4"
            >
              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold text-gray-700">
                  Department / Branch
                </label>
                <input
                  type="text"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-greenfont"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-xs font-bold text-gray-700">
                  Hostel
                </label>
                <input
                  type="text"
                  value={hostel}
                  onChange={(e) => setHostel(e.target.value)}
                  placeholder="e.g. Hostel 4"
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-greenfont"
                />
              </div>
              <div className="flex flex-col gap-1 sm:col-span-2">
                <label className="text-xs font-bold text-gray-700">
                  Study Bio / Current Focus
                </label>
                <input
                  type="text"
                  value={bio}
                  onChange={(e) => setBio(e.target.value)}
                  className="border border-gray-300 rounded-lg px-3 py-2 text-sm text-greenfont"
                />
              </div>
              <div className="sm:col-span-2 flex justify-end">
                <button
                  type="submit"
                  className="px-5 py-2.5 rounded-xl bg-greenfont text-white text-xs font-bold"
                >
                  Save Changes
                </button>
              </div>
            </form>
          )}
        </section>

        {/* Live Study Activity & RSVPs (Visible to Self or Accepted Friends) */}
        {profile.relationship === "FRIENDS" || profile.relationship === "SELF" ? (
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Active Raised Hand Card */}
            <section className="bg-white rounded-2xl p-6 border border-[#e3e8e5] shadow-sm flex flex-col justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold text-greenfont">
                  ✋ Live Study Status
                </h2>
                {profile.active_hand ? (
                  <div className="mt-3 rounded-xl bg-green-50 border border-green-200 p-4">
                    <div className="text-xs font-bold text-green-700">
                      HAND RAISED ({profile.active_hand.remaining_minutes} mins
                      left)
                    </div>
                    <div className="text-base font-bold text-greenfont mt-1">
                      📍 {profile.active_hand.zone_name} •{" "}
                      {profile.active_hand.room_name}
                    </div>
                    <div className="text-xs text-gray-600 mt-1">
                      &ldquo;{profile.active_hand.note}&rdquo;
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-gray-500">
                    {isOwnProfile
                      ? "You don't have your hand raised right now. Go to Live Spaces to raise your hand in any study room."
                      : `${profile.full_name} does not have their hand raised right now.`}
                  </p>
                )}
              </div>

              {isOwnProfile && profile.active_hand && (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={async () => {
                      const updated = await apiConfirmHand(
                        currentUser.roll_number,
                        60
                      );
                      setMyActiveHand(updated);
                      await loadProfile();
                    }}
                    className="px-3 py-2 rounded-xl bg-greenfont text-white text-xs font-bold"
                  >
                    Confirm Still Here (+1h)
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      await apiLowerHand(currentUser.roll_number);
                      setMyActiveHand(null);
                      await loadProfile();
                    }}
                    className="px-3 py-2 rounded-xl bg-red-50 text-red-700 border border-red-200 text-xs font-bold"
                  >
                    Unraise Hand
                  </button>
                </div>
              )}

              {!isOwnProfile && profile.active_hand && currentUser && (
                <button
                  type="button"
                  onClick={async () => {
                    await apiRaiseHand({
                      user_roll: currentUser.roll_number,
                      zone_name: profile.active_hand.zone_name,
                      room_id: profile.active_hand.room_id,
                      room_name: profile.active_hand.room_name,
                      note: `Studying with ${profile.full_name}`,
                      duration_minutes: 120,
                    });
                    navigate("/room");
                  }}
                  className="px-4 py-2.5 rounded-xl bg-greenfont text-white text-xs font-bold w-fit"
                >
                  ✋ Raise Hand in This Room Too
                </button>
              )}
            </section>

            {/* Planned RSVPs Card */}
            <section className="bg-white rounded-2xl p-6 border border-[#e3e8e5] shadow-sm">
              <h2 className="text-lg font-bold text-greenfont">
                📅 Upcoming Study RSVPs
              </h2>
              {profile.rsvps && profile.rsvps.length > 0 ? (
                <div className="mt-3 space-y-3">
                  {profile.rsvps.map((rsvp) => {
                    const isJoined =
                      currentUser &&
                      rsvp.participants?.some(
                        (p) =>
                          p.roll_number.toUpperCase() ===
                          currentUser.roll_number.toUpperCase()
                      );
                    return (
                      <div
                        key={rsvp.rsvp_id}
                        className="rounded-xl bg-roomgreen p-3.5 border border-[#dcebe5]"
                      >
                        <div className="flex justify-between items-start gap-2">
                          <span className="font-bold text-sm text-greenfont">
                            {rsvp.topic}
                          </span>
                          <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-white text-lightgreenfont">
                            {rsvp.start_time}
                          </span>
                        </div>
                        <div className="text-xs text-gray-600 mt-1">
                          📍 {rsvp.zone_name} • {rsvp.room_name}
                        </div>
                        {currentUser && (
                          <div className="mt-2 flex justify-end">
                            <button
                              type="button"
                              onClick={async () => {
                                await apiToggleRSVP(
                                  rsvp.rsvp_id,
                                  currentUser.roll_number
                                );
                                await loadProfile();
                              }}
                              className="px-2.5 py-1 rounded-lg bg-white border border-[#cdd8d3] text-greenfont text-xs font-bold"
                            >
                              {isJoined ? "Leave RSVP" : "Join RSVP"}
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="mt-3 text-sm text-gray-500">
                  No upcoming study RSVPs scheduled.
                </p>
              )}
            </section>
          </div>
        ) : (
          <section className="mt-6 bg-white rounded-2xl p-6 border border-[#e3e8e5] text-center">
            <p className="text-sm text-gray-600 font-medium">
              🔒 Become friends with <strong>{profile.full_name}</strong> to see
              their live study room check-ins and upcoming study RSVPs.
            </p>
          </section>
        )}
      </main>
    </div>
  );
}
