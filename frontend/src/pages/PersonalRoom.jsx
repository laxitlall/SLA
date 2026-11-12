import { useState } from "react";
import reactLogo from "../assets/react.svg";
import { Link } from "react-router";
import { getCampusOccupancySummary } from "../utils/getOccupancy";
import ZoneCard from "../components/ZoneCard";

export default function PersonalRoom() {
  const { summary: zonesSummary } = getCampusOccupancySummary();
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("all");
  const name = "Laxit lall";
  const branch = "Computer Science"
  const abbrName = name.trim().split(/\s+/).map(word => word[0].toUpperCase()).join('');

  const filteredZones = zonesSummary.filter((zone) => {
    const matchesSearch = zone.name
      .toLowerCase()
      .includes(searchQuery.trim().toLowerCase());
    const matchesFilter =
      activeFilter === "all" || zone.zone_type === activeFilter;
    return matchesSearch && matchesFilter;
  });

  const filteredAvailableSeats = filteredZones.reduce(
    (sum, zone) => sum + zone.availableSeats,
    0
  );

  return (
    <div className="bg-roomgreen min-h-screen">
      <header className="sticky top-0 z-30 px-10 py-4 bg-white border-[#e3e8e5] border-b-[1px]">
        <div className="flex justify-between items-center">
          <Link to="/" className="flex items-center gap-3">
            <img className="w-10 h-10" src={reactLogo} alt="logo" />
            <span className="text-xl font-medium text-greenfont">Study Spot</span>
          </Link>
          <div className="hidden gap-3 bg-roomgreen rounded-[10px] px-3 py-2 items-center w-full max-w-xs md:flex">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search for libraries and study rooms"
              className="w-full bg-transparent py-1 px-2 text-greenfont placeholder:text-grayfont font-medium text-sm outline-none"
            />
          </div>
          <div className="flex gap-4 items-center p-2 rounded-lg hover:bg-[#F0F4F2]">
            <div className="px-2 py-1 rounded-[10px] bg-[#dcebe5] text-[#36594f] font-medium">
              {abbrName}
            </div>
            <div className="hidden flex-col sm:flex">
                <span className="text-sm text-greenfont font-bold">{name}</span>
                <span className="text-xs text-gray-500">{branch}</span>
            </div>
          </div>
        </div>
      </header>
      <main className="max-w-[1380px] px-5 py-8 mx-auto lg:px-10 lg:py-10">
        <section className="flex flex-col gap-5 justify-between items-end md:flex-row">
          <div className="w-full md:w-fit">
            <div className="mb-2 font-medium text-lightgreenfont">
              Hello, {name}
            </div>
            <h1 className="text-3xl font-bold text-greenfont">
              Find your place to focus
            </h1>
            <div className="mt-3 text-gray-500">
              Live seat availability across IIT Bombay.
            </div>
          </div>
          <div className="flex w-full items-center h-fit gap-2 px-4 py-3 rounded-xl border border-[#e3e8e5] bg-white text-sm font-medium md:w-fit">
            <span className="text-[#43554e]">Live Now</span>
            <span className="text-[#929a96]">Updated 2 minutes ago</span>
          </div>
        </section>
        <section className="mt-10 flex flex-col gap-5 justify-between md:flex-row">
            <div className="flex flex-2 justify-between gap-5 rounded-xl bg-greenfont p-5 text-white">
                <div className="flex flex-col">
                    <div className="font-bold text-[#9bcabd]">Your next study plan</div>
                    <div className="text-xl font-bold">Quiet Study Room</div>
                </div>
                <button className="bg-white h-fit my-auto text-greenfont py-3 px-3 rounded-xl font-medium">
              View plan
            </button>
            </div>
            <div className="flex flex-1 items-center justify-between gap-5 rounded-xl bg-white p-5 text-greenfont">
                <div className="flex flex-col">
                    <div className="text-xs font-medium text-gray-500">FRIENDS ON CAMPUS</div>
                    <div className="mt-2 text-xl font-bold text-[#2c473e]">3 STUDING NOW</div>
                    <div className="mt-1 text-sm text-gray-400">See where they are</div>
                </div>
            </div>
        </section>
        <section className="mt-10">
          <div className="flex flex-col justify-between md:flex-row">
            <div className="pb-4 md:pb-0">
              <div className="text-xl text-greenfont font-bold">Spaces near you</div>
              <div className="mt-1 text-sm text-gray-500">
                {filteredAvailableSeats} seats available across {filteredZones.length}{" "}
                {filteredZones.length === 1 ? "space" : "spaces"}
              </div>
            </div>
            <div className="flex w-fit rounded-xl bg-[#e9eeeb] p-1 items-center">
              <button
                type="button"
                onClick={() => setActiveFilter("all")}
                className={`rounded-lg px-4 py-2 text-xs font-bold transition ${
                  activeFilter === "all"
                    ? "bg-white text-[#285446] shadow-sm"
                    : "text-[#75807b]"
                }`}
              >
                All spaces
              </button>
              <button
                type="button"
                onClick={() => setActiveFilter("library")}
                className={`rounded-lg px-4 py-2 text-xs font-bold transition ${
                  activeFilter === "library"
                    ? "bg-white text-[#285446] shadow-sm"
                    : "text-[#75807b]"
                }`}
              >
                Library
              </button>
              <button
                type="button"
                onClick={() => setActiveFilter("hostel")}
                className={`rounded-lg px-4 py-2 text-xs font-bold transition ${
                  activeFilter === "hostel"
                    ? "bg-white text-[#285446] shadow-sm"
                    : "text-[#75807b]"
                }`}
              >
                Study room
              </button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-2 mt-5">
            {filteredZones.map((zone) => (
              <ZoneCard key={zone.name} zone={zone} />
            ))}
          </div>
        </section>
      </main>
      <footer></footer>
    </div>
  );
}
