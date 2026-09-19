import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchAnalytics } from './api.js'
import { count, gbp, longDate, percent, percentChange } from './format.js'
import { useReportingWindow } from './reportingWindow.js'
import TrendChart from './components/TrendChart.jsx'
import WindowSelector from './components/WindowSelector.jsx'

/* Which way is better for each stat, and which stats mean anything for this
   client: a cost per result belongs to conversion goals, a cost per 1,000
   reached to awareness goals, and neither is shown where it would mislead.
   Spend has no better direction, so its change is never green. */
const STATS = [
  { key: 'spend', label: 'Spend', format: gbp, better: null },
  { key: 'results', label: 'Results', format: count, better: 'higher' },
  {
    key: 'cpa',
    label: 'CPA',
    format: gbp,
    better: 'lower',
    when: (data) => data.has_conversion_spend || !data.has_awareness_spend,
  },
  {
    key: 'cost_per_1k_reach',
    label: 'Cost / 1,000 reached',
    format: gbp,
    better: 'lower',
    when: (data) => data.has_awareness_spend,
  },
  { key: 'ctr', label: 'CTR', format: percent, better: 'higher' },
]

/* What the Results figure actually counts, which depends on what this client's
   ad sets optimise for. */
const RESULTS_NOTE = {
  reach: "Results are people reached: every ad set that spent in this window optimises for reach, so no cost per result exists",
  action: "Results count each ad set's own optimisation outcome, never every action Meta reports",
  mixed: "Results count each ad set's own outcome, so reach-optimised ad sets contribute people reached",
  unmapped: "Meta reported an optimisation goal this board does not map yet, so results are left unset rather than guessed",
}

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

/* The days this metric can actually be drawn for. A day it cannot be computed
   for is a gap in what we know, not a zero, so it is left out rather than
   plotted — and one point cannot make a line. */
function plottable(daily, key) {
  return daily.filter((day) => day[key] != null)
}

function notEnoughToPlot(points, what) {
  return `Not enough data to plot a trend: only ${longDate(points[0].date)} has ${what}.`
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
  const [stale, setStale] = useState(null)
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
        if (err.name === 'AbortError') return
        /* An account id this board does not recognise is a stale URL, not a
           broken API — a link from another instance, or one left behind by demo
           mode. Drop it and fall back to the default client, because the picker
           only renders once data arrives, so refusing outright strands the page
           with no way back but editing the address bar. The swap is announced
           rather than silent: the reader must know the figures changed client. */
        if (err.status === 404 && accountId) {
          setStale(accountId)
          setSearchParams(
            (prev) => {
              const params = new URLSearchParams(prev)
              params.delete('account')
              return params
            },
            { replace: true },
          )
          return
        }
        setError(err.message)
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [accountId, days, setSearchParams])

  const chooseAccount = (id) => {
    setStale(null)
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev)
        params.set('account', id)
        return params
      },
      { replace: true },
    )
  }

  const account = data?.account
  const comparedWith = `the previous ${days} days`
  const noDelivery = account && data.daily.length === 0
  const cpaPoints = account ? plottable(data.daily, 'cpa') : []
  const reachCostPoints = account ? plottable(data.daily, 'cost_per_1k_reach') : []
  const ctrPoints = account ? plottable(data.daily, 'ctr') : []
  const frequencyPoints = account ? plottable(data.daily, 'frequency') : []
  const stats = account ? STATS.filter((stat) => !stat.when || stat.when(data)) : []
  const resultsNote = account ? RESULTS_NOTE[data.current.results_basis] : null

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

        {stale && (
          <div className="notice" role="status">
            <h3 className="notice__title">Showing a different client</h3>
            <p className="notice__body">
              This board has no account <code>{stale}</code> — that link is probably from
              another instance, or left in the URL by demo mode.
              {account ? ` Showing ${account.client_name} instead.` : ''}
            </p>
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
                {stats.map((stat) => {
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
            {resultsNote && <p className="micro panel__caption">{resultsNote}</p>}
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
            ) : !data.has_conversion_spend && data.has_awareness_spend ? (
              <p className="panel__empty">
                Every ad set that spent in {data.window.label} optimises for reach, so there is
                no cost per result to plot. Its cost per 1,000 reached is below.
              </p>
            ) : cpaPoints.length === 0 ? (
              <p className="panel__empty">
                No results recorded in {data.window.label}, so there is no cost per result to
                plot.
              </p>
            ) : cpaPoints.length < 2 ? (
              <p className="panel__empty">{notEnoughToPlot(cpaPoints, 'a cost per result')}</p>
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

          {data.has_awareness_spend && (
            <section className="panel">
              <div className="panel__head">
                <h2 className="heading">Cost per 1,000 reached trend</h2>
                <p className="micro" style={{ margin: 0 }}>
                  Reach-optimised ad sets · {data.window.label}
                </p>
              </div>
              {reachCostPoints.length === 0 ? (
                <p className="panel__empty">
                  No reach recorded in {data.window.label}.{lastDataNote(account)}
                </p>
              ) : reachCostPoints.length < 2 ? (
                <p className="panel__empty">{notEnoughToPlot(reachCostPoints, 'reach')}</p>
              ) : (
                <TrendChart
                  data={data.daily}
                  dataKey="cost_per_1k_reach"
                  name="Cost per 1,000 reached"
                  tickFormatter={(v) => `£${Number(v).toFixed(2)}`}
                  readoutRows={(p) => [
                    [
                      'Per 1,000 reached',
                      p.cost_per_1k_reach == null ? 'no reach' : gbp(p.cost_per_1k_reach),
                    ],
                    ['Spend', gbp(p.spend)],
                    ['People reached', count(p.results)],
                  ]}
                />
              )}
            </section>
          )}

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
            ) : ctrPoints.length === 0 ? (
              <p className="panel__empty">
                No impressions recorded in {data.window.label}, so there is no click-through
                rate to plot.
              </p>
            ) : ctrPoints.length < 2 ? (
              <p className="panel__empty">
                {notEnoughToPlot(ctrPoints, 'a click-through rate')}
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
            <div className="panel__head">
              <h2 className="heading">Frequency trend</h2>
              <p className="micro" style={{ margin: 0 }}>
                Impressions ÷ reach per day · {data.window.label}
              </p>
            </div>
            {noDelivery ? (
              <p className="panel__empty">
                No delivery recorded for {account.client_name} in {data.window.label}.
                {lastDataNote(account)}
              </p>
            ) : frequencyPoints.length === 0 ? (
              <p className="panel__empty">
                No reach recorded in {data.window.label}, so there is no frequency to plot:
                frequency is impressions ÷ reach, and a day without reach has none.
              </p>
            ) : frequencyPoints.length < 2 ? (
              <p className="panel__empty">{notEnoughToPlot(frequencyPoints, 'a frequency')}</p>
            ) : (
              <TrendChart
                data={data.daily}
                dataKey="frequency"
                name="Frequency"
                tickFormatter={(v) => Number(v).toFixed(1)}
                readoutRows={(p) => [
                  ['Frequency', p.frequency == null ? 'no reach' : Number(p.frequency).toFixed(2)],
                  ['Impressions', count(p.impressions)],
                  ['People reached', count(p.reach)],
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
                    <th scope="col">Goal</th>
                    <th scope="col">Spend</th>
                    <th scope="col">Results</th>
                    <th scope="col">Cost</th>
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
                      <td>{row.goal_label}</td>
                      <td>
                        <span className="row__figure">{gbp(row.spend)}</span>
                      </td>
                      <td>
                        <span
                          className={`row__figure${row.results == null ? ' row__figure--absent' : ''}`}
                        >
                          {count(row.results)}
                        </span>
                        <span className="row__id">{row.results_label}</span>
                      </td>
                      <td>
                        <span
                          className={`row__figure${row.cost == null ? ' row__figure--absent' : ''}`}
                        >
                          {gbp(row.cost)}
                        </span>
                        <span className="row__id">{row.cost_label}</span>
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
