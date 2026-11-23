import { Link, useNavigate } from "react-router";
import { logoutUser } from "../utils/api";

export default function Home() {
  const navigate = useNavigate();

  const handleGuestContinue = () => {
    logoutUser();
    navigate("/room");
  };

  return (
    <>
      <h1 className="text-4xl font-bold text-greenfont pb-5">
        How would you like to enter?
      </h1>
      <div className="text-grayfont pb-5">
        Sign in for social features, or explore live spaces as a guest.
      </div>
      <div className="flex flex-col gap-4">
        <Link
          to="/login"
          className="group flex justify-between bg-[#174c3f] rounded-[15px] text-whitefont px-6 py-5 shadow-[0_20px_70px_rgba(23,76,63,0.15)] items-center"
        >
          <div className="flex flex-col items-start">
            <div className="text-whitefont font-bold">Log in</div>
            <div className="mt-1text-[#C4C4C4]">Return to your profile</div>
          </div>
          <div className="text-white text-xl group-hover:translate-x-1">→</div>
        </Link>
        <Link
          to="/signup"
          className="group flex justify-between border-solid border-[#636363] border-1 rounded-[15px] text-whitefont px-6 py-5 items-center hover:border-lightgreenfont hover:bg-[#f7faf8]"
        >
          <div className="flex flex-col items-start">
            <div className="text-greenfont font-bold">Sign up</div>
            <div className="mt-1 text-grayfont"> Create a personalized campus profile</div>
          </div>
          <div className="text-black text-xl group-hover:translate-x-1">→</div>
        </Link>
        <div className="my-1 flex items-center gap-4">
          <span className="h-px flex-1 bg-grayfont" />
          <span className="text-xs font-bold text-grayfont">OR</span>
          <span className="h-px flex-1 bg-grayfont" />
        </div>
        <button
          type="button"
          onClick={handleGuestContinue}
          className="group flex justify-center gap-3 rounded-[10px] px-6 py-5 text-[#36594f] bg-[#eef3f0] cursor-pointer hover:bg-[#e3ece7]"
        >
          <div className="font-medium">Continue as guest</div>
          <div className="text-greenfont text-xl group-hover:translate-x-1">→</div>
        </button>
      </div>
    </>
  );
}
