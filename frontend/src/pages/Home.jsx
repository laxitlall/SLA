import reactLogo from '../assets/react.svg'
import { Link } from "react-router";

export default function Home() {
    return(
        <main className="min-h-screen bg-whitefont p-3">
       <div className='mx-auto grid min-h-[95vh] max-w-[50%] overflow-hidden rounded-[28px] bg-white shadow-[0_20px_70px_rgba(21,20,20,0.1)]'>
          <section className='flex flex-col p-7 items-center'>
            <div className='self-start flex gap-3 items-center'>
              <img className='w-10 h-10' src={reactLogo} alt="logo"/>
              <span className='text-xl font-medium text-greenfont'>Study Spot</span>
            </div>
            <div className='flex flex-col py-10 w-[70%]'>
              <div className='pb-5 text-lightgreenfont'>WELCOME TO STUDYSPOT</div>
              <h1 className='text-4xl font-bold text-greenfont pb-5'>How would you like to enter?</h1>
              <div className='text-grayfont pb-5'>Sign in for social features, or explore live spaces as a guest.</div>
              <div className='flex flex-col gap-4'>
                <Link to="/login" className='flex justify-between bg-[#174c3f] rounded-[10px] text-whitefont px-6 py-5 shadow-[0_20px_70px_rgba(23,76,63,0.15)]'>
                  <div className='flex flex-col gap-4 items-start'>
                    <div className='text-whitefont font-bold'>Log in</div>
                    <div className='text-[#C4C4C4]'>Return to your profile</div>
                  </div>
                  <div>next</div>
                </Link>
                <Link to="/signup" className='flex justify-between border-solid border-[#636363] border-1 rounded-[10px] text-whitefont px-6 py-5'>
                  <div className='flex flex-col gap-4 items-start'>
                    <div className='text-greenfont font-bold'>Sign up</div>
                    <div className='text-grayfont'>Create a personalized campus profile</div>
                  </div>
                  <div>next</div>
                </Link>
                 <div className="my-1 flex items-center gap-4">
                  <span className="h-px flex-1 bg-grayfont" />
                  <span className="text-xs font-bold text-grayfont">OR</span>
                  <span className="h-px flex-1 bg-grayfont" />
                 </div>
                 <button className='rounded-[10px] px-6 py-5 text-[#36594f] bg-[#eef3f0]'>
                  <div className='text-xl font-medium'>Continue as guest</div>
                 </button>
              </div>
            </div>
          </section>
       </div>
    </main>
    );
}