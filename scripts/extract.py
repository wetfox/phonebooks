#!/usr/bin/env python3
"""Extract directory listings from a text-layer Danish phonebook PDF."""

import argparse
import json
import os
import re
import time
import traceback
from pathlib import Path

import pdfplumber

CHUNK = 25
DOTRUN = re.compile(r"\.{3,}")
MERGE = re.compile(r"\.{3,}\s+\.{3,}")
HEM = re.compile(r"\bhem\w*\s*n?r?\.?", re.I)
FAX = re.compile(r"\b(telefax|fax|telefaks)\b", re.I)
GARB = re.compile(r"""[«»^"”“'’~*|•\x60]""")
OCR_DIG = {
    "l": "1", "I": "1", "|": "1", "i": "1", "!": "1", "U": "0", "u": "0",
    "O": "0", "o": "0", "D": "0", "Q": "0", "B": "8", "S": "5", "s": "5",
    "G": "6", "g": "9", "Z": "2", "z": "2", "A": "4", "T": "7", "E": "3",
}
CHUNK_RE = re.compile(
    "[" + re.escape("0123456789") + re.escape("".join(OCR_DIG)) + r"\s\-]{5,}"
)
WORD = re.compile(r"[A-ZÆØÅ][a-zæøå]{2,}")
OCCUPATIONS = [
    "mask.arb", "maskinmest", "arkit", "civ.ing", "civiling", "fotogr",
    "tekn.dir", "cand.act", "cand.jur", "cand.polit", "cand.mag",
    "cand.scient", "adm.dir", "adm.bef", "kleinsm", "lokomotivfør",
    "o.postb", "konsulent", "provis", "montør", "mal.mest", "gartn.medhj",
    "elektr", "tømrer", "snedker", "murer", "bager", "slagter", "kok",
    "sygepl", "lærer", "læge", "tandlæge", "telegrafist", "kontorist",
    "kont.ass", "assistent", "bogholder", "skibsfører", "chauf", "fuldm",
    "redakt", "bogtryk", "maler", "vognmand", "vognmd", "gartner",
    "skomager", "blikkensl", "smed", "sekr", "dir", "ing", "jur",
    "kiroprakt", "pædagog", "rekl.ch", "gross", "blik.sl", "faglær",
    "pedel", "skuesp", "organ", "afd.led", "slagt", "sygehjlp", "tekn",
    "bankass", "autoudlej", "mur.mest", "typogr", "bygn.sn", "tryk", "tandl",
]
OCC_RE = re.compile(
    r"(?<![A-Za-zæøå])("
    + "|".join(re.escape(x) for x in sorted(OCCUPATIONS, key=len, reverse=True))
    + r")\.?(?![A-Za-zæøå])",
    re.I,
)


def norm(value):
    return re.sub(r"\s+", " ", GARB.sub(" ", value or "")).strip()


def normalize_num(value):
    digits = []
    for char in re.sub(r"\s+", "", value):
        if char.isdigit():
            digits.append(char)
        elif char in OCR_DIG:
            digits.append(OCR_DIG[char])
        else:
            break
    return "".join(digits)


def split_camel(value):
    parts, current = [], ""
    for index, char in enumerate(value):
        nxt = value[index + 1] if index + 1 < len(value) else ""
        prev = value[index - 1] if index else ""
        if current and char.isupper() and (
            prev.islower() or (prev.isupper() and nxt.islower())
        ):
            parts.append(current)
            current = char
        else:
            current += char
    if current:
        parts.append(current)
    return parts


def parse_head(head):
    inherited = head.startswith("-")
    if inherited:
        head = head[1:].strip()
    match = OCC_RE.search(head)
    occupation = match.group(1) if match else None
    if match:
        head = OCC_RE.sub(" ", head).strip()
    tokens = head.split()
    house = street = ""
    if tokens and re.search(r"\d", tokens[-1]):
        house = tokens.pop()
    elif tokens and re.fullmatch(r"[A-ZÆØÅ]{1,3}", tokens[-1]) and len(tokens) >= 2:
        house = tokens.pop()
    if tokens:
        street = tokens.pop()
    names = []
    for token in tokens:
        if len(token) > 6 and not re.search(r"\d", token):
            pieces = split_camel(token)
            names.extend(pieces if len(pieces) > 1 else [token])
        else:
            names.append(token)
    return inherited, occupation, street, house, norm(" ".join(names))


def parse_tail(tail):
    fax = bool(FAX.search(tail))
    unlisted = bool(HEM.search(tail))
    value = HEM.sub(" ", FAX.sub(" ", tail))
    word = WORD.search(value)
    number_zone = value[:word.start()] if word else value
    leftover = value[word.start():].strip() if word else ""
    phone = None
    extras = []
    short = ""
    for match in CHUNK_RE.finditer(number_zone):
        digits = normalize_num(match.group(0))
        if not digits:
            continue
        if phone is None and len(digits) >= 8:
            phone = digits[:8]
            if len(digits) > 8:
                extras.append(digits[8:])
        elif phone is None and 5 <= len(digits) < 8:
            short = digits
        else:
            extras.append(digits)
    return phone, extras, fax, unlisted, short, leftover


def last_written_page(path):
    if not path.exists() or not path.stat().st_size:
        return 0
    with path.open("rb") as stream:
        size = stream.seek(0, os.SEEK_END)
        stream.seek(max(0, size - 200_000))
        tail = stream.read().decode("utf-8", "replace")
    for line in reversed(tail.strip().splitlines()):
        try:
            return int(json.loads(line).get("page", 0))
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
    return 0


def extract(pdf_path, output_path, error_path, start_page, end_page, chunk_size, resume, overwrite):
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if start_page < 1 or chunk_size < 1:
        raise ValueError("start page and chunk size must be positive")
    if output_path.resolve() == pdf_path.resolve():
        raise ValueError("output path cannot be the input PDF")
    if error_path.resolve() in {pdf_path.resolve(), output_path.resolve()}:
        raise ValueError("error log path must be separate from the PDF and JSONL output")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    error_path.parent.mkdir(parents=True, exist_ok=True)

    if resume:
        if not output_path.exists():
            raise FileNotFoundError("--resume requires an existing output file")
        start_page = max(start_page, last_written_page(output_path) + 1)
    elif output_path.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {output_path}; choose another path or use --overwrite")

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
    last_page = min(end_page or total_pages, total_pages)
    if start_page > last_page:
        raise ValueError(f"start page {start_page} is after selected last page {last_page}")

    print(f"PDF pages: {total_pages}; processing {start_page}-{last_page}", flush=True)
    output_mode = "a" if resume else "w"
    error_mode = "a" if resume else "w"
    written = dropped = errors = 0
    surname_context = None
    started = time.time()
    first_index, stop_index = start_page - 1, last_page

    with output_path.open(output_mode, encoding="utf-8") as output, error_path.open(
        error_mode, encoding="utf-8"
    ) as error_log:
        for chunk_start in range(first_index, stop_index, chunk_size):
            chunk_stop = min(chunk_start + chunk_size, stop_index)
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    for page_index in range(chunk_start, chunk_stop):
                        try:
                            text = (
                                pdf.pages[page_index]
                                .filter(lambda obj: obj.get("object_type") != "char" or float(obj.get("size", 0)) < 6.0)
                                .extract_text(x_tolerance=1.5, y_tolerance=3.0, layout=True, use_text_flow=True)
                                or ""
                            )
                        except Exception as exc:
                            errors += 1
                            error_log.write(f"page {page_index + 1} extract: {exc}\n")
                            continue

                        pending = []
                        for raw_line in text.splitlines():
                            try:
                                line = MERGE.sub(".....", norm(raw_line))
                                if not line:
                                    continue
                                if not DOTRUN.search(line):
                                    pending.append(line)
                                    continue
                                work = norm(" ".join(pending) + " " + line)
                                pending = []
                                marks = list(DOTRUN.finditer(work))
                                current_head = work[:marks[0].start()].strip()
                                for index, mark in enumerate(marks):
                                    end = marks[index + 1].start() if index + 1 < len(marks) else len(work)
                                    between = work[mark.end():end].strip()
                                    inherited, occupation, street, house, names = parse_head(current_head)
                                    phone, extras, fax, unlisted, short, leftover = parse_tail(between)
                                    surname_inherited = False
                                    if inherited:
                                        if surname_context:
                                            names = norm(surname_context + " " + names)
                                            surname_inherited = True
                                    elif names:
                                        surname_context = names.split()[0]
                                    if not names and not street and not phone and not unlisted and not fax:
                                        dropped += 1
                                        current_head = leftover
                                        continue
                                    record = {
                                        "page": page_index + 1, "names": names,
                                        "surname_inherited": surname_inherited, "street": street,
                                        "house": house, "occupation": occupation, "phone": phone,
                                        "short_digits": short, "fax": fax, "extras": extras,
                                        "unlisted": unlisted, "raw": norm(raw_line),
                                    }
                                    output.write(json.dumps(record, ensure_ascii=False) + "\n")
                                    written += 1
                                    current_head = leftover
                                if current_head.strip():
                                    pending.append(current_head.strip())
                            except Exception as exc:
                                errors += 1
                                error_log.write(f"page {page_index + 1} line: {exc}\n")
            except Exception as exc:
                errors += 1
                error_log.write(f"chunk starting page {chunk_start + 1}: {exc}\n")
                traceback.print_exc(file=error_log)

            output.flush()
            elapsed = time.time() - started
            rate = (chunk_stop - first_index) / elapsed if elapsed else 0
            print(
                f"through page {chunk_stop}: rows={written}, dropped={dropped}, "
                f"errors={errors}, {rate:.2f} pages/s",
                flush=True,
            )

    print(f"DONE rows={written}, dropped={dropped}, errors={errors}, elapsed={int(time.time()-started)}s")
    return written, dropped, errors


def main():
    parser = argparse.ArgumentParser(description="Extract listings from a searchable phonebook PDF.")
    parser.add_argument("pdf", type=Path, help="local source PDF")
    parser.add_argument("--output", required=True, type=Path, help="output JSONL file")
    parser.add_argument("--errors", type=Path, help="error log (defaults beside output)")
    parser.add_argument("--start-page", type=int, default=1, help="first page, inclusive")
    parser.add_argument("--end-page", type=int, help="last page, inclusive")
    parser.add_argument("--chunk-size", type=int, default=CHUNK)
    parser.add_argument("--resume", action="store_true", help="continue after last page in output")
    parser.add_argument("--overwrite", action="store_true", help="replace an existing output")
    args = parser.parse_args()
    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite cannot be used together")
    errors = args.errors or args.output.with_suffix(".errors.log")
    try:
        extract(args.pdf, args.output, errors, args.start_page, args.end_page,
                args.chunk_size, args.resume, args.overwrite)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()