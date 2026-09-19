import { useEffect, useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { fetchConfig } from '../api.js'

const TABS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/analytics', label: 'Analytics' },
]

/* The app's header: the agency's name, then the page tabs. The query string
   rides along with every link, so the reporting window you picked survives a
   trip to Analytics and back.

   On a demo instance it also carries the notice that the figures are invented.
   It sits in the header rather than on a page, so it is on screen wherever you
   are and cannot be scrolled past. */
export default function NavBar() {
  const { search } = useLocation()
  const [demo, setDemo] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetchConfig(controller.signal)
      .then((config) => setDemo(Boolean(config.demo)))
      .catch(() => {
        /* An instance too old to answer /api/config is a real one: no banner. */
      })
    return () => controller.abort()
  }, [])

  return (
    <header className="appbar">
      <div className="appbar__inner">
        <Link to={{ pathname: '/', search }} className="appbar__brand">
          SG Digital Marketing
        </Link>
        <nav className="appbar__nav" aria-label="Pages">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={{ pathname: tab.to, search }}
              end={tab.end}
              className="appbar__tab"
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
        {demo && (
          <p className="appbar__demo" role="status">
            Demo data — not real client accounts
          </p>
        )}
      </div>
    </header>
  )
}
