# Composing suspending functions

`launch` returns a `Job` and does not carry a result. `async` returns a `Deferred<T>` representing a future result. Obtain that result with `await()`.

```kotlin
val deferred = async { computeAnswer() }
val answer = deferred.await()
```
