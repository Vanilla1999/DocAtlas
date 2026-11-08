# Scheduler architecture

Meridian separates ownership, planning, execution and display to permit independent restarts.

## Planner

The planner solves interval conflicts using instrument availability and reservation priority. It can compute a plan while execution is suspended. A computed plan is not permission to bypass a weather interlock or clock check.

## Prototype recovery

The retired prototype cleared pending reservations when time drifted and restarted on its first local clock sample. These behaviours must not be used to recover the current gateway.
