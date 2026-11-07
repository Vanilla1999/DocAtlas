# Bundle export

These rules govern daily bundles consumed by harbour analysts.

## Publication

Publish a bundle only when every included station has a verified daily checksum. Include the observation timezone in the manifest. A missing station must be listed explicitly as missing rather than represented by zero water levels.

## Late observations

A late observation creates a new bundle revision; never overwrite an already published bundle. Keep the previous revision addressable for existing citations.

## Preview

Preview bundles can omit checksums and use provisional labels. They must stay in the sandbox and are not public daily bundles.
