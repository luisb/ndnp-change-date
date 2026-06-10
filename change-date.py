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
        description="Change date of an issue in an NDNP batch and/or manage questionable dates.",
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
    parser.add_argument("-v", "--verbose", action="store_true", 
                        help="Show additional messages in output")

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
        path.write_text(data, encoding="UTF-8")


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


def replace_bytes_file(path: Path, old: bytes, new: bytes, dry_run: bool, stats: dict, verbose: bool) -> None:
    if not path.exists():
        if verbose:
            log_action(f'[VERBOSE] The path "{path}" does not exist.')
        return
    
    data = path.read_bytes()
    new_data = data.replace(old, new)
    if new_data != data:
        log_action(f"update contents: {path}", dry_run)
        stats["updated"] += 1

        if not dry_run:
            path.write_bytes(new_data)
    else:
        if verbose:
            log_action(f'[VERBOSE] No change required.', dry_run)


def ensure_missing(path: Path, label: str) -> None:
    if path.exists():
        raise FileExistsError(f"{label} already exists: {path}")


def mets_xml_to_text(root: ET.Element) -> str:
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True).decode("UTF-8")


def batch_xml_to_text(root: ET.Element) -> str:
    xml_str = ET.tostring(root, encoding="UTF-8", xml_declaration=True).decode("UTF-8")

    xml_str = re.sub(r"<batch .*(?=name=)",'<batch xmlns:ndnp="http://www.loc.gov/ndnp" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns="http://www.loc.gov/ndnp" xsi:schemaLocation="http://www.loc.gov/ndnp ./schema/ndnpBatch.xsd" ', xml_str)

    return xml_str


def validate_issue_identity(issue_path: Path, from_date_path: str, from_edition: str) -> None:
    issue_suffix = issue_path.name[-10:]
    expected = f"{from_date_path}{from_edition}"
    
    if issue_suffix != expected:
        raise ValueError(
            "The issue directory does not match --from-date/--from-edition: "
            f'the issue directory is "{issue_suffix}", but with --from-date/--from-edition '
            f'expected "{expected}".')


def validate_mets_date_and_edition(
        src_path: Path,
        expected_date: str,
        expected_edition: str, 
        dry_run: bool,
        verbose: bool) -> tuple[bool, bool]:

    tree = ET.parse(src_path)
    root = tree.getroot()

    found_date = False
    found_edition = False

    for elem in root.findall(".//mods:originInfo/mods:dateIssued", NS):
        if elem.get("qualifier") == "questionable":
            continue
        if elem.text == expected_date:
            if verbose:
                log_action(f'[VERBOSE] found non-questionable dateIssued element with value "{expected_date}".', dry_run)
            found_date = True
            break

    edition_elem = root.find(".//mods:detail[@type='edition']/mods:number", NS)
    if edition_elem is not None and edition_elem.text == str(int(expected_edition)):
        if verbose:
            log_action(f'[VERBOSE] found edition number element with value "{str(int(expected_edition))}".', dry_run)
        found_edition = True

    if not found_date and verbose:
        log_action(f'[VERBOSE] did not find non-questionable dateIssued element with value "{expected_date}".', dry_run)
    if not found_edition and verbose:
        log_action(f'[VERBOSE] did not find edition number element with value "{str(int(expected_edition))}".', dry_run)
    return found_date, found_edition


def batch_has_exact_issue(
    src_path: Path,
    expected_date: str,
    expected_edition: str,
    expected_stem: str, 
    dry_run: bool,
    verbose: bool) -> bool:

    tree = ET.parse(src_path)
    root = tree.getroot()

    if verbose:
        log_action(f'[VERBOSE] Searching for .//ndnp:issue', dry_run)
    issues = root.findall(".//ndnp:issue", NS)
    if len(issues) == 0:
        if verbose:
            log_action(f'[VERBOSE] Found {len(issues)} issues.', dry_run)
            log_action(f'[VERBOSE] Searching for .//issue', dry_run)
        issues = root.findall(".//issue", NS)

    if verbose:
        log_action(f'[VERBOSE] found {len(issues)} issue entries in BATCH.xml.', dry_run)
    for issue in issues:
        issue_date = issue.get("issueDate")
        edition_order = issue.get("editionOrder")
        issue_text = (issue.text or "").strip()

        if (issue_date == expected_date
            and int(edition_order) == int(expected_edition)
            and expected_stem in issue_text):
            if verbose:
                log_action(f'[VERBOSE] found matching issue entry with issueDate="{issue_date}", editionOrder="{str(int(edition_order))}", '
                           f'and issue path containing "{expected_stem}".', dry_run)
            return True

    return False


def build_updated_mets_xml(
    src_path: Path,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    from_edition: Optional[str] = None,
    to_edition: Optional[str] = None,
    from_questionable: Optional[str] = None,
    to_questionable: Optional[str] = None, 
    dry_run: bool = False,
    verbose: bool = False) -> str:

    tree = ET.parse(src_path)
    root = tree.getroot()

    mods_ns = f"{{{NS['mods']}}}"
    origin_info = root.find(".//mods:originInfo", NS)

    # Update LABEL attribute on root <mets> element
    if from_date and to_date:
        label = root.get("LABEL")
        if label and verbose:
            log_action(f'[VERBOSE] LABEL attribute found: "{label}".', dry_run)
        if label and from_date in label:
            if verbose:
                log_action(f'[VERBOSE] updating LABEL attribute {from_date} -> {to_date}.', dry_run)
            root.set("LABEL", label.replace(from_date, to_date))

        # Update only non-questionable MODS:dateIssued values
        for elem in root.findall(".//mods:originInfo/mods:dateIssued", NS):
            if verbose:
                log_action(f'[VERBOSE] found {len(root.findall(".//mods:originInfo/mods:dateIssued", NS))} '
                           f'dateIssued {"element" if len(root.findall(".//mods:originInfo/mods:dateIssued", NS)) == 1 else "elements"}.', dry_run)
            qualifier = elem.get("qualifier")
            if qualifier == "questionable":
                if verbose:
                    log_action(f'[VERBOSE] skipping dateIssued element with qualifier "questionable" and value "{elem.text}".', dry_run)
                continue
            if elem.text == from_date:
                if verbose:
                    log_action(f'[VERBOSE] updating dateIssued element value {from_date} -> {to_date}.', dry_run)
                elem.text = to_date

    # Update edition number
    if from_edition and to_edition:
        edition_elem = root.find(".//mods:detail[@type='edition']/mods:number", NS)
        if edition_elem is not None and edition_elem.text == str(int(from_edition)):
            if verbose:
                log_action(f'[VERBOSE] updating edition number {str(int(from_edition))} -> {str(int(to_edition))}.', dry_run)
            edition_elem.text = str(int(to_edition))

    # Handle questionable dateIssued
    if from_questionable or to_questionable:
        if origin_info is not None:
            questionable_elem = None
            normal_elem = None

            if verbose:
                log_action(f'[VERBOSE] searching for questionable dateIssued elements to update, delete, or add.', dry_run)
            for elem in origin_info.findall("mods:dateIssued", NS):
                if elem.get("qualifier") == "questionable":
                    if from_questionable is None or elem.text == from_questionable:
                        questionable_elem = elem
                elif normal_elem is None:
                    normal_elem = elem

            # Case 1: -q only -> delete matching questionable date
            if from_questionable and not to_questionable:
                if questionable_elem is not None and questionable_elem.text == from_questionable:
                    if verbose:
                        log_action(f'[VERBOSE] removing questionable dateIssued element with value "{from_questionable}".', dry_run)
                    origin_info.remove(questionable_elem)

            # Case 2: -q and -Q -> change matching questionable date
            elif from_questionable and to_questionable:
                if questionable_elem is not None and questionable_elem.text == from_questionable:
                    if verbose:
                        log_action(f'[VERBOSE] updating questionable dateIssued element value {from_questionable} -> {to_questionable}.', dry_run)
                    questionable_elem.text = to_questionable

            # Case 3: -Q only -> add questionable date after normal dateIssued
            elif not from_questionable and to_questionable:
                if questionable_elem is None:
                    new_elem = ET.Element(f"{mods_ns}dateIssued", {
                        "encoding": "iso8601",
                        "qualifier": "questionable",
                    })
                    new_elem.text = to_questionable

                    if verbose:
                        log_action(f'[VERBOSE] adding new questionable dateIssued element with value "{to_questionable}".', dry_run)
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
    to_edition: str, 
    dry_run: bool, 
    verbose: bool) -> str:

    tree = ET.parse(src_path)
    root = tree.getroot()

    old_stem = f"{from_date_path}{from_edition}"
    new_stem = f"{to_date_path}{to_edition}"

    if verbose:
        log_action(f'[VERBOSE] Searching for .//ndnp:issue', dry_run)
    issues = root.findall(".//ndnp:issue", NS)
    if len(issues) == 0:
        log_action(f'[VERBOSE] Found {len(issues)} issues.', dry_run)
        log_action(f'[VERBOSE] Searching for .//issue', dry_run)
        issues = root.findall(".//issue", NS)
        
    if verbose:
        log_action(f'[VERBOSE] found {len(issues)} issue entries in BATCH.xml.', dry_run)

    for issue in issues:
        issue_date = issue.get("issueDate")
        edition_order = issue.get("editionOrder")
        issue_text = issue.text or ""

        if issue_date == from_date and int(edition_order) == int(from_edition):
            if verbose:
                log_action(f'[VERBOSE] updating issue entry with issueDate="{from_date}" -> "{to_date}", '
                           f'editionOrder="{str(int(from_edition))}" -> "{str(int(to_edition))}", '
                           f'and issue text containing "{old_stem}" -> "{new_stem}".', dry_run)
            issue.set("issueDate", to_date)
            issue.set("editionOrder", str(int(to_edition)))
            issue.text = issue_text.replace(old_stem, new_stem)
            break
    
    # Clean up ndnp: namespace prefixes in XML
    if verbose:
        log_action(f'[VERBOSE] removing "ndnp:" namespace prefixes from BATCH.xml.', dry_run)
    xml_str = batch_xml_to_text(root)
    xml_str = xml_str.replace("ndnp:", "")

    return xml_str


def mets_has_questionable_date(src_path: Path, target_date: str, dry_run: bool, verbose: bool) -> bool:
    tree = ET.parse(src_path)
    root = tree.getroot()

    for elem in root.findall(".//mods:originInfo/mods:dateIssued", NS):
        if elem.get("qualifier") == "questionable" and elem.text == target_date:
            if verbose:
                log_action(f'[VERBOSE] found questionable dateIssued element with value "{target_date}".', dry_run)
            return True
    if verbose:
        log_action(f'[VERBOSE] did not find questionable dateIssued element with value "{target_date}".', dry_run)
    return False


def mets_has_any_questionable_date(src_path: Path, dry_run: bool, verbose: bool) -> bool:
    tree = ET.parse(src_path)
    root = tree.getroot()

    for elem in root.findall(".//mods:originInfo/mods:dateIssued", NS):
        if elem.get("qualifier") == "questionable":
            if verbose:
                log_action(f'[VERBOSE] found questionable dateIssued element with value "{elem.text}".', dry_run)
            return True
    if verbose:
        log_action(f'[VERBOSE] did not find any questionable dateIssued elements.', dry_run)
    return False


def main():
    parser = build_parser()
    args = parser.parse_args()

    batch_path = args.batch_path
    issue_path = args.issue_path

    batch_xml_path = batch_path / "BATCH.xml"
    batch_xml_1_path = batch_path / "BATCH_1.xml"

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
    
    dry_run = args.dry_run
    verbose = args.verbose

    date_args = [from_date, from_edition, to_date, to_edition]
    date_args_present = [value is not None for value in date_args]
    
    if verbose:
        log_action(f'[VERBOSE] check if any date options are given, all date options are given.', dry_run)
    if any(date_args_present) and not all(date_args_present):
        parser.error(
            "When using date/edition changes, -d, -e, -D, and -E must all be provided.")

    is_date_change = all(date_args_present)
    is_questionable_change = (from_questionable is not None or to_questionable is not None)

    if is_date_change and not is_questionable_change and verbose:
        log_action(f'[VERBOSE] date change operation detected.', dry_run)

    if is_questionable_change and not is_date_change and verbose:
        log_action(f'[VERBOSE] questionable date operation detected.', dry_run)

    if is_date_change and is_questionable_change and verbose:
        log_action(f'[VERBOSE] date change and questionable date operations detected.', dry_run)

    if not is_date_change and not is_questionable_change:
        parser.error(
            "Nothing to do. Provide -d/-e/-D/-E for a date change and/or -q/-Q for questionable-date changes.")

    if is_date_change:
        if verbose:
            log_action(f'[VERBOSE] checking from_date "{from_date}" and edition "{str(int(from_edition))}" '
                       f'is not the same as to_date "{to_date}" and edition "{str(int(to_edition))}".', dry_run)
        if from_date == to_date and from_edition == to_edition:
            parser.error(
                "The to_date and to_edition cannot be the same values as the "
                "from_date and from_edition.")
    
    # Ensure issue directory is in the format YYYYMMDDEE
    if verbose:
        log_action(f'[VERBOSE] check that the issue directory ends in 10 digits', dry_run)
    if not re.search(r"\d{10}$", issue_path.name):
        parser.error(f"Issue directory name does not end with YYYYMMDDEE: {issue_path.name}")

    if from_questionable and verbose:
        log_action(f'[VERBOSE] checking that from_questionable date "{from_questionable}" is not the same as '
                   f'to_questionable date "{to_questionable}".', dry_run)
    if (from_questionable
        and to_questionable
        and from_questionable == to_questionable):
        parser.error("The to_questionable date cannot be the same as the from_questionable date.")

    stats = {
        "written": 0,
        "deleted": 0,
        "renamed": 0,
        "updated": 0,
    }

    if is_date_change:
        try: 
            if verbose:
                log_action(f'[VERBOSE] checking issue directory "{issue_path.name[-10:]} matches from_date and edition "{from_date_path}{from_edition}".', dry_run)
            validate_issue_identity(issue_path, from_date_path, from_edition)
        except ValueError as e:
            parser.error(str(e))

        src_mets_path = issue_path / f"{from_date_path}{from_edition}.xml"
        dst_mets_path = issue_path / f"{to_date_path}{to_edition}.xml"

        src_mets_path_1 = issue_path / f"{from_date_path}{from_edition}_1.xml"

        src_issue_pdf_path = issue_path / f"{from_date_path}{from_edition}.pdf"
        dst_issue_pdf_path = issue_path / f"{to_date_path}{to_edition}.pdf"

        new_issue_name = issue_path.name[:-10] + to_date_path + to_edition
        new_issue_path = issue_path.with_name(new_issue_name)
        
        if verbose:
            log_action(f'[VERBOSE] checking if METS file "{src_mets_path}" exists', dry_run)
        if not src_mets_path.exists():
            parser.error(f"Source METS file does not exist: {src_mets_path}. "
                         "This path is derived from --from-date/--from-edition, so verify those "
                         "values match the issue directory and source METS name.")

        if verbose:
            log_action(f'[VERBOSE] checking if from_date "{from_date}" and from_edition "{int(from_edition)}" are in the METS file.', dry_run)
        found_date, found_edition = validate_mets_date_and_edition(
            src_path=src_mets_path,
            expected_date=from_date,
            expected_edition=from_edition,
            dry_run=dry_run,
            verbose=verbose)
        
        if not found_date and not found_edition:
            parser.error(f'Neither from_date "{from_date}" nor from_edition "{int(from_edition)}" '
                            f'was found in {src_mets_path}.')
        elif not found_date:
            parser.error(f'The from_date "{from_date}" was not found as a non-questionable '
                            f'dateIssued in {src_mets_path}.')
        elif not found_edition:
            parser.error(
                f'The from_edition "{int(from_edition)}" was not found in {src_mets_path}.'
            )

        if verbose:
            log_action(f'[VERBOSE] checking there are no collisions for destination METS, issue PDF, and issue directory.', dry_run)
        # Complete destination collision checks before modifying data
        if src_mets_path.exists():
            ensure_missing(dst_mets_path, "Destination METS file")

        if src_issue_pdf_path.exists():
            ensure_missing(dst_issue_pdf_path, "Destination issue PDF")

        if new_issue_path != issue_path:
            ensure_missing(new_issue_path, "Destination issue directory")

        if verbose:
            log_action(f'[VERBOSE] checking "{batch_xml_path}" exists.', dry_run)
        if not batch_xml_path.exists():
            parser.error(f"BATCH.xml file does not exist: {batch_xml_path}")

        expected_stem = f"{from_date_path}{from_edition}"

        if verbose:
            log_action(f'[VERBOSE] checking that from_date "{from_date}, edition "{int(from_edition)}", and "{expected_stem}" '
                       f'are in one line in the BATCH.xml file.', dry_run)

        if not batch_has_exact_issue(
            batch_xml_path,
            from_date,
            from_edition,
            expected_stem,
            dry_run,
            verbose):

            parser.error(
                f"No exact matching issue entry was found in {batch_xml_path} for "
                f'issueDate="{from_date}", editionOrder="{int(from_edition)}", '
                f'and issue path containing "{expected_stem}".'
            )
        
    else:
        if verbose:
            log_action(f'[VERBOSE] counting number of METS files in issue directory.', dry_run)
        mets_files = [
            p for p in issue_path.glob("*.xml")
            if p.is_file() and re.fullmatch(r"\d{10}\.xml", p.name)
        ]
        if verbose:
            file = f"{'file' if len(mets_files) == 1 else 'files'}"
            log_action(f'[VERBOSE] found {len(mets_files)} METS {file}.', dry_run)
        if len(mets_files) != 1:
            parser.error(
                f"Expected exactly one METS file with a 10-digit name in {issue_path}; found {len(mets_files)}."
            )
        
        src_mets_path = mets_files[0]
        src_mets_path_1 = src_mets_path.with_name(f"{src_mets_path.stem}_1.xml")

    # Ensure from_questionable exists as questionable date
    if from_questionable:
        if verbose:
            log_action(f'[VERBOSE] checking METS file "{src_mets_path}" exists.', dry_run)
        if not src_mets_path.exists():
            parser.error(f"Source METS file does not exist: {src_mets_path}")

        if verbose:
            log_action(f'[VERBOSE] checking METS contains from_questionable date "{from_questionable}".', dry_run)
        if not mets_has_questionable_date(src_mets_path, from_questionable, dry_run, verbose):
            parser.error(f'The questionable date "{from_questionable}" was not found in {src_mets_path}.')

    # Ensure source METS exists for questionable-date operations
    if verbose:
        log_action(f'[VERBOSE] checking METS file "{src_mets_path}" exists.', dry_run)
    if from_questionable or to_questionable:
        if not src_mets_path.exists():
            parser.error(f"Source METS file does not exist: {src_mets_path}")

    # If creating a questionable date, error if any questionable date already exists
    if to_questionable and not from_questionable:
        if verbose:
            log_action(f'[VERBOSE] checking if there is already a questionable date.', dry_run)
        if mets_has_any_questionable_date(src_mets_path, dry_run, verbose):
            parser.error(
                f'A questionable date already exists in {src_mets_path}; '
                f'use -q to update it instead of adding another one.'
            )
    
    # METS file
    if src_mets_path.exists():
        if is_date_change:
            if verbose:
                log_action(f'[VERBOSE] building new METS file.', dry_run)
            data = build_updated_mets_xml(
                src_path=src_mets_path,
                from_date=from_date,
                to_date=to_date,
                from_edition=from_edition,
                to_edition=to_edition,
                from_questionable=from_questionable,
                to_questionable=to_questionable,
                dry_run=dry_run,
                verbose=verbose
            )
            if verbose:
                log_action(f'[VERBOSE] writing METS file to "{dst_mets_path}".', dry_run)
            write_text_file(dst_mets_path, data, dry_run, stats)
            if verbose:
                log_action(f'[VERBOSE] deleting "{src_mets_path}".', dry_run)
            delete_file(src_mets_path, dry_run, stats)
        else:
            if verbose:
                log_action(f'[VERBOSE] building new METS file.', dry_run)
            data = build_updated_mets_xml(
                src_path=src_mets_path,
                from_questionable=from_questionable,
                to_questionable=to_questionable,
                dry_run=dry_run,
                verbose=verbose
            )
            if verbose:
                log_action(f'[VERBOSE] overwriting METS file "{src_mets_path}".', dry_run)
            write_text_file(src_mets_path, data, dry_run, stats, overwrite=True)

    # Delete old METS _1.xml file
    if verbose:
        log_action(f'[VERBOSE] deleting METS_1 file "{src_mets_path_1}".', dry_run)
    delete_file(src_mets_path_1, dry_run, stats)

    # Issue PDF file
    if is_date_change:
        if verbose:
            log_action(f'[VERBOSE] if issue PDF exists, renaming it to "{dst_issue_pdf_path}".', dry_run)
        rename_path(src_issue_pdf_path, dst_issue_pdf_path, dry_run, stats)
        
    # Update dates in .pdf and .jp2 files
    if is_date_change:
        if verbose:
            log_action(f'[VERBOSE] updating *.pdf and *.jp2 files.', dry_run)
        files = list(issue_path.rglob("*.pdf")) + list(issue_path.rglob("*.jp2"))
        old_bytes = from_date.encode("ascii")
        new_bytes = to_date.encode("ascii")

        for file in files:
            if verbose:
                log_action(f'[VERBOSE] replacing "{from_date}" with "{to_date}" in file {file}.', dry_run)
            replace_bytes_file(file, old_bytes, new_bytes, dry_run, stats, verbose)

        # Rename issue folder
        if verbose:
            log_action(f'[VERBOSE] renaming issue directory "{issue_path}" to "{new_issue_path}".', dry_run)
        rename_path(issue_path, new_issue_path, dry_run, stats)

    # BATCH.xml file
    if is_date_change:
        if batch_xml_path.exists():
            if verbose:
                log_action(f'[VERBOSE] building new BATCH.xml file "{batch_xml_path}".', dry_run)
            data = build_updated_batch_xml(
                batch_xml_path,
                from_date,
                to_date,
                from_date_path,
                to_date_path,
                from_edition,
                to_edition,
                dry_run,
                verbose
            )
            if verbose:
                log_action(f'[VERBOSE] overwriting BATCH.xml file to "{batch_xml_path}".', dry_run)
            write_text_file(batch_xml_path, data, dry_run, stats, overwrite=True)

        # Delete BATCH_1.xml
        if verbose:
            log_action(f'[VERBOSE] deleting BATCH_1.xml file "{batch_xml_1_path}".', dry_run)
        delete_file(batch_xml_1_path, dry_run, stats)

    log_action(
        "summary: "
        f"written={stats['written']}, "
        f"deleted={stats['deleted']}, "
        f"renamed={stats['renamed']}, "
        f"updated={stats['updated']}",
        dry_run,
    )


if __name__ == "__main__":
    main()
