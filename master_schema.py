# master_schema.py

# Defines the Pydantic schema for triple extraction.
# Predicates are NOT hardcoded — the LLM discovers them from page content.
# Each triple carries metadata so the OWL generator can build a rich ontology.

# Imports
# Pydantic imports, used for type checking and validation
from pydantic import BaseModel, Field

# Typing imports, used for type hints
from typing import List, Optional, Literal

# Triple class
class Triple(BaseModel):
    """
    A semantic triple extracted from a faculty web page.

    subject       : The entity the fact is about (e.g. "Debabrata Das")
    predicate     : A camelCase relationship name invented by the LLM
                    (e.g. "hasDesignation", "worksAt", "authoredPublication")
    object        : The value or target entity
    predicate_type: Whether this predicate links to another named entity
                    (ObjectProperty) or to a plain string/literal (DatatypeProperty)
    subject_class : OWL class the subject belongs to (e.g. "Faculty")
    object_class  : OWL class the object belongs to — only for ObjectProperty triples
                    (e.g. "ResearchArea", "Award", "Course").
                    Leave empty for DatatypeProperty triples.
    """

    # descriptions defined for each field are used to generate the OWL ontology which are passed to the LLM
    # acting as a prompt to the LLM for generating the ontology dynamically    

    # Subject
    subject: str = Field(
        description="The source entity, such as a person, department name, organization, or course."
    )
    # Predicate
    predicate: str = Field(
        description=(
            "A camelCase relationship name freely invented to capture the fact. "
            "Examples: worksAt, authoredDocument, hasEmail, locatedIn, partOf, "
            "relatedTo. Do NOT restrict yourself to these examples—invent exact "
            "names that best fit the text."
        )
    )
    # Object
    object: str = Field(
        description="The target value or entity name."
    )

    # Predicate type
    predicate_type: Literal["ObjectProperty", "DatatypeProperty"] = Field(
        description=(
            "ObjectProperty  → object is a named entity (another individual). "
            "DatatypeProperty → object is a plain literal (string, year, email, …)."
        )
    )
    # Subject class
    subject_class: str = Field(
        description=(
            "The OWL Class the subject belongs to. "
            "Examples: Person, Organization, Location, Event, Concept."
        )
    )
    # Object class
    object_class: Optional[str] = Field(
        default=None,
        description=(
            "The OWL Class the object belongs to — only for ObjectProperty triples. "
            "Examples: Project, Publication, Institution, Skill. "
            "Leave null/empty for DatatypeProperty triples."
        )
    )

# Ontology data class
class OntologyData(BaseModel):
    """Container for all extracted triples from one faculty page."""
    triples: List[Triple] = Field(
        description="List of extracted semantic triples representing the ontology."
    )
