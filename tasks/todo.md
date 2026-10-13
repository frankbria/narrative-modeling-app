# Issue #712: charts read the whole dataset to use one or two columns

## Plan
- [x] RED: each chart reads its own columns from a Parquet-backed dataset (the reads are
      watched, not replaced); a CSV is parsed with the others skipped.
- [x] `s3_service.read_columns_from_bytes(content, columns)`: Parquet by column, CSV with a
      callable `usecols` (a name the file lacks is left out, never an error), anything else
      read whole and narrowed.
- [x] Histogram and box plot read their one column; the correlation matrix still reads all.
- [x] Scatter, line and time series: the column set is the chart's columns plus the ones the
      parsed filter list names. The three handlers were at cc 9, 13 and 7 and repeated one
      flow, which is now `_chart`; each keeps its own payload builder.
- [x] Found on the way: a line chart's numeric x was sent as text (pandas hands plain ints,
      the numpy checks never matched). Numbers stay numbers.
