#!/usr/bin/env python3
"""
Usage:
  python3 to_cookie_header.py cookies.json
  cat cookies.json | python3 to_cookie_header.py
"""
import sys
import json

def read_stdin():
    return sys.stdin.read()

def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()
    else:
        data = read_stdin()

    if not data.strip():
        print('No input JSON provided.', file=sys.stderr)
        sys.exit(2)

    try:
        obj = json.loads(data)
    except Exception as e:
        print('Invalid JSON:', e, file=sys.stderr)
        sys.exit(3)

    parts = []
    for k, v in obj.items():
        s = str(v)
        if ';' in s:
            print(f'Warning: value for key "{k}" contains semicolon. This may break Cookie header.', file=sys.stderr)
        parts.append(f'{k}={s}')

    cookie_header = 'Cookie: ' + '; '.join(parts)
    print(cookie_header)

if __name__ == '__main__':
    main()
