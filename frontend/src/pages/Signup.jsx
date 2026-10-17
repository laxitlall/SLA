import reactLogo from '../assets/react.svg'
import { Link } from "react-router";

export default function Signup() {
    return (
        <main className="min-h-screen bg-whitefont p-3">
                       <div className='mx-auto grid min-h-[95vh] max-w-[50%] overflow-hidden rounded-[28px] bg-white shadow-[0_20px_70px_rgba(21,20,20,0.1)]'>
                          <section className='flex flex-col p-7 items-center'>
                            <div className='self-start flex gap-3 items-center'>
                              <img className='w-10 h-10' src={reactLogo} alt="logo"/>
                              <span className='text-xl font-medium text-greenfont'>Study Spot</span>
                            </div>
                            <div className='flex flex-col py-10 w-[70%]'>
                              <div className='pb-5 text-lightgreenfont'>WELCOME TO STUDYSPOT</div>
                              <h1 className='text-4xl font-bold text-greenfont pb-5'>Welcome Back!</h1>
                              <div className='text-grayfont'>Use your university roll number to continue</div>
                              <form className='flex flex-col gap-4 mt-9'>
                                <div className='flex flex-col gap-2'>
                                    <label className='font-medium text-[#434343]'>Full name</label>
                                    <input type="text" placeholder="Enter your full name" className='text-[#838383] border border-gray-300 rounded-md py-5 px-4' />
                                </div>
                                <div className='flex flex-col gap-2'>
                                    <label className='font-medium text-[#434343]'>University Roll Number</label>
                                    <input type="text" placeholder="Enter your university roll number" className='text-[#838383] border border-gray-300 rounded-md py-5 px-4' />
                                </div>
                                <div className='flex flex-col gap-2'>
                                    <label className='font-medium text-[#434343]'>University email</label>
                                    <input type="email" placeholder="Enter your university email" className='text-[#838383] border border-gray-300 rounded-md py-5 px-4' />
                                </div>
                                <div className='flex flex-col gap-2'>
                                    <label className='font-medium text-[#434343]'>Password</label>
                                    <input type="password" placeholder="At least 8 characters" className='text-[#838383] border border-gray-300 rounded-md py-5 px-4' />
                                </div>
                                <div className='flex flex-col gap-2'>
                                    <label className='font-medium text-[#434343]'>Confirm Password</label>
                                    <input type="password" placeholder="Confirm your password" className='text-[#838383] border border-gray-300 rounded-md py-5 px-4' />
                                </div>
                                <button className='flex justify-center bg-[#174c3f] rounded-[10px] text-whitefont px-6 py-5 shadow-[0_20px_70px_rgba(23,76,63,0.15)]'>
                                    <span className='text-whitefont font-bold'>Create my account</span>
                                </button>
                                <Link to="/" className='text-center text-[#636363] font-medium'>Back to all options</Link>
                              </form>
                            </div>
                          </section>
                       </div>
                    </main>
    )
}