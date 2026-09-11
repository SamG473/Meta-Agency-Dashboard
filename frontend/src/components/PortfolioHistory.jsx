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

function Readout({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="readout">
      <div className="readout__date">{longDate(label)}</div>
      <dl className="readout__list">
        <dt>Portfolio spend</dt>
        <dd>{gbp(point.spend)}</dd>
        <dt>Results</dt>
        <dd>{point.conversions}</dd>
        <dt>Accounts delivering</dt>
        <dd>{point.accounts}</dd>
      </dl>
    </div>
  )
}

/* Deliberately shows the whole retained record rather than the selected
   window. Meta's own interface discards this; keeping it is the reason the
   architecture stores rather than queries live. */
export default function PortfolioHistory({ history, lastDataDate }) {
  if (!history.length) {
    return (
      <section className="retained">
        <div className="retained__head">
          <h3 className="label" style={{ margin: 0 }}>
            Retained portfolio history
          </h3>
        </div>
        <div className="notice">
          <h4 className="notice__title">Nothing retained yet</h4>
          <p className="notice__body">
            Once the ingest runs, every day it pulls is kept here permanently — including
            the history Meta&rsquo;s own reporting rolls off.
          </p>
        </div>
      </section>
    )
  }

  const first = history[0].date
  const last = history[history.length - 1].date

  return (
    <section className="retained">
      <div className="retained__head">
        <h3 className="label" style={{ margin: 0 }}>
          Retained portfolio history
        </h3>
        <p className="micro" style={{ margin: 0 }}>
          {history.length} day{history.length === 1 ? '' : 's'} kept ·{' '}
          {longDate(first)} to {longDate(last)}
        </p>
      </div>

      <ResponsiveContainer width="100%" height={190}>
        <AreaChart data={history} margin={{ top: 6, right: 4, bottom: 4, left: 0 }}>
          <defs>
            <pattern id="ward-hatch" width="5" height="5" patternUnits="userSpaceOnUse">
              <rect width="5" height="5" fill="var(--ground-sunk)" />
              <path d="M0 5L5 0" stroke="var(--rule-strong)" strokeWidth="1" />
            </pattern>
          </defs>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tickLine={false}
            axisLine={{ stroke: 'var(--rule-strong)' }}
            minTickGap={12}
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
            name="Portfolio spend"
          />
        </AreaChart>
      </ResponsiveContainer>

      <p className="micro" style={{ marginTop: '0.5rem' }}>
        Combined daily spend across every tracked account · last data {longDate(lastDataDate)}
      </p>
    </section>
  )
}
