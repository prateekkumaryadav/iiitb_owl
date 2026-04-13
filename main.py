# main.py
# Entry point for the IIIT-B Faculty Ontology Pipeline.
#
# Usage examples:
#   # Single faculty page (default mode)
#   python main.py --url https://www.iiitb.ac.in/faculty/debabrata-das
#
#   # Specify output file
#   python main.py --url https://www.iiitb.ac.in/faculty/debabrata-das \
#                  --output debabrata_das.owl
#
#   # Depth crawl (discover and process multiple faculty pages)
#   python main.py --url https://www.iiitb.ac.in/faculty \
#                  --depth 1 --max-pages 3

import argparse
import sys
import re

from scraper import scrape_faculty_page, get_internal_links
from master_schema import OntologyData
from extractor import extract_triples
from owl_generator import generate_owl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _faculty_name_from_url(url: str) -> str:
    """
    Best-effort: extract a human-readable name from a faculty profile URL.
    e.g.  ".../faculty/debabrata-das"  →  "Debabrata Das"
    """
    slug = url.rstrip("/").split("/")[-1]
    # Replace hyphens with spaces and title-case
    name = re.sub(r"[^a-zA-Z\s]", "", slug.replace("-", " ")).strip().title()
    return name


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="IIIT-B Faculty Ontology Pipeline — scrape → extract triples → OWL"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="https://www.iiitb.ac.in/faculty/debabrata-das",
        help="Faculty profile URL to process (default: Debabrata Das).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="faculty_ontology.owl",
        help="Output OWL file name (default: faculty_ontology.owl).",
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=0,
        help="0 = single page only; 1 = also follow faculty sub-links found on the page.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Max pages to crawl when --depth 1 (protects API quota).",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  IIIT-B Faculty Ontology Pipeline")
    print("=" * 60)
    print(f"  Seed URL   : {args.url}")
    print(f"  Output     : {args.output}")
    print(f"  Depth      : {args.depth}  |  Max pages: {args.max_pages}")
    print("=" * 60 + "\n")

    # ── Build list of URLs to process ─────────────────────────────────────────
    target_urls = [args.url]
    if args.depth > 0:
        print(f"[Main] Discovering faculty links on {args.url} …")
        found = get_internal_links(args.url, focus="faculty")
        target_urls.extend(found)
        # Deduplicate
        seen, deduped = set(), []
        for u in target_urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        target_urls = deduped

    if len(target_urls) > args.max_pages:
        print(f"[Main] Found {len(target_urls)} URLs — truncating to {args.max_pages}.")
        target_urls = target_urls[: args.max_pages]

    # ── Process each URL ──────────────────────────────────────────────────────
    global_triples = []

    for idx, current_url in enumerate(target_urls):
        print(f"\n[Page {idx+1}/{len(target_urls)}] {current_url}")
        print("-" * 56)

        # -- Step 1: Scrape --------------------------------------------------
        print("[Step 1/3] Scraping page …")
        raw_text = scrape_faculty_page(current_url)
        if not raw_text:
            print("  ✗ Could not extract text. Skipping.")
            continue
        print(f"  ✓ {len(raw_text)} characters extracted.")

        # -- Step 2: Extract triples -----------------------------------------
        faculty_name = _faculty_name_from_url(current_url)
        print(f"[Step 2/3] Sending to LLM (faculty hint: '{faculty_name}') …")
        page_data = extract_triples(raw_text, faculty_name=faculty_name)

        if page_data and page_data.triples:
            print(f"  ✓ {len(page_data.triples)} triple(s) extracted.")
            global_triples.extend(page_data.triples)
        else:
            print("  ✗ No triples found on this page.")

    # ── Sanity check ──────────────────────────────────────────────────────────
    if not global_triples:
        print("\n[Main] Pipeline failed — no triples extracted across all pages.")
        sys.exit(1)

    print(f"\n[Main] Total triples accumulated: {len(global_triples)}")

    # ── Preview ──────────────────────────────────────────────────────────────
    print("\n[Preview] First 15 triples:")
    for i, t in enumerate(global_triples[:15], 1):
        prop_tag = "OP" if t.predicate_type == "ObjectProperty" else "DP"
        print(f"  {i:>2}. [{prop_tag}] ({t.subject_class}) "
              f"{t.subject}  --[{t.predicate}]-->  "
              f"{t.object}"
              + (f"  ({t.object_class})" if t.object_class else ""))

    # ── Generate OWL ─────────────────────────────────────────────────────────
    print(f"\n[Step 3/3] Generating OWL: {args.output} …")
    output_ontology = OntologyData(triples=global_triples)
    generate_owl(output_ontology, args.output)

    print("\n✅ Pipeline complete!\n")


if __name__ == "__main__":
    main()
