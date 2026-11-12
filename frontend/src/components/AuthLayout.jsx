import { Outlet } from "react-router";
import reactLogo from "../assets/react.svg";

export default function AuthLayout() {
  return (
    <main className="min-h-screen bg-whitefont p-3">
      <div className="mx-auto grid min-h-[95vh] max-w-[90%] overflow-hidden rounded-[28px] bg-white shadow-[0_20px_70px_rgba(21,20,20,0.1)] lg:max-w-[800px]">
        <section className="flex flex-col p-7 items-center">
          <div className="self-start flex gap-3 items-center">
            <img className="w-10 h-10" src={reactLogo} alt="logo" />
            <span className="text-xl font-medium text-greenfont">Study Spot</span>
          </div>
          <div className="mx-auto flex flex-col py-10 w-[100%] lg:w-[70%] md:w-[80%]">
            <div className="pb-5 text-lightgreenfont">WELCOME TO STUDYSPOT</div>
            <Outlet />
          </div>
        </section>
      </div>
    </main>
  );
}
