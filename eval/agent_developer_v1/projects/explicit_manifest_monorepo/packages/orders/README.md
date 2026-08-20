# Orders module

OrdersModule is the module that prepares and submits customer orders.
OrdersDraftStore is the module-local draft storage component.
OrdersDraftStore stores draft orders as JSON records keyed by order id before upload.
OrderSubmission validates a draft and delegates network retry decisions to ProjectRetryPolicy.
OrderValidationContract requires a non-empty customer id, at least one line item, and a positive total.
