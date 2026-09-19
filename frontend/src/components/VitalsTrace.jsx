/* A single line: this client's goal metric over time. Days where the metric
   cannot be computed break the line rather than being bridged or zeroed. */
const W = 132
const H = 30
const PAD = 3

export default function VitalsTrace({ account }) {
  const { trend, goal_label: label } = account

  const points = trend.map((d) => (typeof d.value === 'number' ? d.value : null))
  const known = points.filter((v) => v != null)

  if (known.length === 0) {
    return (
      <svg
        className="trace trace--empty"
        width={W}
        height={H}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`No ${label} recorded for ${account.client_name} in this window`}
      >
        <line
          x1={PAD}
          y1={H / 2}
          x2={W - PAD}
          y2={H / 2}
          stroke="var(--rule-strong)"
          strokeWidth="1"
          strokeDasharray="4 5"
        />
      </svg>
    )
  }

  const lo = Math.min(...known)
  const hi = Math.max(...known)
  const span = hi - lo || Math.max(hi, 1)

  const x = (i) =>
    trend.length === 1 ? W / 2 : PAD + (i / (trend.length - 1)) * (W - PAD * 2)
  const y = (v) => H - PAD - ((v - lo) / span) * (H - PAD * 2)

  const segments = []
  let current = []
  points.forEach((v, i) => {
    if (v == null) {
      if (current.length) segments.push(current)
      current = []
    } else {
      current.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    }
  })
  if (current.length) segments.push(current)

  const last = points.reduce((acc, v, i) => (v != null ? { v, i } : acc), null)

  return (
    <svg
      className="trace"
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`${label} over ${trend.length} days for ${account.client_name}`}
    >
      {segments.map((seg, i) =>
        seg.length === 1 ? (
          <circle
            key={i}
            cx={Number(seg[0].split(',')[0])}
            cy={Number(seg[0].split(',')[1])}
            r="1.6"
            fill="var(--ink)"
          />
        ) : (
          <polyline
            key={i}
            points={seg.join(' ')}
            fill="none"
            stroke="var(--ink)"
            strokeWidth="1.35"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ),
      )}
      {last && <circle cx={x(last.i)} cy={y(last.v)} r="2" fill="var(--ink)" />}
    </svg>
  )
}
