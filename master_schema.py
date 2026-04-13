# importing the required modules

# pydantic for data validation
from pydantic import BaseModel, Field

# for type hinting
from typing import List, Literal

# defining the triple class for storing the triples
class Triple(BaseModel):
    # subject of the triple
    subject: str = Field(description="The source entity, e.g., 'Prof. Sadagopan' or 'Data Structures'")
    
    # predicate of the triple
    predicate: Literal[
        "teachesCourse", 
        "isMemberOf", 
        "hasResearchInterest", 
        "hasDepartment",
        "hasEmail",
        "hasDesignation",
        "hasQualification",
        "isAuthorOf",
        "hasJoinedYear"
    ] = Field(description="The relationship between subject and object. Must strictly be one of the defined literals.")
    
    # object of the triple
    object: str = Field(description="The target entity, e.g., 'IIIT Bangalore', 'Machine Learning', or 'CS101'")

# defining the ontology data class for storing the triples
class OntologyData(BaseModel):
    # list of triples
    triples: List[Triple] = Field(description="List of extracted semantic triples representing the ontology.")
