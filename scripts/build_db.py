#!/usr/bin/env python3
"""Load extracted JSONL listings into a local DuckDB database."""

import argparse
from pathlib import Path

import duckdb


def build_database(rows_path, database_path, overwrite=False):
    if not rows_path.is_file():
        raise FileNotFoundError(f"JSONL input not found: {rows_path}")
    if rows_path.resolve() == database_path.resolve():
        raise ValueError("database path cannot be the input JSONL")
    if database_path.exists() and not overwrite:
        raise FileExistsError(f"Database exists: {database_path}; choose another path or use --overwrite")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if overwrite and database_path.exists():
        database_path.unlink()

    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            """CREATE TABLE listings AS
               SELECT * FROM read_json_auto(?, format='newline_delimited')""",
            [str(rows_path.resolve())],
        )
        connection.execute(
            """CREATE TABLE street_residents AS
               SELECT street, house, names, phone, occupation, unlisted, page
               FROM listings WHERE street IS NOT NULL"""
        )
        rows, pages, violations = connection.execute(
            """SELECT count(*), count(DISTINCT page),
               sum(CASE WHEN NOT (
                   (phone IS NOT NULL AND length(phone) = 8)
                   OR coalesce(unlisted, false) OR coalesce(fax, false)
               ) THEN 1 ELSE 0 END)
               FROM listings"""
        ).fetchone()
    except Exception:
        connection.close()
        if database_path.exists():
            database_path.unlink()
        raise
    else:
        connection.close()

    rows, pages, violations = int(rows or 0), int(pages or 0), int(violations or 0)
    print(f"Database created: {database_path}")
    print(f"Rows: {rows}; pages: {pages}; invariant violations: {violations}")
    return rows, pages, violations


def main():
    parser = argparse.ArgumentParser(description="Load phonebook JSONL into DuckDB.")
    parser.add_argument("rows", type=Path, help="input JSONL file")
    parser.add_argument("database", type=Path, help="output DuckDB file")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing database")
    args = parser.parse_args()
    try:
        build_database(args.rows, args.database, args.overwrite)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()