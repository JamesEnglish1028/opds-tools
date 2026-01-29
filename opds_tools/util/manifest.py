# utils/manifest.py
import os
import mimetypes
import logging
from ebooklib import epub
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

def epub_to_manifest(exploded_dir, base_url, manifest_url=None):
    import mimetypes
    from urllib.parse import urljoin

    # Use folder name as identifier if not embedded
    identifier = os.path.basename(exploded_dir.rstrip("/"))
    title = identifier  # Default title unless extracted elsewhere

    if not manifest_url or not manifest_url.startswith("http"):
        raise ValueError("manifest_url must be a full URL for Thorium compatibility")

    # Helper: Collect files
    def collect_files(base):
        for root, _, files in os.walk(base):
            for file in files:
                full_path = os.path.join(root, file)
                yield os.path.relpath(full_path, base)

    reading_order = []
    resources = []

    for rel_path in sorted(collect_files(exploded_dir)):
        ext = os.path.splitext(rel_path)[1].lower()
        mime_type, _ = mimetypes.guess_type(rel_path)
        if not mime_type:
            continue

        # Always use forward slashes for manifest hrefs
        web_path = rel_path.replace(os.sep, "/")

        base_href = manifest_url.rsplit("/", 1)[0] + "/"

        entry = {
            "href": urljoin(base_href, rel_path.replace(os.sep, "/")),
            "type": mime_type
        }

        if mime_type in ["application/xhtml+xml", "image/svg+xml"]:
            reading_order.append(entry)
        else:
            resources.append(entry)

    manifest = {
        "@context": "https://readium.org/webpub-manifest/context.jsonld",
        "metadata": {
            "title": title,
            "identifier": identifier,
            "@type": "https://schema.org/Book",
            "readingProgression": "ltr",
            "conformsTo": "https://readium.org/webpub-manifest/profiles/epub"
        },
        "readingOrder": reading_order,
        "resources": resources,
        "links": [
            {
                "rel": "self",
                "href": manifest_url,  # aboslute within manifest directory
                "type": "application/webpub+json"
            }
        ]
    }

    return manifest
