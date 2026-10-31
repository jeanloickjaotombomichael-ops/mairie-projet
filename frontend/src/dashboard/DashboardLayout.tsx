import '@/dashboard/dashboard.css'
import { useCallback, useState } from 'react'
import { Outlet } from 'react-router'
import AssistantPanel from '@/dashboard/AssistantPanel'
import DashSidebar from '@/dashboard/DashSidebar'
import DossiersProvider from '@/dashboard/DossiersProvider'
import MailsProvider from '@/dashboard/MailsProvider'
import Topbar from '@/dashboard/Topbar'
import { useDashboardTheme } from '@/dashboard/theme'

/** Cadre de l'espace personnel : barre supérieure, menu latéral, assistant et page affichée. */
function DashboardLayout() {
  const [theme, setTheme] = useDashboardTheme()
  const [menuOpen, setMenuOpen] = useState(false)
  const [assistantOpen, setAssistantOpen] = useState(false)

  const closeMenu = useCallback(() => setMenuOpen(false), [])
  const openAssistant = useCallback(() => setAssistantOpen(true), [])
  const closeAssistant = useCallback(() => setAssistantOpen(false), [])

  return (
    <DossiersProvider>
      <MailsProvider>
        <div data-dash-theme={theme} className="dash-root full-height bg-fond flex flex-col">
          <Topbar
            theme={theme}
            onThemeChange={setTheme}
            menuOpen={menuOpen}
            onMenuToggle={() => setMenuOpen((open) => !open)}
          />
          <DashSidebar open={menuOpen} onClose={closeMenu} onOpenAssistant={openAssistant} />
          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
          <AssistantPanel open={assistantOpen} onClose={closeAssistant} />
        </div>
      </MailsProvider>
    </DossiersProvider>
  )
}

export default DashboardLayout
