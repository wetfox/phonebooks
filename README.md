# Danish phonebooks → DuckDB

Turn historical Danish telephone directories into structured data you can query with SQL.

Phonebooks contain more than phone numbers: names, addresses, occupations, and a record of who was listed where. This project takes those entries from a PDF text layer, parses their irregular formatting, and builds a local DuckDB database for exploration and analysis.

Developed for historical Danish phonebooks with a searchable text layer, with parsing rules tailored to a three-column, name-indexed layout.

## What it does

- **Extracts structured listings:** names, streets, house numbers, occupations, and phone numbers, with fields for fax and unlisted entries.
- **Interprets directory conventions:** carries forward repeated surnames, recognises occupation abbreviations, and normalises common character substitutions in phone numbers.
- **Keeps results traceable:** each record retains its source page number and raw text line for inspection.
- **Supports longer extraction runs:** processes selected page ranges in configurable chunks, reports progress, logs extraction errors, and can resume after the last written page.
- **Makes the data queryable:** exports JSONL and builds DuckDB tables for all listings and listings organised by street.

## From document layout to data

```text
Searchable PDF → text extraction → entry parsing → JSONL → DuckDB
```

The extraction combines `pdfplumber` with parsing rules for the directory's typography and entry structure. Leader-dot runs separate entry headings from telephone details; the parser then resolves names, addresses, occupations, and number fields. JSONL provides an inspectable intermediate format before loading into DuckDB.

The database contains two tables:

| Table | Contents |
| --- | --- |
| `listings` | Extracted records, including source text and parsing fields |
| `street_residents` | Street, house number, names, phone, occupation, unlisted status, and source page for entries with a street value |

For example, count extracted listings by street:

```sql
SELECT street, count(*) AS listings
FROM street_residents
GROUP BY street
ORDER BY listings DESC;
```

## Setup

Use Python 3.12 (tested with 3.12.4).

```sh
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```sh
# macOS or Linux
source .venv/bin/activate
```

Then install the dependencies:

```sh
python -m pip install -r requirements.txt
```

## Run

Extract a page range from a local PDF, then build the database:

```sh
python scripts/extract.py "PATH_TO_LOCAL_PDF" --output data/rows.jsonl --start-page 101 --end-page 115
python scripts/build_db.py data/rows.jsonl data/phonebook.duckdb
```

Choose pages containing directory listings. Page numbers are one-based and inclusive; omit the page range options to process the full PDF.

The extractor opens the PDF in chunks of 25 pages by default; adjust this with `--chunk-size`. To continue an interrupted run, repeat the extraction command with `--resume`, using the same PDF, output file, and page range. Existing outputs are protected from replacement unless `--overwrite` is supplied.

The database loader reports row counts, source page counts, and the number of records outside its phone/fax/unlisted checks.

## Project files

- [`scripts/extract.py`](scripts/extract.py): PDF extraction, entry parsing, and JSONL output.
- [`scripts/build_db.py`](scripts/build_db.py): DuckDB loading and street-oriented table creation.
- [`docs/pipeline.md`](docs/pipeline.md): processing details and notes for adapting the parser to other layouts.

Source PDFs and generated records stay local. The repository contains the pipeline and documentation; `.gitignore` excludes PDFs, databases, generated data, and internal working notes. Extracted listings contain personal data, so keep generated files local as well.
