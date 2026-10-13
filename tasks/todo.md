# Issue #964: a chart request in flight during a transformation re-caches the old data

## Problem
#960 clears a dataset's chart caches when it moves. A request that started before the
move finishes afterwards and writes the old chart back under `(dataset, type, column)`.
Nothing on the row says which file it came from and it never expires.

## Plan
- [ ] RED: compute from the old file, move the dataset, write the cache, read.
- [ ] A cached chart carries the file it was computed from: `VisualizationCache.source_url`,
      and a digest of it in the Redis key. A read for a dataset's current file is served
      only an entry computed from that file. The three generators read the dataset first
      and pass its `s3_url` to both the read and the write.
- [ ] `get_cached_visualization` and `cache_visualization` are at cc 9 and 7: split.
- [ ] Remove the three `delete_pattern("stats_{id}_*")` calls: nothing writes such a key.
- [ ] `ColumnStats`: its route is called by nothing (#889); the criterion moves there.
