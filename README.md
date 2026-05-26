# change-date

`change-date` is a command-line Python script for updating the date and edition for an issue inside an NDNP batch. It validates input paths and dates, renames issue-level files, updates XML content, updates embedded date metadata in `.pdf` and `.jp2` files, renames the issue directory, and removes stale `_1.xml` files. The `_1.xml` files are deleted so that the batch can be revalidated using "Validate All Unvalidated, and Update" in the DVV.

## Requirements

- Python 3.9 or newer is recommended.
- The script uses only the Python standard library: `argparse`, `re`, `pathlib`, and `datetime`.

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
| `-i`, `--issue-path` | Yes | Absolute or relative path to the issue directory to update. |
| `-d`, `--from-date` | Yes | Existing issue date in `YYYY-MM-DD` format. |
| `-e`, `--from-edition` | Yes | Existing edition number as an integer greater than or equal to 1. |
| `-D`, `--to-date` | Yes | New issue date in `YYYY-MM-DD` format. |
| `-E`, `--to-edition` | Yes | New edition number as an integer greater than or equal to 1. |
| `-n`, `--dry-run` | No | Show planned changes without modifying files. |

## Example

```bash
python3 change-date.py \
  -b /mnt/ingest/batches/batch_curiv_delilahbeasley \
  -i /mnt/ingest/batches/batch_curiv_delilahbeasley/sn88086183/00516992189/1901010101 \
  -d 1901-01-01 \
  -e 1 \
  -D 1901-01-08 \
  -E 2
```

This updates issue `1901010101` to `1901010802`, renames matching issue-level files, updates XML references, and removes stale `_1.xml` files.

## What it does

Given a batch directory, an issue directory, a source date and edition, and a target date and edition, the script performs these operations:

- Validates that the batch and issue paths exist and are directories.
- Validates input dates in `YYYY-MM-DD` format.
- Builds source and destination filenames using date strings in both `YYYY-MM-DD` and `YYYYMMDD` formats.
- Copies the issue METS XML to its new filename while replacing the old issue date with the new one.
- Deletes the old METS XML and the old `_1.xml` companion file if they exist.
- Renames the issue PDF to match the new date and edition if the file exists.
- Walks the issue directory recursively and replaces embedded date strings in `.pdf` and `.jp2` files.
- Renames the issue directory to match the new date and edition.
- Updates `BATCH.xml` by replacing the issue date and path date values, then deletes `BATCH_1.xml` if present.

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

- `<issue_path>/<from_date_path><from_edition>.xml`
- `<issue_path>/<from_date_path><from_edition>_1.xml`
- `<issue_path>/<from_date_path><from_edition>.pdf`
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
- Add structured logging or a `--verbose` flag for better output.
- Others?
