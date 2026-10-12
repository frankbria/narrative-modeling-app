# Issue #596: the nginx webhook guard's server-block slice is unguarded

## Problem
`test_nginx_webhook_route.py::_server_block()` takes everything from the first
`listen 443` to the end of the file. Correct while the TLS server is the last block;
a server appended later would have its locations compared with the TLS server's, which
nginx never does: a false green or a false red.

## Plan
- [ ] `_server_block()` returns the body of the one server block that listens on 443,
      brace-balanced, and fails with the count when there is not exactly one.
- [ ] Mutation tests on a copy of the real config: a second server appended with a
      longer location does not change the verdict in either direction; a second TLS
      server fails loudly.
- [ ] `MAX_WEBHOOK_BODY_MB`: pinned to the shipped `2m`. Stripe events are a few KB and
      2 MB is already three orders of magnitude of room; a different cap should be a
      deliberate edit of both files, not a value anywhere up to 8.
