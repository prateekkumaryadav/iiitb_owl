import requests
from bs4 import BeautifulSoup

def scrape_text_from_url(url: str) -> str:
    """
    Fetches the content of the URL, removes scripts and styles,
    and returns a clean string of text.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script and style elements
    for script_or_style in soup(["script", "style", "header", "footer", "nav"]):
        script_or_style.decompose()

    # Get text and collapse whitespace
    text = soup.get_text(separator=' ')
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    clean_text = ' '.join(chunk for chunk in chunks if chunk)
    
    return clean_text

from urllib.parse import urlparse, urljoin

def get_internal_links(base_url: str) -> list:
    """
    Crawls the base_url. Extracts and filters all internal links
    to avoid crawling entire unrelated domains.
    Returns a unique list of valid academic URLs.
    """
    try:
        response = requests.get(base_url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error checking links on {base_url}: {e}")
        return []
    
    soup = BeautifulSoup(response.text, "html.parser")
    domain = urlparse(base_url).netloc
    
    links = set()
    keywords = ["faculty", "course", "academic", "department", "program", "research"]
    
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        full_url = urljoin(base_url, href)
        parsed_url = urlparse(full_url)
        
        # Only keep links within the same domain
        if parsed_url.netloc == domain:
            # Drop anchors
            clean_url = full_url.split('#')[0]
            # Ensure it's relevant
            if any(kw in clean_url.lower() for kw in keywords):
                links.add(clean_url)
                
    return list(links)

if __name__ == "__main__":
    test_url = "https://www.iiitb.ac.in/faculty"
    print(f"Scraping: {test_url}")
    text = scrape_text_from_url(test_url)
    print(f"Extracted {len(text)} characters.")
    print("Preview:", text[:500])
