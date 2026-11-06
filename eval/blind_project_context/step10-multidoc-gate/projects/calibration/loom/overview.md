# Loom renderer

Loom renders museum collection images from preserved camera originals. The production rendering queue is distinct from the interactive preview service.

## Data flow

A manifest binds camera files to object identifiers. Workers produce derivatives, and a publisher exposes approved derivatives to visitors. Re-rendering changes derivatives without changing the preserved camera files.

## Queue ownership

Workers lease jobs from a shared queue. A lease is a scheduling mechanism, not proof that an output has passed review. The publisher reads the review state separately.
