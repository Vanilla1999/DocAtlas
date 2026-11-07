# Runtime state is not part of the source change

The one successful client run retained its requests, responses, receipts,
source fixture, configuration, tool events, stdout/stderr and outcome here.
Disposable client cache and the generated OpenCode/DocAtlas SQLite state were
moved outside the checkout after the completed run; they were not deleted or
included in the commit. Source/database immutability was checked before that
move. Their original locations remain in raw receipts as execution evidence,
not as portable paths for a future rerun. Reproduce with a fresh output directory.
