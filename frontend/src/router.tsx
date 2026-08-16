import { createBrowserRouter, Navigate } from 'react-router-dom'
import App from './App'
import { AdminRoute, ProtectedRoute } from './state/AuthContext'
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
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'register', element: <RegisterPage /> },
      {
        path: 'products/new',
        element: (
          <ProtectedRoute>
            <ProductUploadPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'simulations/new',
        element: (
          <ProtectedRoute>
            <ScenarioConfigPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'simulations/:id',
        element: (
          <ProtectedRoute>
            <SimulationRunPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'dashboard',
        element: (
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'dashboard/:id',
        element: (
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: 'admin',
        element: (
          <ProtectedRoute>
            <AdminRoute>
              <AdminPage />
            </AdminRoute>
          </ProtectedRoute>
        ),
      },
    ],
  },
])
