#!/usr/bin/env python3

import argparse
import re
from pathlib import Path
from datetime import datetime

def valid_path_directory(path):
    out_path = Path(path)
    
    if not out_path.exists():
        raise argparse.ArgumentTypeError(f"The path {path} does not exist.")
    
    if not out_path.is_dir():
        raise argparse.ArgumentTypeError(f"The path {path} is not a directory.")
        
    return out_path


def valid_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"The date {date_str} does not match the format YYYY-MM-DD or is invalid.")


def valid_int(num):
    try:
        out_num = int(num)
    except ValueError:
        raise argparse.ArgumentTypeError(f"The value {num} is not an integer.")
    
    if out_num < 1:
        raise argparse.ArgumentTypeError(f"The value {num} must be 1 or greater.")
    
    return out_num


def build_parser():
    parser = argparse.ArgumentParser(
        prog="change-date",
        description="Change date of an issue in an NDNP batch",
    )

    parser.add_argument("-b", "--batch-path", type=valid_path_directory, required=True)
    parser.add_argument("-i", "--issue-path", type=valid_path_directory, required=True)
    parser.add_argument("-d", "--from-date", type=valid_date, required=True)
    parser.add_argument("-e", "--from-edition", type=valid_int, required=True)
    parser.add_argument("-D", "--to-date", type=valid_date, required=True)
    parser.add_argument("-E", "--to-edition", type=valid_int, required=True)
    parser.add_argument("-n", "--dry-run", action="store_true",
        help="Show what would change without modifying any files",
    )

    return parser


def log_action(message, dry_run):
    prefix = "[DRY-RUN]" if dry_run else "[RUN]"
    print(f"{prefix} {message}")


def write_text_file(path: Path, data: str, dry_run: bool, stats: dict, overwrite: bool = False):
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")

    log_action(f"write file: {path}", dry_run)
    stats["written"] += 1

    if not dry_run:
        path.write_text(data, encoding="utf-8")


def delete_file(path: Path, dry_run: bool, stats: dict):
    if not path.exists():
        return

    log_action(f"delete file: {path}", dry_run)
    stats["deleted"] += 1

    if not dry_run:
        path.unlink()


def rename_path(src: Path, dst: Path, dry_run: bool, stats: dict):
    if not src.exists():
        return
    
    if src == dst:
        return
    
    if dst.exists():
        raise FileExistsError(f"Target already exists: {dst}")

    log_action(f"rename: {src} -> {dst}", dry_run)
    stats["renamed"] += 1

    if not dry_run:
        src.rename(dst)


def replace_bytes_file(path: Path, old: bytes, new: bytes, dry_run: bool, stats: dict):
    if not path.exists():
        return
    
    data = path.read_bytes()
    new_data = data.replace(old, new)
    if new_data != data:
        log_action(f"update contents: {path}", dry_run)
        stats["updated"] += 1

        if not dry_run:
            path.write_bytes(new_data)
    parser = build_parser()
    args = parser.parse_args()

    stats = {
        "written": 0,
        "deleted": 0,
        "renamed": 0,
        "updated": 0,
    }

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
    write_text_file(dst_mets_path, data)

    # Delete old METS file
    delete_file(src_mets_path)

# Delete old METS _1.xml file
src_mets_path_1 = issue_path / f"{from_date_path}{from_edition}_1.xml"
delete_file(src_mets_path_1)

# Issue PDF file (if exists)
src_issue_pdf_path = issue_path / f"{from_date_path}{from_edition}.pdf"
dst_issue_pdf_path = issue_path / f"{to_date_path}{to_edition}.pdf"

rename_path(src_issue_pdf_path, dst_issue_pdf_path)

# Update dates in .pdf and .jp2 files
files = list(issue_path.rglob("*.pdf")) + list(issue_path.rglob("*.jp2"))

for file in files:
    replace_bytes_file(file, from_date.encode("ascii"), to_date.encode("ascii"))

# Rename issue folder
if issue_path.exists():
    new_issue_name = re.sub(r"\d{10}$", to_date_path + to_edition, issue_path.name)
    new_issue_path = issue_path.with_name(new_issue_name)
        write_text_file(dst_mets_path, data, args.dry_run, stats)
        delete_file(src_mets_path, args.dry_run, stats)

    delete_file(src_mets_path_1, args.dry_run, stats)

    rename_path(src_issue_pdf_path, dst_issue_pdf_path, args.dry_run, stats)

        replace_bytes_file(file, old_bytes, new_bytes, args.dry_run, stats)

    rename_path(issue_path, new_issue_path, args.dry_run, stats)

        write_text_file(batch_xml_path, data, args.dry_run, stats, overwrite=True)

    delete_file(batch_xml_1_path, args.dry_run, stats)

    log_action(
        "summary: "
        f"written={stats['written']}, "
        f"deleted={stats['deleted']}, "
        f"renamed={stats['renamed']}, "
        f"updated={stats['updated']}",
        args.dry_run,
    )
