# change-date

`change-date` is a command-line Python script that updates the date and edition metadata for a single issue in an NDNP batch, renames related issue files, updates `BATCH.xml`, and optionally manages a questionable `mods:dateIssued` value in the issue METS XML. 

It validates input paths and dates, renames issue-level files, updates XML content, updates embedded date metadata in `.pdf` and `.jp2` files, renames the issue directory, and removes stale `_1.xml` files. The `_1.xml` files are deleted so that the batch can be revalidated using "Validate All Unvalidated, and Update" in the DVV.

## Requirements

- Python 3.9 or newer.
- The script uses only the Python standard library: `argparse`, `pathlib`, `datetime`, `re`, and `xml.etree.ElementTree`.

## Usage

```bash
python3 change-date.py \
  --batch-path /path/to/batch \
  --issue-path /path/to/batch/lccn/reel/issue \
  --from-date 1901-01-01 \
  --from-edition 1 \
  --to-date 1901-01-02 \
  --to-edition 2
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `-b`, `--batch-path` | Yes | Absolute or relative path to the NDNP batch directory. |
| `-i`, `--issue-path` | Yes | Absolute or relative path to the issue directory. Must be a directory whose name ends in `YYYYMMDDEE`. |
| `-d`, `--from-date` | Yes | Current issue date in `YYYY-MM-DD` format. |
| `-e`, `--from-edition` | Yes | Current edition number, integer `>= 1`. |
| `-D`, `--to-date` | Yes | New issue date in `YYYY-MM-DD` format. |
| `-E`, `--to-edition` | Yes | New edition number, integer `>= 1`. |
| `-q`, `--from-questionable` | No | Existing questionable date to delete or replace. |
| `-Q`, `--to-questionable` | No | New questionable date to add or replace with. |
| `-n`, `--dry-run` | No | Show planned changes without writing, deleting, or renaming files. |

## Examples

### Change date and edition only

```bash
python3 change-date \
  -b /data/batches/batch_001 \
  -i /data/batches/batch_001/issues/1900010101 \
  -d 1900-01-01 \
  -e 1 \
  -D 1900-01-08 \
  -E 2
```

### Change date and remove a questionable date

```bash
python3 change-date \
  -b /data/batches/batch_001 \
  -i /data/batches/batch_001/issues/1900010101 \
  -d 1900-01-01 \
  -e 1 \
  -D 1900-01-08 \
  -E 2 \
  -q 1900-01-03
```

### Change date and replace a questionable date

```bash
python3 change-date \
  -b /data/batches/batch_001 \
  -i /data/batches/batch_001/issues/1900010101 \
  -d 1900-01-01 \
  -e 1 \
  -D 1900-01-08 \
  -E 2 \
  -q 1900-01-03 \
  -Q 1900-01-04
```

### Change date and add a new questionable date

```bash
python3 change-date \
  -b /data/batches/batch_001 \
  -i /data/batches/batch_001/issues/1900010101 \
  -d 1900-01-01 \
  -e 1 \
  -D 1900-01-08 \
  -E 2 \
  -Q 1900-01-04
```


## What it does

Given a batch directory, an issue directory, a source date and edition, and a target date and edition, the script performs these operations:

- Validates that the batch and issue paths exist and are directories.
- Validates input dates in `YYYY-MM-DD` format.
- Change the issue date and edition in the METS XML and writes the METS XML to the new filename.
- Deletes the old METS XML and the old `_1.xml` companion file if they exist.
- Renames the issue PDF to match the new date and edition if the file exists.
- Walks the issue directory recursively and replaces embedded date strings in `.pdf` and `.jp2` files.
- Renames the issue directory to match the new date and edition.
- Updates `BATCH.xml` by replacing the `issueDate`, `editionOrder`, and path date values, then deletes `BATCH_1.xml` if present.
- Add, replace, or delete a questionable `mods:dateIssued` value in the METS XML.

## Dry run

A dry-run mode is useful for verifying planned file operations before making destructive changes. File writes, deletes, and renames are routed through helper functions that log actions instead of executing them.

## How filenames are derived

The script formats dates in two ways:

- `YYYY-MM-DD` for text replacement inside XML and other file contents.
- `YYYYMMDD` for issue filenames and directory names.

Editions are zero-padded to two digits, so edition `1` becomes `01` and edition `2` becomes `02`.

That means:

- `from-date 1901-01-01` becomes `19010101`
- `from-edition 1` becomes `01`
- The issue stem becomes `1901010101`

## Files affected

Depending on what exists in the issue directory and batch directory, the script may touch these files:

- `<issue_path>/<from_date><from_edition>.xml`
- `<issue_path>/<from_date><from_edition>_1.xml`
- `<issue_path>/<from_date><from_edition>.pdf`
- Any recursive `*.pdf` files under the issue directory
- Any recursive `*.jp2` files under the issue directory
- `<batch_path>/BATCH.xml`
- `<batch_path>/BATCH_1.xml`

The issue directory itself will also be renamed from a  `YYYYMMDDEE` pattern to the target date and edition value.

## Exit behavior

The script will terminate with an error if a required directory is missing, if a date is invalid, or if an edition is less than 1. Files that are optional are guarded with existence checks before delete or rename operations.

## Notes and cautions

- This script performs destructive actions such as deleting files, modifying binary files, and renaming paths, so `--dry-run` is strongly recommended before running it against production data.

## Future improvements

- Add ability to import CSV file of date changes.
- Add a `--verbose` flag for more detailed actions.
