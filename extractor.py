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

    # System prompt: structural rules only — zero topic hints, zero predicate examples.
    # The LLM reads the text and decides what facts exist and how to name the relationships.
    system_prompt = f"""
You are a Knowledge Graph extraction engine.

Read the text below (from a university faculty web page) and extract every
meaningful fact as a semantic triple.

=== OUTPUT FORMAT ===
Return ONLY a valid JSON object conforming EXACTLY to this JSON Schema — nothing else:
{json.dumps(schema_json, indent=2)}

=== STRUCTURAL RULES ===

1. PREDICATE — invent a concise camelCase name that best describes the relationship
   between subject and object.  Use your own judgement; there is no approved list.

2. SUBJECT — must be the name of a real entity present in the text
   (a person, an organisation, a publication, an award, …).
{f'   The main person on this page is "{faculty_name}" — use that exact spelling.' if faculty_name else ''}
   Never use honorifics (Dr., Prof., Mr.) in the subject field.

3. PREDICATE TYPE
   - ObjectProperty   → the object is a named real-world entity (another individual).
   - DatatypeProperty → the object is a plain literal value (a string, number, email, …).

4. CLASSES — assign the most specific descriptive class name you can find for both
   subject_class and object_class.  Use your own judgement; there is no approved list.
   object_class must be null for DatatypeProperty triples.

5. IGNORE navigation menus, breadcrumbs, footer boilerplate, and duplicate lines.

6. Aim for up to 35 high-quality, non-redundant triples per text block.

Output ONLY the JSON object. No explanation, no markdown fences.
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
