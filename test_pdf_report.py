#!/usr/bin/env python3
"""
Test PDF generation with DRM combination data.
This simulates what the PDF report will contain.
"""

# Simulate the results structure
mock_results = {
    "summary": {
        "total_publications": 6,
        "pages_analyzed": 2,
        "pages_with_errors": 0,
        "unique_formats": 2,
        "unique_media_types": 2,
        "unique_drm_schemes": 4,
        "unique_drm_combinations": 5,
        "media_type_counts": {
            "EPUB": 5,
            "PDF": 1
        },
        "drm_scheme_counts": {
            "Adobe DRM": 3,
            "Readium LCP": 2,
            "No DRM": 1,
            "Watermark": 1
        },
        "drm_combination_counts": {
            "Adobe DRM": 2,
            "Readium LCP": 1,
            "Adobe DRM & Readium LCP": 1,
            "No DRM": 1,
            "Watermark": 1
        },
        "publication_type_counts": {
            "Book": 5,
            "Audiobook": 1
        },
        "publication_type_percentages": {
            "Book": 83.3,
            "Audiobook": 16.7
        }
    }
}

print("=" * 80)
print("PDF REPORT PREVIEW - ODL FEED ANALYSIS")
print("=" * 80)
print()

print("SUMMARY")
print("-" * 80)
summary = mock_results["summary"]
print(f"Total Publications:           {summary['total_publications']}")
print(f"Pages Analyzed:               {summary['pages_analyzed']}")
print(f"Pages With Errors:            {summary['pages_with_errors']}")
print(f"Unique Formats (MIME Types):  {summary['unique_formats']}")
print(f"Unique Media Types:           {summary['unique_media_types']}")
print(f"Unique DRM Schemes:           {summary['unique_drm_schemes']}")
print(f"Unique DRM Combinations:      {summary['unique_drm_combinations']}")
print()

print("PUBLICATION TYPES")
print("-" * 80)
print(f"{'Type':<20} {'Count':<10} {'% of Collection':<20}")
print("-" * 80)
for pub_type in sorted(summary['publication_type_counts'].keys()):
    count = summary['publication_type_counts'][pub_type]
    pct = summary['publication_type_percentages'][pub_type]
    print(f"{pub_type:<20} {count:<10} {pct:.1f}%")
print()

print("MEDIA TYPE DISTRIBUTION")
print("-" * 80)
print(f"{'Media Type':<20} {'Count':<10} {'% of Collection':<20}")
print("-" * 80)
total_pubs = summary['total_publications']
for media_type in sorted(summary['media_type_counts'].keys()):
    count = summary['media_type_counts'][media_type]
    pct = (count / total_pubs) * 100
    print(f"{media_type:<20} {count:<10} {pct:.1f}%")
print()

print("DRM SCHEME DISTRIBUTION (All Instances)")
print("-" * 80)
print("Note: Publications with multiple DRM types are counted multiple times.")
print()
print(f"{'DRM Scheme':<30} {'Count':<10} {'% of Publications':<20}")
print("-" * 80)
for drm_scheme in sorted(summary['drm_scheme_counts'].keys()):
    count = summary['drm_scheme_counts'][drm_scheme]
    pct = (count / total_pubs) * 100
    print(f"{drm_scheme:<30} {count:<10} {pct:.1f}%")
print()

print("DRM PROTECTION COMBINATIONS (By Publication)")
print("-" * 80)
print("Note: Each publication is counted exactly once by its specific DRM configuration.")
print()
print(f"{'DRM Configuration':<35} {'Publications':<15} {'% of Collection':<20} {'Type':<15}")
print("-" * 80)

# Sort combinations
def sort_key(item):
    combo = item[0]
    if combo == "No DRM":
        return (0, combo)
    elif combo == "Unknown DRM":
        return (3, combo)
    elif "&" in combo:
        return (2, combo)
    else:
        return (1, combo)

for drm_combo in sorted(summary['drm_combination_counts'].items(), key=sort_key):
    combo_name, count = drm_combo
    pct = (count / total_pubs) * 100
    
    # Determine type label
    if "&" in combo_name:
        type_label = "Multiple DRM ⚠️"
    elif combo_name == "No DRM":
        type_label = "DRM-free"
    elif combo_name == "Unknown DRM":
        type_label = "Unknown"
    else:
        type_label = "Single DRM"
    
    print(f"{combo_name:<35} {count:<15} {pct:<19.1f}% {type_label:<15}")

print()
print("=" * 80)
print("✅ PDF will include both DRM views:")
print("   1. DRM Scheme Distribution (shows all instances)")
print("   2. DRM Protection Combinations (shows single vs. multiple)")
print("=" * 80)
