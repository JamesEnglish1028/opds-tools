# OPDS Feed Format Analyzer - Implementation Plan

## Feature Overview
Add a new utility to analyze OPDS feeds by publication format and DRM type without validation overhead.

**Objective:** Page through an OPDS feed and generate a statistical report showing:
- Publication counts by format (PDF, EPUB, etc.)
- DRM type breakdown for EPUBs (No DRM, Adobe DRM, LCP DRM)
- Summary statistics by page and overall

---

## Architecture Analysis

### Current Structure
```
opds_tools/
├── routes/
│   ├── validate.py          ← Validation route (reference)
│   ├── main.py              ← View catalogs
│   ├── opds_crawler.py      ← Crawl & ingest
│   └── [NEW] analyze.py     ← Format analyzer route
├── util/
│   ├── palace_validator.py  ← Has fetch_all_pages() function
│   └── [NEW] feed_analyzer.py ← Format analysis logic
└── templates/
    ├── validate_feed.html    ← Validation UI (reference)
    └── [NEW] analyze_feed.html ← Analysis UI
```

### Key Existing Components to Reuse

**1. `palace_validator.py::fetch_all_pages()`**
- Already paginates through OPDS feeds
- Handles next page links
- Returns dict of {url: feed_data}
- **Can reuse this directly!**

**2. Template Pattern from `validate_feed.html`**
- URL input field
- Max pages limiter
- Download JSON report button
- Results display cards

---

## Implementation Plan

### Phase 1: Backend Utility (New File)

**File:** `opds_tools/util/feed_analyzer.py`

```python
"""
OPDS Feed Format Analyzer

Analyzes OPDS feeds for publication format and DRM statistics
without performing validation.
"""

from typing import Dict, List, Any
from collections import defaultdict
from opds_tools.util.palace_validator import fetch_all_pages


def detect_format(publication: dict) -> str:
    """
    Detect publication format from links.
    
    Checks link types in order of priority:
    - application/epub+zip → EPUB
    - application/pdf → PDF
    - Other types as-is
    
    Returns:
        Format string (e.g., "EPUB", "PDF", "UNKNOWN")
    """
    links = publication.get("links", [])
    
    for link in links:
        link_type = link.get("type", "").lower()
        
        if "epub" in link_type:
            return "EPUB"
        elif "pdf" in link_type:
            return "PDF"
        elif "audiobook" in link_type:
            return "AUDIOBOOK"
        elif link_type:
            # Extract format from MIME type (e.g., application/vnd.something)
            return link_type.split("/")[-1].upper()
    
    return "UNKNOWN"


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
    max_pages: int = None
) -> Dict[str, Any]:
    """
    Analyze an OPDS feed for format and DRM statistics.
    
    Args:
        url: Starting OPDS feed URL
        max_pages: Maximum pages to fetch (None = all)
        
    Returns:
        Dictionary with:
        - format_counts: {format: count}
        - drm_counts: {drm_type: count} (EPUBs only)
        - page_stats: [{url, formats, drm_types}]
        - summary: {total_pubs, pages_analyzed, formats, drm_types}
    """
    # Fetch all pages
    feeds = fetch_all_pages(url, max_pages=max_pages)
    
    # Aggregated statistics
    format_counts = defaultdict(int)
    drm_counts = defaultdict(int)
    page_stats = []
    total_publications = 0
    
    for page_url, feed_data in feeds.items():
        # Skip error pages
        if "error" in feed_data:
            page_stats.append({
                "url": page_url,
                "error": feed_data["error"]
            })
            continue
        
        # Page-level statistics
        page_formats = defaultdict(int)
        page_drm = defaultdict(int)
        
        publications = feed_data.get("publications", [])
        
        for pub in publications:
            total_publications += 1
            
            # Detect format
            format_type = detect_format(pub)
            format_counts[format_type] += 1
            page_formats[format_type] += 1
            
            # Detect DRM (EPUBs only)
            drm_type = detect_drm_type(pub, format_type)
            if drm_type != "N/A":
                drm_counts[drm_type] += 1
                page_drm[drm_type] += 1
        
        page_stats.append({
            "url": page_url,
            "publication_count": len(publications),
            "formats": dict(page_formats),
            "drm_types": dict(page_drm)
        })
    
    return {
        "format_counts": dict(format_counts),
        "drm_counts": dict(drm_counts),
        "page_stats": page_stats,
        "summary": {
            "total_publications": total_publications,
            "pages_analyzed": len([p for p in page_stats if "error" not in p]),
            "pages_with_errors": len([p for p in page_stats if "error" in p]),
            "unique_formats": len(format_counts),
            "unique_drm_types": len([d for d in drm_counts.keys() if d != "N/A"])
        }
    }
```

---

### Phase 2: Flask Route (New File)

**File:** `opds_tools/routes/analyze.py`

```python
from flask import Blueprint, request, render_template, Response
import json

from opds_tools.util.feed_analyzer import analyze_feed_url

analyze_bp = Blueprint("analyze", __name__)


@analyze_bp.route("/analyze-feed", methods=["GET", "POST"])
def analyze_feed_view():
    """
    Analyze OPDS feed for format and DRM statistics.
    """
    results = {}
    feed_url = ""
    max_pages = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "clear":
            return render_template("analyze_feed.html", results={}, feed_url="", max_pages=None)

        feed_url = request.form.get("feed_url")
        max_pages_input = request.form.get("max_pages")

        if max_pages_input:
            try:
                max_pages = int(max_pages_input)
                if max_pages < 1:
                    max_pages = None
            except ValueError:
                max_pages = None

        download_json = request.form.get("download_json")
        
        if feed_url:
            # Run analysis
            results = analyze_feed_url(feed_url, max_pages=max_pages)
            
            if download_json:
                return Response(
                    json.dumps(results, indent=2),
                    mimetype="application/json",
                    headers={"Content-Disposition": "attachment;filename=feed_analysis.json"}
                )

    return render_template("analyze_feed.html", results=results, feed_url=feed_url, max_pages=max_pages)
```

---

### Phase 3: Frontend Template (New File)

**File:** `opds_tools/templates/analyze_feed.html`

```html
{% extends "base.html" %}
{% block title %}Analyze OPDS Feed{% endblock %}

{% block content %}
<div class="container py-4">
  <h3 class="mb-4">📊 Analyze OPDS Feed Format & DRM</h3>
  
  <div class="alert alert-info">
    <i class="bi bi-info-circle me-1"></i>
    <strong>What this does:</strong> Pages through an OPDS feed and generates a report on publication formats (PDF, EPUB) and DRM types (Adobe, LCP, None) without performing validation.
  </div>

  <form method="POST" class="mb-4">
    <div class="row g-2 align-items-end">
      <div class="col-md-6">
        <label for="feed_url" class="form-label">Feed URL</label>
        <input type="url" id="feed_url" name="feed_url" class="form-control" 
               placeholder="Enter OPDS feed URL" required value="{{ feed_url }}">
      </div>
      <div class="col-md-2">
        <label for="max_pages" class="form-label">Max Pages</label>
        <input type="number" id="max_pages" name="max_pages" class="form-control" 
               placeholder="e.g. 5" min="1" value="{{ max_pages or '' }}">
      </div>
      <div class="col-md-auto d-flex gap-2">
        <button type="submit" class="btn btn-primary" name="action" value="analyze">Analyze</button>
        <button type="submit" class="btn btn-outline-secondary" name="action" value="clear">Clear</button>
      </div>
    </div>
  </form>

  {% if results %}
    <form method="POST" action="{{ url_for('analyze.analyze_feed_view') }}" class="mb-3">
      <input type="hidden" name="feed_url" value="{{ feed_url }}">
      <input type="hidden" name="max_pages" value="{{ max_pages or '' }}">
      <input type="hidden" name="download_json" value="1">
      <button type="submit" class="btn btn-outline-secondary btn-sm">⬇️ Download JSON Report</button>
    </form>

    <!-- Summary Card -->
    <div class="card mb-3">
      <div class="card-header bg-primary text-white">
        <i class="bi bi-bar-chart me-1"></i> Analysis Summary
      </div>
      <div class="card-body">
        <div class="row">
          <div class="col-md-3">
            <p class="mb-1"><strong>Total Publications:</strong></p>
            <h4>{{ results.summary.total_publications }}</h4>
          </div>
          <div class="col-md-3">
            <p class="mb-1"><strong>Pages Analyzed:</strong></p>
            <h4>{{ results.summary.pages_analyzed }}</h4>
          </div>
          <div class="col-md-3">
            <p class="mb-1"><strong>Unique Formats:</strong></p>
            <h4>{{ results.summary.unique_formats }}</h4>
          </div>
          <div class="col-md-3">
            <p class="mb-1"><strong>DRM Types:</strong></p>
            <h4>{{ results.summary.unique_drm_types }}</h4>
          </div>
        </div>
      </div>
    </div>

    <!-- Format Distribution Card -->
    <div class="card mb-3">
      <div class="card-header">
        <i class="bi bi-file-earmark me-1"></i> Format Distribution
      </div>
      <div class="card-body">
        <table class="table table-striped">
          <thead>
            <tr>
              <th>Format</th>
              <th>Count</th>
              <th>Percentage</th>
              <th>Visual</th>
            </tr>
          </thead>
          <tbody>
            {% for format, count in results.format_counts.items() %}
            <tr>
              <td><strong>{{ format }}</strong></td>
              <td>{{ count }}</td>
              <td>{{ "%.1f"|format((count / results.summary.total_publications * 100)) }}%</td>
              <td>
                <div class="progress" style="height: 20px;">
                  <div class="progress-bar" role="progressbar" 
                       style="width: {{ (count / results.summary.total_publications * 100) }}%"
                       aria-valuenow="{{ count }}" aria-valuemin="0" 
                       aria-valuemax="{{ results.summary.total_publications }}">
                  </div>
                </div>
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>

    <!-- DRM Distribution Card (EPUBs) -->
    {% if results.drm_counts %}
    <div class="card mb-3">
      <div class="card-header">
        <i class="bi bi-shield-lock me-1"></i> DRM Distribution (EPUBs Only)
      </div>
      <div class="card-body">
        {% set epub_total = results.format_counts.get('EPUB', 0) %}
        <table class="table table-striped">
          <thead>
            <tr>
              <th>DRM Type</th>
              <th>Count</th>
              <th>Percentage of EPUBs</th>
              <th>Visual</th>
            </tr>
          </thead>
          <tbody>
            {% for drm, count in results.drm_counts.items() %}
            {% if drm != "N/A" %}
            <tr>
              <td>
                <strong>{{ drm.replace("_", " ") }}</strong>
                {% if drm == "NO_DRM" %}
                  <span class="badge bg-success">Open</span>
                {% elif drm == "ADOBE_DRM" %}
                  <span class="badge bg-warning">Adobe</span>
                {% elif drm == "LCP_DRM" %}
                  <span class="badge bg-info">LCP</span>
                {% endif %}
              </td>
              <td>{{ count }}</td>
              <td>
                {% if epub_total > 0 %}
                  {{ "%.1f"|format((count / epub_total * 100)) }}%
                {% else %}
                  N/A
                {% endif %}
              </td>
              <td>
                {% if epub_total > 0 %}
                <div class="progress" style="height: 20px;">
                  <div class="progress-bar 
                    {% if drm == 'NO_DRM' %}bg-success
                    {% elif drm == 'ADOBE_DRM' %}bg-warning
                    {% elif drm == 'LCP_DRM' %}bg-info
                    {% endif %}" 
                    role="progressbar" 
                    style="width: {{ (count / epub_total * 100) }}%"
                    aria-valuenow="{{ count }}" aria-valuemin="0" 
                    aria-valuemax="{{ epub_total }}">
                  </div>
                </div>
                {% endif %}
              </td>
            </tr>
            {% endif %}
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    {% endif %}

    <!-- Page-by-Page Details (Collapsible) -->
    <div class="card">
      <div class="card-header">
        <a class="text-decoration-none text-dark" data-bs-toggle="collapse" href="#pageDetails">
          <i class="bi bi-chevron-down me-1"></i> Page-by-Page Details
        </a>
      </div>
      <div class="collapse" id="pageDetails">
        <div class="card-body">
          {% for page in results.page_stats %}
            <div class="mb-3 pb-3 border-bottom">
              <h6>{{ page.url }}</h6>
              {% if page.error %}
                <p class="text-danger">❌ Error: {{ page.error }}</p>
              {% else %}
                <p class="mb-1"><strong>Publications:</strong> {{ page.publication_count }}</p>
                <p class="mb-1"><strong>Formats:</strong> {{ page.formats }}</p>
                <p class="mb-1"><strong>DRM Types:</strong> {{ page.drm_types }}</p>
              {% endif %}
            </div>
          {% endfor %}
        </div>
      </div>
    </div>

  {% endif %}
</div>
{% endblock %}
```

---

### Phase 4: Integration

**1. Register Blueprint in `opds_tools/__init__.py`**

Add these lines:
```python
from .routes.analyze import analyze_bp

# In create_app():
app.register_blueprint(analyze_bp)
```

**2. Add Menu Link in `opds_tools/templates/base.html`**

Find the OPDS Utilities dropdown (around line 55) and add:
```html
<li>
  <a class="dropdown-item" href="{{ url_for('analyze.analyze_feed_view') }}">
    <i class="bi bi-bar-chart me-1"></i> Analyze Feed Format & DRM
  </a>
</li>
```

---

## Testing Plan

### Test Cases

**1. Format Detection**
- Test feed with mixed PDF/EPUB
- Test feed with only EPUBs
- Test feed with audiobooks
- Test feed with unknown formats

**2. DRM Detection**
- Test with LCP DRM EPUBs
- Test with Adobe DRM EPUBs
- Test with DRM-free EPUBs
- Test with mixed DRM types

**3. Pagination**
- Test with single page feed
- Test with multi-page feed
- Test with max_pages limiter
- Test with broken pagination

**4. Error Handling**
- Test with invalid URL
- Test with non-OPDS feed
- Test with feed that returns errors mid-pagination

---

## File Checklist

- [ ] Create `opds_tools/util/feed_analyzer.py`
- [ ] Create `opds_tools/routes/analyze.py`
- [ ] Create `opds_tools/templates/analyze_feed.html`
- [ ] Update `opds_tools/__init__.py` to register blueprint
- [ ] Update `opds_tools/templates/base.html` to add menu link
- [ ] Test with sample OPDS feeds
- [ ] Document in README

---

## Advantages of This Approach

✅ **Reuses existing code** - `fetch_all_pages()` already handles pagination  
✅ **No validation overhead** - Fast analysis without schema/pydantic checks  
✅ **Follows existing patterns** - Similar to validate route structure  
✅ **Clean separation** - Analysis logic isolated in util module  
✅ **Extensible** - Easy to add more statistics later  
✅ **User-friendly** - Visual charts and downloadable JSON report  

---

## Future Enhancements (Optional)

- **Chart visualization** using Chart.js or similar
- **Export to CSV** for spreadsheet analysis
- **Language distribution** analysis
- **Publisher statistics**
- **Price range** analysis
- **Historical comparison** (save analysis results to DB)

---

## Estimated Implementation Time

- Backend utility: **2-3 hours**
- Flask route: **30 minutes**
- Frontend template: **2-3 hours**
- Integration & testing: **1-2 hours**
- **Total: 6-9 hours**
