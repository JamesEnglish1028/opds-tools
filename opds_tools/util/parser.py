from opds_tools.util.helpers import flatten_access_value, parse_alt_identifier
from urllib.parse import urlparse, urljoin, parse_qs
import bleach
import logging

logger = logging.getLogger(__name__)

# <-- FUNCTION Extraction of OPDS Data -->
def extract_opds_data(data, base_url=None):
    items = []
    publications = data.get('publications') or data.get('items') or []

    for pub in publications:
        metadata = pub.get('metadata', {})
        title = metadata.get('title', 'Untitled')
        subtitle = metadata.get('subtitle', 'None')
        identifier = metadata.get('identifier', '')
        published = metadata.get('published', '')
        language = metadata.get('language', '')
        series = metadata.get("series",'')
        license = metadata.get('license','')
        
        # Extract and simplify the publication type
        raw_type = metadata.get('@type') or metadata.get('type')
        type_value = None
        if isinstance(raw_type, str):
            type_value = raw_type.split('/')[-1]  # Get "EBook" from "http://schema.org/EBook"
        elif isinstance(raw_type, list):
            # Some feeds might provide multiple types
            type_value = ', '.join(t.split('/')[-1] for t in raw_type if isinstance(t, str))


        # Author
        raw_authors = metadata.get('authors') or metadata.get('author')
        if isinstance(raw_authors, str):
            authors = raw_authors
        elif isinstance(raw_authors, dict):
            authors = raw_authors.get('name', '')
        elif isinstance(raw_authors, list):
            authors = ', '.join([
                a.get('name', '') if isinstance(a, dict) else str(a)
                for a in raw_authors
            ])
        else:
            authors = ''

        # Publisher and Publisher Links
        raw_publisher = metadata.get('publisher', '')
        publisher = ''
        publisher_links = []

        if isinstance(raw_publisher, str):
            publisher = raw_publisher

        elif isinstance(raw_publisher, dict):
            publisher = raw_publisher.get('name', '')
            for link in raw_publisher.get('links', []):
                if isinstance(link, dict) and link.get('href'):
                    publisher_links.append({
                        'href': urljoin(base_url, link['href']) if base_url else link['href'],
                        'type': link.get('type'),
                        'title': link.get('title', ''),
                        'rel': link.get('rel', '')
                    })

                elif isinstance(raw_publisher, list):
                    publishers = []
                    for p in raw_publisher:
                        if isinstance(p, dict):
                            name = p.get('name', '')
                            if name:
                                publishers.append(name)
                            for link in p.get('links', []):
                                if isinstance(link, dict) and link.get('href'):
                                    publisher_links.append({
                                        'href': urljoin(base_url, link['href']) if base_url else link['href'],
                                        'type': link.get('type'),
                                        'title': link.get('title', ''),
                                        'rel': link.get('rel', '')
                                    })
                        else:
                            publishers.append(str(p))
                    publisher = ', '.join(publishers)


        # Publication Type (e.g., EBook)
        pub_type = metadata.get('@type', '')

        # Subjects
        subject_data = metadata.get('subject', [])
        if isinstance(subject_data, str):
            subjects = subject_data
        elif isinstance(subject_data, list):
            subjects = [
                s.get('name', '') if isinstance(s, dict) else str(s)
                for s in subject_data
            ]
        elif isinstance(subject_data, dict):
            subjects = subject_data.get('name', '')
        else:
            subjects = ''

        # belongsTo
        belongs_to_parts = []
        belongs_to_data = metadata.get('belongsTo', {})
        if isinstance(belongs_to_data, dict):
            for key, value in belongs_to_data.items():
                if isinstance(value, str):
                    belongs_to_parts.append({'label': key.title(), 'name': value, 'url': None})
                elif isinstance(value, dict):
                    name = value.get('name', '')
                    pos = value.get('position')
                    links = value.get('links', [])
                    url = None
                    for link in links:
                        if isinstance(link, dict) and link.get('rel') == 'self':
                            url = link.get('href')
                            break
                    if name:
                        label = f"{key.title()} (Position {pos})" if pos is not None else key.title()
                        belongs_to_parts.append({'label': label, 'name': name, 'url': url})
                elif isinstance(value, list):
                    for v in value:
                        if isinstance(v, dict):
                            name = v.get('name', '')
                            url = None
                            for link in v.get('links', []):
                                if isinstance(link, dict) and link.get('rel') == 'self':
                                    url = link.get('href')
                                    break
                            if name:
                                belongs_to_parts.append({'label': key.title(), 'name': name, 'url': url})
                        else:
                            belongs_to_parts.append({'label': key.title(), 'name': str(v), 'url': None})

        # Image
        image_info = None
        for link in pub.get('images', []):
            if isinstance(link, dict):
                href = link.get('href')
                if href:
                    image_info = {
                        'href': urljoin(base_url, href) if base_url else href,
                        'type': link.get('type'),
                        'height': link.get('height'),
                        'width': link.get('width')
                    }
                    break


        # extract and clean Description
            ALLOWED_TAGS = [
            'p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'a', 'b', 'i', 'u'
            ]
            ALLOWED_ATTRIBUTES = {
            'a': ['href', 'title', 'target', 'rel']
            }

            raw_description = metadata.get('description', '')

            sanitized_description = bleach.clean(
                raw_description,
                tags=ALLOWED_TAGS,
                attributes=ALLOWED_ATTRIBUTES,
                strip=True
            )

        # altIdentifier
        alt_identifiers_raw = metadata.get('altIdentifier', [])
        if not isinstance(alt_identifiers_raw, list):
            alt_identifiers_raw = [alt_identifiers_raw] if alt_identifiers_raw else []
        alt_identifiers = [parse_alt_identifier(val) for val in alt_identifiers_raw]

        # Accessibility
        accessibility_data = metadata.get('accessibility', {})
        accessibility = {
            'conformsTo': flatten_access_value(accessibility_data.get('conformsTo')),
            'certification': flatten_access_value(accessibility_data.get('certification')),
            'accessMode': flatten_access_value(accessibility_data.get('accessMode')),
            'accessModeSufficient': flatten_access_value(accessibility_data.get('accessModeSufficient')),
            'feature': flatten_access_value(accessibility_data.get('feature')),
            'hazard': flatten_access_value(accessibility_data.get('hazard')),
            'summary': flatten_access_value(accessibility_data.get('summary')),
        }
        # Publication Links 
        
        # Initialize containers
        acquisition_links = []
        self_link = None

        for link in pub.get('links', []):
            if isinstance(link, dict):
                rel = link.get('rel', '')
                href = link.get('href')
                # Capture self link separately
                if rel == 'self':
                    self_link = urljoin(base_url, href) if base_url else href
                    continue  # Skip adding to acquisition_links

                type_ = link.get('type', '')
                if type_ and href:
                    acquisition_links.append({
                        'type': type_,
                        'rel': rel,
                        'href': urljoin(base_url, href) if base_url else href
                    })


        items.append({
            'title': title,
            'self_href': self_link,
            'subtitle': subtitle,
            'author': authors,
            'description' : metadata.get('description'),
            'publisher': publisher,
            'publisher_links':publisher_links,
            'published': published,
            'license': license,
            'identifier': identifier,
            'modified': metadata.get('modified'),
            'alt_identifier': alt_identifiers,
            'accessibility': accessibility,
            'subjects': subjects,
            'series': series,
            'language': language,
            'belongs_to': belongs_to_parts,
            'image': image_info,
            'publication_type': pub_type,
            'acquisition_links': acquisition_links,
            "contains": extract_contained_articles(metadata.get("contains")),
        })

    return items

#<-- FUNCTION: extract the facets --->
def extract_facet_collections(data):
    """
    Extracts facet groups from OPDS 2.0 feeds.
    Returns a list of facet groups, each with a title and list of links.
    """
    base_url = data.get("_base_url", "")
    facets = data.get("facets", [])

    facet_groups = []

    for facet in facets:
        group_title = facet.get("metadata", {}).get("title", "Untitled Facet")
        links = []

        for link in facet.get("links", []):
            links.append({
                "href": urljoin(base_url, link.get("href")),
                "title": link.get("title", "Untitled"),
                "type": link.get("type"),
                "numberOfItems": link.get("properties", {}).get("numberOfItems"),
            })

        facet_groups.append({
            "title": group_title,
            "links": links
        })

    return facet_groups


#<-- FUNCTION extract the paged feed links -->

def extract_navigation_links(data):
    nav_links = {
        'self': None, 'next': None, 'previous': None,
        'first': None, 'last': None,
        'current_page': None,
        'total_pages': None
    }

    for link in data.get('links', []):
        if isinstance(link, dict):
            rel = link.get('rel')
            href = link.get('href')
            if rel in nav_links:
                nav_links[rel] = href

    # Try to parse current page from self link
    if nav_links['self']:
        parsed = urlparse(nav_links['self'])
        params = parse_qs(parsed.query)
        current = params.get('currentPage', [None])[0]
        if current and current.isdigit():
            nav_links['current_page'] = int(current)

    if nav_links['last']:
        parsed = urlparse(nav_links['last'])
        params = parse_qs(parsed.query)
        total = params.get('currentPage', [None])[0]
        if total and total.isdigit():
            nav_links['total_pages'] = int(total)

    return nav_links

# Extract the Contains collection 
def extract_contained_articles(contains_obj):
    if not contains_obj:
        return None

    issue = contains_obj.get("issue", {})
    articles = issue.get("article", [])

    extracted_articles = []
    for article in articles:
        title = article.get("name")
        links = article.get("links", [])
        href = None
        for link in links:
            if link.get("rel") == "publication":
                href = link.get("href")
                break

        images = article.get("images", [])
        image_url = images[0].get("href") if images else None

        extracted_articles.append({
            "title": title,
            "href": href,
            "image": image_url,
        })

    return extracted_articles


def extract_catalog_metadata(data):
    """
    Extracts metadata fields from the OPDS catalog-level metadata object.
    Returns a dictionary with relevant fields.
    """
    metadata = data.get("metadata", {})
    links = data.get("links", [])

    # Find the authentication document link
    auth_document_url = None
    for link in links:
        if link.get("rel") == "http://opds-spec.org/auth/document":
            auth_document_url = link.get("href")
            break

    return {
        "feed_name": metadata.get("title", "Untitled Feed"),
        "number_of_items": metadata.get("numberOfItems"),
        "items_per_page": metadata.get("itemsPerPage"),
        "modified": metadata.get("modified"),
        "identifier": metadata.get("identifier"),
        "language": metadata.get("language"),
        "subtitle": metadata.get("subtitle"),
        "description": metadata.get("description"),
        "auth_document_url": auth_document_url
    }

def extract_catalog_links(data):
    """
    Extracts specific catalog-level links: search, authentication, and token endpoints.
    Returns a list of dictionaries with href, type, rel, and title (if available).
    """
    links = data.get("links", [])
    extracted_links = []

    # Define the rels we care about
    relevant_rels = {
        "search",
        "authentication",  # OPDS Authentication rel
        "http://opds-spec.org/auth/token",  # Token endpoint
        "http://opds-spec.org/auth/document",  # Authentication document
        "token_endpoint", #templated toekn endpoint
    }

    for link in links:
        rel = link.get("rel")
        if rel in relevant_rels:
            extracted_links.append({
                "href": link.get("href"),
                "type": link.get("type"),
                "rel": rel,
                "title": link.get("title")
            })

    return extracted_links


def extract_navigation_collections(data):
    """
    Extracts navigation collection links from an OPDS 2.0 feed.
    Returns a list of dicts with href, title, type, and rel.
    """
    base_url = data.get("_base_url", "")
    navigation = data.get("navigation", [])
    return [
        {
            "href": urljoin(base_url, link.get("href")),
            "title": link.get("title", "Untitled"),
            "type": link.get("type"),
            "rel": link.get("rel")
        }
        for link in navigation
        if "href" in link
    ]

from urllib.parse import urljoin

def extract_groups(data):
    """
    Extracts top-level OPDS 'groups' as an array of objects with metadata, links, navigation, and publications.
    Each group is returned as a dictionary.
    """
    base_url = data.get("_base_url", "")
    groups = data.get("groups", [])

    extracted = []

    for group in groups:
        group_data = {
            "title": group.get("metadata", {}).get("title", "Untitled Group"),
            "numberOfItems": group.get("metadata", {}).get("numberOfItems"),
            "links": [
                {
                    "href": urljoin(base_url, link.get("href")),
                    "type": link.get("type"),
                    "rel": link.get("rel")
                }
                for link in group.get("links", [])
                if "href" in link
            ],
            "navigation": [
                {
                    "href": urljoin(base_url, nav.get("href")),
                    "title": nav.get("title", "Untitled"),
                    "type": nav.get("type"),
                    "rel": nav.get("rel")
                }
                for nav in group.get("navigation", [])
                if "href" in nav
            ],
            "publications": [
                {
                    "title": pub.get("metadata", {}).get("title", "Untitled"),
                    "author": pub.get("metadata", {}).get("author"),
                    "type": pub.get("metadata", {}).get("@type"),
                    "identifier": pub.get("metadata", {}).get("identifier"),
                    "language": pub.get("metadata", {}).get("language"),
                    "modified": pub.get("metadata", {}).get("modified"),
                    "links": [
                        {
                            "href": urljoin(base_url, link.get("href")),
                            "type": link.get("type"),
                            "rel": link.get("rel")
                        }
                        for link in pub.get("links", [])
                        if "href" in link
                    ],
                    "images": [
                        {
                            "href": urljoin(base_url, img.get("href")),
                            "type": img.get("type"),
                            "height": img.get("height"),
                            "width": img.get("width")
                        }
                        for img in pub.get("images", [])
                        if "href" in img
                    ]
                }
                for pub in group.get("publications", [])
            ]
        }

        extracted.append(group_data)

    return extracted



def process_auth_doc(data):
    links = data.get("links", [])
    auth_methods = data.get("authentication", [])

    organized_links = {
        "General": [],
        "Users": [],
        "Custom Extensions": [],
        "Authentication Endpoints": [],
    }

    for link in links:
        rel = link.get("rel", "")
        display = {
            "title": link.get("title", ""),
            "href": link.get("href"),
            "type": link.get("type", ""),
            "label": None,
        }

        if rel == "start":
            display["label"] = "OPDS Catalog URL"
            organized_links["General"].append(display)
        elif rel == "register":
            display["label"] = "Register a User Account Link"
            organized_links["General"].append(display)
        elif rel == "http://librarysimplified.org/terms/rel/patron-password-reset":
            display["label"] = "Custom Extension: Patron Password Reset"
            organized_links["Custom Extensions"].append(display)
        elif rel == "http://opds-spec.org/shelf":
            display["label"] = "Shelf (User’s Books)"
            organized_links["Users"].append(display)
        elif rel == "http://librarysimplified.org/terms/rel/user-profile":
            display["label"] = "User Profile"
            organized_links["Users"].append(display)
        else:
            display["label"] = f"rel: {rel}"
            organized_links["General"].append(display)

    for method in auth_methods:
        method_type = method.get("type", "")
        description = method.get("description", "")
        inputs = method.get("inputs", [])
        organized_links["Authentication Endpoints"].append({
            "type": method_type,
            "description": description,
            "inputs": inputs,
        })

    return organized_links

# Extract ODL 


def extract_publications_with_odl(feed):
    """
    Extract ODL publications. For each publication:
      - If it has licenses, return one record per license
      - Else, return one record for the publication with odl=None
    """
    out = []

    for pub in feed.get("publications", []):
        meta = pub.get("metadata", {})
        title = meta.get("title", "Untitled")
        authors = [a.get("name") for a in meta.get("author", []) if a.get("name")]

        # Core OPDS fields
        links = pub.get("links", [])
        images = pub.get("images", [])
        belongs_to = meta.get("belongsTo")
        subjects = meta.get("subject")
        reading_order = pub.get("readingOrder", [])
        resources = pub.get("resources", [])

        # ODL License Handling
        licenses = pub.get("licenses")
        if licenses:
            for lic in licenses:
                lic_meta = lic.get("metadata", {})
                out.append({
                    "title": title,
                    "authors": authors,
                    "metadata": meta,
                    "links": links,
                    "images": images,
                    "subjects": subjects,
                    "belongs_to": belongs_to,
                    "reading_order": reading_order,
                    "resources": resources,
                    "odl": {
                        "identifier": lic_meta.get("identifier"),
                        "format": lic_meta.get("format", []),
                        "created": lic_meta.get("created"),
                        "price": lic_meta.get("price"),
                        "terms": lic_meta.get("terms"),
                        "protection": lic_meta.get("protection"),
                        "order": lic_meta.get("order"),
                        "links": lic.get("links", []),
                        "href": lic.get("href"),
                        "type": lic.get("type"),
                        "rel": lic.get("rel"),
                        # Optional: include full raw license for future parsing
                        "raw": lic,
                    }
                })
        else:
            out.append({
                "title": title,
                "authors": authors,
                "metadata": meta,
                "links": links,
                "images": images,
                "subjects": subjects,
                "belongs_to": belongs_to,
                "reading_order": reading_order,
                "resources": resources,
                "odl": None
            })

    return out
