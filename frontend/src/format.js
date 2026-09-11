const money = new Intl.NumberFormat('en-GB', {
  style: 'currency',
  currency: 'GBP',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const whole = new Intl.NumberFormat('en-GB')

const day = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

const dayShort = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
})

export const gbp = (n) => (n == null ? '—' : money.format(n))
export const count = (n) => (n == null ? '—' : whole.format(n))

export const longDate = (iso) => (iso ? day.format(new Date(`${iso}T00:00:00`)) : '—')
export const shortDate = (iso) => (iso ? dayShort.format(new Date(`${iso}T00:00:00`)) : '')

export const signedPercent = (dev) => {
  if (dev == null) return '—'
  const pct = Math.round(dev * 100)
  if (pct === 0) return 'on target'
  return `${pct > 0 ? '+' : ''}${pct}%`
}

const ratio = new Intl.NumberFormat('en-GB', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/* Formats a value in the units of whichever metric this client is measured on,
   so a Leads target reads "40" and a Cost per lead target reads "£2.50". */
export function metricValue(value, unit) {
  if (value == null) return '—'
  switch (unit) {
    case 'currency':
      return money.format(value)
    case 'ratio':
      return `${ratio.format(value)}×`
    case 'count':
    default:
      return whole.format(Math.round(value))
  }
}

export const STATE_LABEL = {
  on_track: 'On track',
  behind: 'Behind',
  no_target: 'No target',
  no_data: 'No data',
}
