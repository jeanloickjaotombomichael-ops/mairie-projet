import { Outlet } from 'react-router'
import Header from '@/components/Header'
import Footer from '@/components/Footer'

/** Cadre du site public : en-tête, page affichée, pied de page. */
function SiteLayout() {
  return (
    <div id="top" className="full-height flex flex-col bg-background text-foreground">
      <Header />
      <div className="flex flex-1 flex-col">
        <Outlet />
      </div>
      <Footer />
    </div>
  )
}

export default SiteLayout
