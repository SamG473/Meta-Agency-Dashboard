import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { gbp, longDate, shortDate } from '../format.js'

const DAY = 86400000

/* UTC on the way in and on the way out. Parsing a plain date as local time puts
   midnight BST an hour into the previous UTC day, which shifted every axis
   label back by one; it would also make a day 23 or 25 hours long across a DST
   change, and the gap test counts whole days. */
const asTime = (iso) => Date.parse(`${iso}T00:00:00Z`)
const asDate = (t) => new Date(t).toISOString().slice(0, 10)

/* Real elapsed time on the x-axis, and a break wherever the record skips days.
   Two runs of delivery two months apart are two runs, not one rising trend, so
   a null point one day after each run ends cuts the area rather than letting it
   draw straight through the gap. */
function timeline(history) {
  const points = []
  history.forEach((row, i) => {
    const previous = history[i - 1]
    if (previous && asTime(row.date) - asTime(previous.date) > DAY) {
      points.push({ t: asTime(previous.date) + DAY, date: null, spend: null })
    }
    points.push({ ...row, t: asTime(row.date) })
  })
  return points
}

function Readout({ active, payload }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  if (!point?.date) return null // the null point that breaks a gap
  return (
    <div className="readout">
      <div className="readout__date">{longDate(point.date)}</div>
      <dl className="readout__list">
        <dt>Portfolio spend</dt>
        <dd>{gbp(point.spend)}</dd>
        <dt>Results</dt>
        <dd>{point.results ?? '—'}</dd>
        <dt>Accounts delivering</dt>
        <dd>{point.accounts}</dd>
      </dl>
    </div>
  )
}

/* Daily spend over the selected window — the same window as the tiles above.
   Retention is a separate statement: a window longer than the record says so
   rather than quietly showing a wider range. */
export default function PortfolioHistory({ history, lastDataDate, windowLabel, retention }) {
  const stored = retention?.days_stored ?? 0
  const storedNote = stored
    ? `${stored} day${stored === 1 ? '' : 's'} on record, ${longDate(retention.first_date)} to ${longDate(retention.last_date)}`
    : null

  if (!history.length) {
    return (
      <section className="retained">
        <div className="retained__head">
          <h3 className="label" style={{ margin: 0 }}>
            Portfolio history
          </h3>
          <p className="micro" style={{ margin: 0 }}>
            No days with data · {windowLabel}
          </p>
        </div>
        {stored ? (
          <p className="panel__empty">
            Nothing was recorded in {windowLabel}. {storedNote} — widen the window to reach
            it.
          </p>
        ) : (
          <div className="notice">
            <h4 className="notice__title">Nothing retained yet</h4>
            <p className="notice__body">
              Once the ingest runs, every day it pulls is kept here permanently — including
              the history Meta&rsquo;s own reporting rolls off.
            </p>
          </div>
        )}
      </section>
    )
  }

  const points = timeline(history)

  return (
    <section className="retained">
      <div className="retained__head">
        <h3 className="label" style={{ margin: 0 }}>
          Portfolio history
        </h3>
        <p className="micro" style={{ margin: 0 }}>
          {history.length} day{history.length === 1 ? '' : 's'} with data · {windowLabel}
        </p>
      </div>

      <ResponsiveContainer width="100%" height={190}>
        <AreaChart data={points} margin={{ top: 6, right: 4, bottom: 4, left: 0 }}>
          <defs>
            <pattern id="ward-hatch" width="5" height="5" patternUnits="userSpaceOnUse">
              <rect width="5" height="5" fill="var(--ground-sunk)" />
              <path d="M0 5L5 0" stroke="var(--rule-strong)" strokeWidth="1" />
            </pattern>
          </defs>
          <CartesianGrid vertical={false} />
          {/* Time, not position: a two-month gap occupies two months of axis. */}
          <XAxis
            dataKey="t"
            type="number"
            scale="time"
            domain={['dataMin', 'dataMax']}
            ticks={history.map((row) => asTime(row.date))}
            tickFormatter={(t) => shortDate(asDate(t))}
            tickLine={false}
            axisLine={{ stroke: 'var(--rule-strong)' }}
            minTickGap={28}
          />
          <YAxis
            tickFormatter={(v) => `£${v}`}
            tickLine={false}
            axisLine={false}
            width={52}
          />
          <Tooltip content={<Readout />} cursor={{ stroke: 'var(--ink)', strokeWidth: 1 }} />
          <Area
            type="monotone"
            dataKey="spend"
            stroke="var(--ink)"
            strokeWidth={1.75}
            fill="url(#ward-hatch)"
            isAnimationActive={false}
            connectNulls={false}
            name="Portfolio spend"
          />
        </AreaChart>
      </ResponsiveContainer>

      <p className="micro" style={{ marginTop: '0.5rem' }}>
        Combined daily spend across every tracked account · last data {longDate(lastDataDate)}
      </p>
      {retention?.starts_after_window && (
        <p className="micro" style={{ marginTop: '0.35rem' }}>
          This window starts before the record does: {storedNote}
        </p>
      )}
    </section>
  )
}
