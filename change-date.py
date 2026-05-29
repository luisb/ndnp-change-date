#!/usr/bin/env python3

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, date
from typing import Optional

NS = {
    "mets": "http://www.loc.gov/METS/",
    "mods": "http://www.loc.gov/mods/v3",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "xlink": "http://www.w3.org/1999/xlink",
    "mix": "http://www.loc.gov/mix/",
    "premis": "http://www.loc.gov/standards/premis",
    "dsig": "http://www.w3.org/2000/09/xmldsig#",
    "ndnp": "http://www.loc.gov/ndnp",
}

for prefix, uri in NS.items():
    ET.register_namespace(prefix if prefix != "mets" else "", uri)


def valid_path_directory(path) -> Path:
    out_path = Path(path)
    
    if not out_path.exists():
        raise argparse.ArgumentTypeError(f"The path {path} does not exist.")
    
    if not out_path.is_dir():
        raise argparse.ArgumentTypeError(f"The path {path} is not a directory.")
        
    return out_path


def valid_date(date_str) -> date:
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"The date {date_str} does not match the format YYYY-MM-DD or is invalid.")


def valid_int(num) -> int:
    try:
        out_num = int(num)
    except ValueError:
        raise argparse.ArgumentTypeError(f"The value {num} is not an integer.")
    
    if out_num < 1:
        raise argparse.ArgumentTypeError(f"The value {num} must be 1 or greater.")
    
    return out_num


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="change-date",
        description="Change date of an issue in an NDNP batch",
    )

    parser.add_argument("-b", "--batch-path", type=valid_path_directory, required=True)
    parser.add_argument("-i", "--issue-path", type=valid_path_directory, required=True)
    parser.add_argument("-d", "--from-date", type=valid_date)
    parser.add_argument("-e", "--from-edition", type=valid_int)
    parser.add_argument("-D", "--to-date", type=valid_date)
    parser.add_argument("-E", "--to-edition", type=valid_int)
    parser.add_argument("-q", "--from-questionable", type=valid_date, 
                        help="Specify questionable date to delete or change")
    parser.add_argument("-Q", "--to-questionable", type=valid_date, 
                        help="Specify questionable date to add or change to")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Show what would change without modifying any files")

    return parser


def log_action(message, dry_run) -> None:
    prefix = "[DRY-RUN]" if dry_run else "[RUN]"
    print(f"{prefix} {message}")


def write_text_file(path: Path, data: str, dry_run: bool, stats: dict, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")

    log_action(f"write file: {path}", dry_run)
    stats["written"] += 1

    if not dry_run:
        path.write_text(data, encoding="utf-8")


def delete_file(path: Path, dry_run: bool, stats: dict) -> None:
    if not path.exists():
        return

    log_action(f"delete file: {path}", dry_run)
    stats["deleted"] += 1

    if not dry_run:
        path.unlink()


def rename_path(src: Path, dst: Path, dry_run: bool, stats: dict) -> None:
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


def replace_bytes_file(path: Path, old: bytes, new: bytes, dry_run: bool, stats: dict) -> None:
    if not path.exists():
        return
    
    data = path.read_bytes()
    new_data = data.replace(old, new)
    if new_data != data:
        log_action(f"update contents: {path}", dry_run)
        stats["updated"] += 1

        if not dry_run:
            path.write_bytes(new_data)


def ensure_missing(path: Path, label: str) -> None:
    if path.exists():
        raise FileExistsError(f"{label} already exists: {path}")


def mets_xml_to_text(root: ET.Element) -> str:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def batch_xml_to_text(root: ET.Element) -> str:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def build_updated_mets_xml(
    src_path: Path,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    from_edition: Optional[str] = None,
    to_edition: Optional[str] = None,
    from_questionable: Optional[str] = None,
    to_questionable: Optional[str] = None) -> str:

    tree = ET.parse(src_path)
    root = tree.getroot()

    mods_ns = f"{{{NS['mods']}}}"
    origin_info = root.find(".//mods:originInfo", NS)

    # Update LABEL attribute on root <mets> element
    if from_date and to_date:
        label = root.get("LABEL")
        if label and from_date in label:
            root.set("LABEL", label.replace(from_date, to_date))

        # Update only non-questionable MODS:dateIssued values
        for elem in root.findall(".//mods:originInfo/mods:dateIssued", NS):
            qualifier = elem.get("qualifier")
            if qualifier == "questionable":
                continue
            if elem.text == from_date:
                elem.text = to_date

    # Update edition number
    if from_edition and to_edition:
        edition_elem = root.find(".//mods:detail[@type='edition']/mods:number", NS)
        if edition_elem is not None and edition_elem.text == str(int(from_edition)):
            edition_elem.text = str(int(to_edition))

    # Handle questionable dateIssued
    if from_questionable or to_questionable:
        if origin_info is not None:
            questionable_elem = None
            normal_elem = None

            for elem in origin_info.findall("mods:dateIssued", NS):
                if elem.get("qualifier") == "questionable":
                    if from_questionable is None or elem.text == from_questionable:
                        questionable_elem = elem
                elif normal_elem is None:
                    normal_elem = elem

            # Case 1: -q only -> delete matching questionable date
            if from_questionable and not to_questionable:
                if questionable_elem is not None and questionable_elem.text == from_questionable:
                    origin_info.remove(questionable_elem)

            # Case 2: -q and -Q -> change matching questionable date
            elif from_questionable and to_questionable:
                if questionable_elem is not None and questionable_elem.text == from_questionable:
                    questionable_elem.text = to_questionable

            # Case 3: -Q only -> add questionable date after normal dateIssued
            elif not from_questionable and to_questionable:
                if questionable_elem is None:
                    new_elem = ET.Element(f"{mods_ns}dateIssued", {
                        "encoding": "iso8601",
                        "qualifier": "questionable",
                    })
                    new_elem.text = to_questionable

                    if normal_elem is not None:
                        children = list(origin_info)
                        insert_at = children.index(normal_elem) + 1
                        origin_info.insert(insert_at, new_elem)
                    else:
                        origin_info.append(new_elem)

    return mets_xml_to_text(root)

def build_updated_batch_xml(
    src_path: Path,
    from_date: str,
    to_date: str,
    from_date_path: str,
    to_date_path: str,
    from_edition: str,
    to_edition: str) -> str:

    tree = ET.parse(src_path)
    root = tree.getroot()

    old_stem = f"{from_date_path}{from_edition}"
    new_stem = f"{to_date_path}{to_edition}"

    for issue in root.findall(".//ndnp:issue", NS):
        issue_date = issue.get("issueDate")
        edition_order = issue.get("editionOrder")
        issue_text = issue.text or ""

        if issue_date == from_date and edition_order == str(int(from_edition)):
            issue.set("issueDate", to_date)
            issue.set("editionOrder", str(int(to_edition)))
            issue.text = issue_text.replace(old_stem, new_stem)
            break

    return batch_xml_to_text(root)


def mets_has_questionable_date(src_path: Path, target_date: str) -> bool:
    tree = ET.parse(src_path)
    root = tree.getroot()

    for elem in root.findall(".//mods:originInfo/mods:dateIssued", NS):
        if elem.get("qualifier") == "questionable" and elem.text == target_date:
            return True
        
    return False


def mets_has_any_questionable_date(src_path: Path) -> bool:
    tree = ET.parse(src_path)
    root = tree.getroot()

    for elem in root.findall(".//mods:originInfo/mods:dateIssued", NS):
        if elem.get("qualifier") == "questionable":
            return True
        
    return False


def main():
    parser = build_parser()
    args = parser.parse_args()

    date_args = [args.from_date, args.from_edition, args.to_date, args.to_edition]
    date_args_present = [value is not None for value in date_args]
    
    if any(date_args_present) and not all(date_args_present):
        parser.error(
            "When using date/edition changes, -d, -e, -D, and -E must all be provided.")

    is_date_change = all(date_args_present)
    is_questionable_change = (args.from_questionable is not None or args.to_questionable is not None)

    if not is_date_change and not is_questionable_change:
        parser.error(
            "Nothing to do. Provide -d/-e/-D/-E for a date change and/or -q/-Q for questionable-date changes.")

    if is_date_change:
        if args.from_date == args.to_date and args.from_edition == args.to_edition:
            parser.error(
                "The to_date and to_edition cannot be the same values as the "
                "from_date and from_edition.")
    
    # Ensure issue directory is in the format YYYYMMDDEE
    if not re.search(r"\d{10}$", args.issue_path.name):
        parser.error(f"Issue directory name does not end with YYYYMMDDEE: {args.issue_path.name}")

    if (args.from_questionable
        and args.to_questionable
        and args.from_questionable == args.to_questionable):
        parser.error("The to_questionable date cannot be the same as the from_questionable date.")

    stats = {
        "written": 0,
        "deleted": 0,
        "renamed": 0,
        "updated": 0,
    }

    batch_path = args.batch_path
    issue_path = args.issue_path

    from_date = args.from_date.strftime("%Y-%m-%d") if args.from_date else None
    from_date_path = args.from_date.strftime("%Y%m%d") if args.from_date else None
    from_edition = f"{args.from_edition:02d}" if args.from_edition else None

    to_date = args.to_date.strftime("%Y-%m-%d") if args.to_date else None
    to_date_path = args.to_date.strftime("%Y%m%d") if args.to_date else None
    to_edition = f"{args.to_edition:02d}" if args.to_edition else None

    from_questionable = (args.from_questionable.strftime("%Y-%m-%d")
                         if args.from_questionable else None)

    to_questionable = (args.to_questionable.strftime("%Y-%m-%d")
                       if args.to_questionable else None)
    
    if is_date_change:
        src_mets_path = issue_path / f"{from_date_path}{from_edition}.xml"
        dst_mets_path = issue_path / f"{to_date_path}{to_edition}.xml"

        src_mets_path_1 = issue_path / f"{from_date_path}{from_edition}_1.xml"

        src_issue_pdf_path = issue_path / f"{from_date_path}{from_edition}.pdf"
        dst_issue_pdf_path = issue_path / f"{to_date_path}{to_edition}.pdf"

        new_issue_name = issue_path.name[:-10] + to_date_path + to_edition
        new_issue_path = issue_path.with_name(new_issue_name)

        # Complete destination collision checks before modifying data
        if src_mets_path.exists():
            ensure_missing(dst_mets_path, "Destination METS file")

        if src_issue_pdf_path.exists():
            ensure_missing(dst_issue_pdf_path, "Destination issue PDF")

        if new_issue_path != issue_path:
            ensure_missing(new_issue_path, "Destination issue directory")


    else:
        mets_files = [
            p for p in issue_path.glob("*.xml")
            if p.is_file() and re.fullmatch(r"\d{10}\.xml", p.name)
        ]

        if len(mets_files) != 1:
            parser.error(
                f"Expected exactly one METS file with a 10-digit name in {issue_path}, found {len(mets_files)}."
            )
        
        src_mets_path = mets_files[0]
        src_mets_path_1 = src_mets_path.with_name(f"{src_mets_path.stem}_1.xml")

    batch_xml_path = batch_path / "BATCH.xml"
    batch_xml_1_path = batch_path / "BATCH_1.xml"

    # Ensure from_questionable exists as questionable date
    if from_questionable:
        if not src_mets_path.exists():
            parser.error(f"Source METS file does not exist: {src_mets_path}")

        if not mets_has_questionable_date(src_mets_path, from_questionable):
            parser.error(f'The questionable date "{from_questionable}" was not found in {src_mets_path}.')

    # Ensure source METS exists for questionable-date operations
    if args.from_questionable or args.to_questionable:
        if not src_mets_path.exists():
            parser.error(f"Source METS file does not exist: {src_mets_path}")

    # If creating a questionable date, error if any questionable date already exists
    if args.to_questionable and not args.from_questionable:
        if mets_has_any_questionable_date(src_mets_path):
            parser.error(
                f'A questionable date already exists in {src_mets_path}; '
                f'use -q to update it instead of adding another one.'
            )
    
    # METS file
    if src_mets_path.exists():
        if is_date_change:
            data = build_updated_mets_xml(
                src_path=src_mets_path,
                from_date=from_date,
                to_date=to_date,
                from_edition=from_edition,
                to_edition=to_edition,
                from_questionable=from_questionable,
                to_questionable=to_questionable
            )
            write_text_file(dst_mets_path, data, args.dry_run, stats)
            delete_file(src_mets_path, args.dry_run, stats)
        else:
            data = build_updated_mets_xml(
                src_path=src_mets_path,
                from_questionable=from_questionable,
                to_questionable=to_questionable
            )
            write_text_file(src_mets_path, data, args.dry_run, stats, overwrite=True)

    # Delete old METS _1.xml file
    delete_file(src_mets_path_1, args.dry_run, stats)

    # Issue PDF file
    if is_date_change:
        rename_path(src_issue_pdf_path, dst_issue_pdf_path, args.dry_run, stats)
        
    # Update dates in .pdf and .jp2 files
    if is_date_change:
        files = list(issue_path.rglob("*.pdf")) + list(issue_path.rglob("*.jp2"))
        old_bytes = from_date.encode("ascii")
        new_bytes = to_date.encode("ascii")

        for file in files:
            replace_bytes_file(file, old_bytes, new_bytes, args.dry_run, stats)

        # Rename issue folder
        rename_path(issue_path, new_issue_path, args.dry_run, stats)

    # BATCH.xml file
    if is_date_change:
        if batch_xml_path.exists():
            data = build_updated_batch_xml(
                batch_xml_path,
                from_date,
                to_date,
                from_date_path,
                to_date_path,
                from_edition,
                to_edition,
            )
            write_text_file(batch_xml_path, data, args.dry_run, stats, overwrite=True)

        # Delete BATCH_1.xml
        delete_file(batch_xml_1_path, args.dry_run, stats)

    log_action(
        "summary: "
        f"written={stats['written']}, "
        f"deleted={stats['deleted']}, "
        f"renamed={stats['renamed']}, "
        f"updated={stats['updated']}",
        args.dry_run,
    )


if __name__ == "__main__":
    main()