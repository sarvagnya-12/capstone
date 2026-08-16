import { Outlet } from 'react-router-dom'

function App() {
  return (
    <div>
      <header>
        <strong>DryRunAI</strong>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}

export default App
