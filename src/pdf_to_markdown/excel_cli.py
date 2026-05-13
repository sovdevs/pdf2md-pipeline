"""pdf2excel — full pipeline: PDF(s) → JSON artifacts → CSV + XLSX.

Usage:
    pdf2excel --input input/ --output output/
    pdf2excel --input input/ --output output/ --workers 4 --template templates/my.xlsx
    pdf2excel --files a.pdf b.pdf --output output/
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from pdf_to_markdown.structured.batch_runner import run_batch
from pdf_to_markdown.structured.csv_writer import write_csv_outputs

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert PDFs to structured CSV and XLSX."
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input", type=Path,
                             help="A PDF file or folder of PDFs.")
    input_group.add_argument("--files", nargs="+", type=Path,
                             help="Explicit list of PDF paths.")

    parser.add_argument("--output", type=Path, default=Path("output"),
                        help="Output folder (default: output/).")
    parser.add_argument("--intermediate", type=Path, default=Path("intermediate"),
                        help="Folder for intermediate JSON artifacts (default: intermediate/).")
    parser.add_argument("--template", type=Path, default=None,
                        help="Optional Excel template for batch output.")
    parser.add_argument("--workers", type=int, default=2,
                        help="Parallel workers for Phase 1 extraction (default: 2).")
    parser.add_argument("--force", action="store_true",
                        help="Re-extract even if intermediate artifacts exist.")
    parser.add_argument("--csv", action="store_true", default=True,
                        help="Also write per-document CSV files (default: on).")

    # P2 — LLM extraction
    parser.add_argument("--schema", type=Path, default=None,
                        help="Path to extraction schema JSON (enables LLM extraction).")
    llm_group = parser.add_mutually_exclusive_group()
    llm_group.add_argument("--use-llm", dest="use_llm", action="store_true", default=True,
                           help="Use LLM extraction when --schema is provided (default).")
    llm_group.add_argument("--no-llm", dest="use_llm", action="store_false",
                           help="Disable LLM extraction even if --schema is provided.")
    parser.add_argument("--llm-concurrency", type=int, default=2,
                        help="Max concurrent LLM calls (default: 2).")
    args = parser.parse_args()

    # Collect PDF paths
    if args.files:
        pdf_paths = [p for p in args.files if p.suffix.lower() == ".pdf"]
    elif args.input.is_file():
        pdf_paths = [args.input]
    elif args.input.is_dir():
        pdf_paths = sorted(args.input.glob("*.pdf"))
    else:
        print(f"Input not found: {args.input}")
        sys.exit(1)

    if not pdf_paths:
        print("No PDF files found.")
        sys.exit(1)

    print(f"Found {len(pdf_paths)} PDF(s). Processing…\n")

    # Load schema and API key for P2 LLM extraction
    schema = None
    api_key = ""
    if args.schema and args.use_llm:
        from pdf_to_markdown.structured.schema import load_schema
        schema = load_schema(args.schema)
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        if not api_key:
            print("WARNING: --schema provided but no GOOGLE_API_KEY in environment. Falling back to P1.")
            schema = None

    report = run_batch(
        pdf_paths=pdf_paths,
        intermediate_dir=args.intermediate,
        output_dir=args.output,
        workers=args.workers,
        force=args.force,
        template_path=args.template,
        schema=schema,
        api_key=api_key,
        llm_concurrency=args.llm_concurrency,
    )

    # Write per-document CSV files
    if args.csv:
        from pdf_to_markdown.structured.batch_runner import _load_artifacts
        csv_root = args.output / "csv"
        for pdf in pdf_paths:
            stem = pdf.stem
            pair = _load_artifacts(args.intermediate, stem)
            if pair:
                doc, record = pair
                written = write_csv_outputs(doc, record, csv_root / stem, stem)
                logging.getLogger(__name__).info(
                    f"  CSV {pdf.name}: {len(written)} file(s)"
                )

    print(f"\n{'─'*50}")
    print(f"Done. {report['succeeded']}/{report['total']} succeeded.")
    if report["failed"]:
        print(f"  {report['failed']} failed — see output/failed_files.json")
    print(f"  → output/batch_results.xlsx")
    sys.exit(0 if report["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
