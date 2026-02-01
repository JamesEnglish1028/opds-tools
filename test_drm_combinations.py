#!/usr/bin/env python3
"""
Test script to demonstrate single vs. multiple DRM scheme detection.
Shows how publications with different DRM combinations are counted.
"""

import json
from opds_tools.util.odl_analyzer import detect_odl_drm_scheme


# Test publications with different DRM scenarios
test_publications = [
    {
        "name": "Publication 1: Adobe DRM only",
        "pub": {
            "metadata": {"@type": "http://schema.org/Book", "title": "Book 1"},
            "licenses": [{
                "metadata": {
                    "protection": {
                        "format": ["application/vnd.adobe.adept+xml"]
                    }
                }
            }]
        }
    },
    {
        "name": "Publication 2: Readium LCP only",
        "pub": {
            "metadata": {"@type": "http://schema.org/Book", "title": "Book 2"},
            "licenses": [{
                "metadata": {
                    "protection": {
                        "format": ["application/vnd.readium.lcp.license.v1.0+json"]
                    }
                }
            }]
        }
    },
    {
        "name": "Publication 3: Adobe DRM & Readium LCP (both)",
        "pub": {
            "metadata": {"@type": "http://schema.org/Book", "title": "Book 3"},
            "licenses": [{
                "metadata": {
                    "protection": {
                        "format": [
                            "application/vnd.adobe.adept+xml",
                            "application/vnd.readium.lcp.license.v1.0+json"
                        ]
                    }
                }
            }]
        }
    },
    {
        "name": "Publication 4: No DRM",
        "pub": {
            "metadata": {"@type": "http://schema.org/Book", "title": "Book 4"},
            "licenses": [{
                "metadata": {
                    "identifier": "lic-123",
                    "format": ["application/epub+zip"]
                    # No protection field
                }
            }]
        }
    },
    {
        "name": "Publication 5: Watermark only",
        "pub": {
            "metadata": {"@type": "http://schema.org/Book", "title": "Book 5"},
            "licenses": [{
                "metadata": {
                    "protection": {
                        "format": ["application/vnd.watermark+json"]
                    }
                }
            }]
        }
    },
    {
        "name": "Publication 6: Adobe DRM only (different pub)",
        "pub": {
            "metadata": {"@type": "http://schema.org/Book", "title": "Book 6"},
            "licenses": [{
                "metadata": {
                    "protection": {
                        "format": ["application/vnd.adobe.adept+xml"]
                    }
                }
            }]
        }
    }
]


def simulate_analysis():
    """Simulate the analysis logic to show counting differences."""
    
    print("=" * 80)
    print("DRM DETECTION: SINGLE vs. MULTIPLE DRM SCHEMES")
    print("=" * 80)
    print()
    
    # Track both methods
    drm_scheme_counts = {}  # Counts each DRM instance (old method)
    drm_combination_counts = {}  # Counts publications by combination (new method)
    
    for test_case in test_publications:
        name = test_case["name"]
        pub = test_case["pub"]
        
        drm_schemes = detect_odl_drm_scheme(pub)
        
        print(f"📘 {name}")
        print(f"   Detected DRM: {drm_schemes}")
        
        # Method 1: Count each DRM instance (can count a pub multiple times)
        for drm in drm_schemes:
            drm_scheme_counts[drm] = drm_scheme_counts.get(drm, 0) + 1
        
        # Method 2: Count publication once by its combination
        sorted_drm = sorted([d for d in drm_schemes if d not in ['No DRM', 'Unknown DRM']])
        if sorted_drm:
            combination_key = ' & '.join(sorted_drm)
            drm_combination_counts[combination_key] = drm_combination_counts.get(combination_key, 0) + 1
        elif 'No DRM' in drm_schemes:
            drm_combination_counts['No DRM'] = drm_combination_counts.get('No DRM', 0) + 1
        elif 'Unknown DRM' in drm_schemes:
            drm_combination_counts['Unknown DRM'] = drm_combination_counts.get('Unknown DRM', 0) + 1
        
        print()
    
    print("=" * 80)
    print("COUNTING METHOD 1: DRM Scheme Distribution (All Instances)")
    print("=" * 80)
    print("Each DRM type is counted separately.")
    print("Publications with multiple DRM types contribute to multiple counts.\n")
    
    total_instances = sum(drm_scheme_counts.values())
    for drm, count in sorted(drm_scheme_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(test_publications)) * 100
        print(f"  {drm:20s} : {count:2d} instances ({percentage:5.1f}% of publications)")
    
    print(f"\n  Total instances: {total_instances}")
    print(f"  Note: This can exceed the number of publications ({len(test_publications)}) ")
    print(f"        because publications with multiple DRM types are counted multiple times.")
    
    print("\n" + "=" * 80)
    print("COUNTING METHOD 2: DRM Protection Combinations (By Publication)")
    print("=" * 80)
    print("Each publication is counted exactly once by its specific DRM configuration.\n")
    
    for combo, count in sorted(drm_combination_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(test_publications)) * 100
        marker = "🔒 MULTIPLE" if '&' in combo else "🔓" if combo == "No DRM" else "🔐 SINGLE"
        print(f"  {marker:12s} {combo:30s} : {count:2d} publications ({percentage:5.1f}%)")
    
    print(f"\n  Total publications: {len(test_publications)}")
    print(f"  Note: This exactly equals the number of publications because ")
    print(f"        each publication is counted only once.")
    
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    print()
    print("Method 1 (All Instances):")
    print("  ✓ Shows how many publications use each DRM type")
    print("  ✓ Useful for understanding DRM technology adoption")
    print("  ✗ Can't distinguish single vs. multiple DRM scenarios")
    print()
    print("Method 2 (By Publication):")
    print("  ✓ Shows how many publications have single vs. multiple DRM")
    print("  ✓ Each publication counted exactly once")
    print("  ✓ Highlights publications with Adobe DRM & LCP together (⚠️)")
    print("  ✓ Better for understanding publication-level DRM complexity")
    print()
    print("Both methods are now displayed in the ODL analysis report!")
    print()


if __name__ == "__main__":
    simulate_analysis()
