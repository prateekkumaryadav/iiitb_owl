# importing the required modules

# argparse for parsing the arguments passed through command line
import argparse

# sys for system-specific parameters and functions
import sys

# scraper for scraping the text data from the URL
from scraper import scrape_text_from_url

# master_schema for defining the schema of the ontology
from master_schema import OntologyData, Triple

# extractor for extracting the triples from the text data
from extractor import extract_triples

# owl_generator for generating the OWL file
from owl_generator import generate_owl

def main():
    # parsing the arguments passed through command line based on the requirements
    parser = argparse.ArgumentParser(description="Run the automated Ontology Generation Pipeline")
    
    # for the target url to crawl for the ontology generation
    parser.add_argument("--url", type=str, default="https://www.iiitb.ac.in/faculty", help="Target URL to crawl")
    
    # for the output file name used in the owl_generator module
    parser.add_argument("--output", type=str, default="iiitb_ontology.owl", help="Output OWL file name")
    
    # for the focus of the LLM
    parser.add_argument("--focus", type=str, choices=["faculty", "courses", "all"], default="all", help="Force the LLM to focus on extracting only 'faculty' or 'courses' to prevent mixed outputs")
    
    # for the depth of the LLM
    parser.add_argument("--depth", type=int, default=0, help="0 for single page, 1 to extract and visit sub-links")
    
    # for the max pages to crawl within the depth
    parser.add_argument("--max-pages", type=int, default=5, help="Maximum number of pages to crawl to protect API limits")

    args = parser.parse_args()
    
    
    # STEP 1: Printing the arguments passed through command line based on the requirements
    print(f"""Starting Crawler Execution \n 
              Seed URL: {args.url} \n 
              Extraction Focus: {args.focus.upper()} \n 
              Depth: {args.depth} | Max Pages: {args.max_pages}""", end="\n")
    
    # Evaluate Target URLs
    target_urls = [args.url]
    if args.depth > 0:
        from scraper import get_internal_links

        # Crawling the seed url for academic internal links matching focus(eg. faculty, courses, etc.)
        print(f"\nCrawling {args.url} for academic internal links matching focus={args.focus}...")

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
        
    # Limiting the number of pages to crawl within the depth because to cater API limits
    if len(target_urls) > args.max_pages:
        print(f"Found {len(target_urls)} links, truncating to --max-pages={args.max_pages}")
        target_urls = target_urls[:args.max_pages]
    
    global_triples = []
    
    # Process each URL
    for index, current_url in enumerate(target_urls):

        # Printing the current URL being processed
        print(f"\nProcessing Page {index+1}/{len(target_urls)}: {current_url}")
        
# = = = = = Going to the scraper.py file for scraping the text data from the URL = = = = =

        # Scraping text data from the current URL (step 1 of 2)
        print("Scraping text data")
        raw_text = scrape_text_from_url(current_url)
        
        # Checking if the text is extracted successfully
        if not raw_text:
            print("Failed to extract text. Skipping.")
            continue
            
        # Printing the number of characters extracted
        print(f"Extracted {len(raw_text)} characters.")
        
        # Sending text to Groq LLM (Focus: {args.focus.upper()}) for triple extraction (step 2 of 2)
        print(f"Sending text to Groq LLM (Focus: {args.focus.upper()}) for triple extraction...")
        
# = = = = = Going to the extractor.py file for extracting the triples from the text data = = = = =

        # Since extract_triples has chunking, it's safe to just call it
        page_ontology_data = extract_triples(raw_text, focus=args.focus)
        
        # Checking if the triples are extracted successfully
        if page_ontology_data and len(page_ontology_data.triples) > 0:
            # Printing the number of triples extracted
            print(f"Extracted {len(page_ontology_data.triples)} triples from this page.")
            global_triples.extend(page_ontology_data.triples)
        else:
            print("No triples found on this page.")
            
    # PROGRAMMATIC INFERENCE: Automatically inject missing isMemberOf relations
    # This is done to ensure that all faculty members are mapped to the university
    if args.focus == "faculty":
        print("\n[Post-Processing] Applying Semantic Inference Rules...")
        subjects_with_member = set(t.subject for t in global_triples if t.predicate == "isMemberOf")
        unique_subjects = set(t.subject for t in global_triples)
        
        inferred_count = 0
        for subj in unique_subjects:
            if subj not in subjects_with_member:
                # The LLM forgot to assign them to the university! Inject it manually.

# = = = = = Going to the master_schema.py file for defining the schema of the ontology = = = = =
                
                # Triple() is used to create a new triple
                global_triples.append(Triple(subject=subj, predicate="isMemberOf", object="IIIT Bangalore"))
                inferred_count += 1
        print(f" -> Inferred {inferred_count} missing 'isMemberOf -> IIIT Bangalore' relationships.")
            
    # Printing the total number of triples accumulated
    print(f"CRAWL COMPLETE. with Total Triples Accumulated: {len(global_triples)}")
    
    # Checking if the triples are extracted successfully
    if len(global_triples) == 0:
        print("Pipeline failed to extract any triples across all pages.")
        sys.exit(1)
        
    # Preview of combined Knowledge Graph for verification
    print("\nPreview of combined Knowledge Graph:")
    # printing the first 10 triples for verification
    for i, triple in enumerate(global_triples[:10]):
        print(f"   {i+1}. {triple.subject} -> {triple.predicate} -> {triple.object}")

    # if len(global_triples) > 10:
    #     print("   ... (truncated)")
        
    # Generating OWL representation
    print(f"\nGenerating OWL representation: {args.output}...")

# = = = = = Going to the master_schema.py file for defining the schema of the ontology = = = = =

    # OntologyData() is used to create a new ontology
    output_ontology = OntologyData(triples=global_triples)

# = = = = = Going to the owl_generator.py file for generating the OWL file = = = = =

    generate_owl(output_ontology, args.output)
    
    print("\nPipeline Complete\n")

if __name__ == "__main__":
    main()
