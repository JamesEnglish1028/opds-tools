"""
ODL Feed Format Analyzer

Analyzes ODL (Open Distribution License) feeds for publication format, 
media type, DRM scheme, and licensing statistics.
"""

from typing import Dict, List, Any, Tuple
from collections import defaultdict
import requests


def detect_odl_formats(publication: dict) -> List[str]:
    """
    Detect publication formats from ODL licenses array.
    
    ODL publications have a 'licenses' array where each license object
    contains a 'metadata' with 'format' field indicating supported formats.
    
    Returns:
        List of format strings (e.g., ["application/epub+zip", "text/html"])
        Returns ["UNKNOWN"] if no valid format found
    """
    found_formats = set()
    
    licenses = publication.get("licenses", [])
    if not isinstance(licenses, list):
        return ["UNKNOWN"]
    
    for license_obj in licenses:
        metadata = license_obj.get("metadata", {})
        formats = metadata.get("format", [])
        
        if isinstance(formats, list):
            for fmt in formats:
                if fmt:
                    found_formats.add(fmt)
        elif isinstance(formats, str) and formats:
            found_formats.add(formats)
    
    if found_formats:
        return sorted(list(found_formats))
    
    return ["UNKNOWN"]


def normalize_format_type(format_str: str) -> str:
    """
    Normalize format MIME type to readable publication type.
    
    Maps MIME types to publication types:
    - application/epub+zip -> EPUB
    - application/pdf -> PDF
    - text/html -> WebPublication
    - audio/* -> Audiobook
    - etc.
    
    Returns:
        Normalized format type (e.g., "EPUB", "PDF", "Audiobook")
    """
    format_lower = format_str.lower()
    
    if "epub" in format_lower:
        return "EPUB"
    elif "pdf" in format_lower:
        return "PDF"
    elif "audio" in format_lower:
        return "Audiobook"
    elif "html" in format_lower or "webpub" in format_lower:
        return "WebPublication"
    elif "opf" in format_lower or "oebps" in format_lower:
        return "OPEB"
    else:
        # Extract from MIME type
        if "/" in format_str:
            parts = format_str.split("/")
            if len(parts) > 1:
                subtype = parts[1].replace("+", " ").replace("-", " ").title()
                return subtype
        return format_str.upper()


def classify_odl_publication_type(publication: dict) -> str:
    """
    Classify ODL publication by metadata.@type (schema.org vocabulary).
    
    Returns:
        "Book", "Audiobook", "Periodical", or "Other"
    """
    metadata = publication.get("metadata", {})
    pub_type = metadata.get("@type") or metadata.get("type")
    
    if not pub_type:
        return "Other"
    
    if isinstance(pub_type, list):
        type_values = pub_type
    else:
        type_values = [pub_type]
    
    normalized = [str(t).strip().lower() for t in type_values if t]
    
    def matches_any(targets: list) -> bool:
        for t in normalized:
            for target in targets:
                if t.endswith(target):
                    return True
        return False
    
    if matches_any(["schema.org/book", "schema.org/ebook"]):
        return "Book"
    if matches_any(["schema.org/audiobook"]):
        return "Audiobook"
    if matches_any(["schema.org/periodical", "schema.org/publicationissue", "schema.org/article"]):
        return "Periodical"
    
    return "Other"


def detect_odl_drm_scheme(publication: dict) -> List[str]:
    """
    Detect DRM protection schemes from ODL licenses.
    
    Checks the 'protection' field in license metadata for:
    - Adobe DRM (application/vnd.adobe.adept+xml)
    - Readium LCP (application/vnd.readium.lcp.license.v1.0+json)
    - No protection (no protection field)
    
    Returns:
        List of DRM schemes found (e.g., ["Adobe DRM", "LCP"])
        Returns ["No DRM"] if no protection found
    """
    drm_schemes = set()
    
    licenses = publication.get("licenses", [])
    if not isinstance(licenses, list):
        return ["No DRM"]
    
    has_any_protection = False
    
    for license_obj in licenses:
        metadata = license_obj.get("metadata", {})
        protection = metadata.get("protection", {})
        
        if not protection:
            continue
        
        has_any_protection = True
        
        # Check protection format field
        formats = protection.get("format", [])
        if isinstance(formats, list):
            for fmt in formats:
                fmt_lower = str(fmt).lower()
                if "adobe" in fmt_lower or "adept" in fmt_lower:
                    drm_schemes.add("Adobe DRM")
                elif "readium" in fmt_lower or "lcp" in fmt_lower:
                    drm_schemes.add("Readium LCP")
                elif "watermark" in fmt_lower:
                    drm_schemes.add("Watermark")
        elif isinstance(formats, str):
            fmt_lower = formats.lower()
            if "adobe" in fmt_lower or "adept" in fmt_lower:
                drm_schemes.add("Adobe DRM")
            elif "readium" in fmt_lower or "lcp" in fmt_lower:
                drm_schemes.add("Readium LCP")
    
    if drm_schemes:
        return sorted(list(drm_schemes))
    
    return ["No DRM"] if not has_any_protection else ["Unknown DRM"]


def extract_license_terms(publication: dict) -> Dict[str, Any]:
    """
    Extract license terms from ODL publication.
    
    Returns dict with:
    - concurrency: Number of simultaneous loans
    - lending_period: Length of loan period (in days or seconds)
    - price: Price/cost information
    - markets: Target markets (public_library, academic_library, etc.)
    - copy_allowed: Whether copying is allowed
    - print_allowed: Whether printing is allowed
    - tts_allowed: Whether text-to-speech is allowed
    """
    terms = {
        'concurrency': None,
        'lending_period': None,
        'price': None,
        'markets': [],
        'copy_allowed': None,
        'print_allowed': None,
        'tts_allowed': None,
        'devices': None
    }
    
    licenses = publication.get("licenses", [])
    if not isinstance(licenses, list) or not licenses:
        return terms
    
    # Use first license for term extraction (most have single license)
    license_obj = licenses[0]
    metadata = license_obj.get("metadata", {})
    
    # Extract terms
    license_terms = metadata.get("terms", {})
    terms['concurrency'] = license_terms.get("concurrency")
    terms['lending_period'] = license_terms.get("length")
    terms['price'] = metadata.get("price")
    terms['markets'] = metadata.get("markets", [])
    
    # Extract protection details
    protection = metadata.get("protection", {})
    terms['copy_allowed'] = protection.get("copy", False)
    terms['print_allowed'] = protection.get("print", False)
    terms['tts_allowed'] = protection.get("tts", False)
    terms['devices'] = protection.get("devices")
    
    return terms


def analyze_odl_feed(
    feed_url: str,
    auth: Tuple[str, str] = None,
    max_pages: int = None,
    progress_callback = None
) -> Dict[str, Any]:
    """
    Analyze an ODL feed for format and licensing statistics.
    
    Args:
        feed_url: Starting ODL feed URL
        auth: Optional (username, password) tuple for authentication
        max_pages: Maximum pages to fetch (None = all)
        progress_callback: Optional callback function(event_type, data) for progress updates
        
    Returns:
        Dictionary with analysis results including:
        - format_counts: {format: count}
        - media_type_counts: {media_type: count}
        - drm_scheme_counts: {drm_scheme: count}
        - publication_type_counts: {type: count}
        - page_stats: [{url, formats, drm_schemes}]
        - summary: {total_pubs, pages_analyzed, formats, drm_schemes, etc}
    """
    
    print(f"\n🔬 Starting ODL feed analysis...")
    if progress_callback:
        progress_callback('started', {'url': feed_url, 'max_pages': max_pages})
    
    # Fetch all pages
    print(f"📊 Fetching pages from: {feed_url}")
    
    all_feeds = {}
    current_url = feed_url
    page_count = 0
    current_auth = auth
    
    try:
        while current_url and (max_pages is None or page_count < max_pages):
            page_count += 1
            print(f"   📖 Fetching page {page_count}: {current_url}")
            
            try:
                response = requests.get(current_url, auth=current_auth, timeout=10)
                response.raise_for_status()
                feed_data = response.json()
                
                all_feeds[current_url] = feed_data
                
                if progress_callback:
                    progress_callback('page_fetched', {
                        'current_page': page_count,
                        'url': current_url,
                        'publications': len(feed_data.get('publications', []))
                    })
                
                # Check for next link
                next_url = None
                for link in feed_data.get("links", []):
                    if link.get("rel") == "next":
                        next_url = link.get("href")
                        break
                
                if next_url and "token=" in next_url:
                    current_auth = None
                current_url = next_url
                
            except requests.RequestException as e:
                print(f"   ❌ Error fetching page {page_count}: {e}")
                all_feeds[current_url] = {"error": str(e)}
                break
                
    except Exception as e:
        print(f"❌ Error during fetch loop: {e}")
        return {"error": str(e)}
    
    print(f"✅ Fetched {page_count} pages")
    
    if progress_callback:
        progress_callback('pages_fetched', {'total_pages': page_count})
    
    # Analyze pages
    print(f"📈 Analyzing {page_count} pages...")
    
    # Aggregated statistics
    format_counts = defaultdict(int)  # Individual format counts
    media_type_counts = defaultdict(int)  # Normalized media types
    drm_scheme_counts = defaultdict(int)
    drm_combination_counts = defaultdict(int)  # Track single vs. multiple DRM
    publication_type_counts = defaultdict(int)
    page_stats = []
    total_publications = 0
    pages_with_errors = 0
    
    for idx, (page_url, feed_data) in enumerate(all_feeds.items(), 1):
        
        if idx % 10 == 0:
            print(f"   Processing page {idx}/{len(all_feeds)}...")
        
        # Skip error pages
        if "error" in feed_data:
            pages_with_errors += 1
            page_stats.append({
                "url": page_url,
                "error": feed_data["error"]
            })
            if progress_callback:
                progress_callback('page_error', {
                    'page': idx,
                    'url': page_url,
                    'error': feed_data["error"]
                })
            continue
        
        # Page-level statistics
        page_formats = defaultdict(int)
        page_media_types = defaultdict(int)
        page_drm_schemes = defaultdict(int)
        page_publication_types = defaultdict(int)
        
        publications = feed_data.get("publications", [])
        
        if progress_callback:
            progress_callback('page_processing', {
                'current_page': idx,
                'total_pages': len(all_feeds),
                'url': page_url,
                'publications': len(publications),
                'total_publications': total_publications
            })
        
        for pub in publications:
            total_publications += 1
            
            # Detect formats (raw MIME types)
            formats_list = detect_odl_formats(pub)
            for fmt in formats_list:
                format_counts[fmt] += 1
                page_formats[fmt] += 1
            
            # Normalize to media types (EPUB, PDF, etc.)
            media_types = [normalize_format_type(fmt) for fmt in formats_list]
            for media_type in media_types:
                media_type_counts[media_type] += 1
                page_media_types[media_type] += 1
            
            # Detect DRM schemes
            drm_schemes = detect_odl_drm_scheme(pub)
            for drm in drm_schemes:
                drm_scheme_counts[drm] += 1
                page_drm_schemes[drm] += 1
            
            # Track DRM combinations (single vs. multiple)
            if len(drm_schemes) > 0:
                # Sort for consistent combination keys
                sorted_drm = sorted([d for d in drm_schemes if d not in ['No DRM', 'Unknown DRM']])
                if sorted_drm:
                    combination_key = ' & '.join(sorted_drm)
                    drm_combination_counts[combination_key] += 1
                elif 'No DRM' in drm_schemes:
                    drm_combination_counts['No DRM'] += 1
                elif 'Unknown DRM' in drm_schemes:
                    drm_combination_counts['Unknown DRM'] += 1
            
            # Classify publication type
            pub_type = classify_odl_publication_type(pub)
            publication_type_counts[pub_type] += 1
            page_publication_types[pub_type] += 1
        
        page_stats.append({
            "url": page_url,
            "publication_count": len(publications),
            "formats": dict(page_formats),
            "media_types": dict(page_media_types),
            "drm_schemes": dict(page_drm_schemes),
            "publication_types": dict(page_publication_types)
        })
    
    print(f"📊 Calculating summary statistics...")
    
    # Convert to stats with percentages
    media_type_stats = []
    for media_type, count in sorted(media_type_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_publications * 100) if total_publications > 0 else 0
        media_type_stats.append({
            "media_type": media_type,
            "count": count,
            "percentage": round(percentage, 1)
        })
    
    drm_scheme_stats = []
    for drm, count in sorted(drm_scheme_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_publications * 100) if total_publications > 0 else 0
        drm_scheme_stats.append({
            "drm_scheme": drm,
            "count": count,
            "percentage": round(percentage, 1)
        })
    
    publication_type_stats = []
    pub_type_percentages = {}
    for pub_type, count in sorted(publication_type_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_publications * 100) if total_publications > 0 else 0
        publication_type_stats.append({
            "type": pub_type,
            "count": count,
            "percentage": round(percentage, 1)
        })
        pub_type_percentages[pub_type] = round(percentage, 1)
    
    # DRM combination statistics (single vs. multiple)
    drm_combination_stats = []
    for combination, count in sorted(drm_combination_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_publications * 100) if total_publications > 0 else 0
        drm_combination_stats.append({
            "combination": combination,
            "count": count,
            "percentage": round(percentage, 1)
        })
    
    summary = {
        "total_publications": total_publications,
        "pages_analyzed": len(all_feeds) - pages_with_errors,
        "pages_with_errors": pages_with_errors,
        "unique_formats": len(format_counts),
        "unique_media_types": len(media_type_counts),
        "unique_drm_schemes": len(drm_scheme_counts),
        "unique_drm_combinations": len(drm_combination_counts),
        "media_type_counts": dict(media_type_counts),
        "drm_scheme_counts": dict(drm_scheme_counts),
        "drm_combination_counts": dict(drm_combination_counts),
        "publication_type_counts": dict(publication_type_counts),
        "publication_type_percentages": pub_type_percentages
    }
    
    print(f"✅ Analysis complete!")
    print(f"   Total publications: {total_publications}")
    print(f"   Pages analyzed: {summary['pages_analyzed']}")
    print(f"   Unique media types: {summary['unique_media_types']}")
    print(f"   Unique DRM schemes: {summary['unique_drm_schemes']}")
    
    return {
        "summary": summary,
        "media_type_stats": media_type_stats,
        "drm_scheme_stats": drm_scheme_stats,
        "drm_combination_stats": drm_combination_stats,
        "publication_type_stats": publication_type_stats,
        "format_counts": dict(format_counts),
        "page_stats": page_stats
    }
