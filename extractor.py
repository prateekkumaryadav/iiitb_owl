# extractor.py

# Sends cleaned faculty page text to the Groq LLM and returns
# OntologyData (a list of typed triples with predicate/class metadata).
#
# KEY DESIGN PRINCIPLE: Predicates are NOT hardcoded here.
# The LLM reads the page and freely invents camelCase predicate names
# that best describe each relationship it finds.

# imports
# os is used to get the API key from the environment variables
import os

# json is used to parse the JSON response from the LLM
import json

# time is used to wait for the API rate limit
import time

# re is used to clean the text
import re

# groq is used to interact with the LLM
from groq import Groq

# OntologyData and Triple are used to store the extracted triples
from master_schema import OntologyData, Triple

# Helper: split long text into chunks
# this is used to split the text into chunks of at most max_len chars

# currently limited to 1500 chars per chunk
# this is done to avoid the LLM from hallucinating

def _chunk_text(text: str, max_len: int = 1500) -> list[str]:
    """Split text on word boundaries into chunks of at most max_len chars."""
    words = text.split()
    chunks, current, length = [], [], 0
    for word in words:
        if length + len(word) + 1 > max_len:
            chunks.append(" ".join(current))
            current, length = [word], len(word)
        else:
            current.append(word)
            length += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks

# Name normaliser (same as before)
# this is used to clean the name of the faculty
def _clean_name(raw: str) -> str:
    """Strip honorifics and normalise a person's name."""
    cleaned = re.sub(
        r'^(Prof\.|Dr\.|Mr\.|Mrs\.|Ms\.|Professor|Assistant Professor|'
        r'Associate Professor|Doctor)\s*',
        '', raw, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"['.,]", '', cleaned).strip()
    return cleaned.title()

# Main extraction function
# this is used to extract the triples from the text
def extract_triples(text: str, entity_name: str = "", entity_type: str = "faculty") -> OntologyData:
    """
    Send cleaned text to the LLM and return OntologyData.

    Parameters
    ----------
    text         : Clean text from one page.
    entity_name  : Hint for the LLM so it anchors all triples to the
                   correct subject (avoids hallucinated names).
    entity_type  : Provide context of what kind of page is being scraped.
    """
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    schema_json = OntologyData.model_json_schema()

    # System prompt: structural rules only — zero topic hints, zero predicate examples.
    # The LLM reads the text and decides what facts exist and how to name the relationships.
    
    system_prompt = f"""
You are a precision Knowledge Graph extraction engine for academic institutional data.

Your task: Extract semantic triples from university {entity_type} web pages to build a comprehensive OWL/RDF knowledge graph of faculty, departments, research, and institutional relationships.

=== OUTPUT FORMAT ===
Return ONLY a valid JSON object conforming EXACTLY to this JSON Schema — nothing else:
{json.dumps(schema_json, indent=2)}

=== EXTRACTION GUIDELINES ===

1. SUBJECT
   - Extract ALL entities: faculty members, departments, research groups, publications, courses, projects, awards, degrees, institutions
{f'   - When referring to "{entity_name}", use that EXACT spelling for consistency' if entity_name else ''}
   - NEVER include titles/honorifics (Dr., Prof., Mr., Ms.) in subject names
   - Use full legal names when available (e.g., "John Michael Smith" not "J.M. Smith")
   - For departments/organizations, use official full names

2. PREDICATE (relationship naming)
   - Use precise, semantically rich camelCase predicates
   - Academic domain examples:
     * headOf, memberOf, affiliatedWith, chairOf
     * teaches, supervises, collaboratesWith, advisedBy
     * authored, coauthored, presented, published
     * receivedDegree, awardedGrant, wonAward
     * specializesIn, researchesIn, conducts
     * locatedIn, partOf, establishedIn
   - Be consistent: use the same predicate for similar relationships across extractions

3. PREDICATE TYPE
   - ObjectProperty: object is a named entity (Person, Department, Publication, Award, Institution)
     Examples: "John Smith" memberOf "Computer Science Department"
              "Jane Doe" authored "Machine Learning Paper"
   
   - DatatypeProperty: object is a literal value (string, number, date, email, URL, phone)
     Examples: "John Smith" hasEmail "john@university.edu"
              "Computer Science" foundedIn "1985"
              "Jane Doe" hasPhone "+1-555-0123"

4. SUBJECT_CLASS and OBJECT_CLASS
   - Use specific, hierarchical academic classes:
     * Person types: Faculty, Professor, AssociateProfessor, AssistantProfessor, Lecturer, Researcher, PostDoc, PhDStudent
     * Organization types: Department, ResearchGroup, Institute, Laboratory, Center, University, College
     * Academic outputs: Publication, Journal, Conference, Book, Patent, Thesis
     * Academic entities: Course, Program, Degree, Grant, Award, Project
   - object_class MUST be null for all DatatypeProperty triples
   - Choose the most specific class available (e.g., "AssociateProfessor" over "Faculty")

5. CONTENT TO EXTRACT
   Include:
   ✓ Personal information: names, titles, positions, contact details, office locations
   ✓ Organizational structure: department membership, committee roles, administrative positions
   ✓ Academic credentials: degrees, institutions attended, graduation years
   ✓ Research interests and specializations
   ✓ Publications, patents, and academic outputs
   ✓ Teaching assignments and course information
   ✓ Awards, honors, grants, and recognitions
   ✓ Collaborations and professional networks
   ✓ Projects, labs, and research group affiliations
   
   Exclude:
   ✗ Navigation menus, headers, footers
   ✗ Breadcrumb trails and site structure elements
   ✗ Generic UI text ("Click here", "Learn more", "Back to top")
   ✗ Duplicate information repeated across the page
   ✗ Cookie notices, privacy policies, accessibility statements

6. QUALITY STANDARDS
   - Extract 900-1000 high-quality, non-redundant triples per text chunk, if possible
   - Prioritize factual, verifiable information over vague statements
   - Maintain consistency in entity naming across all triples
   - Ensure each triple adds unique information to the knowledge graph
   - Preserve temporal information (dates, years) when available
   - Include both direct facts and implicit relationships that are clearly stated

7. SPECIAL CASES
   - Email addresses: use predicate "hasEmail" with DatatypeProperty
   - Phone numbers: use predicate "hasPhone" with DatatypeProperty
   - URLs/websites: use predicate "hasWebsite" or "hasProfileURL" with DatatypeProperty
   - Dates: preserve format from source (use predicates like "establishedIn", "graduatedIn", "publishedIn")
   - Multi-word entities: keep as complete phrases (e.g., "Machine Learning Lab" not separate words)
   - Abbreviations: expand when full form is available in text

=== CRITICAL REQUIREMENTS ===
- Output ONLY the JSON object
- NO markdown code fences (no ```json)
- NO explanatory text before or after
- NO comments in the JSON
- Ensure valid JSON syntax (proper escaping, no trailing commas)

Begin extraction now.
"""

    # split the text into chunks of at most 3000 chars
    chunks = _chunk_text(text, max_len=3000)
    all_triples: list[Triple] = []

    print(f"[Extractor] Text split into {len(chunks)} chunk(s) for processing.")

    for i, chunk in enumerate(chunks):
        print(f"Processing chunk {i+1}/{len(chunks)} …")

        response = None
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content":
                         f"Extract triples from this {entity_type} profile text:\n\n{chunk}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                break
            except Exception as e:
                # if rate limit is exceeded, wait for 15 seconds and try again
                if "429" in str(e) or "Too Many Requests" in str(e):
                    wait = 15 * (attempt + 1)
                    print(f"[Rate Limit] Waiting {wait}s …")
                    time.sleep(wait)
                else:
                    print(f"[Error] {e}")
                    break

        # Polite delay between requests
        time.sleep(3)

        if not response:
            continue

        try:
            # load the JSON response
            data = json.loads(response.choices[0].message.content)
            for t_data in data.get("triples", []):
                try:
                    triple = Triple(**t_data)

                    # Normalise subject names if it's a person/faculty
                    if triple.subject_class in ["Faculty", "Person", "Professor", "Staff"] or entity_type == "faculty":
                        triple.subject = _clean_name(triple.subject)

                    # Drop clearly bad triples
                    if len(triple.subject.strip()) < 2:
                        continue
                    if len(triple.predicate.strip()) < 2:
                        continue
                    if len(triple.object.strip()) < 2:
                        continue

                    all_triples.append(triple)

                    # Stop after 35 triples to keep OWL manageable
                    # if len(all_triples) >= 35:
                        # break

                    # Stop after 100 triples to keep OWL manageable
                    # if len(all_triples) >= 100:
                    #     break
                    
                    if len(all_triples) >= 1000:
                        break

                except Exception:
                    pass  # Skip malformed triples

        except Exception as parse_err:
            print(f"[Parse error on chunk {i+1}]: {parse_err}")

        # if len(all_triples) >= 35:
        #     print("  [Extractor] Reached 35-triple limit — stopping early.")
        #     break

        # if len(all_triples) >= 100:
        #     print("[Extractor] Reached 100-triple limit — stopping early.")
        #     break
        if len(all_triples) >= 1000:
            # print("[Extractor] Reached 100-triple limit — stopping early.")
            break

    # Deduplicate by (subject, predicate, object)
    seen = set()
    unique_triples = []
    for t in all_triples:
        key = (t.subject.lower(), t.predicate.lower(), t.object.lower())
        if key not in seen:
            seen.add(key)
            unique_triples.append(t)

    print(f"[Extractor] Extracted {len(unique_triples)} unique triples.")
    return OntologyData(triples=unique_triples)


# Quick self-test
# if __name__ == "__main__":
#     sample = (
#         "Dr. Debabrata Das is Director of IIIT-Bangalore. "
#         "He received his Ph.D. from IIT Kharagpur. "
#         "His research interests include Wireless Access Networks and IoT. "
#         "Email: ddas@iiitb.ac.in"
#     )
#     print("=== Self-test ===")
#     result = extract_triples(sample, entity_name="Debabrata Das")
#     print(result.model_dump_json(indent=2))