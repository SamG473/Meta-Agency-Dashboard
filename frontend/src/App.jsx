import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchBoard, fetchMetrics } from './api.js'
import { STATE_LABEL, count, gbp, longDate, metricValue } from './format.js'
import GoalCell from './components/GoalCell.jsx'
import HistoryPanel from './components/HistoryPanel.jsx'
import PortfolioHistory from './components/PortfolioHistory.jsx'
import TargetCell from './components/TargetCell.jsx'
import VitalsTrace from './components/VitalsTrace.jsx'

const WINDOWS = [
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 0, label: 'All' },
]

/* One stroke weight, one geometry. State is carried by the mark's shape as
   well as by its word, so it survives being read in greyscale. */
function Glyph({ state }) {
  const common = {
    width: 9,
    height: 9,
    viewBox: '0 0 9 9',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.4,
    strokeLinecap: 'square',
    'aria-hidden': true,
    className: 'chip__glyph',
  }
  switch (state) {
    case 'on_track':
      return <svg {...common}><path d="M0.5 4.5h8" /></svg>
    case 'behind':
      return <svg {...common}><path d="M0.5 8L4.5 4l4 4M0.5 4.5L4.5 0.5l4 4" /></svg>
    case 'no_data':
      return <svg {...common}><path d="M0.5 4.5h2.5M6 4.5h2.5" /></svg>
    default:
      return <svg {...common}><circle cx="4.5" cy="4.5" r="3.6" /></svg>
  }
}

function PortfolioStrip({ portfolio, windowLabel }) {
  return (
    <header className="topline">
      <section className="strip" aria-label={`Portfolio totals, ${windowLabel}`}>
        <div className="strip__cell">
          <span className="label">Spend</span>
          <span className="strip__value num">{gbp(portfolio.spend)}</span>
        </div>
        <div className="strip__cell">
          <span className="label">Results</span>
          <span className="strip__value num">{count(portfolio.conversions)}</span>
        </div>
        <div className="strip__cell">
          <span className="label">Accounts</span>
          <span className="strip__value num">{count(portfolio.accounts_tracked)}</span>
        </div>
        <div className="strip__cell">
          <span className="label">Last data</span>
          <span
            className={`strip__value num${
              portfolio.last_data_date ? '' : ' strip__value--muted'
            }`}
          >
            {portfolio.last_data_date ? longDate(portfolio.last_data_date) : 'None yet'}
          </span>
        </div>
      </section>
    </header>
  )
}

function WardRow({ account, index, expanded, onToggle, onSaved, windowLabel, metrics }) {
  const alarm = account.state === 'behind'
  const panelId = `history-${account.account_id}`

  return (
    <>
      <tr className={`row row--enter${alarm ? ' row--alarm' : ''}`} style={{ '--i': index }}>
        <td>
          <span className="row__client">{account.client_name}</span>
          {account.client_name !== account.account_id && (
            <span className="row__id">{account.account_id}</span>
          )}
        </td>
        <td>
          <GoalCell account={account} metrics={metrics} onSaved={onSaved} />
        </td>
        <td className="right">
          <TargetCell account={account} onSaved={onSaved} />
        </td>
        <td className="right">
          <span
            className={`row__figure row__figure--actual${
              account.actual_value == null ? ' row__figure--absent' : ''
            }`}
          >
            {metricValue(account.actual_value, account.goal_unit)}
          </span>
        </td>
        <td>
          <VitalsTrace account={account} />
        </td>
        <td>
          <span className={`chip chip--${account.state}`}>
            <Glyph state={account.state} />
            {STATE_LABEL[account.state] ?? account.state}
          </span>
        </td>
        <td>
          <button
            type="button"
            className="row__expand"
            onClick={onToggle}
            aria-expanded={expanded}
            aria-controls={panelId}
          >
            {expanded ? 'Hide history' : 'History'}
          </button>
        </td>
      </tr>
      {expanded && (
        <tr className="history" id={panelId}>
          <td colSpan={7}>
            <HistoryPanel account={account} windowLabel={windowLabel} />
          </td>
        </tr>
      )}
    </>
  )
}

/* The chosen window lives in the URL so a view can be bookmarked or returned
   to, rather than resetting to 30 days on every load. */
function windowFromParams(params) {
  const raw = params.get('window')
  // Guard the absent case explicitly: Number(null) is 0, which is a valid
  // window value ("all"), so a missing parameter would silently select it.
  if (!raw) return 30
  const parsed = raw === 'all' ? 0 : Number(raw)
  return WINDOWS.some((w) => w.days === parsed) ? parsed : 30
}

export default function App() {
  const [searchParams, setSearchParams] = useSearchParams()
  const days = windowFromParams(searchParams)
  const [board, setBoard] = useState(null)
  const [metrics, setMetrics] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState(() => new Set())

  // Through the router rather than history.replaceState, so the nav bar sees
  // the window and carries it from page to page.
  const setDays = (next) =>
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev)
        params.set('window', next === 0 ? 'all' : String(next))
        return params
      },
      { replace: true },
    )

  const load = useCallback(
    (signal) => {
      setLoading(true)
      return fetchBoard(days, signal)
        .then((data) => {
          setBoard(data)
          setError(null)
        })
        .catch((err) => {
          if (err.name !== 'AbortError') setError(err.message)
        })
        .finally(() => setLoading(false))
    },
    [days],
  )

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load])

  // The goal metrics on offer come from the API so the list cannot drift out
  // of step with what the server will actually accept.
  useEffect(() => {
    const controller = new AbortController()
    fetchMetrics(controller.signal)
      .then(setMetrics)
      .catch((err) => {
        if (err.name !== 'AbortError') setMetrics([])
      })
    return () => controller.abort()
  }, [])

  const toggle = (id) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  return (
    <main className="board">
      {/* Portfolio totals and Clients are sibling bands, so both are h2s under
          one page heading rather than Clients nesting beneath the totals. */}
      <h1 className="visually-hidden">Portfolio</h1>

      {/* Two panels: the totals together with their retained history, then the
          client list beneath them. */}
      <section className="panel">
        <div className="controls">
          <h2 className="heading">Portfolio totals</h2>
          <div className="windows" role="group" aria-label="Reporting window">
            {WINDOWS.map((w) => (
              <button
                key={w.days}
                type="button"
                className="windows__btn"
                aria-pressed={days === w.days}
                onClick={() => setDays(w.days)}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="notice notice--alarm" role="alert">
            <h3 className="notice__title">The board could not reach its data</h3>
            <p className="notice__body">{error}</p>
            <p className="notice__body">
              The dashboard reads from Postgres, never from Meta, so this is the API or the
              database — not your ad account. Check that <code>uvicorn app.main:app</code> is
              running.
            </p>
          </div>
        )}

        {!board && loading && (
          <section className="loading" aria-busy="true">
            <p className="label">Reading the board…</p>
          </section>
        )}

        {board && (
          <>
            <PortfolioStrip portfolio={board.portfolio} windowLabel={board.window.label} />
            <PortfolioHistory
              history={board.portfolio_history ?? []}
              lastDataDate={board.portfolio.last_data_date}
            />
          </>
        )}
      </section>

      {board && (
        <section className="panel ward">
          <h2 className="heading ward__heading">Clients</h2>
          {board.accounts.length === 0 ? (
            <div className="notice">
              <h3 className="notice__title">No accounts on the board yet</h3>
              <p className="notice__body">
                Nothing has been ingested into Postgres. Run{' '}
                <code>python -m ingest.run</code> to pull yesterday, or{' '}
                <code>python -m ingest.run --days 90</code> to backfill.
              </p>
            </div>
          ) : (
            <table className="ward__table">
              <thead>
                <tr>
                  <th scope="col">Client</th>
                  <th scope="col">Goal</th>
                  <th scope="col" className="right">Target</th>
                  <th scope="col" className="right">Actual</th>
                  <th scope="col">Trend</th>
                  <th scope="col">State</th>
                  <th scope="col">
                    <span className="visually-hidden">History</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {board.accounts.map((account, i) => (
                  <WardRow
                    key={account.account_id}
                    account={account}
                    index={i}
                    expanded={expanded.has(account.account_id)}
                    onToggle={() => toggle(account.account_id)}
                    onSaved={() => load()}
                    windowLabel={board.window.label}
                    metrics={metrics}
                  />
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </main>
  )
}
