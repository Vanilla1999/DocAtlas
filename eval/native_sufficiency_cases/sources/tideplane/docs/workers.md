# TidePlane worker operations

A worker executes jobs covered by controller-issued leases.

## Cordon

Run `tide cordon WORKER_ID` to make a worker unavailable for assignment of new jobs.
Cordoning does not cancel jobs that are already running.
Existing jobs may finish normally while the worker remains cordoned.

## Drain

`tide drain WORKER_ID` requests termination after the configured grace period.
Drain and cordon therefore have different effects on existing work.

## Existing leases

An already issued worker lease remains valid for 90 seconds from its issue time.
A later clock-admission failure prevents new leases but does not revoke an otherwise valid existing lease.

## Debugging

Do not attach the development debugger to a production worker.
The debugging restriction does not require terminating a job merely because its worker was cordoned.

