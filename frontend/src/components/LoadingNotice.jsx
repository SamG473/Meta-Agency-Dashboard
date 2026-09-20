import { useEffect, useState } from 'react'
import { API_IS_REMOTE } from '../api.js'

/* A read that has run longer than this is worth explaining. Under it, a notice
   about sleeping servers is noise on what is about to be an instant load. */
const WAKE_NOTICE_AFTER_MS = 2500

/* The wait before data arrives.

   On the deployed demo that wait can be a cold start: the API is on free
   hosting, which stops the service when nobody has asked for anything, so the
   first request of the day pays for it waking up. A blank panel for a minute
   reads as a broken page, which is the wrong thing for a demo to say about
   itself — so past a couple of seconds the page says what is happening and
   roughly how long it will take.

   Local development never sleeps, so the notice is bound to API_IS_REMOTE and
   never appears there. */
export default function LoadingNotice({ label }) {
  const [waking, setWaking] = useState(false)

  useEffect(() => {
    if (!API_IS_REMOTE) return undefined
    const timer = setTimeout(() => setWaking(true), WAKE_NOTICE_AFTER_MS)
    return () => clearTimeout(timer)
  }, [])

  return (
    <section className="loading" aria-busy="true">
      <p className="label">{label}</p>
      {waking && (
        <p className="loading__wake" role="status">
          The demo API is on free hosting, which sleeps when nobody is using it. It is
          waking up now — a first load can take up to a minute. Later loads are instant.
        </p>
      )}
    </section>
  )
}
