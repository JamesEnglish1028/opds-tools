import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger(__name__)

def extract_opensearch_template(data):
    """
    Extract OpenSearch template URL from OPDS JSON feed 'links' with rel='search'.
    """
    for link in data.get('links', []):
        if link.get('rel') == 'search' and 'href' in link:
            return link['href']
    return None

def extract_opensearch_template_from_xml(xml_text):
    """
    Extract OpenSearch template URL from an OpenSearch XML Description Document.
    """
    try:
        ns = {'os': 'http://a9.com/-/spec/opensearch/1.1/'}
        root = ET.fromstring(xml_text)
        # Find all Url elements in the OpenSearch namespace
        for url_elem in root.findall('os:Url', ns):
            # Usually the template attribute holds the search URL template
            template = url_elem.attrib.get('template')
            if template:
                return template
    except ET.ParseError:
        # XML was malformed or parsing failed
        pass
    return None

from xml.etree import ElementTree

def extract_entries_from_opensearch_response(xml_text):
    try:
        root = ElementTree.fromstring(xml_text)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = []

        for entry in root.findall('atom:entry', ns):
            title = entry.find('atom:title', ns)
            link = entry.find('atom:link', ns)
            summary = entry.find('atom:summary', ns)

            entries.append({
                "title": title.text if title is not None else "No Title",
                "link": link.get("href") if link is not None else None,
                "summary": summary.text if summary is not None else None
            })

        return entries

    except Exception as e:
        print("Failed to parse OpenSearch XML response:", e)
        return []
