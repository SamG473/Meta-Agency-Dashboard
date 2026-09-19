import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { gbp, longDate, metricValue, shortDate } from '../format.js'

function Readout({ active, payload, label, goalLabel, goalUnit }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="readout">
      <div className="readout__date">{longDate(label)}</div>
      <dl className="readout__list">
        <dt>Spend</dt>
        <dd>{gbp(point.spend)}</dd>
        <dt>Results</dt>
        <dd>{point.results ?? '—'}</dd>
        <dt>{goalLabel}</dt>
        <dd>
          {point.value == null ? 'none recorded' : metricValue(point.value, goalUnit)}
        </dd>
      </dl>
    </div>
  )
}

export default function HistoryPanel({ account, windowLabel }) {
  const {
    trend,
    target_value: target,
    client_name: name,
    goal_label: goalLabel,
    goal_unit: goalUnit,
  } = account

  if (!trend.length) {
    return (
      <div className="history__inner">
        <p className="history__empty">
          No delivery recorded for {name} in {windowLabel}.
          {account.last_data_date
            ? ` The last day with data was ${longDate(account.last_data_date)} — widen the window to see it.`
            : ' This account has never returned a day of data.'}
        </p>
      </div>
    )
  }

  return (
    <div className="history__inner">
      <div className="history__head">
        <h3 className="label" style={{ margin: 0 }}>
          Retained history — {windowLabel}
        </h3>
        <p className="micro" style={{ margin: 0 }}>
          {trend.length} day{trend.length === 1 ? '' : 's'} on record ·{' '}
          {goalLabel}
          {target ? ` target ${metricValue(target, goalUnit)}` : ' — no target set'}
        </p>
      </div>

      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={trend} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={shortDate}
            tickLine={false}
            axisLine={{ stroke: 'var(--rule-strong)' }}
            minTickGap={16}
          />
          <YAxis
            yAxisId="spend"
            tickFormatter={(v) => `£${v}`}
            tickLine={false}
            axisLine={false}
            width={52}
          />
          <YAxis
            yAxisId="cpr"
            orientation="right"
            tickFormatter={(v) => metricValue(v, goalUnit)}
            tickLine={false}
            axisLine={false}
            width={62}
          />
          <Tooltip
            content={<Readout goalLabel={goalLabel} goalUnit={goalUnit} />}
            cursor={{ fill: 'var(--ground-sunk)' }}
          />
          <Bar
            yAxisId="spend"
            dataKey="spend"
            fill="var(--rule-strong)"
            name="Daily spend"
            maxBarSize={26}
            isAnimationActive={false}
          />
          {target ? (
            <ReferenceLine
              yAxisId="cpr"
              y={target}
              stroke="var(--alarm)"
              strokeDasharray="4 4"
              label={{
                value: 'target',
                position: 'insideTopRight',
                fill: 'var(--alarm)',
                fontSize: 10,
                letterSpacing: '0.12em',
              }}
            />
          ) : null}
          <Line
            yAxisId="cpr"
            type="monotone"
            dataKey="value"
            stroke="var(--ink)"
            strokeWidth={1.75}
            dot={{ r: 2, fill: 'var(--ink)', stroke: 'none' }}
            activeDot={{ r: 4 }}
            name={goalLabel}
            isAnimationActive={false}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <p className="micro" style={{ marginTop: '0.5rem' }}>
        Bars: daily spend (left axis) · Line: {goalLabel} (right axis)
      </p>
    </div>
  )
}
