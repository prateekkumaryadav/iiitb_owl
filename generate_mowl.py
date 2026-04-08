import os
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD

def generate_master_owl(output_file="master_schema.owl"):
    # Initialize Graph
    g = Graph()
    
    # Define primary namespace
    UNI = Namespace("http://example.org/university/")
    g.bind("uni", UNI)
    
    # Define Ontology Header
    ontology_uri = URIRef("http://example.org/university/ontology")
    g.add((ontology_uri, RDF.type, OWL.Ontology))
    g.add((ontology_uri, RDFS.comment, Literal("Master OWL Schema for Institutional Semantic Integration.")))
    
    # --- CLASSES ---
    classes = ["Entity", "Person", "Faculty", "Student", "Department", "Course", "Program", "University"]
    for c in classes:
        cls_uri = URIRef(UNI[c])
        g.add((cls_uri, RDF.type, OWL.Class))
        
    # Subclass relationships
    g.add((URIRef(UNI["Faculty"]), RDFS.subClassOf, URIRef(UNI["Person"])))
    g.add((URIRef(UNI["Student"]), RDFS.subClassOf, URIRef(UNI["Person"])))
    g.add((URIRef(UNI["Person"]), RDFS.subClassOf, URIRef(UNI["Entity"])))
    g.add((URIRef(UNI["Department"]), RDFS.subClassOf, URIRef(UNI["Entity"])))
    g.add((URIRef(UNI["Course"]), RDFS.subClassOf, URIRef(UNI["Entity"])))
    
    # --- OBJECT PROPERTIES (Entity-to-Entity) ---
    obj_props = [
        "isMemberOf",
        "hasDepartment",
        "teachesCourse",
        "offersCourse",
        "isPrerequisiteFor",
        "hasAlumni",
        "hasResearchInterest"
    ]
    for prop in obj_props:
        prop_uri = URIRef(UNI[prop])
        g.add((prop_uri, RDF.type, OWL.ObjectProperty))
        
    # --- DATATYPE PROPERTIES (Entity-to-Literal) ---
    data_props = [
        "hasDuration",
        "hasCredits",
        "hasCourseCode",
        "hasDegree",
        "hasSpecialization",
        "hasEmail"
    ]
    for dprop in data_props:
        dprop_uri = URIRef(UNI[dprop])
        g.add((dprop_uri, RDF.type, OWL.DatatypeProperty))
        
    # Optional constraints (Domain/Range)
    g.add((URIRef(UNI["teachesCourse"]), RDFS.domain, URIRef(UNI["Faculty"])))
    g.add((URIRef(UNI["teachesCourse"]), RDFS.range, URIRef(UNI["Course"])))
    
    g.add((URIRef(UNI["hasEmail"]), RDFS.range, XSD.string))
    
    # Serialize to file
    g.serialize(destination=output_file, format="xml")
    print(f"Master OWL Schema generated successfully: {output_file}")

if __name__ == "__main__":
    generate_master_owl()
