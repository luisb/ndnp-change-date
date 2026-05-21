#!/usr/bin/python

import argparse

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
        out_date = datetime.strptime(date, '%Y-%m-%d')
        return out_date
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
from_date = args.from_date
from_date_path = args.from_date.strftime("%Y%m%d")
from_edition = f"{args.from_edition:02d}"
to_date = args.to_date
to_edition = f"{args.to_edition:02d}"
