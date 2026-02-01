#!/usr/bin/env python3
"""
Test script to analyze ODL DRM detection logic.
Tests various publication scenarios to understand "Unknown DRM" vs "No DRM" classification.
"""

import json
from opds_tools.util.odl_analyzer import detect_odl_drm_scheme


# Test Case 1: Publication with NO licenses array
pub_no_licenses = {
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Test Book 1"
    }
}

# Test Case 2: Publication with empty licenses array
pub_empty_licenses = {
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Test Book 2"
    },
    "licenses": []
}

# Test Case 3: License with NO protection field
pub_no_protection = {
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Test Book 3"
    },
    "licenses": [
        {
            "metadata": {
                "identifier": "lic-123",
                "format": ["application/epub+zip"]
            }
        }
    ]
}

# Test Case 4: License with empty protection object
pub_empty_protection = {
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Test Book 4"
    },
    "licenses": [
        {
            "metadata": {
                "identifier": "lic-456",
                "format": ["application/epub+zip"],
                "protection": {}
            }
        }
    ]
}

# Test Case 5: License with protection but empty format array
pub_protection_no_format = {
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Test Book 5"
    },
    "licenses": [
        {
            "metadata": {
                "identifier": "lic-789",
                "format": ["application/epub+zip"],
                "protection": {
                    "format": []
                }
            }
        }
    ]
}

# Test Case 6: License with protection but unrecognized DRM format
pub_unknown_drm = {
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Test Book 6"
    },
    "licenses": [
        {
            "metadata": {
                "identifier": "lic-101",
                "format": ["application/epub+zip"],
                "protection": {
                    "format": ["application/vnd.custom.drm+xml"]
                }
            }
        }
    ]
}

# Test Case 7: License with Adobe DRM
pub_adobe_drm = {
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Test Book 7"
    },
    "licenses": [
        {
            "metadata": {
                "identifier": "lic-102",
                "format": ["application/epub+zip"],
                "protection": {
                    "format": ["application/vnd.adobe.adept+xml"]
                }
            }
        }
    ]
}

# Test Case 8: License with Readium LCP
pub_lcp_drm = {
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Test Book 8"
    },
    "licenses": [
        {
            "metadata": {
                "identifier": "lic-103",
                "format": ["application/epub+zip"],
                "protection": {
                    "format": ["application/vnd.readium.lcp.license.v1.0+json"]
                }
            }
        }
    ]
}

# Test Case 9: Sample publication structure from conversation (typical ODL)
sample_odl_publication = {
    "metadata": {
        "@type": "http://schema.org/Book",
        "title": "Sample ODL Book",
        "author": [{"name": "John Doe"}],
        "identifier": "urn:isbn:9781234567890",
        "modified": "2025-01-15T10:00:00Z"
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
                # Note: NO protection field
            },
            "links": [
                {
                    "href": "https://example.com/license/12345",
                    "type": "application/vnd.odl.info+json",
                    "rel": "self"
                }
            ]
        }
    ],
    "images": [
        {
            "href": "https://example.com/cover.jpg",
            "type": "image/jpeg"
        }
    ],
    "links": [
        {
            "href": "https://example.com/book/12345",
            "type": "application/epub+zip",
            "rel": "http://opds-spec.org/acquisition/borrow"
        }
    ]
}


def test_drm_detection():
    """Run all test cases and display results."""
    
    test_cases = [
        ("No licenses array", pub_no_licenses),
        ("Empty licenses array", pub_empty_licenses),
        ("License with NO protection field", pub_no_protection),
        ("License with EMPTY protection object", pub_empty_protection),
        ("Protection exists but NO format array", pub_protection_no_format),
        ("Protection with UNRECOGNIZED DRM format", pub_unknown_drm),
        ("Adobe DRM", pub_adobe_drm),
        ("Readium LCP DRM", pub_lcp_drm),
        ("Sample ODL Publication (typical)", sample_odl_publication)
    ]
    
    print("=" * 80)
    print("ODL DRM DETECTION ANALYSIS")
    print("=" * 80)
    print()
    
    for test_name, publication in test_cases:
        result = detect_odl_drm_scheme(publication)
        
        print(f"Test: {test_name}")
        print(f"  Result: {result}")
        print(f"  Classification: {'🔒 UNKNOWN DRM' if result == ['Unknown DRM'] else '🔓 NO DRM' if result == ['No DRM'] else '✅ ' + ', '.join(result)}")
        
        # Show the structure
        if "licenses" in publication:
            if publication["licenses"]:
                for idx, lic in enumerate(publication["licenses"]):
                    metadata = lic.get("metadata", {})
                    protection = metadata.get("protection", None)
                    print(f"    License {idx}: protection field = {protection if protection else 'MISSING'}")
            else:
                print(f"    licenses = [] (empty array)")
        else:
            print(f"    licenses field = MISSING")
        
        print()
    
    print("=" * 80)
    print("SUMMARY OF LOGIC:")
    print("=" * 80)
    print()
    print("Returns 'No DRM' when:")
    print("  1. No 'licenses' field exists")
    print("  2. 'licenses' is not a list")
    print("  3. 'licenses' is empty array")
    print("  4. License exists but has NO 'protection' field in metadata")
    print("  5. License has empty 'protection' object (truthy but empty)")
    print()
    print("Returns 'Unknown DRM' when:")
    print("  1. License HAS 'protection' field (non-empty)")
    print("  2. BUT the protection.format does NOT contain recognized DRM types:")
    print("     - Adobe DRM: contains 'adobe' or 'adept'")
    print("     - Readium LCP: contains 'readium' or 'lcp'")
    print("     - Watermark: contains 'watermark'")
    print()
    print("Returns specific DRM name when:")
    print("  1. License has 'protection.format' array")
    print("  2. AND format contains recognized DRM MIME type strings")
    print()


if __name__ == "__main__":
    test_drm_detection()
