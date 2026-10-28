# CairnStore version 1 consistency

This page applies only to CairnStore major version 1.

## Object reads

After a successful write, a read of the same key may temporarily return the previous value.
Version 1 therefore does not provide immediate read-after-write visibility for object reads.

## Listings

Bucket listings are eventually consistent.
A completed write does not guarantee that the new key appears in the next listing.

## Scope

These statements concern visibility, not response-time guarantees.

