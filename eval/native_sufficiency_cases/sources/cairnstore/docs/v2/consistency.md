# CairnStore version 2 consistency

This page applies only to CairnStore major version 2.

## Object reads

After a successful write, a read of the same key returns the new value.
This read-after-write guarantee applies to object reads addressed by key.

## Listings

Bucket listings remain eventually consistent in version 2.
The object-read guarantee does not extend to the next bucket listing.

## Scope

Changing consistency semantics does not set a contractual response-time target.

