# Automated Ontology Generation Pipeline

This project is an end-to-end, automated pipeline designed to crawl institutional websites, extract raw text data, and utilize Groq's Llama-3.3-70b-versatile Large Language Model to generate structured semantic relationships (triples). These triples are then compiled into a valid OWL format, mapping diverse data sources into a unified semantic format.

## Setup Instructions

### Prerequisites
- Python 3.8+
- [Groq API Key](https://console.groq.com/keys)

### 1. Clone the repository
1. Clone this repository to your local machine.

### 2. Set up Virtual Environment
It is recommended to use a virtual environment to manage dependencies:
```bash
python -m venv venv
```

Activate the virtual environment:
- On macOS and Linux:
  ```bash
  source venv/bin/activate
  ```
- On Windows:
  ```bash
  venv\Scripts\activate
  ```

### 3. Install Dependencies
Install the required Python packages (such as `requests`, `beautifulsoup4`, `groq`, `pydantic`, and `rdflib`):
```bash
pip install -r requirements.txt
```

### 4. Provide Credentials
You need a Groq API Key to run the extraction pipeline. 
Export your API key as an environment variable in your terminal session before running the application:

- On macOS and Linux:
  ```bash
  export GROQ_API_KEY="your_groq_api_key_here"
  ```
- On Windows (Command Prompt):
  ```cmd
  set GROQ_API_KEY="your_groq_api_key_here"
  ```
- On Windows (PowerShell):
  ```powershell
  $env:GROQ_API_KEY="your_groq_api_key_here"
  ```

Alternatively, you can create a `.env` file and use a package like `python-dotenv` if you modify `extractor.py` to load from `.env`. (The provided `.gitignore` automatically ignores `.env` files to prevent leaking your keys).

## Usage

Run the main pipeline by executing `main.py` from the command line:

```bash
python main.py
```

### Arguments:

- `--url`: The target URL to crawl and scrape data from. Default is `https://www.iiitb.ac.in/faculty`.
- `--output`: Output OWL file name for the generated ontology graph data. Default is `iiitb_ontology.owl`.

Example usage with custom arguments:

```bash
python main.py --url https://www.example.edu/about --output example_ontology.owl
```

### What happens when you run it?
1. **Scraping** (`scraper.py`): The pipeline fetches text data from the provided URL, cleaning away scripts and CSS styles.
2. **LLM Extraction** (`extractor.py`): The cleaned text is formatted and sent to the Groq API. The LLM extracts triples strictly according to the Pydantic schema (`master_schema.py`).
3. **OWL Generation** (`owl_generator.py`): Uses RDFLib to construct a knowledge graph from the extracted triples and serializes it to an `.owl` file.

## Verification
You can load the generated `.owl` file (e.g., `iiitb_ontology.owl`) into ontology tools like [Protégé](https://protege.stanford.edu/) to visually verify the structured data.
