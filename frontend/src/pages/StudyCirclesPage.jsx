import { Link } from "react-router";
import Navbar from "../components/Navbar";
import StudyCircles from "../components/StudyCircles";
import { getCurrentUser } from "../utils/api";

export default function StudyCirclesPage() {
  const user = getCurrentUser();

  return (
    <div className="min-h-screen bg-roomgreen">
      <Navbar user={user} />
      <main className="mx-auto max-w-[1380px] px-5 py-7 lg:px-10 lg:py-9">
        {user ? (
          <StudyCircles user={user} />
        ) : (
          <section className="rounded-2xl border border-[#cbded6] bg-white p-6">
            <h1 className="text-2xl font-bold text-greenfont">Study Circles</h1>
            <p className="mt-2 text-sm text-gray-600">Log in to reserve a group-study room and invite friends.</p>
            <Link to="/login" className="mt-4 inline-block rounded-xl bg-greenfont px-4 py-2 text-sm font-bold text-white">Log in</Link>
          </section>
        )}
      </main>
    </div>
  );
}
