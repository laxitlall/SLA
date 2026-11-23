import { Outlet } from "react-router";
import reactLogo from "../assets/react.svg";

export default function CommonLayout() {
  return (
    <main className="min-h-screen bg-whitefont p-3">
      <div className="mx-auto grid min-h-[95vh] max-w-[90%] overflow-hidden rounded-[28px] bg-white shadow-[0_20px_70px_rgba(21,20,20,0.1)] lg:max-w-[1500px] lg:grid-cols-2">
        <section className="relative hidden bg-[#174c3f] p-14 text-white lg:flex lg:flex-col xl:p-20">
          <div className="relative my-auto max-w-2xl py-16">
            <p className="mb-6 text-sm font-bold uppercase tracking-widest text-[#9ed0c1]">Campus space, made simple</p>
            <h1 className="text-5xl font-semibold tracking-tighter xl:text-6xl">
              Find your seat.<br />Focus on what matters.
            </h1>
            <p className="mt-7 max-w-xl text-lg leading-8 text-[#c8ddd6]">
              See live availability across campus libraries and study rooms before you make the walk.
            </p>
            
          </div>
        </section>
        <section className="flex flex-col px-6 items-center justify-end">
          <div className="self-start flex gap-3 items-center">
            <img className="w-10 h-10" src={reactLogo} alt="logo" />
            <span className="text-xl font-medium text-greenfont">Study Spot</span>
          </div>
          <div className="mx-auto flex flex-col py-6 w-full max-w-md lg:py-12 sm:py-12">
            <div className="pb-5 text-lightgreenfont">WELCOME TO STUDYSPOT</div>
            <Outlet />
          </div>
        </section>
      </div>
    </main>
  );
}
