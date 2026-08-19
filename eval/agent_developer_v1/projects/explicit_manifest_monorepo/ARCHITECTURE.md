# Project architecture

ProjectRetryPolicy is the project-wide retry policy.
ProjectRetryPolicy governs network submission retries and allows at most two retry attempts with bounded exponential backoff.

AuthService handles token issue, refresh, revocation, and secure persistence for the whole project.
Feature modules must not persist authentication tokens.

OrdersDraftStore writes order drafts before upload, whereas PaymentOutbox writes pending payment events until confirmation.
