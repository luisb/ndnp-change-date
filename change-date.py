#!/usr/bin/python

import argparse
import re
import subprocess
from pathlib import Path
from datetime import datetime

def valid_path_directory(path):
    out_path = Path(path)
    
    if not out_path.exists():
        raise argparse.ArgumentTypeError(f"The path {path} does not exist.")
    
    if not out_path.is_dir():
        raise argparse.ArgumentTypeError(f"The path {path} is not a directory.")
        
    return out_path


def valid_date(date):
    try:
        return datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"The date {date} does not match the format YYYY-MM-DD or is invalid.")


def valid_int(num):
    try:
        out_num = int(num)
    except ValueError:
        raise argparse.ArgumentTypeError(f"The value {num} is not an integer.")
    
    if out_num < 1:
        raise argparse.ArgumentTypeError(f"The value {num} must be 1 or greater.")
    
    return out_num


def replace_text_file(path: Path, old: str, new: str):
    if not path.exists():
        return
    
    data = path.read_text(encoding="utf-8")
    new_data = data.replace(old, new)
    
    if new_data != data:
        path.write_text(new_data, encoding="utf-8")


parser = argparse.ArgumentParser(
    prog='change-date',
    description="Change date of an issue in an NDNP batch")

parser.add_argument('-b', '--batch-path', type=valid_path_directory, required=True)
parser.add_argument('-i', '--issue-path', type=valid_path_directory, required=True)
parser.add_argument('-d', '--from-date', type=valid_date, required=True)
parser.add_argument('-e', '--from-edition', type=valid_int, required=True)
parser.add_argument('-D', '--to-date', type=valid_date, required=True)
parser.add_argument('-E', '--to-edition', type=valid_int, required=True)

args = parser.parse_args()

batch_path = args.batch_path
issue_path = args.issue_path

from_date = args.from_date.strftime("%Y-%m-%d")
from_date_path = args.from_date.strftime("%Y%m%d")
from_edition = f"{args.from_edition:02d}"

to_date = args.to_date.strftime("%Y-%m-%d")
to_date_path = args.to_date.strftime("%Y%m%d")
to_edition = f"{args.to_edition:02d}"

# METS file
src_mets_path = issue_path / f"{from_date_path}{from_edition}.xml"
dst_mets_path = issue_path / f"{to_date_path}{to_edition}.xml"

if src_mets_path.exists():
    data = src_mets_path.read_text(encoding="utf-8").replace(from_date, to_date)
    dst_mets_path.write_text(data, encoding="utf-8")

    # Delete old METS file
    src_mets_path.unlink()

# Delete old METS _1.xml file
src_mets_path_1 = issue_path / f"{from_date_path}{from_edition}_1.xml"
src_mets_path_1.unlink(missing_ok=True)

# Issue PDF file (if exists)
src_issue_pdf_path = issue_path / f"{from_date_path}{from_edition}.pdf"
dst_issue_pdf_path = issue_path / f"{to_date_path}{to_edition}.pdf"

if src_issue_pdf_path.exists():
    src_issue_pdf_path.rename(dst_issue_pdf_path)

# Update dates in .pdf and .jp2 files
files = list(issue_path.rglob("*.pdf")) + list(issue_path.rglob("*.jp2"))

for file in files:
    cmd = [
        "sed", "-i",
        f"s/{from_date}/{to_date}/g",
        str(file)
    ]
    subprocess.run(cmd, check=True)

# Rename issue folder
if issue_path.exists():
    new_issue_path = re.sub(r"\d{10}$", to_date_path + to_edition, str(issue_path))
    new_issue_path = Path(new_issue_path)

    issue_path.rename(new_issue_path)

# BATCH.xml file
# replace issueDate attribute
replace_text_file(batch_path / "BATCH.xml", from_date, to_date)
# replace path dates
replace_text_file(batch_path / "BATCH.xml", from_date_path, to_date_path)

# Delete BATCH_1.xml
(batch_path / "BATCH_1.xml").unlink(missing_ok=True)
