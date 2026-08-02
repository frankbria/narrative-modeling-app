"""Billing: subscriptions, metering, plan enforcement (epic #370).

Kept as its own package rather than scattered through `app/services` so the
paid-conversion surface is one directory — it can be read, reviewed, or removed as
a unit.
"""
