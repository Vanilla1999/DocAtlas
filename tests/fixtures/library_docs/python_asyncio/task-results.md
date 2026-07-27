# Scheduling and collecting results

`create_task()` schedules one coroutine and returns a `Task`. `gather()` runs multiple awaitables and collects their return values in order. Await the task to obtain its result.

```python
task = asyncio.create_task(compute())
value = await task
values = await asyncio.gather(compute(), compute())
```
