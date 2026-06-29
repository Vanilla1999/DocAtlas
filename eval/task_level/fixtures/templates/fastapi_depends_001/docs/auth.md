# Auth Dependency Convention

Routes that require the internal token must use a shared dependency named `require_token`.

The dependency should read the `X-Token` header and expose the validated token to the route as `token`.

Do not duplicate token validation inside individual route handlers.
