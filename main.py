#!/usr/bin/env python3

import argparse
from sys import stderr, stdin
import os

from bs4 import BeautifulSoup, Comment
from bs4.element import Tag, NavigableString



def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-i", "--input",
        default=None,
        help="Input HTML file path. If omitted and stdin is piped, read from stdin."
    )

    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file path. If omitted, prints to stdout. If the file exists, aborts."
    )

    parser.add_argument(
        "--parser",
        default="html.parser",
        choices=["html.parser", "lxml", "html5lib", "xml", "lxml-xml"],
        help="BeautifulSoup parser to use."
    )

    parser.add_argument(
        "-r", "--remove-tag",
        action="append",
        default=["style", "span", "meta", "script"],
        help="Tag name to decompose (may be specified multiple times), e.g. -r script -r style."
    )
    parser.add_argument(
        "-ka", "--keep-attr",
        action="append",
        default=["href", "src", "alt"],
        help="Attribute name to keep (may be specified multiple times). Default keeps: href, src, alt."
    )

    parser.add_argument(
        "--remove-comments",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Remove HTML comments (default: enabled)."
    )
    parser.add_argument(
        "--same-name-only",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Only unwrap when parent and only-child have same tag name (default: enabled)."
    )
    parser.add_argument(
        "--minimize-nesting",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Unwrap redundant single-child wrappers (default: enabled)."
    )
    parser.add_argument(
        "--remove-empty",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Remove empty tags after cleanup (default: enabled)."
    )
    parser.add_argument(
        "--prettify",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Prettify output (default: enabled)."
    )

    args = parser.parse_args()

    stdin_piped = not stdin.isatty()

    # Disallow having both a file input and piped stdin
    if args.input and stdin_piped:
        print("error: both --input and stdin were provided; choose one", file=stderr)
        raise SystemExit(2)

    # Require one source
    if not args.input and not stdin_piped:
        parser.error("Provide --input FILE or pipe html into stdin (e.g. cat file | script).")

    # Validate file input if used
    if args.input:
        if not os.path.isfile(args.input):
            raise FileNotFoundError(f"file not found: {args.input}")

    # Validate output
    if args.output is not None:
        if os.path.isdir(args.output):
            raise IsADirectoryError(f"output is a directory: {args.output}")
        if os.path.exists(args.output):
            print(f"error: output file exists: {args.output}", file=stderr)
            raise SystemExit(1)

    print(f"input: {args.input or '<stdin>'}", file=stderr)
    print(f"output: {args.output or '-'}", file=stderr)

    return args


def _significant_children(tag: Tag):
    out = []
    for c in tag.contents:
        if isinstance(c, NavigableString) and not c.strip():
            continue
        out.append(c)
    return out


def minimize_nesting(soup: BeautifulSoup, *, same_name_only=True):
    changed = True
    while changed:
        changed = False

        for tag in list(soup.find_all(True)):
            kids = _significant_children(tag)
            if len(kids) != 1 or not isinstance(kids[0], Tag):
                continue

            child = kids[0]

            # keep wrappers that have meaning (attributes)
            if tag.attrs:
                continue

            if same_name_only and child.name != tag.name:
                continue

            tag.unwrap()
            changed = True
            break

    return soup


def remove_empty_tags(soup: BeautifulSoup):
    changed = True
    while changed:
        changed = False
        for tag in list(soup.find_all(True)):
            if not _significant_children(tag):
                tag.decompose()
                changed = True
                break
    return soup


def clean_html(html_content: str, args):
    soup = BeautifulSoup(html_content, args.parser)

    # Remove tags
    for name in args.remove_tag:
        for t in soup.find_all(name):
            t.decompose()

    # Remove comments
    if args.remove_comments:
        for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()

    # Strip attributes (keep only selected)
    keep = set(args.keep_attr or [])
    for tag in soup.find_all(True):
        tag.attrs = {k: v for k, v in tag.attrs.items() if k in keep}

    if args.minimize_nesting:
        minimize_nesting(soup, same_name_only=args.same_name_only)

    if args.remove_empty:
        remove_empty_tags(soup)

    return soup.prettify() if args.prettify else str(soup)



def read_input(args) -> str:
    if args.input:
        with open(args.input, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return stdin.read()

def main():
    args = parse_args()
    html = read_input(args)
    out_text = clean_html(html, args)

    if args.output is None:
        print(out_text)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_text)


if __name__ == "__main__":
    main()
