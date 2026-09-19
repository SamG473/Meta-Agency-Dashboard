import { useSearchParams } from 'react-router-dom'

export const WINDOWS = [
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 0, label: 'All' },
]

function windowFromParams(params) {
  const raw = params.get('window')
  // Guard the absent case explicitly: Number(null) is 0, which is a valid
  // window value ("all"), so a missing parameter would silently select it.
  if (!raw) return 30
  const parsed = raw === 'all' ? 0 : Number(raw)
  return WINDOWS.some((w) => w.days === parsed) ? parsed : 30
}

/* The chosen reporting window lives in the URL (?window=) so a view can be
   bookmarked, and so it follows you from page to page. It goes through the
   router rather than history.replaceState, so the nav bar sees it too. */
export function useReportingWindow() {
  const [searchParams, setSearchParams] = useSearchParams()
  const days = windowFromParams(searchParams)

  const setDays = (next) =>
    setSearchParams(
      (prev) => {
        const params = new URLSearchParams(prev)
        params.set('window', next === 0 ? 'all' : String(next))
        return params
      },
      { replace: true },
    )

  return [days, setDays]
}
