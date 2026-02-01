# ODL Feed Analysis - Quick Reference Guide

## Overview
Similar to the existing OPDS Feed Analyzer, the ODL Feed Analyzer provides insights into Open Distribution License publications including media types, DRM schemes, and licensing terms.

## Files Added/Modified

### New Files
```
opds_tools/util/odl_analyzer.py              # Core analysis engine
opds_tools/routes/analyze_odl.py            # Flask route handler
opds_tools/templates/analyze_odl_feed.html  # UI template
```

### Modified Files
```
opds_tools/__init__.py                       # Added blueprint registration
opds_tools/templates/base.html              # Added navigation menu item
```

## Key Differences from OPDS Analysis

### ODL-Specific Features
1. **License-Based Format Detection**
   - Analyzes `licenses[].metadata.format` array
   - Extracts MIME types from each license object
   - Supports multiple formats per publication

2. **DRM Scheme Detection**
   - Examines `protection.format` field
   - Identifies: Adobe DRM, Readium LCP, No DRM
   - More precise than OPDS bearer token detection

3. **License Terms Analysis**
   - **Concurrency**: Number of simultaneous loans
   - **Lending Period**: Duration in seconds
   - **Price**: Cost information (currency + value)
   - **Markets**: Target market segments (public_library, academic_library, corporate)
   - **Restrictions**: Copy, print, and TTS permissions
   - **Device Limits**: Maximum concurrent devices

4. **Authentication Support**
   - Optional username/password for protected feeds
   - Passed via HTTP Basic Auth

### Format & Type Mapping

**ODL MIME Type → Normalized Media Type**
- `application/epub+zip` → EPUB
- `application/pdf` → PDF
- `text/html` → WebPublication
- `audio/*` → Audiobook
- `application/x-opf+zip` → OPEB

**Publication Types (from metadata.@type)**
- `schema.org/Book` → Book
- `schema.org/AudioBook` → Audiobook
- `schema.org/Periodical`, `schema.org/PublicationIssue` → Periodical
- Other → Other

**DRM Schemes**
- Adobe: `application/vnd.adobe.adept+xml`
- Readium LCP: `application/vnd.readium.lcp.license.v1.0+json`
- No DRM: No protection field present

## API Reference

### Main Analysis Function
```python
from opds_tools.util.odl_analyzer import analyze_odl_feed

results = analyze_odl_feed(
    feed_url="https://example.com/odl/feed.json",
    auth=("username", "password"),  # Optional
    max_pages=10,                    # Optional, None = all pages
    progress_callback=None           # Optional for real-time updates
)
```

### Utility Functions
```python
# Detect formats from publication
formats = detect_odl_formats(publication)  # Returns list of MIME types

# Normalize format to readable type
media_type = normalize_format_type("application/epub+zip")  # Returns "EPUB"

# Classify publication type
pub_type = classify_odl_publication_type(publication)  # Returns "Book", "Audiobook", etc.

# Detect DRM schemes
drm_schemes = detect_odl_drm_scheme(publication)  # Returns list of DRM types

# Extract license terms
terms = extract_license_terms(publication)  # Returns dict with license info
```

## Response Structure

```python
{
    "summary": {
        "total_publications": 1000,
        "pages_analyzed": 10,
        "pages_with_errors": 0,
        "unique_formats": 5,
        "unique_media_types": 3,
        "unique_drm_schemes": 3,
        "media_type_counts": {
            "EPUB": 800,
            "PDF": 150,
            "WebPublication": 50
        },
        "drm_scheme_counts": {
            "No DRM": 500,
            "Adobe DRM": 300,
            "Readium LCP": 200
        },
        "publication_type_counts": {
            "Book": 900,
            "Audiobook": 80,
            "Periodical": 20,
            "Other": 0
        },
        "publication_type_percentages": {
            "Book": 90.0,
            "Audiobook": 8.0,
            "Periodical": 2.0,
            "Other": 0.0
        }
    },
    "media_type_stats": [
        {"media_type": "EPUB", "count": 800, "percentage": 80.0},
        {"media_type": "PDF", "count": 150, "percentage": 15.0},
        {"media_type": "WebPublication", "count": 50, "percentage": 5.0}
    ],
    "drm_scheme_stats": [
        {"drm_scheme": "No DRM", "count": 500, "percentage": 50.0},
        {"drm_scheme": "Adobe DRM", "count": 300, "percentage": 30.0},
        {"drm_scheme": "Readium LCP", "count": 200, "percentage": 20.0}
    ],
    "publication_type_stats": [
        {"type": "Book", "count": 900, "percentage": 90.0},
        ...
    ],
    "format_counts": {
        "application/epub+zip": 800,
        "application/pdf": 150,
        "text/html": 50
    },
    "page_stats": [
        {
            "url": "https://example.com/odl/feed.json?page=1",
            "publication_count": 100,
            "media_types": {"EPUB": 80, "PDF": 15, "WebPublication": 5},
            "drm_schemes": {"No DRM": 50, "Adobe DRM": 30, "Readium LCP": 20},
            "publication_types": {"Book": 90, "Audiobook": 8, "Periodical": 2}
        },
        ...
    ]
}
```

## UI Features

### Summary Dashboard
- Total publications analyzed
- Pages processed
- Unique media types and DRM schemes
- Publication type breakdown with percentages

### Statistics Tables
1. **Media Type Distribution**
   - Format name, count, percentage
   - Visual progress bars

2. **DRM Scheme Distribution**
   - Scheme name (color-coded badges)
   - Count and percentage
   - Visual progress bars

3. **Publication Types**
   - Type, count, percentage breakdown
   - Breakdown: Book, Audiobook, Periodical, Other

4. **Detailed MIME Types**
   - Raw MIME type information
   - Useful for technical analysis

### Page Details
- Collapsible section showing per-page statistics
- First 20 pages + last 5 pages displayed for large feeds
- Download JSON for complete page-by-page data

### Downloads
- **JSON Report**: Complete analysis results in JSON format
- **PDF Report**: Professional formatted report with all statistics

## Usage Examples

### Basic Analysis
```
URL: https://market.feedbooks.com/v2/catalog.json
Max Pages: (leave blank for all)
Username/Password: (leave blank unless required)
Click "Analyze"
```

### Protected Feed
```
URL: https://secure.example.com/odl/feed.json
Max Pages: 5
Username: user@example.com
Password: secret_password
Click "Analyze"
```

### Large Feed (Limited Pages)
```
URL: https://example.com/odl/catalog.json
Max Pages: 10
(This will stop after analyzing 10 pages)
```

## Route Endpoints

- `GET /analyze-odl-feed` - Display analysis form and results
- `POST /analyze-odl-feed` - Submit feed for analysis
- `GET /analyze-odl-feed/pdf` - Download PDF report (requires prior analysis)

## Menu Navigation

Path: **ODL Utilities > Analyze ODL Feed Format & DRM**

## Error Handling

- **Network errors**: Captured and displayed, analysis continues with remaining pages
- **Invalid JSON**: Skipped pages marked with error in results
- **Authentication failures**: Reported before analysis starts
- **Empty feeds**: Results shown with 0 publications

## Performance Notes

- Large feeds (500+ pages) may take several minutes
- Progress bar updates in real-time
- Results cached in memory for subsequent GET requests
- Pagination limiting: Shows first 20 + last 5 pages in UI, download JSON for full data

## Example Analysis Scenario

**Scenario**: Analyzing Feedbooks ODL API

1. Navigate to: ODL Utilities > Analyze ODL Feed Format & DRM
2. Enter URL: `https://market.feedbooks.com/v2/catalog.json`
3. Set Max Pages: `10`
4. Click Analyze
5. Results show:
   - 1000 publications across 10 pages
   - 95% EPUB, 5% PDF
   - 60% No DRM, 30% Adobe DRM, 10% Readium LCP
   - 85% Books, 10% Audiobooks, 5% Periodicals
6. Download JSON for data integration or PDF for sharing

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection refused" | Verify URL is accessible and feed format is valid |
| "Timeout after X seconds" | Feed may be slow; try with smaller max_pages limit |
| "Empty results" | Check that feed contains publications and has valid ODL structure |
| "Authentication failed" | Verify username/password are correct |
| "No media types detected" | Feed may not have licenses or format information |

## References

- ODL Specification: https://github.com/standardebooks/open-distribution-license
- OPDS Catalog Structure: https://specs.opds.io/
- Schema.org Publication Types: https://schema.org/CreativeWork
