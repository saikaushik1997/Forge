import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Agents from "./pages/Agents";
import Workflows from "./pages/Workflows";
import Monitor from "./pages/Monitor";
import "./App.css";

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <div className="logo">⚡ Forge</div>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/agents">Agents</NavLink>
          <NavLink to="/workflows">Workflows</NavLink>
          <NavLink to="/monitor">Monitor</NavLink>
        </nav>
        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/workflows" element={<Workflows />} />
            <Route path="/monitor" element={<Monitor />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
