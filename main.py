# main.py
# Entry point for the IIIT-B Faculty Ontology Pipeline.

# Usage examples:
#   # Single faculty page (default mode)
#   python main.py --url https://www.iiitb.ac.in/faculty/debabrata-das

#   # Specify output file
#   python main.py --url https://www.iiitb.ac.in/faculty/debabrata-das \
#                  --output debabrata_das.owl

#   # Depth crawl (discover and process multiple faculty pages)
#   python main.py --url https://www.iiitb.ac.in/faculty \
#                  --depth 1 --max-pages 3

# importing modules

# argparse for command line arguments
import argparse

# sys for system-specific parameters and functions
import sys

# re for regular expressions
import re

# importing functions from other modules

# scraper.py for scraping faculty pages
from scraper import scrape_faculty_page, get_internal_links

# master_schema.py for ontology data
from master_schema import OntologyData

# extractor.py for extracting triples
from extractor import extract_triples

# owl_generator.py for generating OWL
from owl_generator import generate_owl

# Helper function to extract entity name from URL
def _entity_name_from_url(url: str) -> str:
    """
    Best-effort: extract a human-readable name from a profile URL.
    e.g.  ".../faculty/debabrata-das"  →  "Debabrata Das"
    """
    # Get the last part of the URL
    slug = url.rstrip("/").split("/")[-1]

    # Replace hyphens with spaces and title-case
    name = re.sub(r"[^a-zA-Z\s]", "", slug.replace("-", " ")).strip().title()
    return name

# Main
def main():
    # Create argument parser
    parser = argparse.ArgumentParser(
        description="IIIT-B Faculty Ontology Pipeline — scrape → extract triples → OWL"
    )
    # Add arguments
    parser.add_argument(
        "--url",
        type=str,
        default="https://www.iiitb.ac.in/faculty/debabrata-das",
        help="Profile URL to process.",
    )
    # Add focus argument
    parser.add_argument(
        "--focus",
        type=str,
        choices=["faculty", "department", "courses", "all"],
        default="faculty",
        help="Type of entity being scraped (e.g. faculty, department).",
    )
    # Add output argument
    parser.add_argument(
        "--output",
        type=str,
        default="ontology.owl",
        help="Output OWL file name (default: ontology.owl).",
    )
    # Add depth argument
    parser.add_argument(
        "--depth",
        type=int,
        default=0,
        help="0 = single page only; 1 = also follow sub-links found on the page.",
    )
    # Add max pages argument
    parser.add_argument(
        "--max-pages",
        type=int,
        default=5,
        help="Max pages to crawl when --depth 1 (protects API quota).",
    )
    # Parse arguments
    args = parser.parse_args()

    # Print header
    # print("\n" + "=" * 60)
    print("IIIT-B Faculty Ontology Pipeline")
    # print("=" * 60)
    print(f"Seed URL   : {args.url}")
    print(f"Output     : {args.output}")
    print(f"Depth      : {args.depth}  |  Max pages: {args.max_pages}  |  Focus: {args.focus}")
    # print("=" * 60 + "\n")

    # Build list of URLs to process
    # If depth is 0, process only the seed URL
    target_urls = [args.url]
    
    # If depth is greater than 0, discover and add links
    if args.depth > 0:
        print(f"Discovering {args.focus} links on {args.url}")

        # Get internal links
        found = get_internal_links(args.url, focus=args.focus)

        # Add found links to target URLs
        target_urls.extend(found)
        
        # Deduplicate
        seen, deduped = set(), []
        for u in target_urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        target_urls = deduped

    # Truncate if more than max pages
    if len(target_urls) > args.max_pages:
        print(f"Found {len(target_urls)} URLs — truncating to {args.max_pages}.")
        target_urls = target_urls[: args.max_pages]

    # Process each URL
    global_triples = []

    # Loop through each URL
    for idx, current_url in enumerate(target_urls):
        print(f"\n[Page {idx+1}/{len(target_urls)}] {current_url}")
        # print("-" * 56)

        # Step 1: Scrape
        print("[Step 1/3] Scraping page")
        raw_text = scrape_faculty_page(current_url)
        if not raw_text:
            print("  ✗ Could not extract text. Skipping.")
            continue
        print(f"  ✓ {len(raw_text)} characters extracted.")

        # Step 2: Extract triples
        entity_name = _entity_name_from_url(current_url)

        print(f"[Step 2/3] Sending to LLM ({args.focus} hint: '{entity_name}')")
        page_data = extract_triples(raw_text, entity_name=entity_name, entity_type=args.focus)

        # Add triples to global list
        if page_data and page_data.triples:
            print(f"{len(page_data.triples)} triple(s) extracted.")
            global_triples.extend(page_data.triples)
        else:
            print("No triples found on this page.")

    # Sanity check
    if not global_triples:
        print("\nPipeline failed — no triples extracted across all pages.")
        sys.exit(1)

    # Total triples
    print(f"\nTotal triples accumulated: {len(global_triples)}")

    # Preview
    # print("\nFirst 15 triples:")
    # for i, t in enumerate(global_triples[:15], 1):
    #     prop_tag = "OP" if t.predicate_type == "ObjectProperty" else "DP"
    #     print(f"  {i:>2}. [{prop_tag}] ({t.subject_class}) "
    #           f"{t.subject}  --[{t.predicate}]-->  "
    #           f"{t.object}"
    #           + (f"  ({t.object_class})" if t.object_class else ""))

    # Generate OWL
    print(f"\n[Step 3/3] Generating OWL: {args.output}")

    # Create ontology
    output_ontology = OntologyData(triples=global_triples)

    # Generate OWL
    generate_owl(output_ontology, args.output, entity_type=args.focus)

    print("\nPipeline complete!\n")

if __name__ == "__main__":
    main()
