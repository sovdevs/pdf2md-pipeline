"""pdf2extract — Phase 1 only: PDF → ExtractedDocument + StructuredRecord JSON artifacts.

Usage:
    pdf2extract --input input/ --intermediate intermediate/
    pdf2extract --input report.pdf --intermediate intermediate/ --force
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from pdf_to_markdown.structured.batch_runner import _process_one

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract structured data from PDFs into JSON artifacts."
    )
    parser.add_argument("--input", type=Path, required=True,
                        help="A PDF file or folder of PDFs.")
    parser.add_argument("--intermediate", type=Path, default=Path("intermediate"),
                        help="Where to write JSON artifacts (default: intermediate/).")
    parser.add_argument("--force", action="store_true",
                        help="Re-extract even if artifacts already exist.")
    args = parser.parse_args()

    if args.input.is_file():
        pdf_paths = [args.input]
    elif args.input.is_dir():
        pdf_paths = sorted(args.input.glob("*.pdf"))
    else:
        print(f"Input not found: {args.input}")
        sys.exit(1)

    if not pdf_paths:
        print(f"No PDFs found in '{args.input}'.")
        sys.exit(1)

    print(f"Extracting {len(pdf_paths)} PDF(s)…\n")
    ok, failed = 0, []

    for pdf in pdf_paths:
        result = _process_one(pdf, args.intermediate, force=args.force)
        if result.status == "success":
            ok += 1
        else:
            failed.append(result)

    print(f"\n{'─'*50}")
    print(f"Done. {ok} succeeded, {len(failed)} failed.")
    if failed:
        for r in failed:
            print(f"  FAIL {r.source_file}: {r.error_message}")
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
