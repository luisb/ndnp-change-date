#!/usr/bin/env python3

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

NS = {
    "mets": "http://www.loc.gov/METS/",
    "mods": "http://www.loc.gov/mods/v3",
}

ET.register_namespace("MODS", NS["mods"])

BATCH_NS = {
    "ndnp": "http://www.loc.gov/ndnp",
}

ET.register_namespace("ndnp", BATCH_NS["ndnp"])


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


def ensure_missing(path: Path, label: str):
    if path.exists():
        raise FileExistsError(f"{label} already exists: {path}")


def mets_xml_to_text(root: ET.Element) -> str:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True, 
                       default_namespace=NS["mets"]).decode("utf-8")


def batch_xml_to_text(root: ET.Element) -> str:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True, 
                       default_namespace=BATCH_NS["ndnp"]).decode("utf-8")


def build_updated_mets_xml(
    src_path: Path,
    from_date: str,
    to_date: str,
    from_edition: str,
    to_edition: str,
) -> str:
    tree = ET.parse(src_path)
    root = tree.getroot()

    # Update LABEL attribute on root <mets> element
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
    edition_elem = root.find(".//mods:detail[@type='edition']/mods:number", NS)
    if edition_elem is not None and edition_elem.text == str(int(from_edition)):
        edition_elem.text = str(int(to_edition))

    return mets_xml_to_text(root)

def build_updated_batch_xml(
    src_path: Path,
    from_date: str,
    to_date: str,
    from_date_path: str,
    to_date_path: str,
    from_edition: str,
    to_edition: str,
) -> str:
    tree = ET.parse(src_path)
    root = tree.getroot()

    old_stem = f"{from_date_path}{from_edition}"
    new_stem = f"{to_date_path}{to_edition}"

    for issue in root.findall(".//ndnp:issue", BATCH_NS):
        issue_date = issue.get("issueDate")
        edition_order = issue.get("editionOrder")
        issue_text = issue.text or ""

        if issue_date == from_date and edition_order == str(int(from_edition)):
            issue.set("issueDate", to_date)
            issue.set("editionOrder", str(int(to_edition)))
            issue.text = issue_text.replace(old_stem, new_stem)
            break

    return batch_xml_to_text(root)


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.from_date == args.to_date and args.from_edition == args.to_edition:
        parser.error(
            "The to_date and to_edition cannot be the same values as the "
            "from_date and from_edition."
        )
    
    # Ensure issue directory is in the format YYYYMMDDEE
    if not re.search(r"\d{10}$", args.issue_path.name):
        parser.error(f"Issue directory name does not end with YYYYMMDDEE: {issue_path.name}")

    stats = {
        "written": 0,
        "deleted": 0,
        "renamed": 0,
        "updated": 0,
    }

    batch_path = args.batch_path
    issue_path = args.issue_path

    from_date = args.from_date.strftime("%Y-%m-%d")
    from_date_path = args.from_date.strftime("%Y%m%d")
    from_edition = f"{args.from_edition:02d}"

    to_date = args.to_date.strftime("%Y-%m-%d")
    to_date_path = args.to_date.strftime("%Y%m%d")
    to_edition = f"{args.to_edition:02d}"

    src_mets_path = issue_path / f"{from_date_path}{from_edition}.xml"
    dst_mets_path = issue_path / f"{to_date_path}{to_edition}.xml"

    src_mets_path_1 = issue_path / f"{from_date_path}{from_edition}_1.xml"

    src_issue_pdf_path = issue_path / f"{from_date_path}{from_edition}.pdf"
    dst_issue_pdf_path = issue_path / f"{to_date_path}{to_edition}.pdf"

    new_issue_name = re.sub(r"\d{10}$", to_date_path + to_edition, issue_path.name)
    new_issue_path = issue_path.with_name(new_issue_name)

    batch_xml_path = batch_path / "BATCH.xml"
    batch_xml_1_path = batch_path / "BATCH_1.xml"

    # Complete destination collision checks before modifying data
    if src_mets_path.exists():
        ensure_missing(dst_mets_path, "Destination METS file")

    if src_issue_pdf_path.exists():
        ensure_missing(dst_issue_pdf_path, "Destination issue PDF")

    if new_issue_path != issue_path:
        ensure_missing(new_issue_path, "Destination issue directory")

    # METS file
    if src_mets_path.exists():
        data = build_updated_mets_xml(
            src_mets_path,
            from_date,
            to_date,
            from_edition,
            to_edition,
        )
        write_text_file(dst_mets_path, data, args.dry_run, stats)
        delete_file(src_mets_path, args.dry_run, stats)

    # Delete old METS _1.xml file
    delete_file(src_mets_path_1, args.dry_run, stats)

    # Issue PDF file
    rename_path(src_issue_pdf_path, dst_issue_pdf_path, args.dry_run, stats)

    # Update dates in .pdf and .jp2 files
    files = list(issue_path.rglob("*.pdf")) + list(issue_path.rglob("*.jp2"))
    old_bytes = from_date.encode("ascii")
    new_bytes = to_date.encode("ascii")

    for file in files:
        replace_bytes_file(file, old_bytes, new_bytes, args.dry_run, stats)

    # Rename issue folder
    rename_path(issue_path, new_issue_path, args.dry_run, stats)

    # BATCH.xml file
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