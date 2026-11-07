**Suspend outdoor observations when the wind interlock opens.** Weather suspension affects execution, not reservation ownership; preserve reservation identifiers throughout the suspension. The supplied excerpts do not specify a numeric wind-speed threshold. (`weather.md`, lines 3–7)

**Restart requires both the interlock to close and the duty operator to record a restart approval.** A favourable forecast cannot authorize a restart, and a computed plan cannot bypass the weather interlock or clock checks. (`weather.md`, lines 7 and 13–15; `architecture.md`, lines 5–7)

**An indoor instrument may continue during a wind suspension only if it is explicitly classified as indoor and its own safety interlocks remain closed.** A roof shown as closed on the calendar does not establish indoor classification. (`weather.md`, lines 9–11)

If execution is **also paused for clock offset**, that separate recovery requirement still applies: two consecutive observatory-reference checks must report an absolute offset within two seconds. If the reference clock is unavailable, execution must remain paused; a local clock reading alone cannot satisfy either check. (`clock.md`, lines 3–11)
