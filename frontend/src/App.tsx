import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router'
import AuthRedirect from '@/components/AuthRedirect'
import RequireAuth from '@/components/RequireAuth'
import SiteLayout from '@/components/SiteLayout'
import DashboardLayout from '@/dashboard/DashboardLayout'
import DemandePage from '@/dashboard/pages/DemandePage'
import HomePage from '@/dashboard/pages/HomePage'
import MailPage from '@/dashboard/pages/MailPage'
import NotificationsPage from '@/dashboard/pages/NotificationsPage'
import AgentRequestPage from '@/pages/AgentRequestPage'
import CivilServicesPage from '@/pages/CivilServicesPage'
import ComingSoonPage from '@/pages/ComingSoonPage'
import AboutPage from '@/pages/AboutPage'
import ContactPage from '@/pages/ContactPage'
import Home from '@/pages/Home'
import NotFoundPage from '@/pages/NotFoundPage'
import ScanPage from '@/pages/ScanPage'
import ServiceDetailPage from '@/pages/ServiceDetailPage'
import ServicesPage from '@/pages/ServicesPage'
import VerifyPage from '@/pages/VerifyPage'

/** Remonte en haut à chaque changement de page, ou va à l'ancre (#…). */
function ScrollManager() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    if (hash) {
      const target = document.getElementById(hash.slice(1))
      if (target) {
        target.scrollIntoView()
        return
      }
    }
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' })
  }, [pathname, hash])

  return null
}

function App() {
  return (
    <>
      <ScrollManager />
      <AuthRedirect />
      <Routes>
        {/* Site public : en-tête, page, pied de page */}
        <Route element={<SiteLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/services" element={<ServicesPage />} />
          <Route path="/services/etat-civil" element={<CivilServicesPage />} />
          <Route path="/services/etat-civil/:slug" element={<ServiceDetailPage kind="civil" />} />
          <Route path="/services/:slug" element={<ServiceDetailPage kind="service" />} />
          <Route path="/a-propos" element={<AboutPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/verifier/:token" element={<VerifyPage />} />
          <Route path="/scanner" element={<ScanPage />} />
          <Route path="/demande-agent" element={<AgentRequestPage />} />
          <Route path="/faq" element={<ComingSoonPage page="faq" />} />
          <Route path="/rejoindre" element={<ComingSoonPage page="join" />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>

        {/* Espace utilisateur : réservé aux usagers connectés, sans en-tête ni pied de page du site */}
        <Route
          path="/espace"
          element={
            <RequireAuth>
              <DashboardLayout />
            </RequireAuth>
          }
        >
          <Route index element={<HomePage />} />
          <Route path="demande/:slug" element={<DemandePage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="mail" element={<MailPage />} />
          <Route path="*" element={<Navigate to="/espace" replace />} />
        </Route>
      </Routes>
    </>
  )
}

export default App
