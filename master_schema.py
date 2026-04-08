from pydantic import BaseModel, Field
from typing import List
from enum import Enum
import os
from rdflib import Graph, OWL, RDF

# Dynamically parse allowed properties from the formal MOWL file
def load_allowed_predicates(owl_file="master_schema.owl"):
    g = Graph()
    if os.path.exists(owl_file):
        g.parse(owl_file, format="xml")
        
    props = []
    # Fetch ObjectProperties
    for s, p, o in g.triples((None, RDF.type, OWL.ObjectProperty)):
        props.append(s.split("/")[-1])
    # Fetch DatatypeProperties
    for s, p, o in g.triples((None, RDF.type, OWL.DatatypeProperty)):
        props.append(s.split("/")[-1])
        
    # Fallback just in case OWL file is missing initially
    if not props:
        props = ["isMemberOf", "hasDepartment", "teachesCourse"]
        
    return props

allowed_props = load_allowed_predicates()
PredicateEnum = Enum('PredicateEnum', {p: p for p in allowed_props})

class Triple(BaseModel):
    subject: str = Field(description="The source entity, e.g., 'Prof. Sadagopan' or 'Data Structures'")
    predicate: PredicateEnum = Field(description="The relationship between subject and object. Must strictly be one of the defined literals extracted from the Master OWL.")
    object: str = Field(description="The target entity, e.g., 'IIIT Bangalore', 'Machine Learning', or 'CS101'")

class OntologyData(BaseModel):
    triples: List[Triple] = Field(description="List of extracted semantic triples representing the ontology.")
