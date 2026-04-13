# extractor.py
# Sends cleaned faculty page text to the Groq LLM and returns
# OntologyData (a list of typed triples with predicate/class metadata).
#
# KEY DESIGN PRINCIPLE: Predicates are NOT hardcoded here.
# The LLM reads the page and freely invents camelCase predicate names
# that best describe each relationship it finds.

import os
import json
import time
import re
from groq import Groq
from master_schema import OntologyData, Triple


# ---------------------------------------------------------------------------
# Helper: split long text into chunks
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Name normaliser (same as before)
# ---------------------------------------------------------------------------

def _clean_name(raw: str) -> str:
    """Strip honorifics and normalise a person's name."""
    cleaned = re.sub(
        r'^(Prof\.|Dr\.|Mr\.|Mrs\.|Ms\.|Professor|Assistant Professor|'
        r'Associate Professor|Doctor)\s*',
        '', raw, flags=re.IGNORECASE
    )
    cleaned = re.sub(r"['.,]", '', cleaned).strip()
    return cleaned.title()


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_triples(text: str, faculty_name: str = "") -> OntologyData:
    """
    Send cleaned faculty profile text to the LLM and return OntologyData.

    Parameters
    ----------
    text         : Clean text from one faculty profile page.
    faculty_name : Hint for the LLM so it anchors all triples to the
                   correct subject (avoids hallucinated names).
    """
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    schema_json = OntologyData.model_json_schema()

    # Build the system prompt — no predicate list supplied on purpose
    system_prompt = f"""
You are an expert Knowledge Graph extraction engine for university faculty profiles.

Your task:
Read the raw text of a faculty profile page and extract semantic triples that
capture the most important facts about the faculty member.

=== OUTPUT FORMAT ===
You MUST return valid JSON that strictly conforms to this JSON Schema:
{json.dumps(schema_json, indent=2)}

=== PREDICATE RULES (CRITICAL) ===
- DO NOT use a fixed list of predicates.  Invent the best camelCase predicate
  that precisely describes each relationship you find.
- Good examples: hasDesignation, worksAt, hasEmail, hasQualification,
  hasResearchInterest, authoredPublication, receivedAward, holdsFellowship,
  teachesCourse, holdsPatent, memberOf, chairOf, projectPIOf, projectCoPIOf,
  receivedFellowship, hasBestPaperAward, sponsoredBy.
- Keep predicates concise and reusable across faculty members.

=== SUBJECT RULES ===
- The subject of EVERY triple must be the faculty member's full name
  (e.g. "Debabrata Das") OR a named entity that appears as the object of a
  previously defined triple (e.g. a publication title, award name, course name).
- Always use the faculty member's clean full name — no honorifics like "Dr." or "Prof.".
{f'- The primary faculty member on this page is: "{faculty_name}"' if faculty_name else ''}

=== CLASS RULES ===
- subject_class: pick the most specific OWL class for the subject.
  Common classes: Faculty, Institute, Department, ResearchArea, Publication,
  Award, Course, Project, Fellowship, Patent.
- object_class: required for ObjectProperty triples; use the same class vocabulary.
  Leave null for DatatypeProperty triples.

=== PREDICATE TYPE RULES ===
- DatatypeProperty → object is a plain text/string literal (email, year, title string).
- ObjectProperty   → object is a named real-world entity (institute, area, award, …).

=== EXTRACTION SCOPE ===
Extract facts in this priority order (stop at ~35 triples to stay focused):
1. Basic identity: name, designation, email, affiliation, education/qualifications.
2. Research interests (one triple per interest area).
3. Key courses taught (up to 5).
4. Sponsored projects (up to 5) — PI/CoPI role, title, sponsor.
5. Selected publications (up to 5 journal papers).
6. Honours and awards (up to 5).
7. Fellowships, patents if mentioned.

=== WHAT TO IGNORE ===
- Website navigation links, menus, footers, breadcrumbs.
- Boilerplate legal text, contact addresses.
- Conference paper lists beyond the 5 selected.
- Duplicate triples.

Output ONLY the JSON object. Nothing else.
"""

    chunks = _chunk_text(text, max_len=3000)
    all_triples: list[Triple] = []

    print(f"[Extractor] Text split into {len(chunks)} chunk(s) for processing.")

    for i, chunk in enumerate(chunks):
        print(f"  → Processing chunk {i+1}/{len(chunks)} …")

        response = None
        for attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content":
                         f"Extract triples from this faculty profile text:\n\n{chunk}"}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
                break
            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    wait = 15 * (attempt + 1)
                    print(f"    [Rate Limit] Waiting {wait}s …")
                    time.sleep(wait)
                else:
                    print(f"    [Error] {e}")
                    break

        # Polite delay between requests
        time.sleep(3)

        if not response:
            continue

        try:
            data = json.loads(response.choices[0].message.content)
            for t_data in data.get("triples", []):
                try:
                    triple = Triple(**t_data)

                    # Normalise faculty subject names
                    if triple.subject_class == "Faculty":
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
                    if len(all_triples) >= 35:
                        break

                except Exception:
                    pass  # Skip malformed triples

        except Exception as parse_err:
            print(f"  [Parse error on chunk {i+1}]: {parse_err}")

        if len(all_triples) >= 35:
            print("  [Extractor] Reached 35-triple limit — stopping early.")
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


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sample = (
        "Dr. Debabrata Das is Director of IIIT-Bangalore. "
        "He received his Ph.D. from IIT Kharagpur. "
        "His research interests include Wireless Access Networks and IoT. "
        "Email: ddas@iiitb.ac.in"
    )
    print("=== Self-test ===")
    result = extract_triples(sample, faculty_name="Debabrata Das")
    print(result.model_dump_json(indent=2))
