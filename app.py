from litgpt_wrapper import load_model, generate_candidate, promptify
from pathlib import Path

from flask import Flask, render_template, request, jsonify
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# load the model
fabric, model, tokenizer = load_model(Path('./checkpoints/microsoft/phi-1_5'), 1024)

# PubMed E-utilities URLs
EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

def fetch_pubmed_abstracts(query):
    """Fetch abstracts from PubMed based on the given query and return structured tuples."""

    rewritten_query = generate_candidate(fabric, model, tokenizer, 
                                         "Please extract and list search terms from the following question. "
                                         + "It must be the list of search terms that you would use to search for the answer to the question. "
                                         + "Do not include any punctuation or special characters.", 
                                         query)

    print(f"Rewritten query: {rewritten_query}")

    # Retrieve the IDs of the articles
    search_params = {
        "db": "pubmed",
        "term": rewritten_query,
        "retmode": "json",
        "retmax": 10
    }
    search_response = requests.get(EUTILS_BASE_URL, params=search_params).json()
    article_ids = search_response.get("esearchresult", {}).get("idlist", [])

    # Fetch articles' details
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(article_ids),
        "retmode": "xml",
        "rettype": "abstract"
    }
    fetch_response = requests.get(EFETCH_URL, params=fetch_params).text

    # Parse XML response and create structured data
    root = ET.fromstring(fetch_response)
    articles = []
    for article in root.findall(".//PubmedArticle"):
        title = article.find(".//ArticleTitle").text if article.find(".//ArticleTitle") is not None else "N/A"
        year = article.find(".//PubDate/Year").text if article.find(".//PubDate/Year") is not None else "N/A"

        # Extract authors
        authors = []
        for author in article.findall(".//Author"):
            last_name = author.find("LastName")
            fore_name = author.find("ForeName")
            if last_name is not None and fore_name is not None:
                authors.append(f"{fore_name.text} {last_name.text}")
        authors = ', '.join(authors) if authors else "N/A"

        # Extract the abstract text
        abstract_sections = article.findall(".//AbstractText")
        abstract = " ".join([sec.text.strip() for sec in abstract_sections if sec.text]) if abstract_sections else "N/A"

        articles.append((title, authors, abstract, year))

    return articles

def generate_summary(query, abstracts):
    """Generate a summary for the given query and abstracts."""
    summary = generate_candidate(fabric, model, tokenizer,
                                    "Please answer the following question based on the provided abstracts in one paragraph. "
                                    + "Do not include any information that is not present in the abstracts.",
                                    query, abstracts)
    return summary

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_abstracts', methods=['POST'])
def get_abstracts():
    query = request.json.get('question')
    if not query:
        return jsonify({"error": "No query provided"}), 400

    articles = fetch_pubmed_abstracts(query)
    response_data = [
        {"title": title, "authors": authors, "abstract": abstract, "year": year}
        for title, authors, abstract, year in articles
    ]

    # Combine all abstracts for summarization
    combined_abstracts = " ".join([article['abstract'] for article in response_data if article['abstract'] != "N/A"])
    summary = generate_summary(query, combined_abstracts) if combined_abstracts else "No sufficient data for summarization."

    return jsonify({"articles": response_data, "summary": summary})

if __name__ == '__main__':
    app.run(debug=False)