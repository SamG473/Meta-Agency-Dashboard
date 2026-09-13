import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchAnalytics } from './api.js'
import { count, gbp, longDate, percent, percentChange } from './format.js'
import { useReportingWindow } from './reportingWindow.js'
import TrendChart from './components/TrendChart.jsx'
import WindowSelector from './components/WindowSelector.jsx'

/* Which way is better for each stat. Spend has no better direction — more of
   it is neither an improvement nor a decline — so its change is never green. */
const STATS = [
  { key: 'spend', label: 'Spend', format: gbp, better: null },
  { key: 'results', label: 'Results', format: count, better: 'higher' },
  { key: 'cpa', label: 'CPA', format: gbp, better: 'lower' },
  { key: 'ctr', label: 'CTR', format: percent, better: 'higher' },
]

function DeltaGlyph({ direction }) {
  const common = {
    width: 9,
    height: 9,
    viewBox: '0 0 9 9',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.4,
    strokeLinecap: 'square',
    'aria-hidden': true,
    className: 'delta__glyph',
  }
  if (direction === 'up') return <svg {...common}><path d="M4.5 8.5V1M1 4.5l3.5-3.5 3.5 3.5" /></svg>
  if (direction === 'down') return <svg {...common}><path d="M4.5 0.5V8M1 4.5l3.5 3.5 3.5-3.5" /></svg>
  return <svg {...common}><path d="M0.5 4.5h8" /></svg>
}

/* Green, the on-track chip's colour, only for a real improvement. A decline
   stays muted: alarm red is reserved for an account past its own target. The
   arrow carries direction, so colour only ever confirms it. */
function Delta({ change, better, comparedWith }) {
  if (change == null) return <span className="delta">No prior data</span>

  const pct = Math.round(change * 100)
  const direction = pct === 0 ? 'flat' : pct > 0 ? 'up' : 'down'
  const tone =
    direction === 'flat' || !better
      ? 'neutral'
      : (direction === 'up') === (better === 'higher')
        ? 'better'
        : 'worse'

  return (
    <span className={`delta delta--${tone}`}>
      <DeltaGlyph direction={direction} />
      {percentChange(change)}
      <span className="visually-hidden"> on {comparedWith}</span>
    </span>
  )
}

function lastDataNote(account) {
  return account.last_data_date
    ? ` The last day with data was ${longDate(account.last_data_date)} — widen the window to see it.`
    : ' This client has never returned a day of data.'
}

export default function Analytics() {
  const [days, setDays] = useReportingWindow()
  const [searchParams, setSearchParams] = useSearchParams()
  const accountId = searchParams.get('account')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    fetchAnalytics(accountId, days, controller.signal)
      .then((next) => {
        setData(next)
        setError(null)
      })
      .catch((err) => {
        if (err.name !== 'AbortError') setError(err.message)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [accountId, days])

  const chooseAccount = (id) =>
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev)
        params.set('account', id)
        return params
      },
      { replace: true },
    )

  const account = data?.account
  const comparedWith = `the previous ${days} days`
  const noDelivery = account && data.daily.length === 0

  return (
    <main className="board">
      <h1 className="visually-hidden">
        Analytics{account ? ` — ${account.client_name}` : ''}
      </h1>

      <section className="panel">
        <div className="controls">
          <h2 className="heading">Period-over-period comparison</h2>
          <div className="filters">
            {data?.accounts?.length > 0 && (
              <label className="picker">
                <span className="label">Client</span>
                <select
                  className="goal__select"
                  value={account?.account_id ?? ''}
                  onChange={(e) => chooseAccount(e.target.value)}
                >
                  {data.accounts.map((a) => (
                    <option key={a.account_id} value={a.account_id}>
                      {a.client_name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <WindowSelector days={days} onChange={setDays} />
          </div>
        </div>

        {error && (
          <div className="notice notice--alarm" role="alert">
            <h3 className="notice__title">Analytics could not reach its data</h3>
            <p className="notice__body">{error}</p>
          </div>
        )}

        {!data && loading && (
          <section className="loading" aria-busy="true">
            <p className="label">Reading analytics…</p>
          </section>
        )}

        {data && !account && (
          <div className="notice">
            <h3 className="notice__title">No clients on the board yet</h3>
            <p className="notice__body">
              Nothing has been ingested into Postgres. Run <code>python -m ingest.run --days 90</code>{' '}
              to backfill.
            </p>
          </div>
        )}

        {account && (
          <>
            <header className="topline">
              <section
                className="strip"
                aria-label={`${account.client_name}, ${data.window.label}`}
              >
                {STATS.map((stat) => {
                  const value = data.current[stat.key]
                  return (
                    <div className="strip__cell" key={stat.key}>
                      <span className="label">{stat.label}</span>
                      <span
                        className={`strip__value num${value == null ? ' strip__value--muted' : ''}`}
                      >
                        {stat.format(value)}
                      </span>
                      {data.previous && (
                        <Delta
                          change={data.change[stat.key]}
                          better={stat.better}
                          comparedWith={comparedWith}
                        />
                      )}
                    </div>
                  )
                })}
              </section>
            </header>
            <p className="micro panel__caption">
              {data.previous_window
                ? `Compared with ${comparedWith}, ${longDate(data.previous_window.since)} to ${longDate(data.previous_window.until)}`
                : 'All retained history has no earlier period to compare against'}
            </p>
            <p className="micro panel__caption">
              Results count every action Meta reports, not only conversions, so CPA reads
              lower than true cost per conversion
            </p>
          </>
        )}
      </section>

      {account && (
        <>
          <section className="panel">
            <div className="panel__head">
              <h2 className="heading">CPA trend</h2>
              <p className="micro" style={{ margin: 0 }}>
                Spend ÷ results per day · {data.window.label}
              </p>
            </div>
            {noDelivery ? (
              <p className="panel__empty">
                No delivery recorded for {account.client_name} in {data.window.label}.
                {lastDataNote(account)}
              </p>
            ) : data.daily.every((d) => d.cpa == null) ? (
              <p className="panel__empty">
                No results recorded in {data.window.label}, so there is no cost per result to
                plot.
              </p>
            ) : (
              <TrendChart
                data={data.daily}
                dataKey="cpa"
                name="CPA"
                tickFormatter={(v) => `£${Number(v).toFixed(2)}`}
                readoutRows={(p) => [
                  ['CPA', p.cpa == null ? 'no results' : gbp(p.cpa)],
                  ['Spend', gbp(p.spend)],
                  ['Results', count(p.results)],
                ]}
              />
            )}
          </section>

          <section className="panel">
            <div className="panel__head">
              <h2 className="heading">CTR trend</h2>
              <p className="micro" style={{ margin: 0 }}>
                Clicks ÷ impressions per day · {data.window.label}
              </p>
            </div>
            {noDelivery ? (
              <p className="panel__empty">
                No delivery recorded for {account.client_name} in {data.window.label}.
                {lastDataNote(account)}
              </p>
            ) : data.daily.every((d) => d.ctr == null) ? (
              <p className="panel__empty">
                No impressions recorded in {data.window.label}, so there is no click-through
                rate to plot.
              </p>
            ) : (
              <TrendChart
                data={data.daily}
                dataKey="ctr"
                name="CTR"
                tickFormatter={(v) => `${Number(v)}%`}
                readoutRows={(p) => [
                  ['CTR', p.ctr == null ? 'no impressions' : percent(p.ctr)],
                  ['Clicks', count(p.clicks)],
                  ['Impressions', count(p.impressions)],
                ]}
              />
            )}
          </section>

          <section className="panel">
            <h2 className="heading ward__heading">Campaign / ad set breakdown</h2>
            {!data.breakdown.synced ? (
              <div className="notice">
                <h3 className="notice__title">No ad set detail pulled yet</h3>
                <p className="notice__body">
                  Run <code>python -m ingest.run --days 90</code> to backfill campaign and ad set
                  insights for this client.
                </p>
              </div>
            ) : data.breakdown.rows.length === 0 ? (
              <p className="panel__empty">
                No ad set spent in {data.window.label}.{lastDataNote(account)}
              </p>
            ) : (
              <table className="breakdown">
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Spend</th>
                    <th scope="col">Results</th>
                    <th scope="col">CPA</th>
                  </tr>
                </thead>
                <tbody>
                  {data.breakdown.rows.map((row) => (
                    <tr className="row" key={row.adset_id}>
                      <td>
                        <span className="row__client">{row.adset_name}</span>
                        <span className="row__id">
                          <span className="visually-hidden">Campaign: </span>
                          {row.campaign_name}
                        </span>
                      </td>
                      <td>
                        <span className="row__figure">{gbp(row.spend)}</span>
                      </td>
                      <td>
                        <span className="row__figure">{count(row.results)}</span>
                      </td>
                      <td>
                        <span
                          className={`row__figure${row.cpa == null ? ' row__figure--absent' : ''}`}
                        >
                          {gbp(row.cpa)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </main>
  )
}
