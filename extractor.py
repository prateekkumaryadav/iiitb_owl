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
    
    # defining the focus constraint
    focus_constraint = ""

    # checking the focus
    if focus == "faculty":
        # faculty focus constraint(current aim)
        focus_constraint = "CRITICAL FOREGROUND FOCUS: ONLY extract relationships involving People/Faculty members (e.g., isMemberOf, hasDepartment, hasEmail). Be sure to explicitly extract their email addresses. completely IGNORE university degree offerings like B.Tech/M.Tech. DO NOT extract relationships where the Subject is a Department, Centre, or the University itself (e.g. do not map 'Department of CS' -> 'isMemberOf' -> 'IIIT Bangalore')."
    elif focus == "courses":
        focus_constraint = "CRITICAL FOREGROUND FOCUS: ONLY extract relationships involving Courses, Programs, and Degrees (e.g., offersCourse, hasDuration). completely IGNORE any text about faculty or people."
    else:
        focus_constraint = "Extract relationships for both Faculty and Courses."

    # defining the system prompt for the LLM to extract the triples
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

    # printing the number of chunks
    # this is done to ensure that the LLM processes the entire text 
    # and not just a part of it as it has a token limit which can 
    # lead to incomplete extraction by skipping the latter part of the text
    print(f"Divided text into {len(chunks)} chunks for full extraction processing:")
    for i, chunk in enumerate(chunks):
        print(f" - Extractor working on chunk {i+1} of {len(chunks)} ")
        import time
        max_retries = 3
        response = None
        
        for attempt in range(max_retries):
            try:
                # calling the Groq API to extract the triples
                response = client.chat.completions.create(
                    # using llama-3.3-70b-versatile model for triple extraction
                    # this model is chosen because it is efficient and accurate for this task
                    model="llama-3.3-70b-versatile",
                    
                    # defining the messages for the LLM
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Extract triples from the following text:\n\n{chunk}"}
                    ],
                    
                    # response_format is used to ensure that the LLM returns the response in JSON format
                    response_format={"type": "json_object"},
                    
                    # temperature is used to control the randomness of the LLM
                    # 0.1 is used to ensure that the LLM returns the response in a deterministic way
                    temperature=0.1
                )
                break
            # handling the rate limit error
            except Exception as e:
                if "429" in str(e) or "Too Many Requests" in str(e):
                    wait_time = 15 * (attempt + 1)

                    # waiting for the rate limit error to be resolved by increasing the wait time
                    print(f"    [Rate Limit Hit] Waiting {wait_time}s before retrying...")
                    time.sleep(wait_time)
                else:
                    print(f"    [Error] {e}")
                    break
                    
        # Add a polite 3-second delay between standard requests to avoid angering Groq limits
        time.sleep(3)
        
        if not response:
            continue
            
        try:
            # getting the JSON output from the response
            json_output = response.choices[0].message.content
            
            # loading the JSON output
            data = json.loads(json_output)
            
            import re
            
            # Validate each triple individually to survive LLM hallucinations
            from master_schema import Triple
            for t_data in data.get("triples", []):
                try:
                    valid_triple = Triple(**t_data)
                    
                    # Prevent semantic bleed of Departments being mapped as members of the university
                    if focus == "faculty":
                        lower_subj = valid_triple.subject.lower()
                        if "department" in lower_subj or "centre" in lower_subj or "iiit" in lower_subj:
                            continue
                            
                        # Name string cleaning: Remove "Prof.", "Dr.", etc. to normalize Protege Nodes
                        clean_subj = re.sub(r'^(Prof\.|Dr\.|Mr\.|Mrs\.|Ms\.)\s*', '', valid_triple.subject, flags=re.IGNORECASE)
                        # Fix encoding issues by stripping unsafe uri characters
                        clean_subj = re.sub(r"['\.,]", '', clean_subj).strip()
                        
                        # Discard heavily fragmented Subject hallucination strings (like just "g" or "Rao")
                        if len(clean_subj.split()) == 1 and len(clean_subj) < 4:
                            continue
                            
                        valid_triple.subject = clean_subj
                            
                    all_triples.append(valid_triple)
                except Exception as ve:
                    # Skip the invalid triple instead of crashing the chunk
                    pass
        except Exception as e:
            print(f"Error parsing LLM JSON output on chunk {i+1}: {e}")

    return OntologyData(triples=all_triples)

if __name__ == "__main__":
    sample_text = "Prof. Sadagopan teaches Data Structures at IIIT Bangalore. He is a member of the Computer Science Department."
    print("Testing extraction on sample text...")
    result = extract_triples(sample_text)
    print(result.model_dump_json(indent=2))
