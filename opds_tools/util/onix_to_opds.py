import xml.etree.ElementTree as ET
import json
import logging
import os
import mimetypes
from datetime import datetime
from opds_tools.util.helpers import (
    map_onix_role_to_term,
    guess_mime_type,
    extract_text,
    extract_subjects
)

# --- Logging setup ---
logger = logging.getLogger("opds_tools.onix")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def build_opds_links(product, ns, base_url, acq_url, img_url, isbn13, tag_prefix=""):
    sr_tag = f"{tag_prefix}SupportingResource"
    rct_tag = f"{tag_prefix}ResourceContentType"
    rl_tag = f"{tag_prefix}ResourceLink"

    image_link = None
    image_type = "image/jpeg"
    acq_link = None
    acq_type = "application/octet-stream"

    for sr in product.findall(f"{tag_prefix}CollateralDetail/{sr_tag}", ns):
        content_type = extract_text(sr, rct_tag, ns)

        if content_type == "01":  # Cover image
            link = extract_text(sr, f".//{rl_tag}", ns)
            if link:
                image_link = link
                image_type = guess_mime_type(link)
                logger.info(f"🖼 Found cover image for {isbn13}: {link}")

        elif content_type == "02":  # Acquisition content
            link = extract_text(sr, f".//{rl_tag}", ns)
            if link:
                acq_link = link
                acq_type = guess_mime_type(link)
                logger.info(f"📘 Found acquisition file for {isbn13}: {link} ({acq_type})")

    links = [
        {
            "rel": "self",
            "href": f"{base_url}/{isbn13}.json",
            "type": "application/opds+json"
        }
    ]

    if acq_link:
        links.append({
            "rel": "http://opds-spec.org/acquisition/",
            "href": acq_link,
            "type": acq_type
        })

    return links, image_link, image_type



# --- Main parser ---
def parse_onix_file(file_path, base_url="http://127.0.0.1:5000/uploads", acq_url="http://127.0.0.1:5000/uploads", img_url="http://127.0.0.1:5000/uploads", messages=None):
    if messages is None:
        messages = []

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"❌ XML parsing error in {file_path}: {e}")
        messages.append(("danger", f"XML parsing error: {e}. The ONIX file may be malformed or missing a required opening tag."))
        return {"metadata": {}, "publications": []}, messages


    modified_timestamp = datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()

    onix_version = root.attrib.get("release", "unknown")
    messages.append(("info", f"Detected ONIX version: {onix_version}"))

    uses_namespace = root.tag.startswith("{")
    ns = {}
    tag_prefix = ""

    if uses_namespace:
        ns_uri = root.tag.split('}')[0].strip('{')
        ns = {"onix": ns_uri}
        tag_prefix = "onix:"
        tag_mode = "reference"
    else:
        tag_mode = "short"

    messages.append(("info", f"ONIX uses {tag_mode} tags."))

    products = root.findall(f".//{tag_prefix}Product", ns) or root.findall(f".//{tag_prefix}product", ns)
    logger.info(f"📦 Found {len(products)} products")

    publications = []

    for product in products:
        # --- ISBN-13 ---
        isbn13 = None
        pid_tag = f"{tag_prefix}ProductIdentifier" if tag_mode == "reference" else f"{tag_prefix}productidentifier"
        for pid in product.findall(pid_tag, ns):
            id_type = extract_text(pid, f"{tag_prefix}ProductIDType" if tag_mode == "reference" else f"{tag_prefix}b221", ns)
            if id_type == "15":
                isbn13 = extract_text(pid, f"{tag_prefix}IDValue" if tag_mode == "reference" else f"{tag_prefix}b244", ns)
                break

        if not isbn13:
            messages.append(("warning", "Skipping a product missing ISBN-13."))
            continue

        title = extract_text(
            product,
            f"{tag_prefix}DescriptiveDetail/{tag_prefix}TitleDetail/{tag_prefix}TitleElement/{tag_prefix}TitleText"
            if tag_mode == "reference" else
            f"{tag_prefix}descriptivedetail/{tag_prefix}titledetail/{tag_prefix}titleelement/{tag_prefix}b203",
            ns
        )
        if not title:
            messages.append(("warning", f"Product {isbn13} is missing a title."))

        subjects = extract_subjects(product, tag_prefix, ns)

        # Contributors
        contributors = []
        authors = []
        for c in product.findall(f"{tag_prefix}DescriptiveDetail/{tag_prefix}Contributor", ns):
            role = extract_text(c, f"{tag_prefix}ContributorRole", ns)
            name = extract_text(c, f"{tag_prefix}PersonName", ns) or extract_text(c, f"{tag_prefix}CorporateName", ns)
            if not name:
                continue
            role_term = map_onix_role_to_term(role)
            if role_term == "other":
                messages.append(("warning", f"Unknown contributor role '{role}' for '{name}'"))
            if role_term == "author":
                authors.append(name)
            contributors.append({"name": name, "role": role_term})

        if not contributors:
            messages.append(("warning", f"Product {isbn13} has no contributors listed."))

        language = extract_text(
            product,
            f"{tag_prefix}DescriptiveDetail/{tag_prefix}Language/{tag_prefix}LanguageCode"
            if tag_mode == "reference" else
            f"{tag_prefix}descriptivedetail/{tag_prefix}language/{tag_prefix}b252",
            ns
        )

        publisher = extract_text(
            product,
            f"{tag_prefix}PublishingDetail/{tag_prefix}Publisher/{tag_prefix}PublisherName"
            if tag_mode == "reference" else
            f"{tag_prefix}publishingdetail/{tag_prefix}publisher/{tag_prefix}b081",
            ns
        )

        links, image_link, image_type = build_opds_links(product, ns, base_url, acq_url, img_url, isbn13, tag_prefix)

        images = []
        if image_link:
            images.append({
                "href": f"{img_url}/{image_link}",
                "type": image_type,
                "width": 400,
                "height": 600
            })

        metadata = {
            "@type": "https://schema.org/Book",
            "title": title,
            "identifier": f"urn:isbn:{isbn13}",
            "alternateIdentifier": isbn13,
            "author": authors,
            "contributor": contributors,
            "modified": modified_timestamp,
            "subject": subjects
        }

        if language:
            metadata["language"] = language

        if publisher:
            metadata["publisher"] = {"name": publisher}

        publication = {
            "metadata": metadata,
            "links": links
        }

        if images:
            publication["images"] = images

        publications.append(publication)

    feed_data = {
        "metadata": {"title": "Generated OPDS Catalog"},
        "publications": publications
    }

    return feed_data, messages


def save_opds_feed(feed, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(feed, f, indent=2, ensure_ascii=False)
