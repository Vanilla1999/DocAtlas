# Worker and workspace controls

## Draining one worker

The command `nacre workers drain WORKER --workspace WORKSPACE` stops new task assignments to that named worker only. It does not interrupt its current task, drain sibling workers or pause the workspace.

## Pausing a workspace

The command `nacre workspace pause WORKSPACE` stops new assignments to every worker in that workspace. Tasks already running continue. Other workspaces are unaffected.

## Cancellation

Cancelling a running task requires its exact task identifier, its workspace identifier and cancel permission for that workspace. Drain and pause do not imply cancellation; administer permission alone does not include cancel permission.

## Resuming work

Resuming a workspace removes its pause flag but does not remove a separately set drain flag from a worker. Resume a drained worker explicitly if it should accept new work.

## Worker replacement

Replacing a worker process does not transfer its active ticket to the new worker identity. The replacement must acquire its own authorized session and resume from its durable consumer checkpoint.
