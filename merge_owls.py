import argparse
import glob
import urllib.parse
import difflib
from rdflib import Graph, OWL, RDF

def clean_name(uri):
    if "#" in uri:
        name = uri.split("#")[-1]
    else:
        name = uri.split("/")[-1]
    name = urllib.parse.unquote(name)
    name = name.replace("_", " ")
    return name.lower().strip()

def get_specific_types(g, uri):
    types = list(g.objects(uri, RDF.type))
    specific = [t for t in types if t != OWL.NamedIndividual]
    return set(specific)

def entity_resolution(g):
    import os
    import json
    from groq import Groq
    from rdflib import URIRef
    
    print("Starting LLM-based entity resolution for cross-graph mapping...")
    
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
    unique_indiv_names = list(set(indiv_dict.values()))
    
    # 2. Gather properties
    properties = list(set(g.subjects(RDF.type, OWL.ObjectProperty))) + \
                 list(set(g.subjects(RDF.type, OWL.DatatypeProperty)))
    prop_dict = {str(uri): clean_name(str(uri)) for uri in properties}
    unique_prop_names = list(set(prop_dict.values()))
    
    if not unique_indiv_names and not unique_prop_names:
        return g
        
    prompt = f"""
You are a semantic web ontology aligner. 
Identify pairs of concepts that refer to the EXACT same real-world entity or equivalent relationships, despite slight lexical differences in their names.

I provide two JSON lists of names.
Output a valid JSON object strictly adhering to this schema:
{{
  "same_individuals": [
    ["Name 1", "Name 2"], ...
  ],
  "equivalent_properties": [
    ["Name 1", "Name 2"], ...
  ]
}}

Guidelines:
- Match items that are conceptually identical (e.g. "Meenakshi" & "Meenakshi Dsouza", or "Dept of CS" & "Department of Computer Science").
- DO NOT match identical strings. There is no need to output ["Meenakshi", "Meenakshi"].
- DO NOT false link "hasDuration" and "hasEducation".
- Keep the output as concise as possible. ONLY include genuine synonymous pairings.
- If there are zero matching pairs, output empty arrays [].
- Output ONLY the JSON object.

Example Output:
{{
  "same_individuals": [
    ["Meenakshi", "Meenakshi Dsouza"],
    ["IIIT Bangalore", "IIIT-Bangalore"]
  ],
  "equivalent_properties": [
    ["teaches", "teachesCourse"]
  ]
}}

Inputs:
"individuals": {json.dumps(unique_indiv_names)}
"properties": {json.dumps(unique_prop_names)}
"""
    print("  - Calling Groq LLM (llama-3.3-70b-versatile) for semantic alignment...")
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_completion_tokens=1500
        )
        
        data = json.loads(response.choices[0].message.content)
        
        # Reverse mapping: name -> list of URIs
        name_to_indiv_uris = {}
        for u, n in indiv_dict.items():
            name_to_indiv_uris.setdefault(n, []).append(u)
            
        name_to_prop_uris = {}
        for u, n in prop_dict.items():
            name_to_prop_uris.setdefault(n, []).append(u)
        
        added_same_as = 0
        added_equiv_prop = 0
        
        for pair in data.get("same_individuals", []):
            if isinstance(pair, list) and len(pair) == 2:
                n1, n2 = pair[0], pair[1]
                if not isinstance(n1, str) or not isinstance(n2, str):
                    continue
                uris1 = name_to_indiv_uris.get(n1, [])
                uris2 = name_to_indiv_uris.get(n2, [])
                for u1 in uris1:
                    for u2 in uris2:
                        if u1 != u2:
                            g.add((URIRef(u1), OWL.sameAs, URIRef(u2)))
                            added_same_as += 1
                
        for pair in data.get("equivalent_properties", []):
            if isinstance(pair, list) and len(pair) == 2:
                n1, n2 = pair[0], pair[1]
                if not isinstance(n1, str) or not isinstance(n2, str):
                    continue
                uris1 = name_to_prop_uris.get(n1, [])
                uris2 = name_to_prop_uris.get(n2, [])
                for u1 in uris1:
                    for u2 in uris2:
                        if u1 != u2:
                            g.add((URIRef(u1), OWL.equivalentProperty, URIRef(u2)))
                            added_equiv_prop += 1
                
        print(f"  - Added {added_same_as} owl:sameAs links between individuals.")
        print(f"  - Added {added_equiv_prop} owl:equivalentProperty links between properties.")
        
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
