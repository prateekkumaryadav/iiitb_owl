# importing the required modules

# requests for fetching the content of the URL
import requests

# BeautifulSoup for parsing the HTML content
from bs4 import BeautifulSoup

# urlparse and urljoin for parsing and joining the URLs
from urllib.parse import urlparse, urljoin

# function for scraping the text data from the URL
def scrape_text_from_url(url: str) -> str:
    """
    Fetches the content of the URL, removes scripts and styles,
    and returns a clean string of text.
    """
    # try block for handling the errors
    try:
        # fetching the content of the URL
        response = requests.get(url, timeout=15)

        # checking if the content is fetched successfully
        response.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

    # parsing the HTML content
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove script and style elements for cleaning the text data
    for script_or_style in soup(["script", "style", "header", "footer", "nav"]):
        script_or_style.decompose()

    # Getting text and collapsing whitespace for cleaning the text data
    text = soup.get_text(separator=' ')
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    clean_text = ' '.join(chunk for chunk in chunks if chunk)
    
    # returning the clean text data for the LLM to process it further
    return clean_text

# function for getting the internal links from the base URL
def get_internal_links(base_url: str, focus: str = "all") -> list:
    """
    Crawls the base_url. Extracts and filters all internal links
    to avoid crawling entire unrelated domains.
    Returns a unique list of valid academic URLs.
    """
    # try block for handling the errors
    try:
        # fetching the content of the URL
        response = requests.get(base_url, timeout=15)

        # checking if the content is fetched successfully
        response.raise_for_status()
    except Exception as e:
        print(f"Error checking links on {base_url}: {e}")
        return []
    
    # parsing the HTML content
    soup = BeautifulSoup(response.text, "html.parser")

    # getting the domain of the URL
    domain = urlparse(base_url).netloc
    
    # creating a set for storing the links, set is used to store unique links got from the URL
    links = set()
    
    # checking the focus of the LLM
    if focus == "faculty":
        # keywords for faculty for crawling passed to the LLM
        keywords = ["faculty", "people", "professor"]
    elif focus == "courses":
        # keywords for courses for crawling passed to the LLM
        keywords = ["course", "academic", "department", "program", "degree"]
    else:
        # else for all(future scope)
        # keywords for all
        keywords = ["faculty", "course", "academic", "department", "program", "research"]
    
    # iterating over all the anchor tags
    for a_tag in soup.find_all("a", href=True):
        # getting the href attribute
        href = a_tag["href"].strip()

        # joining the base URL with the href
        full_url = urljoin(base_url, href)
        
        # parsing the URL
        parsed_url = urlparse(full_url)
        
        # Only keep links within the same domain
        if parsed_url.netloc == domain:
            # Drop anchors
            clean_url = full_url.split('#')[0]
            # Ensure it's relevant
            if any(kw in clean_url.lower() for kw in keywords):
                links.add(clean_url)
                
    # returning the list of links
    return list(links)

if __name__ == "__main__":
    test_url = "https://www.iiitb.ac.in/faculty"
    print(f"Scraping: {test_url}")
    text = scrape_text_from_url(test_url)
    print(f"Extracted {len(text)} characters.")
    print("Preview:", text[:500])