# owl_generator.py
# Converts OntologyData (a list of typed triples) into a fully compliant
# OWL/XML ontology that Protege can load and display with:
#   • Named Classes  (owl:Class)
#   • Object Properties  (owl:ObjectProperty) with domain & range
#   • Datatype Properties  (owl:DatatypeProperty) with domain & range
#   • Named Individuals typed to their Class

from rdflib import Graph, URIRef, Literal, Namespace, BNode
from rdflib.namespace import RDF, OWL, RDFS, XSD
from master_schema import OntologyData
import urllib.parse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uri_safe(text: str) -> str:
    """Convert a free-form string to a URI-safe fragment, e.g.
    'Debabrata Das' → 'Debabrata_Das'."""
    safe = text.strip().replace(" ", "_")
    return urllib.parse.quote(safe, safe="_-")


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_owl(ontology_data: OntologyData, output_file: str = "output.owl") -> None:
    """
    Build a rich OWL graph from OntologyData and serialise it to OWL/XML.

    The resulting file, when opened in Protege, will show:
      Classes panel     → every distinct subject_class / object_class
      Object Properties → every predicate marked ObjectProperty
      Data Properties   → every predicate marked DatatypeProperty
      Individuals       → every subject and object entity
    """

    g = Graph()

    # ── Namespaces ────────────────────────────────────────────────────────────
    UNI  = Namespace("http://www.iiitb.ac.in/ontology/university#")
    g.bind("uni",  UNI)
    g.bind("owl",  OWL)
    g.bind("rdfs", RDFS)
    g.bind("xsd",  XSD)

    # ── Ontology declaration ──────────────────────────────────────────────────
    ont_uri = URIRef("http://www.iiitb.ac.in/ontology/university")
    g.add((ont_uri, RDF.type, OWL.Ontology))
    g.add((ont_uri, RDFS.label, Literal("IIIT-Bangalore Faculty Ontology")))
    g.add((ont_uri, RDFS.comment,
           Literal("Auto-generated from IIIT-B faculty web pages. "
                   "Predicates are discovered dynamically by an LLM — "
                   "no hand-coded schema was used.")))

    # ── Step 1: Collect all classes, object props, datatype props ─────────────
    classes:    set[str] = set()
    obj_props:  dict[str, set] = {}   # predicate → {(subj_class, obj_class)}
    data_props: dict[str, set] = {}   # predicate → {subj_class}

    for triple in ontology_data.triples:
        # Subject class
        if triple.subject_class:
            classes.add(triple.subject_class)

        if triple.predicate_type == "ObjectProperty":
            obj_class = triple.object_class or "Thing"
            if triple.object_class:
                classes.add(triple.object_class)
            obj_props.setdefault(triple.predicate, set()).add(
                (triple.subject_class, obj_class)
            )
        else:  # DatatypeProperty
            data_props.setdefault(triple.predicate, set()).add(
                triple.subject_class
            )

    # ── Step 2: Declare OWL Classes ──────────────────────────────────────────
    print(f"[OWL] Declaring {len(classes)} class(es): {sorted(classes)}")
    for cls_name in sorted(classes):
        cls_uri = UNI[_uri_safe(cls_name)]
        g.add((cls_uri, RDF.type,   OWL.Class))
        g.add((cls_uri, RDFS.label, Literal(cls_name)))

    # ── Step 3: Declare ObjectProperties ─────────────────────────────────────
    print(f"[OWL] Declaring {len(obj_props)} ObjectProperty/ies.")
    for pred_name, domain_range_set in obj_props.items():
        prop_uri = UNI[_uri_safe(pred_name)]
        g.add((prop_uri, RDF.type,   OWL.ObjectProperty))
        g.add((prop_uri, RDFS.label, Literal(pred_name)))

        # Collect unique domains and ranges
        domains = {d for d, _ in domain_range_set}
        ranges  = {r for _, r in domain_range_set}

        if len(domains) == 1:
            g.add((prop_uri, RDFS.domain, UNI[_uri_safe(next(iter(domains)))]))
        elif len(domains) > 1:
            # Union domain
            union = BNode()
            g.add((union, RDF.type, OWL.Class))
            items = list(domains)
            lst = _rdf_list(g, [UNI[_uri_safe(d)] for d in items])
            g.add((union, OWL.unionOf, lst))
            g.add((prop_uri, RDFS.domain, union))

        if len(ranges) == 1:
            r = next(iter(ranges))
            g.add((prop_uri, RDFS.range, UNI[_uri_safe(r)]))
        elif len(ranges) > 1:
            union = BNode()
            g.add((union, RDF.type, OWL.Class))
            lst = _rdf_list(g, [UNI[_uri_safe(r)] for r in ranges])
            g.add((union, OWL.unionOf, lst))
            g.add((prop_uri, RDFS.range, union))

    # ── Step 4: Declare DatatypeProperties ───────────────────────────────────
    print(f"[OWL] Declaring {len(data_props)} DatatypeProperty/ies.")
    for pred_name, domain_set in data_props.items():
        prop_uri = UNI[_uri_safe(pred_name)]
        g.add((prop_uri, RDF.type,   OWL.DatatypeProperty))
        g.add((prop_uri, RDFS.label, Literal(pred_name)))
        g.add((prop_uri, RDFS.range, XSD.string))

        domains = list(domain_set)
        if len(domains) == 1:
            g.add((prop_uri, RDFS.domain, UNI[_uri_safe(domains[0])]))
        elif len(domains) > 1:
            union = BNode()
            g.add((union, RDF.type, OWL.Class))
            lst = _rdf_list(g, [UNI[_uri_safe(d)] for d in domains])
            g.add((union, OWL.unionOf, lst))
            g.add((prop_uri, RDFS.domain, union))

    # ── Step 5: Declare NamedIndividuals and assert triples ──────────────────
    individuals_declared: set[str] = set()

    def _ensure_individual(name: str, cls_name: str | None) -> URIRef:
        uri = UNI[_uri_safe(name)]
        if name not in individuals_declared:
            g.add((uri, RDF.type, OWL.NamedIndividual))
            g.add((uri, RDFS.label, Literal(name)))
            if cls_name:
                g.add((uri, RDF.type, UNI[_uri_safe(cls_name)]))
            individuals_declared.add(name)
        return uri

    print(f"[OWL] Asserting {len(ontology_data.triples)} triple(s).")
    for triple in ontology_data.triples:
        subj_uri = _ensure_individual(triple.subject, triple.subject_class)
        pred_uri = UNI[_uri_safe(triple.predicate)]

        if triple.predicate_type == "ObjectProperty":
            obj_uri = _ensure_individual(triple.object, triple.object_class)
            g.add((subj_uri, pred_uri, obj_uri))
        else:
            g.add((subj_uri, pred_uri, Literal(triple.object, datatype=XSD.string)))

    # ── Step 6: Serialise ─────────────────────────────────────────────────────
    print(f"[OWL] Serialising to {output_file} …")
    g.serialize(destination=output_file, format="xml")
    print(f"[OWL] Done.  Classes={len(classes)}  "
          f"ObjectProps={len(obj_props)}  DataProps={len(data_props)}  "
          f"Individuals={len(individuals_declared)}")


# ---------------------------------------------------------------------------
# Helper: build an rdf:List from a Python list of URIRefs
# ---------------------------------------------------------------------------

def _rdf_list(g: Graph, items: list) -> BNode | URIRef:
    """Recursively build an rdf:List and return the head node."""
    from rdflib import RDF
    NIL = RDF.nil
    if not items:
        return NIL
    head = BNode()
    g.add((head, RDF.first, items[0]))
    g.add((head, RDF.rest,  _rdf_list(g, items[1:])))
    return head


# ---------------------------------------------------------------------------
# Manual test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from master_schema import Triple

    sample_data = OntologyData(triples=[
        Triple(subject="Debabrata Das", predicate="hasDesignation",
               object="Director", predicate_type="DatatypeProperty",
               subject_class="Faculty"),
        Triple(subject="Debabrata Das", predicate="worksAt",
               object="IIIT Bangalore", predicate_type="ObjectProperty",
               subject_class="Faculty", object_class="Institute"),
        Triple(subject="Debabrata Das", predicate="hasResearchInterest",
               object="Wireless Access Networks", predicate_type="ObjectProperty",
               subject_class="Faculty", object_class="ResearchArea"),
        Triple(subject="Debabrata Das", predicate="hasEmail",
               object="ddas@iiitb.ac.in", predicate_type="DatatypeProperty",
               subject_class="Faculty"),
    ])
    generate_owl(sample_data, "test_output.owl")
    print("Written: test_output.owl")
