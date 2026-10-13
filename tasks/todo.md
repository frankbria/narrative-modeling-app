# Issue #694: the backend ignores a database named in the MONGODB_URI path

## Problem
`app/main.py` selects `client[MONGODB_DB]` and never reads the URI's path. A URI naming
one database with `MONGODB_DB` naming another runs against the second, silently, and can
disagree with the frontend, which has refused that since #551.

## Plan
- [x] RED: the URI reading, the refusal, and the app not starting.
- [x] `config.database_name_in_uri` (text, no driver: an srv URI means DNS) and
      `config.resolve_database_name`, which also keeps "MONGODB_DB unset" an error. The
      message names the two databases, never the URI.
- [x] The lifespan calls it. The lifespan was one function at cc 11, so it is now named
      steps (`_announce_configuration`, `_connect_database`, `_verify_storage`,
      `_reap_stale_jobs_once`, `_reaper_loop`, `_stop_reaper`, `_close_rate_limit_store`),
      in the same order, with tests for the two that had none.
