# External browser lifecycle

External OIDC uses Android ACTION_VIEW, `app_links`, and `ExternalBrowserIntentService`. Cold starts use `getInitialLink`; warm starts use `uriLinkStream`. Both paths must enforce the same acceptance predicate. Android intent registration and Dart URI validation are separate boundaries: changing only one does not repair the other.
