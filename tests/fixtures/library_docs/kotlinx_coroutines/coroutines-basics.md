# Coroutine basics

`launch` starts a fire-and-forget coroutine and returns a `Job`.

```kotlin
fun main() = runBlocking {
    val job = launch {
        delay(10)
        println("done")
    }
    job.join()
}
```
