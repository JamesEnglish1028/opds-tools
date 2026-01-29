import logging
import csv

logger = logging.getLogger(__name__)

#< -- helper functions -->

#< -- FUNCTION Flatten Access Value -->

def flatten_access_value(value):
    # Treat None, string "None", empty string, or empty list as missing
    if value is None or value == '' or value == 'None' or value == []:
        return None
    if isinstance(value, list):
        return ', '.join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value)
    return str(value)

def flatten_contained_values(value):
    # Trea Non, String "None", empty string, or empty list as missing
    if value is None or value == '' or value == 'None' or value == []:
        return None
    if isinstance(value,list):
        return ', '.join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dump(value)
    return str (value)
    

#< -- FUNCTION is ISBN -->

def is_isbn(urn):
    return isinstance(urn, str) and urn.lower().startswith("urn:isbn:")

#< -- FUNCTION URN to URL -->

def urn_to_url(urn):
    match = re.match(r'^urn:isbn:(\d{9,13}X?)$', urn, re.I)
    if match:
        isbn = match.group(1)
        return f"https://isbnsearch.org/isbn/{isbn}"

    return None

#< -- FUNCTION  PARSE Alt Identifiers --->

def parse_alt_identifier(alt_id):
    # Handle dict-based identifier first
    if isinstance(alt_id, dict):
        value = alt_id.get("value", "")
        id_type = alt_id.get("type", "unknown")
        return parse_alt_identifier(value)  # Recurse with just the value string

    # Now assume alt_id is a string
    if not isinstance(alt_id, str):
        return {
            "value": str(alt_id),
            "type": "Unknown",
            "url": None
        }

    alt_id = alt_id.lower().strip()

    if alt_id.startswith("urn:isbn:"):
        isbn = alt_id.replace("urn:isbn:", "")
        return {
            "value": alt_id,
            "type": "ISBN",
            "isbn_13": isbn if len(isbn) == 13 else "",
            "isbn_10": isbn if len(isbn) == 10 else "",
            "url": f"https://isbnsearch.org/isbn/{isbn}"
        }
    elif alt_id.startswith("doi:") or alt_id.startswith("urn:doi:"):
        doi = alt_id.replace("urn:doi:", "").replace("doi:", "")
        return {
            "value": alt_id,
            "type": "DOI",
            "url": f"https://doi.org/{doi}"
        }
    elif alt_id.startswith("hdl:") or alt_id.startswith("urn:hdl:"):
        handle = alt_id.replace("urn:hdl:", "").replace("hdl:", "")
        return {
            "value": alt_id,
            "type": "Handle",
            "url": f"https://hdl.handle.net/{handle}"
        }
    elif alt_id.startswith("issn:") or alt_id.startswith("urn:issn:"):
        issn = alt_id.replace("urn:issn:", "").replace("issn:", "")
        return {
            "value": alt_id,
            "type": "ISSN",
            "url": f"https://portal.issn.org/resource/ISSN/{issn}"
        }
    elif alt_id.startswith("ark:") or alt_id.startswith("urn:ark:"):
        ark = alt_id.replace("urn:ark:", "").replace("ark:", "")
        return {
            "value": alt_id,
            "type": "ARK",
            "url": f"https://n2t.net/ark:/{ark}"
        }
    elif alt_id.startswith("ocn:") or alt_id.startswith("urn:ocn:"):
        ocn = alt_id.replace("urn:ocn:", "").replace("ocn:", "")
        return {
            "value": alt_id,
            "type": "OCLC",
            "url": f"https://www.worldcat.org/oclc/{ocn}"
        }
    elif alt_id.startswith("urn:proquest.com/document-id/"):
        doc_id = alt_id.replace("urn:proquest.com/document-id/", "")
        return {
            "value": alt_id,
            "type": "ProQuest",
            "url": f"https://www.proquest.com/docview/{doc_id}"
        }
    else:
        return {
            "value": alt_id,
            "type": "Unknown",
            "url": None
        }

from urllib.parse import urlparse, urlunparse

def get_base_url(url):
    """
    Extracts the base URL (scheme + netloc) from a full URL.
    Example: https://example.org/opds/feed -> https://example.org
    """
    parts = urlparse(url)
    return urlunparse((parts.scheme, parts.netloc, '', '', '', ''))

####################
#  ONIX_TO_OPDS.py #

import json
import os
import csv
import mimetypes
import logging
import html  # This imports the html module for unescaping HTML entities



# --- Utility function extract text---
def extract_text(element, path, ns=None):
    found = element.find(path, ns) if ns else element.find(path)
    return found.text.strip() if found is not None and found.text else None

def load_onix_role_mapping():
    path = os.path.join(os.path.dirname(__file__), "..", "static", "dictionaries", "onix_to_marc.json")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        print(f"⚠️ Missing role mapping file: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

ONIX_ROLE_MAP = load_onix_role_mapping()

def map_onix_role_to_term(onix_code):
    return ONIX_ROLE_MAP.get(onix_code, "other")

# BISAC lookup
csvfile = {}
BISAC_LOOKUP = {}
BISAC_CSV_PATH = os.path.join(os.path.dirname(__file__), "../static/dictionaries/bisac_subjects.csv")

try:
    with open(BISAC_CSV_PATH, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Ensure the description is decoded properly if any encoding issues (like \u0026) exist
            description = row['description']
            description = html.unescape(description)  # Decode any HTML entities like \u0026 to '&'
            
            BISAC_LOOKUP[row['code']] = description
except FileNotFoundError:
    logging.warning("⚠️ BISAC subject CSV not found at expected location.")

def guess_mime_type(filename):
    mime, _ = mimetypes.guess_type(filename)
    return mime or "image/jpeg"

# --- THEMA lookup ---
THEMA_LOOKUP = {}
THEMA_JSON_PATH = os.path.join(os.path.dirname(__file__), "../static/dictionaries/20250410_Thema_v1.6_en.json")
try:
    with open(THEMA_JSON_PATH, encoding='utf-8') as f:
        data = json.load(f)
        for code_obj in data["CodeList"]["ThemaCodes"]["Code"]:
            code = code_obj.get("CodeValue")
            label = code_obj.get("CodeDescription")
            if code and label:
                THEMA_LOOKUP[code] = label
except FileNotFoundError:
    logging.warning("⚠️ THEMA subject JSON not found at expected location.")


# --- Subject label mappers ---
def map_bisac_code_to_label(code):
    return BISAC_LOOKUP.get(code)

def map_thema_code_to_label(code):
    return THEMA_LOOKUP.get(code)
    

# --- Extract subject blocks ---
def extract_subjects(product, tag_prefix, ns):
    subjects = []
    for subj in product.findall(f"{tag_prefix}DescriptiveDetail/{tag_prefix}Subject", ns):
        code = extract_text(subj, f"{tag_prefix}SubjectCode", ns)
        scheme_id = extract_text(subj, f"{tag_prefix}SubjectSchemeIdentifier", ns)
        name = None
        scheme_uri = None

        if scheme_id == "10":  # BISAC
            scheme_uri = "https://www.bisg.org/#bisac"
            name = map_bisac_code_to_label(code) or f"BISAC Category {code}"
        elif scheme_id == "93":  # THEMA
            scheme_uri = "https://www.editeur.org/151/thema/"
            name = map_thema_code_to_label(code) or f"THEMA Category {code}"

            # Ensure the ampersand is correctly decoded (in case of escaping like \u0026)
            if name:
                name = html.unescape(name)  # Decode any HTML/Unicode escape sequences like \u0026

        if code:
            subject_obj = {
                "code": code
            }
            if name:
                subject_obj["name"] = name
            if scheme_uri:
                subject_obj["scheme"] = scheme_uri
            subjects.append(subject_obj)
    return subjects

