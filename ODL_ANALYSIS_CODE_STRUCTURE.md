# ODL Analysis Feature - Code Structure Overview

## Architecture Diagram

```
User Interface (Browser)
    ↓
Flask Route Handler (/analyze-odl-feed)
    ↓ (POST/GET)
Routes/analyze_odl.py (Blueprint)
    ↓
    ├→ Caching Layer (in-memory results)
    ├→ Request Validation
    ├→ JSON/PDF Download Logic
    ↓
Util/odl_analyzer.py (Core Engine)
    ↓
    ├→ analyze_odl_feed()
    │   ├→ Fetch pages from feed URL
    │   ├→ Parse each page for publications
    │   ├→ Process each publication:
    │   │   ├→ detect_odl_formats()
    │   │   ├→ normalize_format_type()
    │   │   ├→ classify_odl_publication_type()
    │   │   ├→ detect_odl_drm_scheme()
    │   │   └→ extract_license_terms()
    │   ├→ Aggregate statistics
    │   ├→ Calculate percentages
    │   └→ Return analysis results
    ↓
Templates/analyze_odl_feed.html (Presentation)
    ↓
Rendered HTML + Bootstrap UI
    ↓
User Sees Results
```

## Data Flow

### 1. Input Phase
```
User submits form:
├─ feed_url (required)
├─ max_pages (optional)
├─ username (optional)
└─ password (optional)
    ↓
Route handler validates and prepares auth tuple
```

### 2. Analysis Phase
```
analyze_odl_feed() processes feed:

For each page in feed (up to max_pages):
├─ Fetch page JSON
├─ For each publication in page:
│  ├─ Extract formats array from licenses
│  ├─ Normalize formats to media types
│  ├─ Detect DRM schemes from protection fields
│  ├─ Classify publication type
│  └─ Accumulate statistics
├─ Store per-page statistics
└─ Compute aggregated summary

Results cached in memory
```

### 3. Output Phase
```
Results can be:
├─ Displayed in HTML template
├─ Downloaded as JSON
└─ Exported as PDF report
```

## Class & Function Organization

### odl_analyzer.py

```
Module: opds_tools.util.odl_analyzer

Functions:

1. detect_odl_formats(publication: dict) → List[str]
   - Input: Single ODL publication object
   - Process: Extracts licenses[].metadata.format[]
   - Output: List of MIME type strings

2. normalize_format_type(format_str: str) → str
   - Input: MIME type string
   - Process: Maps to readable format name
   - Output: "EPUB", "PDF", "Audiobook", etc.

3. classify_odl_publication_type(publication: dict) → str
   - Input: Single ODL publication object
   - Process: Analyzes metadata.@type field
   - Output: "Book", "Audiobook", "Periodical", "Other"

4. detect_odl_drm_scheme(publication: dict) → List[str]
   - Input: Single ODL publication object
   - Process: Examines protection.format array
   - Output: List of DRM scheme names

5. extract_license_terms(publication: dict) → Dict[str, Any]
   - Input: Single ODL publication object
   - Process: Extracts license metadata fields
   - Output: Dict with terms (concurrency, price, markets, etc.)

6. analyze_odl_feed(feed_url, auth, max_pages, progress_callback) → Dict
   - Input: Feed URL + optional auth + options
   - Process: Full feed analysis workflow
   - Output: Complete analysis results
```

### analyze_odl.py

```
Module: opds_tools.routes.analyze_odl

Blueprint: odl_analyze_bp

Global State:
_last_odl_analysis: Dict
  ├─ results: Dict (cached analysis results)
  ├─ feed_url: str
  ├─ max_pages: int
  ├─ in_progress: bool
  └─ started_at: float

Routes:

1. POST/GET /analyze-odl-feed
   Decorators: @odl_analyze_bp.route()
   Methods:
     - GET: Display cached results or form
     - POST: 
       * action="clear": Reset cache
       * download_json=1: Send JSON download
       * (default): Run analysis
   
   Logic:
   ├─ Validate inputs
   ├─ Check for download request
   ├─ Call analyze_odl_feed() from util
   ├─ Cache results
   ├─ Limit page display (first 20 + last 5)
   ├─ Render template with results
   └─ Handle errors

2. GET /analyze-odl-feed/pdf
   Decorators: @odl_analyze_bp.route()
   Method: GET
   
   Logic:
   ├─ Check for cached results
   ├─ Create PDF document
   ├─ Add summary tables
   ├─ Add media type distribution
   ├─ Add DRM scheme distribution
   ├─ Add format details
   ├─ Generate PDF
   └─ Return as file download
```

## Template Structure (analyze_odl_feed.html)

```
analyze_odl_feed.html

Main Sections:

1. Form Section
   ├─ Feed URL input
   ├─ Max pages number input
   ├─ Username/Password inputs
   └─ Analyze / Clear buttons

2. Progress Section (hidden initially)
   ├─ Progress bar
   ├─ Current status text
   └─ Statistics badges (pages, pubs, errors)

3. Error Alert (if error)
   └─ Error message display

4. Results Section (if analysis complete)
   ├─ Download buttons (JSON + PDF)
   
   4a. Summary Card
   │   ├─ Total publications
   │   ├─ Pages analyzed
   │   ├─ Unique media types
   │   ├─ Unique DRM schemes
   │   └─ Publication type counts
   
   4b. Media Type Distribution Card
   │   ├─ Table (media_type, count, %, progress bar)
   │   └─ (Sorted by count descending)
   
   4c. DRM Scheme Distribution Card
   │   ├─ Table (DRM scheme, count, %, progress bar)
   │   ├─ Color-coded badges
   │   └─ (Sorted by count descending)
   
   4d. Format MIME Types Card
   │   ├─ Detailed MIME type listing
   │   └─ Raw data for technical users
   
   4e. Page-by-Page Details (Collapsible)
       ├─ Per-page statistics
       ├─ Format display
       ├─ DRM information
       └─ Publication type counts
```

## State Management

### Caching Mechanism
```python
_last_odl_analysis = {
    'results': None,           # Full analysis results dict
    'feed_url': None,          # The feed URL analyzed
    'max_pages': None,         # Max pages parameter used
    'in_progress': False,      # Is analysis currently running
    'started_at': None         # Timestamp when analysis started
}
```

### Why Cache?
1. Avoid re-analyzing on page refresh
2. Support multiple download formats from same analysis
3. Show progress to user
4. Allow subsequent GET requests to retrieve results

### Cache Lifecycle
```
User submits → analysis starts
    ↓ (in_progress = True)
Analysis runs
    ↓
Completes → results stored in cache
    ↓ (in_progress = False)
User refreshes page
    ↓
GET request → loads from cache
User downloads JSON/PDF
    ↓
Uses cached results
User clears
    ↓ (cache reset)
```

## Data Structures

### Publication Object (Input)
```python
{
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Publication Title",
        ...
    },
    "licenses": [
        {
            "metadata": {
                "format": ["application/epub+zip", "text/html"],
                "price": {"currency": "USD", "value": 19.99},
                "terms": {
                    "concurrency": 1,
                    "length": 2592000
                },
                "markets": ["public_library", "academic_library"],
                "protection": {
                    "format": ["application/vnd.adobe.adept+xml"],
                    "copy": False,
                    "print": False,
                    "tts": False
                }
            }
        }
    ]
}
```

### Analysis Result (Output)
```python
{
    "summary": {
        "total_publications": 1000,
        "pages_analyzed": 5,
        "pages_with_errors": 0,
        "unique_formats": 3,
        "unique_media_types": 2,
        "unique_drm_schemes": 3,
        "media_type_counts": {"EPUB": 900, "PDF": 100},
        "drm_scheme_counts": {"No DRM": 600, "Adobe": 300, "LCP": 100},
        "publication_type_counts": {"Book": 900, "Audiobook": 100},
        "publication_type_percentages": {"Book": 90.0, "Audiobook": 10.0}
    },
    "media_type_stats": [
        {"media_type": "EPUB", "count": 900, "percentage": 90.0},
        {"media_type": "PDF", "count": 100, "percentage": 10.0}
    ],
    "drm_scheme_stats": [...],
    "publication_type_stats": [...],
    "format_counts": {"application/epub+zip": 900, ...},
    "page_stats": [
        {
            "url": "https://...",
            "publication_count": 200,
            "media_types": {"EPUB": 180, "PDF": 20},
            "drm_schemes": {"No DRM": 120, "Adobe": 60, "LCP": 20},
            "publication_types": {"Book": 180, "Audiobook": 20}
        },
        ...
    ]
}
```

## Integration Points

### Flask Application
```
opds_tools/__init__.py:
├─ Import: from .routes.analyze_odl import odl_analyze_bp
└─ Register: app.register_blueprint(odl_analyze_bp)
```

### Navigation Menu
```
opds_tools/templates/base.html:
└─ ODL Utilities dropdown
   └─ "Analyze ODL Feed Format & DRM" link
      └─ href="{{ url_for('odl_analyze.analyze_odl_feed_view') }}"
```

### URL Routing
```
/analyze-odl-feed          → analyze_odl_feed_view()
/analyze-odl-feed/pdf      → analyze_odl_feed_pdf()
```

## Dependencies

### Python Libraries
- `requests` - HTTP requests for feed fetching
- `flask` - Web framework
- `reportlab` - PDF generation

### No New Dependencies
- All required libraries already in project requirements.txt
- Compatible with existing OPDS analysis implementation

## Error Handling Strategy

```
Network Errors:
└─ Logged and tracked in page_stats with error field
├─ Analysis continues with remaining pages
└─ Error count shown in UI

Parsing Errors:
├─ Skipped publications marked in debug logging
└─ Analysis continues

Missing Fields:
├─ Gracefully handled with sensible defaults
├─ "UNKNOWN" formats for missing format arrays
└─ "Other" for unclassified publication types

Authentication Failures:
└─ Reported before analysis starts

Feed URL Issues:
├─ Caught by requests library
└─ Error message displayed to user
```

## Performance Characteristics

```
Feed Size: 100 publications
├─ Process time: ~1 second
└─ Memory: ~1 MB

Feed Size: 1,000 publications (10 pages)
├─ Process time: ~5-10 seconds
└─ Memory: ~5 MB

Feed Size: 10,000 publications (100 pages)
├─ Process time: ~30-60 seconds
└─ Memory: ~20 MB

Notes:
- Times vary by feed response time and network latency
- Page display limited to first 20 + last 5 pages
- Download JSON for complete data without UI pagination limits
```

## Testing Checklist

- [ ] Verify route registration in Flask app
- [ ] Test form submission with valid feed URL
- [ ] Test with protected feed (auth credentials)
- [ ] Test max_pages limiting
- [ ] Test JSON download
- [ ] Test PDF download
- [ ] Test error handling (invalid URL, network error)
- [ ] Test large feed handling (pagination)
- [ ] Verify caching behavior (refresh without re-analysis)
- [ ] Verify UI rendering with sample data
- [ ] Test navigation menu link
- [ ] Verify template error display
