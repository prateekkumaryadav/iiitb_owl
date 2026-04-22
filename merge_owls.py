# This script is used to merge multiple OWL files into a single master Knowledge Graph.

# import the required libraries
# argparse is used to parse the command line arguments
import argparse

# glob is used to find all the files that match the given pattern
import glob

# urllib.parse is used to parse the URL
import urllib.parse

# rdflib is used to work with RDF graphs
from rdflib import Graph, OWL, RDF

# This function is used to clean the URI
def clean_name(uri):
    # if the uri contains "#" then split the uri by "#" and take the last part
    if "#" in uri:
        name = uri.split("#")[-1]
    else:
        name = uri.split("/")[-1]
    
    # decode the uri
    name = urllib.parse.unquote(name)
    
    # replace "_" with " "
    name = name.replace("_", " ")
    
    # replace "-" with " "
    name = name.replace("-", " ")

    # Collapse multiple spaces
    name = " ".join(name.split())
    return name.lower().strip()

# this function is used to get the specific types of the uri
def get_specific_types(g, uri):
    types = list(g.objects(uri, RDF.type))
    specific = [t for t in types if t != OWL.NamedIndividual]
    return set(specific)

# this function is used to resolve entities using LLM
def entity_resolution(g):
    # os is used to get the environment variables
    import os
    
    # json is used to work with JSON data
    import json
    
    # Groq is used to work with Groq API
    from groq import Groq

    # URIRef is used to work with URIs
    from rdflib import URIRef
    
    print("Starting LLM-based entity resolution for cross-graph mapping")
    
    # Check if GROQ_API_KEY is present
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("  - WARNING: GROQ_API_KEY not found in environment. Skipping entity resolution.")
        return g
        
    client = Groq(api_key=api_key)
    
    # 1. Gather individuals
    individuals = list(set(g.subjects(RDF.type, OWL.NamedIndividual)))
    # We map URI to cleaned name, but only send unique names to the LLM to save tokens
    indiv_dict = {str(uri): clean_name(str(uri)) for uri in individuals}
    # get the unique names
    unique_indiv_names = list(set(indiv_dict.values()))
    
    # 2. Gather properties
    properties = list(set(g.subjects(RDF.type, OWL.ObjectProperty))) + \
                 list(set(g.subjects(RDF.type, OWL.DatatypeProperty)))
    prop_dict = {str(uri): clean_name(str(uri)) for uri in properties}
    unique_prop_names = list(set(prop_dict.values()))
    
    if not unique_indiv_names and not unique_prop_names:
        return g
        
    # this prompt is used to align the entities
    prompt = f"""
You are a semantic web ontology aligner specializing in university knowledge graphs.
Your task: identify pairs of names that refer to the EXACT same real-world entity or relationship,
despite surface-level lexical differences.

also match the symbols with the words like "&" with "and"

All names below have already been lowercased and normalized. Treat them as case-insensitive.

Match pairs in these situations:
1. Abbreviations vs full forms — "dept of cs" = "department of computer science"
2. Abbreviations embedded in longer names — "cs & e" = "computer science and engineering"
3. Partial names vs full names — "meenakshi" = "meenakshi dsouza" (if clearly the same person)
4. Acronyms — "iiit-b" = "iiit bangalore"
5. Minor spelling / punctuation variants — "dept. of cse" = "department of cse"
6. Ampersand variants — "computer science & engineering" = "computer science and engineering"

DO NOT match:
- Strings that are already identical (no need to report ["meenakshi", "meenakshi"])
- Similar but distinct entities (e.g. "department of cs" ≠ "department of mathematics")
- Properties that sound related but are semantically different (e.g. "hasDuration" ≠ "hasEducation")
- Overly broad matches — when in doubt, leave it out

Output a valid JSON object with this exact schema and nothing else:
{{
  "same_individuals": [
    ["name 1", "name 2"]
  ],
  "equivalent_properties": [
    ["prop 1", "prop 2"]
  ]
}}

Example:
{{
  "same_individuals": [
    ["meenakshi", "meenakshi dsouza"],
    ["dept of cs", "department of computer science"],
    ["department of computer science", "department of computer science and engineering"],
    ["iiit bangalore", "iiit b"]
    ["Department of Computer Science & Engineering", "Department of Computer Science and Engineering"]
  ],
  "equivalent_properties": [
    ["teaches", "teachescourse"]
  ]
}}

Inputs:
"individuals": {json.dumps(unique_indiv_names)}
"properties": {json.dumps(unique_prop_names)}
"""
    # print("  - Calling Groq LLM (llama-3.3-70b-versatile) for semantic alignment...")

    # this is the prompt that is sent to the LLM
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,
            # max_completion_tokens=1500
            max_completion_tokens=4096
        )
        
        data = json.loads(response.choices[0].message.content)
        
        # this is used to map the names to the URIs
        # its done to make it easier to add the 
        # owl:sameAs and owl:equivalentProperty
        name_to_indiv_uris = {}
        for u, n in indiv_dict.items():
            name_to_indiv_uris.setdefault(n, []).append(u)
        
        name_to_prop_uris = {}
        for u, n in prop_dict.items():
            name_to_prop_uris.setdefault(n, []).append(u)
        
        added_same_as = 0
        added_equiv_prop = 0
        
        # adding the owl:sameAs
        # looping through same_individuals from LLM
        for pair in data.get("same_individuals", []):
            if isinstance(pair, list) and len(pair) == 2:
                n1, n2 = pair[0].lower().strip(), pair[1].lower().strip()
                if not isinstance(n1, str) or not isinstance(n2, str):
                    continue
                uris1 = name_to_indiv_uris.get(n1, [])
                uris2 = name_to_indiv_uris.get(n2, [])
                for u1 in uris1:
                    for u2 in uris2:
                        if u1 != u2:
                            g.add((URIRef(u1), OWL.sameAs, URIRef(u2)))
                            added_same_as += 1
        
        # add
        for pair in data.get("equivalent_properties", []):
            if isinstance(pair, list) and len(pair) == 2:
                n1, n2 = pair[0].lower().strip(), pair[1].lower().strip()
                if not isinstance(n1, str) or not isinstance(n2, str):
                    continue
                uris1 = name_to_prop_uris.get(n1, [])
                uris2 = name_to_prop_uris.get(n2, [])
                for u1 in uris1:
                    for u2 in uris2:
                        if u1 != u2:
                            g.add((URIRef(u1), OWL.equivalentProperty, URIRef(u2)))
                            added_equiv_prop += 1
        
        print(f"\tAdded {added_same_as} owl:sameAs links between individuals.")
        print(f"\tAdded {added_equiv_prop} owl:equivalentProperty links between properties.")
        
    except Exception as e:
        import traceback
        print(f"  - LLM alignment failed: {e}")
        traceback.print_exc()
        
    return g

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

    # Injecting entity resolution logic here
    g = entity_resolution(g)

    print(f"\nMerging complete! Total triples in master graph: {len(g)}")
    print(f"Serialising to {args.output}...")
    g.serialize(destination=args.output, format="xml")
    print("Done. You can now load this file into Protégé to explore cross-entity relationships.")

if __name__ == "__main__":
    main()