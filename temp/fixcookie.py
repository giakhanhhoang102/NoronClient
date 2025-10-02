#!/usr/bin/env python3
# extract_username.py
# Usage:
#   python extract_username.py input.txt output.txt
#   python extract_username.py input.txt output.txt --skip-missing

import sys
import argparse

def process(input_path, output_path, skip_missing=False, encoding="utf-8"):
    with open(input_path, "r", encoding=encoding, errors="replace") as fin, \
         open(output_path, "w", encoding=encoding) as fout:
        for lineno, raw in enumerate(fin, start=1):
            line = raw.rstrip("\n")
            if not line:
                # nếu muốn giữ dòng rỗng đầu vào -> ghi {{{}}} ; hiện tại ta bỏ qua
                continue

            parts = line.split("|")
            try:
                username = parts[3].strip()  # **luôn** lấy vị trí index 3
            except IndexError:
                if skip_missing:
                    # bỏ qua dòng không có trường thứ 4
                    continue
                else:
                    username = ""  # vẫn ghi nhưng là rỗng

            fout.write(f"{{{{{username}}}}}\n")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extract username from column index 3 and write as {{{username}}}")
    p.add_argument("input", help="input file (pipe-separated)")
    p.add_argument("output", help="output file")
    p.add_argument("--skip-missing", action="store_true",
                   help="skip lines that do not have a 4th field (index 3)")
    p.add_argument("--encoding", default="utf-8", help="file encoding (default utf-8)")
    args = p.parse_args()

    process(args.input, args.output, skip_missing=args.skip_missing, encoding=args.encoding)
    print(f"Done. Output -> {args.output}")
