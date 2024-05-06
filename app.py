from litgpt_wrapper import load_model, generate_candidate, promptify
from pathlib import Path

import spacy
from collections import Counter

import string

from flask import Flask, render_template, request, jsonify
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)

# load the model
fabric, model, tokenizer = load_model(Path('./checkpoints/google/gemma-2b-it'), 4096)

# Create a translation table that maps all punctuation to None
translator = str.maketrans('', '', string.punctuation)

# Load the small English model
nlp = spacy.load('en_core_web_sm')

# PubMed E-utilities URLs
EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

def fetch_pubmed_abstracts(query):
    """Fetch abstracts from PubMed based on the given query and return structured tuples."""
    # Retrieve the IDs of the articles
    search_params = {
        "db": "pubmed",
        "term": query,
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
                                    "Please answer the following question based on the provided context. "
                                    + "Do not include any information that is not present in the context. "
                                    + "Write a professional answer. "
                                    + "Try your best within the information contained in the context.",
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

    print(f'search terms: {request.json.get("search_terms")}')

    articles = fetch_pubmed_abstracts(request.json.get('search_terms'))
    response_data = [
        {"title": title, "authors": authors, "abstract": abstract, "year": year}
        for title, authors, abstract, year in articles
    ]

    # Combine all abstracts for summarization.
    # Do it one abstract at a time until we hit the limit of 2,000 words.
    # TODO: parallelize it.
    combined_abstracts = ""
    for article in response_data:
        abstract_summary = generate_candidate(fabric, model, tokenizer,
                                     "Please summarize the context into two sentences, "
                                     + "while considering the question. "
                                     + "Write a professional answer. "
                                     + "Do not converse with the user. ", 
                                     query, article['abstract'])
        combined_abstracts += "\n\n"
        combined_abstracts += abstract_summary

        print(f'Abstract summary: {abstract_summary}')

    # remove any line that starts with "Sure"
    combined_abstracts = "\n".join([line for line in combined_abstracts.split("\n") if not line.startswith("Sure")])
    # remove any line that starts with "Here's"
    combined_abstracts = "\n".join([line for line in combined_abstracts.split("\n") if not line.startswith("Here's")])    
    # remove any empty line
    combined_abstracts = "\n".join([line for line in combined_abstracts.split("\n") if line.strip()])

    # print(f'Combined abstracts: {combined_abstracts}')

    summary = generate_summary(query, combined_abstracts) if combined_abstracts else "No sufficient data for summarization."

    print(f'Summary: {summary}')

    # remove any line that starts with "Sure,"
    summary = "\n".join([line for line in summary.split("\n") if not line.startswith("Sure,")])

    return jsonify({"articles": response_data, "summary": summary})

@app.route('/extract_terms', methods=['POST'])
def extract_terms():
    question = request.json.get('question')
    if not question:
        return jsonify({"error": "No question provided"}), 400

    keywords = extract_keywords(question)

    print(f'Original query: {question}')
    print(f'Keywords: {keywords}')

    return jsonify({"terms": keywords})

# Function to extract keywords
def extract_keywords(text, top_n=10):
    # Process the input text with spaCy
    doc = nlp(text)

    # Filter out stop words and punctuation, and keep only nouns and proper nouns
    filtered_tokens = [token.text for token in doc if not token.is_stop and not token.is_punct and token.pos_ in ['NOUN', 'PROPN']]

    # Use Counter to get the most common tokens
    return [word for word, count in Counter(filtered_tokens).most_common(top_n)]

if __name__ == '__main__':
    app.run(debug=False, port=8000)