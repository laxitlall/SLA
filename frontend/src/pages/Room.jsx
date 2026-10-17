import reactLogo from '../assets/react.svg'
import { Link } from "react-router";
import { getCampusOccupancySummary } from '../utils/getOccupancy';

export default function Room() {
    const {summary: zonesSummary, finalAvailableSeats } = getCampusOccupancySummary();
    return (
        <div className="bg-roomgreen min-h-screen">
        <header className="sticky top-0 z-30 px-10 py-4 bg-white border-[#e3e8e5] border-b-[1px]">
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                    <img className='w-10 h-10' src={reactLogo} alt="logo"/>
                    <span className='text-xl font-medium text-greenfont'>Study Spot</span>
                </div>
                <div className="flex gap-3 bg-roomgreen rounded-[10px] px-3 py-2 items-center">
                    <div className="py-1 px-2 text-grayfont font-medium text-sm">Search for libraries and study rooms</div>
                </div>
                <div className="flex gap-4 items-center">
                    <div className="p-2 rounded-[10px] bg-roomgreen text-[#36594f] font-medium text-xs">Guest mode</div>
                    <Link to="/login" className='py-2 px-3 rounded-[10px] text-[#636363] font-bold text-white bg-greenfont'>Log in</Link>
                </div>
            </div>
        </header>
        <main className="max-w-[1380px] px-5 py-8 mx-auto lg:px-10 lg:py-10">
            <section className="flex justify-between items-end">
                <div>
                    <div className="mb-2 text-sm font-medium text-lightgreenfont">LIVE CAMPUS OVERVIEW</div>
                    <h1 className="text-3xl font-bold text-greenfont">Find your place to focus</h1>
                    <div className="mt-3 text-gray-500">Live seat availability across IIT Bombay.</div>
                </div>
                <div className="flex items-center h-fit gap-2 px-4 py-3 rounded-xl border border-[#e3e8e5] bg-white text-sm font-medium">
                    <span className="text-[#43554e]">Live Now</span>
                    <span className="text-[#929a96]">Updated 2 minutes ago</span>
                </div>
            </section>
            <section className="mt-10">
                <div className="flex justify-between">
                    <div>
                        <div className='text-xl text-greenfont font-bold'>Spaces near you</div>
                        <div className="mt-1 text-sm text-gray-500">{finalAvailableSeats} seats available across 22 spaces</div>
                    </div>
                    <div className="flex rounded-xl bg-[#e9eeeb] p-1 items-center">
                        <span className="rounded-lg px-4 py-2 text-xs font-bold transition bg-white text-[#285446] shadow-sm">All spaces</span>
                        <span className="rounded-lg px-4 py-2 text-xs font-bold transition text-[#75807b]">Library</span>
                        <span className="rounded-lg px-4 py-2 text-xs font-bold transition text-[#75807b]">Study room</span>
                    </div>
                </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-2 mt-5">
                    {zonesSummary.map((zone, index) => (
          <div 
            key={index} 
            className="border rounded-xl p-5 shadow-sm bg-white hover:shadow-md transition-shadow cursor-pointer"
          >
            <div className="flex justify-between items-start mb-4">
              <h2 className="text-xl font-semibold text-greenfont">{zone.name}</h2>
              <span className={`px-2 py-1 text-xs rounded-full font-medium bg-roomgreen ${
                zone.availableSeats > 0 ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}>
                {zone.availableSeats > 0 ? 'Open Spaces' : 'Full'}
              </span>
            </div>

            {/* Availability Stats */}
            <div className="space-y-2">
              <p className="text-sm text-gray-600">
                Available Seats: <strong className="text-black">{zone.availableSeats}</strong> / {zone.totalSeats}
              </p>
              
              {/* Progress Bar */}
              <div className="w-full bg-gray-200 h-2 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${zone.occupancyPercentage > 80 ? 'bg-red-500' : 'bg-lightgreenfont'}`}
                  style={{ width: `${zone.occupancyPercentage}%` }}
                />
              </div>
              <p className="text-xs text-right text-gray-500">{zone.occupancyPercentage}% Occupied</p>
            </div>
          </div>
        ))}
                </div>
            </section>
        </main>
        <footer>

        </footer>
        </div>
    );
}