# OPDS Inventory Report Feature - Design Document

## Overview
Add a new feature to generate downloadable inventory reports (CSV or XML) from OPDS feeds. The feature will crawl through paginated OPDS feeds and extract key publication metadata.

## Requirements

### Functional Requirements
1. Accept an OPDS Feed URL as input
2. Page through the entire OPDS feed (follow `rel="next"` links)
3. Extract publication data:
   - Identifier
   - Title
   - Author
   - Publisher
   - Format (EPUB, PDF, WebPub)
   - DRM type (DRM, Bearer Token, None)
4. Generate downloadable reports in CSV and XML formats
5. Provide a user-friendly web interface

### Data Extraction Logic

#### Format Detection
Extract from the `links` array in each publication object:
- Check `type` field in acquisition links
- Map MIME types to formats:
  - `application/epub+zip` → EPUB
  - `application/pdf` → PDF
  - `application/webpub+json` → WebPub
  - `application/audiobook+json` → Audiobook

#### DRM Detection
Analyze the `type` field in acquisition links for DRM indicators:
- Contains `vnd.readium.lcp` → LCP DRM
- Contains `vnd.adobe.adept+xml` → Adobe DRM
- Contains `drm:` or `+drm` → Generic DRM
- `rel` contains `http://opds-spec.org/acquisition/bearer-token` → Bearer Token
- Otherwise → None

## Architecture

### Files to Create

#### 1. Route: `opds_tools/routes/inventory.py`
New blueprint for inventory report generation
- Route: `/inventory-report` (GET, POST)
- Handles URL input, crawling, report generation
- Download endpoints for CSV and XML

#### 2. Utility: `opds_tools/util/inventory_generator.py`
Core logic for:
- OPDS feed crawling with pagination
- Publication data extraction
- Format and DRM detection
- CSV generation
- XML generation

#### 3. Template: `opds_tools/templates/inventory_report.html`
User interface for:
- URL input form
- Progress indication
- Download buttons for CSV/XML
- Preview of extracted data

### Existing Code to Leverage

#### From `opds_crawler.py`:
- `crawl_opds_feed()` function pattern for pagination
- URL handling and error management
- Following `rel="next"` links

#### From `parser.py`:
- `extract_opds_data()` function for publication parsing
- Link extraction logic
- Metadata parsing patterns

#### From `csv_exporter.py`:
- `generate_csv()` function structure
- CSV formatting approach

#### From `analyze.py`:
- Blueprint registration pattern
- Form handling for URL input
- Download response patterns
- Progress tracking approach

## Detailed Design

### 1. Inventory Generator Utility (`util/inventory_generator.py`)

```python
def crawl_feed_for_inventory(feed_url, max_pages=None, auth=None):
    """
    Crawl OPDS feed and extract inventory data.
    
    Returns:
        list: List of dicts with publication inventory data
    """
    # Initialize
    # Follow pagination
    # Extract data
    # Return structured list

def extract_format_from_links(links):
    """
    Determine format(s) from publication links.
    Returns: str (e.g., "EPUB", "EPUB, PDF")
    """
    # Parse links array
    # Map MIME types to formats
    # Return comma-separated formats

def extract_drm_from_links(links):
    """
    Determine DRM type from publication links.
    Returns: str (e.g., "LCP DRM", "Bearer Token", "None")
    """
    # Check acquisition link types
    # Check rel attributes
    # Return DRM type

def generate_inventory_csv(inventory_data):
    """
    Generate CSV from inventory data.
    Returns: str (CSV content)
    """
    # Use csv module
    # Format columns: identifier, title, author, publisher, format, drm
    
def generate_inventory_xml(inventory_data):
    """
    Generate XML from inventory data.
    Returns: str (XML content)
    """
    # Use xml.etree.ElementTree
    # Create structured XML document
```

### 2. Inventory Route (`routes/inventory.py`)

```python
from flask import Blueprint, request, render_template, Response, flash
from opds_tools.util.inventory_generator import (
    crawl_feed_for_inventory,
    generate_inventory_csv,
    generate_inventory_xml
)

inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route("/inventory-report", methods=["GET", "POST"])
def inventory_report_view():
    """
    Main view for generating inventory reports.
    """
    # Handle form submission
    # Crawl feed
    # Cache results
    # Render template with data

@inventory_bp.route("/inventory-report/download-csv", methods=["GET"])
def download_csv():
    """
    Download CSV report.
    """
    # Get cached data
    # Generate CSV
    # Return as attachment

@inventory_bp.route("/inventory-report/download-xml", methods=["GET"])
def download_xml():
    """
    Download XML report.
    """
    # Get cached data
    # Generate XML
    # Return as attachment
```

### 3. Template Design (`templates/inventory_report.html`)

Structure:
1. **Header Section**
   - Title: "OPDS Inventory Report Generator"
   - Description

2. **Input Form**
   - Feed URL input field
   - Optional: Max pages limit
   - Optional: Basic auth fields (username/password)
   - Generate button

3. **Results Section** (shown after generation)
   - Summary statistics:
     - Total publications
     - Pages crawled
     - Format breakdown
     - DRM breakdown
   - Download buttons (CSV, XML)
   - Data preview table (first 20 rows)

4. **Progress Indicator**
   - Show during crawling

### 4. Integration Points

#### In `opds_tools/__init__.py`:
```python
from .routes.inventory import inventory_bp
# ...
app.register_blueprint(inventory_bp)
```

#### In `templates/base.html`:
Add to OPDS Utilities dropdown:
```html
<li>
  <a class="dropdown-item" href="{{ url_for('inventory.inventory_report_view') }}">
    <i class="bi bi-file-earmark-spreadsheet me-1"></i> Generate Inventory Report
  </a>
</li>
```

## Data Structure

### Inventory Record Format
```python
{
    'identifier': 'urn:isbn:9781234567890',
    'title': 'Example Book Title',
    'author': 'Author Name',
    'publisher': 'Publisher Name',
    'format': 'EPUB, PDF',  # Comma-separated if multiple
    'drm': 'LCP DRM'  # or 'Bearer Token', 'None', etc.
}
```

### CSV Output Format
```csv
identifier,title,author,publisher,format,drm
urn:isbn:9781234567890,Example Book Title,Author Name,Publisher Name,"EPUB, PDF",LCP DRM
```

### XML Output Format
```xml
<?xml version="1.0" encoding="UTF-8"?>
<inventory>
  <publication>
    <identifier>urn:isbn:9781234567890</identifier>
    <title>Example Book Title</title>
    <author>Author Name</author>
    <publisher>Publisher Name</publisher>
    <format>EPUB, PDF</format>
    <drm>LCP DRM</drm>
  </publication>
  <!-- More publications... -->
</inventory>
```

## Error Handling

1. **Network Errors**: Catch and display friendly error messages
2. **Invalid URLs**: Validate URL format before crawling
3. **Pagination Issues**: Handle broken next links gracefully
4. **Missing Data**: Use empty strings or "N/A" for missing fields
5. **Timeout**: Implement reasonable timeout for large feeds

## Performance Considerations

1. **Caching**: Store results in memory for download generation
2. **Progress Updates**: Consider adding async progress updates for large feeds
3. **Limits**: Offer max_pages option to limit crawling
4. **Efficiency**: Reuse existing parser functions where possible

## Testing Strategy

1. Test with various OPDS feeds:
   - Different pagination styles
   - Various DRM types
   - Different format combinations
2. Test error scenarios:
   - Invalid URLs
   - Network failures
   - Malformed feeds
3. Verify CSV and XML output format
4. Test download functionality

## Future Enhancements

1. Add JSON export option
2. Add filtering options (by format, DRM type, etc.)
3. Support for scheduled/automated reports
4. Database storage of inventory snapshots
5. Comparison between different feed versions
6. Excel (XLSX) export option

## Implementation Steps

1. ✅ Create design document
2. Create `inventory_generator.py` utility
3. Create `inventory.py` route
4. Create `inventory_report.html` template
5. Register blueprint in `__init__.py`
6. Add navigation link in `base.html`
7. Test with sample OPDS feeds
8. Document usage in README

## Dependencies

Existing dependencies in `requirements.txt` should cover needs:
- Flask (web framework)
- requests (HTTP requests)
- csv (built-in, CSV generation)
- xml.etree.ElementTree (built-in, XML generation)

## Security Considerations

1. **URL Validation**: Validate and sanitize input URLs
2. **Auth Handling**: Securely handle basic auth credentials
3. **Rate Limiting**: Consider rate limiting for public deployments
4. **Input Sanitization**: Sanitize all extracted data before display
5. **File Size Limits**: Limit output file sizes for very large feeds
