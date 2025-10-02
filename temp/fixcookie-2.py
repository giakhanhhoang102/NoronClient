#!/usr/bin/env python3
# extract_between_filewide.py
# Usage examples:
#  python extract_between_filewide.py input.txt output.txt --start "cookie" --end "device_profile_ref_id"
#  python extract_between_filewide.py input.txt output.txt --start "<tag.*?>" --end "</tag>" --regex

import argparse
import re
from pathlib import Path
import sys

def remove_newlines(s, to_space=False):
    if to_space:
        s = s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        return re.sub(r"\s+", " ", s).strip()
    else:
        return s.replace("\r\n", "").replace("\n", "").replace("\r", "")

def find_all_between_whole_text(text, start, end, use_regex=False):
    # returns list of extracted strings (may be empty)
    if use_regex:
        try:
            pattern = re.compile(f"({start})(.*?)({end})", re.DOTALL)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")
    else:
        # escape literals for regex and use non-greedy capture
        s = re.escape(start)
        e = re.escape(end)
        pattern = re.compile(f"({s})(.*?)({e})", re.DOTALL)
    matches = [m.group(2) for m in pattern.finditer(text)]
    return matches

def main(inp_path, out_path, start, end, use_regex=False, encoding="utf-8", newline_to_space=False, write_if_none=False):
    inp = Path(inp_path)
    if not inp.exists():
        print("ERR: input file not found:", inp_path)
        sys.exit(1)
    text = inp.read_text(encoding=encoding, errors="replace")
    matches = find_all_between_whole_text(text, start, end, use_regex=use_regex)

    out = Path(out_path)
    with out.open("w", encoding=encoding) as fout:
        if not matches and write_if_none:
            # keep previous behavior: write one empty {{{}}} if nothing found
            fout.write("{{{}}}\n")
        else:
            for m in matches:
                clean = remove_newlines(m, to_space=newline_to_space)
                fout.write(f"{{{{{clean}}}}}\n")

    print(f"Done. Found {len(matches)} match(es). Output -> {out_path}")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extract all substrings between start and end across entire file and output as {{{value}}}")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    p.add_argument("--regex", action="store_true", help="treat start/end as regex")
    p.add_argument("--encoding", default="utf-8")
    p.add_argument("--newline-to-space", action="store_true", help="replace newlines inside match with a single space")
    p.add_argument("--write-if-none", action="store_true", help="if no matches found, write one empty {{{}}} to output")
    args = p.parse_args()
    try:
        main(args.input, args.output, args.start, args.end, use_regex=args.regex,
             encoding=args.encoding, newline_to_space=args.newline_to_space, write_if_none=args.write_if_none)
    except ValueError as e:
        print("ERROR:", e)
        sys.exit(2)
