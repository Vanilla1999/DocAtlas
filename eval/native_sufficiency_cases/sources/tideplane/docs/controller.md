# TidePlane controller rules

The controller validates promotion prerequisites and worker lease admission.

## Migration interlock

Promotion is prohibited while a write migration is active.
Finishing or cancelling the write migration releases this interlock.
Healthy staged replicas do not bypass the migration interlock.

## Clock admission

A worker may receive a new lease only when its absolute clock offset from the controller is no more than 250 milliseconds.
A healthy status report does not override the clock-offset limit.
Admission checks do not shorten an already issued lease; the worker lease duration is specified in the worker manual.

## Administrative requests

Do not edit the controller identity while a leadership transfer is running.
Identity maintenance is unrelated to a worker's cordon state.

