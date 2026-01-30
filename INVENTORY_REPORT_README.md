# OPDS Inventory Report Feature

## Overview
The OPDS Inventory Report feature allows you to generate downloadable inventory reports from OPDS 2.0 feeds in CSV or XML format. This is useful for cataloging, analysis, and documentation of digital library collections.

## Features

✅ **Automated Feed Crawling**: Automatically pages through entire OPDS feeds following `rel="next"` links  
✅ **Format Detection**: Identifies publication formats (EPUB, PDF, WebPub, Audiobook, etc.)  
✅ **DRM Detection**: Detects DRM types (LCP, Adobe, Bearer Token, None)  
✅ **Multiple Export Formats**: Download as CSV or Excel (.xlsx) spreadsheets  
✅ **Statistics Dashboard**: View format and DRM distribution before downloading  
✅ **Data Preview**: Preview first 20 records in the browser  
✅ **Basic Auth Support**: Optional username/password for protected feeds  
✅ **Page Limiting**: Optionally limit crawling to a specific number of pages

## How to Use

### Access the Feature

1. Start your OPDS Tools application
2. Navigate to **OPDS Utilities** → **Generate Inventory Report**
3. Or visit: `http://localhost:5000/inventory-report`

### Generate a Report

1. **Enter Feed URL**: Provide the URL of an OPDS 2.0 feed
   - Example: `https://example.com/opds/catalog.json`

2. **Optional Settings**:
   - **Max Pages**: Limit the number of pages to crawl (leave empty for unlimited)
   - **Username/Password**: For feeds requiring Basic Authentication

3. **Click "Generate Inventory"**: The system will:
   - Crawl through all pages of the feed
   - Extract publication metadata
   - Display summary statistics
   - Show format and DRM distribution
   - Preview the data

4. **Download Results**:
   - Click **Download CSV** for CSV spreadsheet format
   - Click **Download Excel** for Excel (.xlsx) format with formatted headers and frozen rows

## Report Contents

Each inventory record includes:

| Column | Description | Example |
|--------|-------------|---------|
| **identifier** | Publication identifier (ISBN, URN, etc.) | `urn:isbn:9781234567890` |
| **title** | Publication title | `"The Great Gatsby"` |
| **author** | Author name(s) | `"F. Scott Fitzgerald"` |
| **publisher** | Publisher name | `"Scribner"` |
| **format** | Media format(s) | `"EPUB, PDF"` |
| **drm** | DRM protection type | `"LCP DRM"`, `"None"`, `"Bearer Token"` |

## Output Formats

### CSV Format
```csv
identifier,title,author,publisher,format,drm
urn:isbn:9781234567890,The Great Gatsby,F. Scott Fitzgerald,Scribner,"EPUB, PDF",None
urn:isbn:9780987654321,1984,George Orwell,Penguin,EPUB,LCP DRM
```

### Excel (.xlsx) Format
Professional Excel spreadsheet with:
- **Formatted headers**: Blue background with white text
- **Frozen header row**: Headers stay visible when scrolling
- **Auto-adjusted columns**: Each column sized appropriately
- **Clean formatting**: Left-aligned text with word wrapping
- **Professional appearance**: Ready to share with stakeholders

## Format Detection

The system detects the following formats from MIME types in acquisition links:

- **EPUB**: `application/epub+zip`
- **PDF**: `application/pdf`
- **WebPub**: `application/webpub+json`
- **Audiobook**: `application/audiobook+json`
- **DiViNa**: `application/divina+json`
- **Comic**: `application/vnd.comicbook+zip`
- **MOBI**: `application/x-mobipocket-ebook`

## DRM Detection

The system detects the following DRM types:

- **LCP DRM**: Readium LCP protection
- **Adobe DRM**: Adobe ADEPT DRM
- **Bearer Token**: Token-based authentication
- **DRM**: Generic DRM (when specific type unknown)
- **None**: No DRM protection
- **Unknown**: Unable to determine

## Statistics Dashboard

The report includes:

- **Total Publications**: Number of publications found
- **Pages Crawled**: Number of feed pages processed
- **Unique Formats**: Number of distinct format types
- **DRM Types**: Number of distinct DRM types
- **Format Distribution**: Bar chart showing format breakdown with percentages
- **DRM Distribution**: Bar chart showing DRM breakdown with percentages

## Use Cases

### 1. Collection Analysis
Generate reports to analyze your digital library:
- What formats are available?
- How much content is DRM-protected?
- What's the total collection size?

### 2. Vendor Reporting
Provide inventory reports to stakeholders:
- Share collection statistics
- Document available formats
- Track DRM usage

### 3. Migration Planning
Assess collections before migration:
- Identify format compatibility
- Plan DRM handling strategies
- Estimate workload

### 4. Compliance & Auditing
Document collection contents:
- Track licensed content
- Verify publisher agreements
- Maintain inventory records

## Error Handling

The system handles various error scenarios:

- **Network Errors**: Displays friendly error messages for connection issues
- **Invalid URLs**: Validates URL format before crawling
- **Malformed Feeds**: Continues processing even if some publications have issues
- **Missing Data**: Uses "Unknown" or "N/A" for missing fields
- **Authentication Failures**: Reports auth errors clearly

Errors are displayed in a dedicated section with details about what went wrong.

## Performance Considerations

- **Large Feeds**: For feeds with thousands of publications, consider using the "Max Pages" limit
- **Caching**: Results are cached in memory for quick re-download
- **Timeout**: Network requests timeout after 30 seconds per page
- **Progress**: The system logs progress to help track long-running operations

## Technical Details

### Files Created
- `opds_tools/util/inventory_generator.py` - Core business logic
- `opds_tools/routes/inventory.py` - Flask route handlers
- `opds_tools/templates/inventory_report.html` - User interface

### API Endpoints
- `GET/POST /inventory-report` - Main view
- `GET /inventory-report/download-csv` - CSV download
- `GET /inventory-report/download-xml` - XML download

### Dependencies
Uses existing dependencies:
- `requests` - HTTP requests
- `csv` - CSV generation (built-in)
- `openpyxl` - Excel file generation

## Testing

Run the unit tests:
```bash
python test_inventory.py
```

Tests cover:
- Format extraction
- DRM detection
- Author/publisher parsing
- CSV generation
- XML generation

## Future Enhancements

Potential improvements:
- [ ] JSON export format

- [ ] Filter by format or DRM type
- [ ] Scheduled/automated reports
- [ ] Database storage of snapshots
- [ ] Comparison between feed versions
- [ ] Advanced statistics and charts

## Support

For issues or questions:
1. Check the error messages in the UI
2. Review application logs
3. Verify feed URL is accessible
4. Ensure feed is valid OPDS 2.0 format

## License

Part of OPDS Tools - see main project license.
