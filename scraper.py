# scraper.py

# Fetches and cleans text from a faculty profile page.
# Strips site-wide navigation, headers, footers, and sidebars so the
# extractor only sees the actual profile content.

# Imports
# requests is used to fetch the web page
import requests

# BeautifulSoup is used to parse the HTML content
from bs4 import BeautifulSoup, Tag as BS4Tag

# urlparse and urljoin are used to parse and join URLs
from urllib.parse import urlparse, urljoin

# Primary scraper — faculty profile page
# Function to fetch and clean text from a faculty profile page
def scrape_faculty_page(url: str) -> str:
    """
    Fetch a faculty profile URL and return only the biography / profile content
    as clean plain text, with all navigation boilerplate removed.
    """
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"[Scraper] Error fetching {url}: {e}")
        return ""

    soup = BeautifulSoup(response.text, "html.parser")

    # Step 1: Nuke elements that are definitely boilerplate
    
    # Remove script, style, and noscript tags
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    
    # Remove header, footer, nav, and aside tags
    for tag in soup.find_all(["header", "footer", "nav", "aside"]):
        tag.decompose()

    # Remove elements by common CSS class / id patterns for nav menus.
    # IMPORTANT: collect tags into a list first, THEN decompose — never mutate
    # the live iterator because it can produce NoneType nodes mid-loop.
    nav_hints = [
        "navbar", "nav-", "menu", "sidebar", "breadcrumb",
        "header", "footer", "topbar", "dropdown", "mobile-menu",
    ]
    tags_to_remove = []
    for tag in soup.find_all(True):
        # Guard: skip NavigableString and other non-Tag objects
        if not isinstance(tag, BS4Tag):
            continue
        cls = " ".join(tag.get("class", []))
        tag_id = tag.get("id", "")
        combined = (cls + " " + tag_id).lower()
        if any(hint in combined for hint in nav_hints):
            tags_to_remove.append(tag)
    for tag in tags_to_remove:
        tag.decompose()

    # Step 2: Try to isolate the main content container
    main_content = None

    # Heuristic 1: <main> tag
    # this heuristic is used to find the main content of the page
    main_content = soup.find("main")

    # Heuristic 2: common content div IDs / classes
    if not main_content:
        for selector in ["#content", "#main-content", ".faculty-profile",
                          ".profile-content", ".page-content", ".container-content",
                          ".faculty-details", "article"]:
            main_content = soup.select_one(selector)
            if main_content:
                break

    # Heuristic 3: find the largest block of paragraph text
    # finding the largest block of text helps to remove the noise from the page
    if not main_content:
        candidates = sorted(
            soup.find_all(["div", "section"]),
            key=lambda t: len(t.get_text()),
            reverse=True
        )
        main_content = candidates[0] if candidates else None

    target = main_content if main_content else soup

    # Step 3: Extract and clean text
    text = target.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]

    # First pass: filter out obvious noise lines
    seen_lines: set[str] = set()
    cleaned_lines = []
    prev_blank = False

    for line in lines:
        if not line:
            if not prev_blank:
                cleaned_lines.append("")
            prev_blank = True
            continue

        prev_blank = False

        # Skip very short lines
        if len(line) < 4:
            continue

        # Skip bare URLs and javascript: fragments
        # this is used to skip the lines that are bare URLs or javascript: fragments
        if line.startswith("http") or line.startswith("javascript:"):
            continue

        # Skip lines that are pure navigation duplicates.
        # The IIITB site repeats the nav menu 5-6 times; keep only the first
        # occurrence of each unique line to collapse repetition.
        lower = line.lower()
        if lower in seen_lines:
            continue
        seen_lines.add(lower)

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


# Generic scraper (kept for compatibility with depth crawling)
# this is used to scrape the text from the web page
def scrape_text_from_url(url: str) -> str:
    """
    Generic page scraper — delegates to the faculty page scraper.
    """
    return scrape_faculty_page(url)


# Internal-links crawler (used by depth mode in main.py)
# this is used to crawl the internal links of the web page
def get_internal_links(base_url: str, focus: str = "all") -> list:
    """
    Crawls base_url for internal links that match the given focus keyword set.
    Returns a deduplicated list of relevant URLs on the same domain.
    """
    try:
        response = requests.get(base_url, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"[Scraper] Error checking links on {base_url}: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    domain = urlparse(base_url).netloc

    if focus == "faculty":
        keywords = ["faculty", "people", "professor", "staff", "researcher"]
    elif focus == "courses":
        keywords = ["course", "academic", "department", "program", "degree", "module"]
    else:
        # Broader set of keywords to discover a wider variety of institutional knowledge
        keywords = ["faculty", "course", "academic", "department", "program", "research", "publications", "projects", "events", "news", "about"]

    links = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.netloc == domain:
            clean_url = full_url.split("#")[0]
            if any(kw in clean_url.lower() for kw in keywords):
                links.add(clean_url)

    return list(links)


# Manual test
# if __name__ == "__main__":
#     url = "https://www.iiitb.ac.in/faculty/debabrata-das"
#     print(f"[Test] Scraping: {url}")
#     text = scrape_faculty_page(url)
#     print(f"[Test] Extracted {len(text)} characters.")
#     print("\n--- First 2000 chars ---\n")
#     print(text[:2000])