# Danish phonebook extraction

A small research pipeline that turns a searchable Danish phonebook PDF into newline-delimited JSON and a DuckDB database.

The parser was developed against one historical, three-column, name-indexed phonebook. It is a work in progress and does not yet handle every phonebook layout. It uses the PDF text layer and does not run OCR. No source PDFs or extracted records are tracked in the public source tree; local artifacts are kept in the ignored .local archive.

## Setup

Use Python 3.12 (tested with 3.12.4).

    python -m venv .venv
    python -m pip install -r requirements.txt

Activate the environment with the command for your shell:

Windows PowerShell:

    .venv\Scripts\Activate.ps1

macOS or Linux:

    source .venv/bin/activate

## Run

Keep source PDFs and generated data on your machine. For example, put generated files under the ignored data directory.

    python scripts/extract.py "PATH_TO_LOCAL_PDF" --output data/rows.jsonl --start-page 101 --end-page 115
    python scripts/build_db.py data/rows.jsonl data/phonebook.duckdb

Omit the page range options to process the full PDF. Page numbers are one-based and inclusive. The extractor opens the PDF in chunks to limit memory use. Use the resume option to continue an interrupted run with the same PDF and output file. Existing outputs are protected; pass the overwrite option only when you mean to replace them.

The JSONL records retain a raw source line for checking parser results. Treat generated files as personal data and keep them local. The database contains a listings table and a street_residents table. The loader prints aggregate counts only.

## Project status

This is a research snapshot, not a maintained data service or a complete Denmark-wide dataset. The parser has known extraction errors and is tuned to a particular book layout. See the pipeline notes in docs/pipeline.md for the method and limitations.

The local PDFs, parsed records, databases, logs, rendered pages, samples, and internal working notes are excluded from Git by .gitignore.