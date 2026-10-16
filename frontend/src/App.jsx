import { useState } from 'react'
import heroImg from './assets/hero.png'
import reactLogo from './assets/react.svg'
import viteLogo from './assets/vite.svg'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center">
      <h1 className="text-4xl font-bold text-blue-600">
        SLA Project
      </h1>

      <p className="mt-4 text-gray-600">
        Tailwind CSS is working!
      </p>

      <button className="mt-6 rounded-lg bg-blue-600 px-6 py-3 text-white hover:bg-blue-700">
        Get Started
      </button>
    </div>
  )
}

export default App
