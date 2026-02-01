# ODL Feed Analysis Feature - Implementation Summary

## Overview
Added a comprehensive ODL feed analysis feature to the OPDS Tools application that mirrors the existing OPDS feed analysis capability but tailored specifically for ODL (Open Distribution License) JSON publications.

## New Components Created

### 1. **ODL Analyzer Utility Module** (`opds_tools/util/odl_analyzer.py`)
Core analysis engine that processes ODL feeds and extracts publication metadata.

#### Key Functions:

- **`detect_odl_formats(publication)`**
  - Extracts publication formats from ODL licenses array
  - Returns raw MIME types from each license metadata
  - Example: `["application/epub+zip", "text/html"]`

- **`normalize_format_type(format_str)`**
  - Converts MIME types to readable publication types
  - Maps: EPUB, PDF, Audiobook, WebPublication, etc.
  - Enables consistent reporting across different MIME type variations

- **`classify_odl_publication_type(publication)`**
  - Classifies publications by schema.org type
  - Returns: Book, Audiobook, Periodical, or Other
  - Analyzes metadata.@type field

- **`detect_odl_drm_scheme(publication)`**
  - Identifies DRM protection schemes
  - Detects: Adobe DRM, Readium LCP, No DRM
  - Examines protection.format field in licenses

- **`extract_license_terms(publication)`**
  - Extracts licensing information
  - Captures: concurrency, lending period, price, markets
  - Returns: copy/print/TTS restrictions, device limits

- **`analyze_odl_feed(feed_url, auth, max_pages, progress_callback)`**
  - Main analysis function that orchestrates feed processing
  - Supports pagination through ODL feeds
  - Optional authentication support
  - Generates comprehensive statistics
  - Provides progress callbacks for UI updates

#### Output Structure:
```python
{
    "summary": {
        "total_publications": int,
        "pages_analyzed": int,
        "pages_with_errors": int,
        "unique_formats": int,
        "unique_media_types": int,
        "unique_drm_schemes": int,
        "media_type_counts": {media_type: count},
        "drm_scheme_counts": {scheme: count},
        "publication_type_counts": {type: count},
        "publication_type_percentages": {type: percentage}
    },
    "media_type_stats": [{media_type, count, percentage}, ...],
    "drm_scheme_stats": [{drm_scheme, count, percentage}, ...],
    "publication_type_stats": [{type, count, percentage}, ...],
    "format_counts": {mime_type: count},
    "page_stats": [{url, publication_count, media_types, drm_schemes, ...}, ...]
}
```

### 2. **ODL Analysis Route Handler** (`opds_tools/routes/analyze_odl.py`)
Flask blueprint that handles HTTP requests for ODL feed analysis.

#### Routes:

- **`POST/GET /analyze-odl-feed`**
  - Main analysis interface
  - Accepts: feed_url, max_pages, username (optional), password (optional)
  - Caches results in memory for subsequent GET requests
  - Supports download of JSON reports

- **`GET /analyze-odl-feed/pdf`**
  - Generates PDF reports from cached analysis results
  - Includes summary statistics, media type distribution, DRM schemes

#### Features:
- Result caching to prevent re-analysis on page refresh
- JSON download capability for raw data
- PDF report generation with professional formatting
- Error handling and logging
- Pagination limiting for large datasets (displays first 20 + last 5 pages)

### 3. **ODL Analysis Template** (`opds_tools/templates/analyze_odl_feed.html`)
Bootstrap-based responsive UI for ODL feed analysis.

#### Sections:

1. **Input Form**
   - Feed URL field (required)
   - Max pages limit
   - Optional authentication (username/password for protected feeds)
   - Analyze and Clear buttons

2. **Summary Card**
   - Total publications count
   - Pages analyzed
   - Unique media types
   - Unique DRM schemes
   - Publication type breakdown (Book, Audiobook, Periodical, Other)

3. **Media Type Distribution**
   - Tabular view of formats (EPUB, PDF, WebPublication, Audiobook, etc.)
   - Count and percentage for each media type
   - Visual progress bars

4. **DRM Scheme Distribution**
   - Breakdown of DRM protection types
   - Color-coded badges (Adobe DRM = warning, LCP = info, No DRM = success)
   - Percentage and count statistics

5. **Format MIME Types (Detailed)**
   - Raw MIME type information from licenses
   - Useful for technical analysis and debugging

6. **Page-by-Page Details**
   - Collapsible section showing per-page statistics
   - Displays first 20 and last 5 pages for large feeds
   - Can download JSON for complete details

7. **Progress Indicator**
   - Shows during analysis
   - Updates with: pages fetched, publications counted, errors encountered
   - Real-time progress bar

### 4. **Configuration & Registration**

#### Modified Files:
- **`opds_tools/__init__.py`**
  - Added import: `from .routes.analyze_odl import odl_analyze_bp`
  - Registered blueprint: `app.register_blueprint(odl_analyze_bp)`

- **`opds_tools/templates/base.html`**
  - Added navigation menu item in ODL Utilities dropdown
  - Link: "Analyze ODL Feed Format & DRM"
  - Icon: bar-chart

## Feature Comparison: OPDS vs ODL Analysis

| Aspect | OPDS | ODL |
|--------|------|-----|
| **Format Detection** | From publication links | From license metadata |
| **Media Types** | EPUB, PDF, AUDIOBOOK, etc. | EPUB, PDF, WebPublication, Audiobook, etc. |
| **DRM Schemes** | Bearer Token, Adobe, LCP | Adobe DRM, Readium LCP, No DRM |
| **Publication Types** | Book, Audiobook, Periodical | Book, Audiobook, Periodical |
| **License Terms** | Not extracted | Extracted (concurrency, lending, price, markets) |
| **Authentication** | Not supported | Supported (optional username/password) |
| **Pagination** | Via next link in feed | Via next link in feed |

## Technical Highlights

1. **ODL-Specific Format Handling**
   - Properly parses ODL licenses array structure
   - Extracts metadata from each license object
   - Normalizes MIME types to readable formats

2. **DRM Detection**
   - Examines protection.format field for DRM indicators
   - Distinguishes between Adobe DRM and Readium LCP
   - Identifies unprotected publications

3. **Comprehensive Statistics**
   - Per-page statistics for detailed analysis
   - Aggregated summary statistics
   - Percentage calculations
   - Publication type classification

4. **Authentication Support**
   - Optional credentials for protected ODL feeds
   - Passed to requests.get() via auth parameter
   - Credentials not logged or stored permanently

5. **Error Handling**
   - Gracefully handles pages with errors
   - Tracks error count in results
   - Continues processing remaining pages
   - Provides error messages in page-by-page details

## Usage

1. Navigate to: **ODL Utilities > Analyze ODL Feed Format & DRM** from the main menu
2. Enter ODL feed URL (required)
3. Optionally:
   - Set max pages limit (leave blank for all pages)
   - Provide authentication credentials if feed requires it
4. Click "Analyze" to start processing
5. View results with:
   - Summary statistics
   - Media type distribution
   - DRM scheme breakdown
   - Publication type analysis
6. Download results as JSON or PDF for sharing/archiving

## Sample Analysis Results

For the Brightwood ODL publication provided:
- **Media Type**: application/epub+zip → EPUB
- **Publication Type**: Book (schema.org/Book)
- **DRM Schemes Detected**: Adobe DRM (application/vnd.adobe.adept+xml), Readium LCP
- **License Terms**: 
  - Concurrency: 1
  - Lending Period: 5,097,600 seconds (~59 days)
  - Price: $16.95 USD
  - Markets: public_library, academic_library, corporate
  - Restrictions: No copy, No print, No TTS

## Future Enhancement Possibilities

1. **License Term Analysis**
   - Enhanced reporting on licensing restrictions
   - Comparison of different market configurations
   - Term matrix analysis

2. **Advanced Filtering**
   - Filter by DRM scheme
   - Filter by media type
   - Filter by publication type
   - Filter by price range

3. **Batch Analysis**
   - Analyze multiple feeds simultaneously
   - Comparative analysis across sources

4. **Visualization**
   - Charts and graphs for distribution data
   - Heat maps for format/DRM combinations

5. **Export Options**
   - CSV export for spreadsheet analysis
   - Excel with formatting
   - Custom report templates
