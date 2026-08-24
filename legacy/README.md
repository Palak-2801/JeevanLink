# Legacy

`old_app_standalone.py` is the original single-file prototype, formerly
named `app (1) (1).py`.

It defined its own database schema (`lat`, `lon`, `is_available`,
`is_verified`) which did not match `jeevanlink/schema.sql`
(`latitude`, `longitude`, `available`, `verified`). Having two backends
write to the same SQLite file was the main source of confusion.

The real application is the `jeevanlink/` package. This file is kept for
reference only and does not need to be run.
