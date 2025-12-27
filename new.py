import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime
import json
import os


HEADERS = {"User-Agent": "AI-Web-Scraper/1.0"}
MAX_PAGES = 10
TIMEOUT = 8

KEYWORDS = {
    "about": ["about", "who we are", "company", "our story"],
    "product": ["product", "solution", "service", "platform"],
    "contact": ["contact", "get in touch", "reach us"],
    "career": ["career", "jobs", "hiring"]
}

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return BeautifulSoup(r.text, "lxml"), None
    except Exception as e:
        return None, str(e)

def classify_page(text):
    scores = {k: 0 for k in KEYWORDS}
    text = text.lower()
    for k, words in KEYWORDS.items():
        for w in words:
            if w in text:
                scores[k] += 1
    return max(scores, key=scores.get) if max(scores.values()) > 0 else "unknown"

def extract_emails(text):
    return list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}", text)))

def extract_phones(text):
    return list(set(re.findall(r"\+?\d[\d\s().-]{7,}", text)))

def extract_socials(links):
    socials = {}
    for l in links:
        if "linkedin.com" in l: socials["LinkedIn"] = l
        if "twitter.com" in l or "x.com" in l: socials["Twitter/X"] = l
        if "instagram.com" in l: socials["Instagram"] = l
        if "youtube.com" in l: socials["YouTube"] = l
    return socials

def smart_summary(text):
    lines = [l.strip() for l in text.split(".") if len(l.split()) > 6]
    return ". ".join(lines[:3]) + "." if lines else "Not enough content to summarize."

def scrape(url):
    visited = set()
    pages = []
    errors = []

    result = {
        "identity": {},
        "business_summary": {},
        "contact": {},
        "signals": {},
        "metadata": {}
    }

    soup, err = fetch(url)
    if err:
        return {"fatal_error": err}

    visited.add(url)
    pages.append(url)

    homepage_text = soup.get_text(" ", strip=True)

    result["identity"]["company_name"] = soup.title.text if soup.title else "Not found"
    result["identity"]["website"] = url

    result["contact"]["emails"] = extract_emails(homepage_text)
    result["contact"]["phones"] = extract_phones(homepage_text)

    links = [urljoin(url, a["href"]) for a in soup.find_all("a", href=True)]
    internal_links = [l for l in links if urlparse(l).netloc == urlparse(url).netloc]

    about_text = []
    product_text = []

    for link in internal_links:
        if link in visited or len(visited) >= MAX_PAGES:
            continue

        page, err = fetch(link)
        visited.add(link)
        pages.append(link)

        if err:
            errors.append({link: err})
            continue

        text = page.get_text(" ", strip=True)
        page_type = classify_page(text)

        if page_type == "about":
            about_text.append(text)
        elif page_type == "product":
            product_text.append(text)
        elif page_type == "contact":
            result["contact"]["contact_page"] = link
        elif page_type == "career":
            result["signals"]["careers_page"] = link

    if about_text:
        result["business_summary"]["what_they_do"] = smart_summary(" ".join(about_text))
        result["business_summary"]["source"] = "about page (inferred)"
    else:
        result["business_summary"]["what_they_do"] = smart_summary(homepage_text)
        result["business_summary"]["source"] = "homepage (fallback)"

    if product_text:
        result["business_summary"]["offerings"] = smart_summary(" ".join(product_text))

    result["signals"]["social_links"] = extract_socials(internal_links)

    result["metadata"] = {
        "timestamp": datetime.utcnow().isoformat(),
        "pages_crawled": pages,
        "errors": errors,
        "limitations": "HTML-only scraping; JS-rendered content may be missing"
    }

    return result


def save_to_json(data, url):
    domain = urlparse(url).netloc.replace("www.", "")
    filename = f"{domain}_scrape.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    return os.path.abspath(filename)


if __name__ == "__main__":
    import sys

    url = sys.argv[1]
    output = scrape(url)

    file_path = save_to_json(output, url)

    print("Scraping completed.")
    print(f"Data saved to: {file_path}")

    
