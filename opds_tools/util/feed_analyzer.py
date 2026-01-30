"""
OPDS Feed Format Analyzer

Analyzes OPDS feeds for publication format and DRM statistics
without performing validation.
"""

from typing import Dict, List, Any, Tuple
from collections import defaultdict
from opds_tools.util.palace_validator import fetch_all_pages


def detect_formats(publication: dict) -> List[str]:
    """
    Detect ALL publication formats from publication links.
    
    Only looks at acquisition links:
    - http://opds-spec.org/acquisition
    - http://opds-spec.org/acquisition/open-access
    A publication may have multiple formats (e.g., both EPUB and PDF).
    
    Returns:
        List of format strings (e.g., ["EPUB", "PDF"], ["AUDIOBOOK"], etc.)
        Returns ["UNKNOWN"] if no valid format found
    """
    links = publication.get("links", [])
    
    found_formats = set()
    
    for link in links:
        rel = link.get("rel", "").lower()
        link_type = link.get("type", "").lower()
        
        # Only look at acquisition links
        if rel not in (
            "http://opds-spec.org/acquisition",
            "http://opds-spec.org/acquisition/open-access",
        ):
            continue
        
        if not link_type:
            continue
        
        # Check for formats
        if "epub" in link_type:
            found_formats.add("EPUB")
        elif "pdf" in link_type:
            found_formats.add("PDF")
        elif "audiobook" in link_type or link_type.startswith("audio/"):
            found_formats.add("AUDIOBOOK")
        elif link_type.startswith("application/"):
            # Extract format from application/* types
            parts = link_type.split("/")
            if len(parts) > 1:
                subtype = parts[1]
                if "." in subtype:
                    vendor = subtype.split(".")[-1].upper()
                    found_formats.add(vendor)
                else:
                    found_formats.add(subtype.upper())
    
    # Return sorted list of formats found
    if found_formats:
        return sorted(list(found_formats))
    
    return ["UNKNOWN"]


def detect_drm_type(publication: dict, format_type: str) -> str:
    """
    Detect DRM type for a publication.
    
    Checks:
    - Link properties for DRM scheme
    - Link rel types (license, borrow, etc.)
    
    Returns:
        "NO_DRM", "ADOBE_DRM", "LCP_DRM", or "UNKNOWN_DRM"
    """
    if format_type != "EPUB":
        return "N/A"
    
    links = publication.get("links", [])
    
    for link in links:
        # Check properties for DRM scheme
        properties = link.get("properties", {})
        
        # Common DRM indicators in properties
        if "lcp" in str(properties).lower():
            return "LCP_DRM"
        if "adobe" in str(properties).lower() or "adept" in str(properties).lower():
            return "ADOBE_DRM"
        
        # Check link rel for acquisition types
        rel = link.get("rel", "")
        if rel == "http://opds-spec.org/acquisition/open-access":
            return "NO_DRM"
        
        # Check for DRM-free indicators in link type
        link_type = link.get("type", "")
        if "drm-free" in link_type.lower():
            return "NO_DRM"
    
    # Default: assume no DRM if no indicators found
    # (This is a heuristic - feeds should be explicit)
    return "NO_DRM"


def analyze_feed_url(
    url: str,
    max_pages: int = None,
    progress_callback = None
) -> Dict[str, Any]:
    """
    Analyze an OPDS feed for format and DRM statistics.
    
    Args:
        url: Starting OPDS feed URL
        max_pages: Maximum pages to fetch (None = all)
        progress_callback: Optional callback function(event_type, data) for progress updates
        
    Returns:
        Dictionary with:
        - format_counts: {format: count}
        - drm_counts: {drm_type: count} (EPUBs only)
        - combined_counts: {(format, drm): count}
        - page_stats: [{url, formats, drm_types}]
        - summary: {total_pubs, pages_analyzed, formats, drm_types}
    """
    # Fetch all pages
    print(f"\n🔍 Starting feed analysis...")
    if progress_callback:
        progress_callback('started', {'url': url, 'max_pages': max_pages})
    
    feeds = fetch_all_pages(url, max_pages=max_pages, progress_callback=progress_callback)
    print(f"📊 Processing {len(feeds)} pages of data...")
    
    if progress_callback:
        progress_callback('pages_fetched', {'total_pages': len(feeds)})
    
    # Aggregated statistics
    format_counts = defaultdict(int)  # Individual format counts
    format_combination_counts = defaultdict(int)  # Multi-format combinations
    drm_counts = defaultdict(int)
    combined_counts = defaultdict(int)  # (format, drm) tuple keys
    page_stats = []
    total_publications = 0
    
    for idx, (page_url, feed_data) in enumerate(feeds.items(), 1):
        if idx % 10 == 0:  # Log every 10 pages
            print(f"   Processing page {idx}/{len(feeds)}...")
        
        # Skip error pages
        if "error" in feed_data:
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
        page_format_combinations = defaultdict(int)
        page_drm = defaultdict(int)
        page_combined = defaultdict(int)
        
        publications = feed_data.get("publications", [])
        
        # Send progress callback AFTER we know the publication count
        if progress_callback:
            progress_callback('page_processing', {
                'current_page': idx,
                'total_pages': len(feeds),
                'url': page_url,
                'publications': len(publications),
                'total_publications': total_publications
            })
        
        for pub in publications:
            total_publications += 1
            
            # Detect all formats for this publication
            formats_list = detect_formats(pub)
            
            # Count each individual format
            for fmt in formats_list:
                format_counts[fmt] += 1
                page_formats[fmt] += 1
            
            # Count format combinations
            format_combo = "+".join(formats_list)
            format_combination_counts[format_combo] += 1
            page_format_combinations[format_combo] += 1
            
            # Detect DRM (for each EPUB format)
            if "EPUB" in formats_list:
                drm_type = detect_drm_type(pub, "EPUB")
                if drm_type != "N/A":
                    drm_counts[drm_type] += 1
                    page_drm[drm_type] += 1
                
                # Combined format+DRM for EPUB
                combined_key = ("EPUB", drm_type)
                combined_counts[combined_key] += 1
                page_combined[combined_key] += 1
            
            # For PDFs, track as N/A DRM
            if "PDF" in formats_list:
                combined_key = ("PDF", "N/A")
                combined_counts[combined_key] += 1
                page_combined[combined_key] += 1
        
        page_stats.append({
            "url": page_url,
            "publication_count": len(publications),
            "formats": dict(page_formats),
            "format_combinations": dict(page_format_combinations),
            "drm_types": dict(page_drm),
            "combined": {f"{k[0]}+{k[1]}": v for k, v in page_combined.items()}
        })
    
    print(f"📈 Calculating statistics...")
    
    # Convert combined_counts to a more readable format with percentages
    combined_stats = []
    for (format_type, drm_type), count in sorted(combined_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_publications * 100) if total_publications > 0 else 0
        combined_stats.append({
            "format": format_type,
            "drm": drm_type,
            "count": count,
            "percentage": round(percentage, 1)
        })
    
    print(f"📊 Creating format combination stats...")
    
    # Convert format combinations to stats with percentages
    format_combo_stats = []
    for combo, count in sorted(format_combination_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_publications * 100) if total_publications > 0 else 0
        format_combo_stats.append({
            "combination": combo,
            "count": count,
            "percentage": round(percentage, 1)
        })
    
    print(f"🔄 Serializing combined counts...")
    
    # Convert tuple keys to strings for JSON serialization
    combined_counts_serializable = {
        f"{format_type}+{drm_type}": count 
        for (format_type, drm_type), count in combined_counts.items()
    }
    
    print(f"✨ Building final results dictionary...")
    print(f"   Total publications: {total_publications}")
    print(f"   Unique formats: {len(format_counts)}")
    print(f"   Format combinations: {len(format_combination_counts)}")
    print(f"   Pages with data: {len([p for p in page_stats if 'error' not in p])}")
    
    result = {
        "format_counts": dict(format_counts),
        "format_combination_counts": dict(format_combination_counts),
        "format_combo_stats": format_combo_stats,
        "drm_counts": dict(drm_counts),
        "combined_counts": combined_counts_serializable,
        "combined_stats": combined_stats,
        "page_stats": page_stats,
        "summary": {
            "total_publications": total_publications,
            "pages_analyzed": len([p for p in page_stats if "error" not in p]),
            "pages_with_errors": len([p for p in page_stats if "error" in p]),
            "unique_formats": len(format_counts),
            "unique_format_combinations": len(format_combination_counts),
            "unique_drm_types": len([d for d in drm_counts.keys() if d != "N/A"])
        }
    }
    
    print(f"✅ Analysis complete! Returning results.\n")
    return result
