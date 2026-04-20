import argparse
import glob
from rdflib import Graph

def main():
    parser = argparse.ArgumentParser(description="Merge multiple OWL files into a single master Knowledge Graph.")
    parser.add_argument("input_files", nargs='+', help="List of OWL files to merge (supports glob patterns like *.owl)")
    parser.add_argument("--output", "-o", default="merged_master.owl", help="Output file name")
    args = parser.parse_args()

    files_to_merge = []
    for pattern in args.input_files:
        files_to_merge.extend(glob.glob(pattern))
    
    files_to_merge = list(set(files_to_merge))
    
    if not files_to_merge:
        print("No OWL files found to merge.")
        return

    g = Graph()
    print(f"Loading {len(files_to_merge)} ontology files...")
    
    for f in files_to_merge:
        print(f"  - Parsing {f}")
        try:
            g.parse(f, format="xml")
        except Exception as e:
            print(f"    Error parsing {f}: {e}")

    print(f"\nMerging complete! Total triples in master graph: {len(g)}")
    print(f"Serialising to {args.output}...")
    g.serialize(destination=args.output, format="xml")
    print("Done. You can now load this file into Protégé to explore cross-entity relationships.")

if __name__ == "__main__":
    main()
