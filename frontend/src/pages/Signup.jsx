import { Link, useNavigate } from "react-router";
import { useRef, useState } from "react";
import { apiSignup } from "../utils/api";

const IITB_ROLL_PATTERN = "^(\\d{2}[0-9A-Za-z]\\d{6}|\\d{2}[A-Za-z]\\d{4})$";
const IITB_EMAIL_PATTERN = "^[^\\s@]+@iitb\\.(ac\\.in|AC\\.IN)$";

export default function Signup() {
  const navigate = useNavigate();
  const confirmPasswordRef = useRef(null);
  const [fullName, setFullName] = useState("");
  const [rollNumber, setRollNumber] = useState("");
  const [email, setEmail] = useState("");
  const [branch, setBranch] = useState("");
  const [hostel, setHostel] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");

  const handleSignup = async (e) => {
    e.preventDefault();
    setErrorMsg("");
    try {
      await apiSignup({
        full_name: fullName,
        roll_number: rollNumber,
        email,
        branch,
        hostel,
        password,
      });
      navigate("/room");
    } catch (err) {
      setErrorMsg(err.message || "Could not create account.");
    }
  };

  return (
    <>
      <h1 className="text-4xl font-bold text-greenfont pb-5">Create Campus Profile</h1>
      <div className="text-grayfont">Use your IIT Bombay roll number and @iitb.ac.in email</div>

      {errorMsg && (
        <div className="mt-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-xs font-medium text-red-700">
          {errorMsg}
        </div>
      )}

      <form className="flex flex-col gap-4 mt-9" onSubmit={handleSignup}>
        <div className="flex flex-col gap-2">
          <label className="font-medium text-[#434343]">Full name</label>
          <input
            type="text"
            placeholder="Enter your full name"
            className="text-[#838383] border border-gray-300 rounded-md py-5 px-4"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
            <label className="font-medium text-[#434343]">University email</label>
            <input
              type="email"
              placeholder="Enter your university email"
              className="text-[#838383] border border-gray-300 rounded-md py-5 px-4"
              required
              pattern={IITB_EMAIL_PATTERN}
              title="Must be an @iitb.ac.in email address"
              value={email}
              onChange={(e) => {
                e.target.setCustomValidity("");
                setEmail(e.target.value);
              }}
              onInvalid={(e) => {
                if (e.target.validity.patternMismatch) {
                  e.target.setCustomValidity(
                    "Please enter a valid IITB email ending with @iitb.ac.in."
                  );
                }
              }}
            />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex flex-col gap-2">
            <label className="font-medium text-[#434343]">
              Department / Branch
            </label>
            <input
              type="text"
              placeholder="e.g. Computer Science"
              className="text-[#838383] border border-gray-300 rounded-md py-4 px-4"
              required
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="font-medium text-[#434343]">Hostel</label>
            <input
              type="text"
              placeholder="e.g. Hostel 4"
              className="text-[#838383] border border-gray-300 rounded-md py-4 px-4"
              required
              value={hostel}
              onChange={(e) => setHostel(e.target.value)}
            />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex flex-col gap-2">
            <label className="font-medium text-[#434343]">Password</label>
            <input
              type="password"
              placeholder="At least 8 characters"
              className="text-[#838383] border border-gray-300 rounded-md py-5 px-4"
              required
              minLength={8}
              value={password}
              onChange={(e) => {
                const val = e.target.value;
                setPassword(val);
                if (confirmPasswordRef.current) {
                  confirmPasswordRef.current.setCustomValidity(
                    confirmPassword && confirmPassword !== val
                      ? "Passwords do not match."
                      : ""
                  );
                }
              }}
            />
          </div>
          <div className="flex flex-col gap-2">
            <label className="font-medium text-[#434343]">Confirm Password</label>
            <input
              ref={confirmPasswordRef}
              type="password"
              placeholder="Confirm your password"
              className="text-[#838383] border border-gray-300 rounded-md py-5 px-4"
              required
              minLength={8}
              value={confirmPassword}
              onChange={(e) => {
                const val = e.target.value;
                setConfirmPassword(val);
                e.target.setCustomValidity(
                  val && val !== password ? "Passwords do not match." : ""
                );
              }}
            />
          </div>
        </div>
        <button
          type="submit"
          className="flex justify-center bg-[#174c3f] rounded-[10px] text-whitefont px-6 py-5 shadow-[0_20px_70px_rgba(23,76,63,0.15)] cursor-pointer"
        >
          <span className="text-whitefont font-bold">Create my account</span>
        </button>
        <Link to="/" className="text-center text-[#636363] font-medium">
          Back to all options
        </Link>
      </form>
    </>
  );
}
