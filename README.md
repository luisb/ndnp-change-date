# change-date

Update the date, edition, and questionable-date metadata for an issue in an NDNP batch.

## Requirements

- Python 3.9 or newer.
- The script uses only the Python standard library.

## Usage

```bash
python3 change-date.py \
  --batch-path /path/to/batch \
  --issue-path /path/to/batch/lccn/reel/issue \
  [options]
```

### Arguments

 Option | Meaning |
|---|---|
| `-b`, `--batch-path` | Path to the NDNP batch directory. |
| `-i`, `--issue-path` | Path to the issue directory. |
| `-d`, `--from-date` | Source issue date in `YYYY-MM-DD`. |
| `-e`, `--from-edition` | Source edition number, integer `>= 1`. |
| `-D`, `--to-date` | Destination issue date in `YYYY-MM-DD`. |
| `-E`, `--to-edition` | Destination edition number, integer `>= 1`. |
| `-q`, `--from-questionable` | Existing questionable date to delete or replace. |
| `-Q`, `--to-questionable` | New questionable date to add or replace with. |
| `-n`, `--dry-run` | Show actions without writing, deleting, renaming, or modifying files. |
| `-v`, `--verbose` | Display detailed runtime messages. |

## Modes

### 1. Full date/edition change

Use `-d`, `-e`, `-D`, and `-E` together. All four options are required for this mode.

This mode:

- Updates the root METS `LABEL` when it contains the old date.
- Updates `mods:dateIssued` values in the issue METS XML, but not questionable dates.
- Updates the edition number in `mods:detail[@type='edition']/mods:number`.
- Writes a new METS file named for the destination date/edition.
- Deletes the existing METS file.
- Deletes the existing `_1.xml` validation file if present.
- Renames the issue PDF if present.
- Replaces the old date with the new date in the metadata of `.pdf` and `.jp2` files in the same issue directory.
- Renames the issue directory to match the new `YYYYMMDDEE` format.
- Updates the matching `<issue>` line in `BATCH.xml`.
- Deletes `BATCH_1.xml` if present.

Example:

```bash
python3 change-date \
  -b /data/batches/batch_curiv_delilahbeasley \
  -i /data/batches/batch_curiv_delilahbeasley/sn88086183/00516992189/1948010201 \
  -d 1948-01-02 \
  -e 1 \
  -D 1947-01-02 \
  -E 2
```

### 2. Delete a questionable date

Use `-q` by itself.

This mode finds the issue METS file in the issue directory and removes the matching `mods:dateIssued` element whose `qualifier` is `questionable`.

Example:

```bash
python3 change-date.py \
  -b /data/batch_curiv_delilahbeasley \
  -i /data/batch_curiv_delilahbeasley/sn88086183/00516992189/1948010201 \
  -q 1947-01-02
```

### 3. Replace a questionable date

Use `-q` and `-Q` together.

This mode updates the matching questionable `mods:dateIssued` value in the issue METS file.

Example:

```bash
python3 change-date.py \
  -b /data/batch_curiv_delilahbeasley \
  -i /data/batch_curiv_delilahbeasley/sn88086183/00516992189/1948010201 \
  -q 1949-01-02 \
  -Q 1947-01-02
```

### 4. Add a questionable date

Use `-Q` by itself.

This mode adds a new `mods:dateIssued encoding="iso8601" qualifier="questionable"` element after the first non-questionable `mods:dateIssued` entry when possible. If no normal `dateIssued` exists, the new element is appended under `mods:originInfo`.

Example:

```bash
python3 change-date.py \
  -b /data/batch_curiv_delilahbeasley \
  -i /data/batch_curiv_delilahbeasley/sn88086183/00516992189/1948010201 \
  -Q 1947-01-02
```

## Validation rules

The script stops with an error in these cases:

- Only some of `-d`, `-e`, `-D`, `-E` are provided; full date/edition changes require all four values.
- None of the date/edition or questionable-date options are provided.
- `from-date/from-edition` and `to-date/to-edition` are identical.
- `from-questionable` and `to-questionable` are identical.
- The issue directory name does not end with `YYYYMMDDEE`.
- The source METS file required for the selected mode does not exist.
- A specified `from-questionable` value is not found as a questionable date in the METS file.
- `-Q` is used without `-q` when a questionable date already exists in the METS file.
- A destination METS file, destination PDF, or destination issue directory already exists during a full rename operation.

## Dry run

Use `-n` or `--dry-run` to preview changes.

Example:

```bash
python3 change-date \
  -b /data/batches/batch_curiv_delilahbeasley \
  -i /data/batches/batch_curiv_delilahbeasley/sn88086183/00516992189/1948010201 \
  -d 1948-01-02 \
  -e 1 \
  -D 1947-01-02 \
  -E 2 \
  -n
```

Dry-run output is prefixed with `[DRY-RUN]`; normal execution is prefixed with `[RUN]`.

## Notes

- XML output is serialized with `ElementTree.tostring()`, so formatting and whitespace may differ from the original source even when the XML content is unchanged semantically.
- This script performs destructive actions such as deleting files, modifying binary files, and renaming paths, so `--dry-run` is strongly recommended before running it against production data.

## Testing checklist

Before using this in production, test at least these cases against sample data:

- Full date/edition change.
- `-Q` only, add questionable date.
- `-q` + `-Q`, replace questionable date.
- `-q` only, delete questionable date.
- Dry-run output for each mode.
- Collision handling when destination files or directories already exist.

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

## Future improvements

- Add ability to import CSV file of date changes.
