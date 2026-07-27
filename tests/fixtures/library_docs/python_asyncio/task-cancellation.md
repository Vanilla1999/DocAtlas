# Cancelling tasks

`create_task()` schedules a coroutine. A scheduled task can be cancelled.

```python
task = asyncio.create_task(worker())
task.cancel()
```
