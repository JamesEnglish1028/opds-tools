# ODL DRM Detection Logic Analysis

## Executive Summary

The ODL analyzer classifies publications into three DRM categories:
- **"No DRM"** - Publications with no protection or missing protection fields
- **"Unknown DRM"** - Publications with protection field present but unrecognized DRM format
- **Specific DRM** (Adobe DRM, Readium LCP, Watermark) - Publications with recognized DRM schemes

---

## JSON Structures That Trigger Each Classification

### 🔓 "No DRM" Classification

Publications return **"No DRM"** when:

#### 1. No `licenses` field exists
```json
{
  "metadata": {
    "@type": "http://schema.org/Book",
    "title": "My Book"
  }
  // NO licenses field at all
}
```

#### 2. Empty `licenses` array
```json
{
  "metadata": {...},
  "licenses": []  // Empty array
}
```

#### 3. License exists but NO `protection` field
```json
{
  "metadata": {...},
  "licenses": [
    {
      "metadata": {
        "identifier": "lic-123",
        "format": ["application/epub+zip"]
        // NO protection field
      }
    }
  ]
}
```
**This is the most common scenario for DRM-free ODL publications.**

#### 4. License has empty `protection` object
```json
{
  "metadata": {...},
  "licenses": [
    {
      "metadata": {
        "identifier": "lic-456",
        "format": ["application/epub+zip"],
        "protection": {}  // Empty object (falsy in Python)
      }
    }
  ]
}
```

---

### 🔒 "Unknown DRM" Classification

Publications return **"Unknown DRM"** when:

#### 1. Protection exists with empty format array
```json
{
  "metadata": {...},
  "licenses": [
    {
      "metadata": {
        "identifier": "lic-789",
        "format": ["application/epub+zip"],
        "protection": {
          "format": []  // Empty array - protection exists but no format specified
        }
      }
    }
  ]
}
```

#### 2. Protection with unrecognized DRM format
```json
{
  "metadata": {...},
  "licenses": [
    {
      "metadata": {
        "identifier": "lic-101",
        "format": ["application/epub+zip"],
        "protection": {
          "format": ["application/vnd.custom.drm+xml"]  // Custom/unknown DRM
        }
      }
    }
  ]
}
```

**Any DRM format string that doesn't contain:**
- "adobe" or "adept"
- "readium" or "lcp"
- "watermark"

Will be classified as "Unknown DRM".

---

### ✅ Specific DRM Classifications

#### Adobe DRM
```json
{
  "metadata": {...},
  "licenses": [
    {
      "metadata": {
        "protection": {
          "format": ["application/vnd.adobe.adept+xml"]
        }
      }
    }
  ]
}
```

Detection: Format string contains `"adobe"` or `"adept"` (case-insensitive)

---

#### Readium LCP
```json
{
  "metadata": {...},
  "licenses": [
    {
      "metadata": {
        "protection": {
          "format": ["application/vnd.readium.lcp.license.v1.0+json"]
        }
      }
    }
  ]
}
```

Detection: Format string contains `"readium"` or `"lcp"` (case-insensitive)

---

#### Watermark
```json
{
  "metadata": {...},
  "licenses": [
    {
      "metadata": {
        "protection": {
          "format": ["application/vnd.watermark+json"]
        }
      }
    }
  ]
}
```

Detection: Format string contains `"watermark"` (case-insensitive)

---

## Code Logic Flow

```python
def detect_odl_drm_scheme(publication: dict) -> List[str]:
    drm_schemes = set()
    
    licenses = publication.get("licenses", [])
    
    # If no licenses or not a list → "No DRM"
    if not isinstance(licenses, list):
        return ["No DRM"]
    
    has_any_protection = False
    
    for license_obj in licenses:
        metadata = license_obj.get("metadata", {})
        protection = metadata.get("protection", {})
        
        # If protection is empty/missing → skip this license
        if not protection:
            continue
        
        # Protection exists (even if empty format array)
        has_any_protection = True
        
        # Check format strings
        formats = protection.get("format", [])
        for fmt in formats:
            if "adobe" in fmt.lower() or "adept" in fmt.lower():
                drm_schemes.add("Adobe DRM")
            elif "readium" in fmt.lower() or "lcp" in fmt.lower():
                drm_schemes.add("Readium LCP")
            elif "watermark" in fmt.lower():
                drm_schemes.add("Watermark")
    
    # Return results
    if drm_schemes:
        return sorted(list(drm_schemes))
    
    # No DRM found
    if not has_any_protection:
        return ["No DRM"]
    else:
        return ["Unknown DRM"]  # Protection exists but not recognized
```

---

## Key Insights

### Critical Detection Point
The **presence of a `protection` field** (even if empty object `{}`) determines classification:

| Scenario | `protection` field | DRM Classification |
|----------|-------------------|-------------------|
| Field missing entirely | ❌ No | **No DRM** |
| Field is empty object `{}` | ❌ No (falsy) | **No DRM** |
| Field has `{"format": []}` | ✅ Yes (truthy) | **Unknown DRM** |
| Field has recognized format | ✅ Yes | **Adobe DRM / LCP / Watermark** |
| Field has unrecognized format | ✅ Yes | **Unknown DRM** |

### Python Truthiness
The code uses `if not protection:` which evaluates:
- Empty dict `{}` → False (skips, counts as No DRM)
- Dict with any content `{"format": []}` → True (has_any_protection = True)

---

## Sample Real-World ODL Publication

Most DRM-free ODL publications look like this:

```json
{
  "metadata": {
    "@type": "http://schema.org/Book",
    "title": "Sample ODL Book",
    "author": [{"name": "John Doe"}],
    "identifier": "urn:isbn:9781234567890"
  },
  "licenses": [
    {
      "metadata": {
        "identifier": "license-uuid-12345",
        "format": ["application/epub+zip", "application/pdf"],
        "created": "2025-01-01T00:00:00Z",
        "price": {
          "currency": "USD",
          "value": 9.99
        },
        "terms": {
          "concurrency": 5,
          "expires": "2026-01-01T00:00:00Z"
        }
        // NOTE: No "protection" field
      },
      "links": [...]
    }
  ],
  "images": [...],
  "links": [...]
}
```

**Classification: "No DRM"** (no protection field in license metadata)

---

## Testing Your Feed

To determine which publications cause "Unknown DRM" counts:

1. **Look for licenses with `protection` field present**
2. **Check the `protection.format` array values**
3. **If format doesn't match known patterns → "Unknown DRM"**

### Example Query (if data is in database):
```sql
SELECT 
  data->>'title' as title,
  data->'licenses'->0->'metadata'->'protection' as protection
FROM odl_publications
WHERE 
  data->'licenses'->0->'metadata'->'protection' IS NOT NULL
  AND data->'licenses'->0->'metadata'->'protection' != '{}'::jsonb;
```

This will show you all publications with non-empty protection fields.

---

## Recommendations

If you're seeing unexpected "Unknown DRM" counts:

1. **Inspect the actual protection.format values** in your feed
2. **Check for typos** in DRM MIME types
3. **Consider adding new DRM detection patterns** if you encounter legitimate DRM schemes not currently recognized
4. **Verify feed source** - some publishers may use proprietary DRM schemes

---

## Test Script

Run the included test script to verify behavior:

```bash
cd /Users/jamesenglish/Desktop/Projects/opds-tools
source venv/bin/activate
python test_drm_detection.py
```

This will show all classification scenarios with detailed output.
