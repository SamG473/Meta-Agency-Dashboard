import { Link, NavLink, useLocation } from 'react-router-dom'

const TABS = [
  { to: '/', label: 'Overview', end: true },
  { to: '/analytics', label: 'Analytics' },
]

/* The app's header: the agency's name, then the page tabs. The query string
   rides along with every link, so the reporting window you picked survives a
   trip to Analytics and back. */
export default function NavBar() {
  const { search } = useLocation()

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
      </div>
    </header>
  )
}
