import { createBrowserRouter, Navigate } from 'react-router-dom'
import App from './App'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ProductUploadPage from './pages/ProductUploadPage'
import ScenarioConfigPage from './pages/ScenarioConfigPage'
import SimulationRunPage from './pages/SimulationRunPage'
import DashboardPage from './pages/DashboardPage'
import AdminPage from './pages/AdminPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/login" replace /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      { path: 'products/new', element: <ProductUploadPage /> },
      { path: 'simulations/new', element: <ScenarioConfigPage /> },
      { path: 'simulations/:id', element: <SimulationRunPage /> },
      { path: 'dashboard', element: <DashboardPage /> },
      { path: 'admin', element: <AdminPage /> },
    ],
  },
])
