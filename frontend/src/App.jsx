import './App.css'
import { BrowserRouter, Routes, Route } from "react-router";
import AuthLayout from "./components/AuthLayout";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import Room from "./pages/Room";
import PersonalRoom from "./pages/PersonalRoom";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AuthLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
        </Route>
        <Route path="/room" element={<Room />} />
        <Route path="/personal-room" element={<PersonalRoom />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App
