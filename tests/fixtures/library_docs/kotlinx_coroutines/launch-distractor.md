# Launch cancellation

A `Job` returned by `launch` can be cancelled and joined.

```kotlin
val job = launch { doWork() }
job.cancelAndJoin()
```

This page does not describe result-bearing coroutines.
