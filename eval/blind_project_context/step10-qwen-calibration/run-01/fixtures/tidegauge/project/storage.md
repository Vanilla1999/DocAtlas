# Journal storage

Journal files contain original live observations. Exported bundles are derived products, not journal replacements until their checksums have been verified.

## Retention

Keep a journal file for at least seven days and until the corresponding export checksum is verified. Both conditions must hold before deletion. A legal hold blocks deletion regardless of age or checksum status.

## Capacity

The capacity monitor reports filesystem free space every minute. A low-space alert pauses new survey imports; it does not shorten journal retention or remove a legal hold.

## Historical default

The retired prototype deleted files after two days without checking exports. This behaviour is documented for migration diagnosis and is not the live service policy.
