import { Fragment } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { longDate, shortDate } from '../format.js'

const DAY = 86400000

/* Longer than this between two plotted days and the line breaks rather than
   spanning the hole; shorter and it joins. A quiet day inside a run is still
   one trend; two months of nothing is two separate runs of delivery. */
const GAP_DAYS = 7

/* UTC on the way in and out. Parsing a plain date as local time puts midnight
   BST an hour into the previous UTC day, which shifts every label back by one. */
const asTime = (iso) => Date.parse(`${iso}T00:00:00Z`)
const asDate = (t) => new Date(t).toISOString().slice(0, 10)

/* A day the metric cannot be computed for is left out entirely, so the line
   joins straight across it. A gap longer than GAP_DAYS gets an explicit null
   point instead, which breaks the line there. */
function series(data, dataKey) {
  const points = data
    .filter((row) => row[dataKey] != null)
    .map((row) => ({ ...row, t: asTime(row.date) }))

  const out = []
  points.forEach((point, i) => {
    const previous = points[i - 1]
    if (previous && point.t - previous.t > GAP_DAYS * DAY) {
      out.push({ t: previous.t + DAY, date: null, [dataKey]: null })
    }
    out.push(point)
  })
  return out
}

/* Evenly spaced y ticks from zero, stepping by 1, 2, 2.5 or 5 times a power of
   ten, so a small rate reads "0.1%" rather than Recharts' "0.085%". */
function niceTicks(values) {
  const max = Math.max(...values.filter((v) => typeof v === 'number'))
  if (!(max > 0)) return undefined
  const raw = max / 4
  const magnitude = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].find((m) => m * magnitude >= raw) * magnitude
  const top = Math.ceil(max / step) * step
  return Array.from({ length: Math.round(top / step) + 1 }, (_, i) => Number((i * step).toFixed(6)))
}

function Readout({ active, payload, rows }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  if (!point?.date) return null // the null point that breaks a long gap
  return (
    <div className="readout">
      <div className="readout__date">{longDate(point.date)}</div>
      <dl className="readout__list">
        {rows(point).map(([term, value]) => (
          <Fragment key={term}>
            <dt>{term}</dt>
            <dd>{value}</dd>
          </Fragment>
        ))}
      </dl>
    </div>
  )
}

/* One metric per day as a single ink line, on a real time axis: the distance
   between two points is the number of days between them, so a fortnight's
   silence looks like a fortnight. */
export default function TrendChart({ data, dataKey, name, tickFormatter, readoutRows }) {
  const points = series(data, dataKey)
  const ticks = niceTicks(points.map((point) => point[dataKey]))

  return (
    <ResponsiveContainer width="100%" height={190}>
      <LineChart data={points} margin={{ top: 6, right: 4, bottom: 4, left: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="t"
          type="number"
          scale="time"
          domain={['dataMin', 'dataMax']}
          ticks={points.filter((point) => point.date).map((point) => point.t)}
          tickFormatter={(t) => shortDate(asDate(t))}
          tickLine={false}
          axisLine={{ stroke: 'var(--rule-strong)' }}
          minTickGap={28}
        />
        <YAxis
          ticks={ticks}
          domain={ticks ? [0, ticks[ticks.length - 1]] : [0, 'auto']}
          tickFormatter={tickFormatter}
          tickLine={false}
          axisLine={false}
          width={52}
        />
        <Tooltip
          content={<Readout rows={readoutRows} />}
          cursor={{ stroke: 'var(--ink)', strokeWidth: 1 }}
        />
        <Line
          type="monotone"
          dataKey={dataKey}
          name={name}
          stroke="var(--ink)"
          strokeWidth={1.75}
          dot={{ r: 2, fill: 'var(--ink)', stroke: 'none' }}
          activeDot={{ r: 4 }}
          connectNulls={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
