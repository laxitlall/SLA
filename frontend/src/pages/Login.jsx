import { Link, useNavigate } from "react-router";
import { useState } from "react";
import { apiLogin } from "../utils/api";

const IITB_ROLL_PATTERN = "^(\\d{2}[0-9A-Za-z]\\d{6}|\\d{2}[A-Za-z]\\d{4})$";

export default function Login() {
  const navigate = useNavigate();
  const [rollNumber, setRollNumber] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const handleLogin = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    try {
      await apiLogin(rollNumber, password);
      navigate("/room");
    } catch (err) {
      setErrorMsg(err.message || "Invalid credentials");
    }
  };

  return (
    <>
      <h1 className="text-4xl font-bold text-greenfont pb-5">Welcome Back!</h1>
      <div className="text-grayfont">
        Use your university roll number to continue
      </div>

      {errorMsg && (
        <div className="mt-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-xs font-medium text-red-700">
          {errorMsg}
        </div>
      )}

      <form className="flex flex-col gap-4 mt-9" onSubmit={handleLogin}>
        <div className="flex flex-col gap-2">
          <label className="font-medium text-[#434343]">University Roll Number</label>
          <input
            type="text"
            placeholder="e.g. 23B1001 or 200050001"
            className="text-[#838383] border border-gray-300 rounded-md py-5 px-4"
            required
            pattern={IITB_ROLL_PATTERN}
            title="Enter a valid IITB roll number (e.g. 200050001, 19D070001, or 23B1001)"
            value={rollNumber}
            onChange={(e) => {
              e.target.setCustomValidity("");
              setRollNumber(e.target.value);
            }}
            onInvalid={(e) => {
              if (e.target.validity.patternMismatch) {
                e.target.setCustomValidity(
                  "Please enter a valid IITB roll number (e.g. 200050001, 19D070001, or 23B1001)."
                );
              }
            }}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label className="font-medium text-[#434343]">Password</label>
          <input
            type="password"
            placeholder="At least 8 characters"
            className="text-[#838383] border border-gray-300 rounded-md py-5 px-4"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className="flex justify-end items-center text-xs">
          <button
            type="button"
            className="text-[#36594f] text-right font-medium"
          >
            Forgot password?
          </button>
        </div>
        <button
          type="submit"
          className="flex justify-center bg-[#174c3f] rounded-[10px] text-whitefont px-6 py-5 shadow-[0_20px_70px_rgba(23,76,63,0.15)] cursor-pointer"
        >
          <span className="text-whitefont font-bold">Log in to StudySpot</span>
        </button>
        <Link to="/" className="text-center text-[#636363] font-medium">
          Back to all options
        </Link>
      </form>
    </>
  );
}
