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

function Readout({ active, payload, label, rows }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="readout">
      <div className="readout__date">{longDate(label)}</div>
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

/* One metric per day as a single ink line, styled like the retained portfolio
   history. A day the metric cannot be computed for breaks the line rather than
   being bridged or drawn as zero. */
export default function TrendChart({ data, dataKey, name, tickFormatter, readoutRows }) {
  const ticks = niceTicks(data.map((d) => d[dataKey]))

  return (
    <ResponsiveContainer width="100%" height={190}>
      <LineChart data={data} margin={{ top: 6, right: 4, bottom: 4, left: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="date"
          tickFormatter={shortDate}
          tickLine={false}
          axisLine={{ stroke: 'var(--rule-strong)' }}
          minTickGap={12}
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
