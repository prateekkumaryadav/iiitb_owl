import argparse
import sys
from scraper import scrape_text_from_url
from extractor import extract_triples
from owl_generator import generate_owl

def main():
    parser = argparse.ArgumentParser(description="Run the automated Ontology Generation Pipeline")
    parser.add_argument("--url", type=str, default="https://www.iiitb.ac.in/faculty", help="Target URL to crawl")
    parser.add_argument("--output", type=str, default="iiitb_ontology.owl", help="Output OWL file name")
    parser.add_argument("--focus", type=str, choices=["faculty", "courses", "all"], default="all", help="Force the LLM to focus on extracting only 'faculty' or 'courses' to prevent mixed outputs")
    parser.add_argument("--depth", type=int, default=0, help="0 for single page, 1 to extract and visit sub-links")
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum number of pages to crawl to protect API limits")

    
    args = parser.parse_args()
    
    print("========================================")
    print(f"Starting Crawler Execution")
    print(f"Seed URL: {args.url}")
    print(f"Extraction Focus: {args.focus.upper()}")
    print(f"Depth: {args.depth} | Max Pages: {args.max_pages}")
    print("========================================")
    
    # Evaluate Target URLs
    target_urls = [args.url]
    if args.depth > 0:
        from scraper import get_internal_links
        print(f"\n[0] Crawling {args.url} for academic internal links matching focus={args.focus}...")
        found_links = get_internal_links(args.url, focus=args.focus)
        target_urls.extend(found_links)
        # Deduplicate and keep original url first
        seen = set()
        deduped = []
        for u in target_urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        target_urls = deduped
        
    if len(target_urls) > args.max_pages:
        print(f"Found {len(target_urls)} links, truncating to --max-pages={args.max_pages}")
        target_urls = target_urls[:args.max_pages]
    
    from master_schema import OntologyData, PredicateEnum, Triple
    global_triples = []
    
    # Process each URL
    for index, current_url in enumerate(target_urls):
        print(f"\n=== Processing Page {index+1}/{len(target_urls)}: {current_url} ===")
        
        print("  -> [1/2] Scraping text data...")
        raw_text = scrape_text_from_url(current_url)
        if not raw_text:
            print("  -> Failed to extract text. Skipping.")
            continue
            
        print(f"  -> Extracted {len(raw_text)} characters.")
        
        print(f"  -> [2/2] Sending text to Groq LLM (Focus: {args.focus.upper()}) for triple extraction...")
        # Since extract_triples has chunking, it's safe to just call it
        page_ontology_data = extract_triples(raw_text, focus=args.focus)
        
        if page_ontology_data and len(page_ontology_data.triples) > 0:
            print(f"  -> Extracted {len(page_ontology_data.triples)} triples from this page.")
            global_triples.extend(page_ontology_data.triples)
        else:
            print("  -> No triples found on this page.")
            
    # PROGRAMMATIC INFERENCE: Automatically inject missing isMemberOf relations
    if args.focus == "faculty":
        print("\n[Post-Processing] Applying Semantic Inference Rules...")
        subjects_with_member = set(t.subject for t in global_triples if t.predicate == PredicateEnum.isMemberOf)
        unique_subjects = set(t.subject for t in global_triples)
        
        inferred_count = 0
        for subj in unique_subjects:
            if subj not in subjects_with_member:
                # The LLM forgot to assign them to the university! Inject it manually.
                global_triples.append(Triple(subject=subj, predicate=PredicateEnum.isMemberOf, object="IIIT Bangalore"))
                inferred_count += 1
        print(f"  -> Inferred {inferred_count} missing 'isMemberOf -> IIIT Bangalore' relationships.")
            
    print("\n========================================")
    print(f"CRAWL COMPLETE. Total Triples Accumulated: {len(global_triples)}")
    
    if len(global_triples) == 0:
        print("Pipeline failed to extract any triples across all pages.")
        sys.exit(1)
        
    print("\nPreview of combined Knowledge Graph:")
    for i, triple in enumerate(global_triples[:10]):
        print(f"   {i+1}. {triple.subject} -> {triple.predicate} -> {triple.object}")
    if len(global_triples) > 10:
        print("   ... (truncated)")
        
    # Genrate OWL
    print(f"\nGenerating Master OWL representation: {args.output}...")
    master_ontology = OntologyData(triples=global_triples)
    generate_owl(master_ontology, args.output)
    
    print("\nPipeline Complete!")
    print(f"Check '{args.output}' and load it in Protege to verify.")
    print("========================================")

if __name__ == "__main__":
    main()
