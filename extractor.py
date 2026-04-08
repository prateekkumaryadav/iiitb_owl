import os
import json
from groq import Groq
from master_schema import OntologyData

def extract_triples(text: str, focus: str = "all") -> OntologyData:
    """
    Takes raw text, sends it to Groq API with instructions to extract 
    triples strictly conforming to the OntologyData schema, and returns the parsed schema.
    """
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    schema_json = OntologyData.model_json_schema()
    
    focus_constraint = ""
    if focus == "faculty":
        focus_constraint = "CRITICAL FOREGROUND FOCUS: ONLY extract relationships involving People/Faculty members (e.g., isMemberOf, hasDepartment, hasEmail). Be sure to explicitly extract their email addresses. completely IGNORE university degree offerings like B.Tech/M.Tech."
    elif focus == "courses":
        focus_constraint = "CRITICAL FOREGROUND FOCUS: ONLY extract relationships involving Courses, Programs, and Degrees (e.g., offersCourse, hasDuration). completely IGNORE any text about faculty or people."
    else:
        focus_constraint = "Extract relationships for both Faculty and Courses."

    system_prompt = f"""
    You are an expert Semantic Web extraction pipeline. 
    Your job is to read raw text content from university web pages and extract semantic relationships (triples).
    
    {focus_constraint}
    
    You MUST output valid JSON that strictly conforms to the following JSON Schema:
    {json.dumps(schema_json, indent=2)}
    
    Important Constraints:
    - Never invent predicates. Only use the literal predicates defined in the schema.
    - Deep Entity Mapping: If a person belongs to a specific department, map it properly (e.g., "Ahana Pradhan" -> "hasDepartment" -> "Computer Science"). DO NOT set their department as "IIIT Bangalore".
    - Ignore Boilerplate: Do NOT extract generic website navigation or footer lists. Focus on the core content of the page context.
    - Exhaustive Extraction: You MUST extract EVERY SINGLE valid relationship you find in this text block. Do not artificially limit yourself. Leave no entity behind.
    - Output ONLY the JSON object, nothing else.
    """

    def chunk_text(text, max_len=1000):
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        for word in words:
            # +1 for the space
            if current_length + len(word) + 1 > max_len:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += len(word) + 1
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

    chunks = chunk_text(text, max_len=1000)
    all_triples = []

    print(f"Divided text into {len(chunks)} chunks for full extraction processing:")
    for i, chunk in enumerate(chunks):
        print(f"  -> Extractor working on chunk {i+1} of {len(chunks)}...")
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract triples from the following text:\n\n{chunk}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            json_output = response.choices[0].message.content
            data = json.loads(json_output)
            
            # Validate each triple individually to survive LLM hallucinations
            from master_schema import Triple
            for t_data in data.get("triples", []):
                try:
                    valid_triple = Triple(**t_data)
                    all_triples.append(valid_triple)
                except Exception as ve:
                    # Skip the invalid triple instead of crashing the chunk
                    pass
            
        except Exception as e:
            print(f"Error during LLM extraction on chunk {i+1}: {e}")

    return OntologyData(triples=all_triples)

if __name__ == "__main__":
    sample_text = "Prof. Sadagopan teaches Data Structures at IIIT Bangalore. He is a member of the Computer Science Department."
    print("Testing extraction on sample text...")
    result = extract_triples(sample_text)
    print(result.model_dump_json(indent=2))
