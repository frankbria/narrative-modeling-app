# Issues #573 and #572: the cache route's untested error path, and per-file coverage

## #573
- [ ] A test makes `cache_service.invalidate_user_cache` raise and asserts the route
      answers 500 with the generic body, an `X-Request-ID`, and nothing of the exception
      (#269's contract). `app/api/routes/cache.py` goes from 82% to 100%.

## #572
Re-run today (coverage 7.8.2, numpy 2.3.0, scipy 1.15.3, Python 3.13.16) on the cache tests:

| `--cov=` | result |
|---|---|
| `app.api.routes.cache` (dotted module) | works: 12 tests, cache.py reported |
| `app/api/routes` (directory), `app` (package) | work |
| `app/api/routes/cache.py` (a file path) | tests pass, **no data collected** |

The crash the issue reports no longer happens. The trap that is left is the opposite one:
a file path is not a coverage source, and the issue's own table lists it as working.
- [ ] `docs/TEST_INFRASTRUCTURE.md`: say which forms measure one file, with both
      signatures quoted so they can be searched for.
- [ ] CI uses `--cov=app` (checked).
