# VellumBuild configuration

VellumBuild combines invocation settings with project and machine settings.

## Precedence

For ordinary settings, a command-line argument has highest priority.
An environment variable takes priority over the project file.
The project's `vellum.toml` takes priority over machine defaults.
The complete order is command line, environment, project file, then machine defaults.

## Project values

The project file may contain target definitions and ordinary build settings.
Secret-placement restrictions from the security manual still apply; precedence does not authorize storing a secret in a forbidden location.

## Target aliases

An alias chooses a named target.
Do not create an alias that points to itself.
Target-alias restrictions do not change configuration precedence.

