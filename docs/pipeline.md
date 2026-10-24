# Pipeline notes

## Processing steps

1. scripts/extract.py reads the PDF text layer with pdfplumber, in chunks of 25 pages by default.
2. It segments entries around leader-dot runs, parses the entry from the right-hand side, and writes one JSON object per line.
3. scripts/build_db.py loads the JSONL into DuckDB and builds a street-oriented table from rows with a street value.

The parser preserves the original line in each output record so a result can be checked against its source page. Surname inheritance, short or damaged phone digits, fax entries, and unlisted numbers have separate fields.

## Scope and limitations

The parser was tuned on a historical Danish name-indexed volume with a searchable text layer. Other books may use a different schema or page layout and can require a separate parser. This code does not perform OCR or resolve spelling variants. The research notes for the original run report residual errors, especially in front matter, back matter, and malformed lines.

A short pipeline run confirms that extraction and DuckDB loading work on the selected pages. It does not measure completeness or certify record accuracy.