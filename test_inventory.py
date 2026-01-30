#!/usr/bin/env python3
"""
Quick test script to verify the inventory generator utility works correctly.
Tests the core functions without requiring a full Flask app.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from opds_tools.util.inventory_generator import (
    extract_format_from_links,
    extract_drm_from_links,
    extract_author,
    extract_publisher,
    extract_inventory_record,
    generate_inventory_csv,
    generate_inventory_excel
)

def test_format_extraction():
    """Test format extraction from links."""
    print("Testing format extraction...")
    
    # Test EPUB
    links = [
        {'rel': 'http://opds-spec.org/acquisition', 'type': 'application/epub+zip', 'href': 'test.epub'}
    ]
    result = extract_format_from_links(links)
    assert result == 'EPUB', f"Expected 'EPUB', got '{result}'"
    print("  ✓ EPUB format detected")
    
    # Test multiple formats
    links = [
        {'rel': 'http://opds-spec.org/acquisition', 'type': 'application/epub+zip', 'href': 'test.epub'},
        {'rel': 'http://opds-spec.org/acquisition', 'type': 'application/pdf', 'href': 'test.pdf'}
    ]
    result = extract_format_from_links(links)
    assert 'EPUB' in result and 'PDF' in result, f"Expected 'EPUB, PDF', got '{result}'"
    print("  ✓ Multiple formats detected")

def test_drm_extraction():
    """Test DRM extraction from links."""
    print("\nTesting DRM extraction...")
    
    # Test LCP DRM
    links = [
        {'rel': 'http://opds-spec.org/acquisition', 
         'type': 'application/epub+zip;profile=http://readium.org/lcp', 
         'href': 'test.epub'}
    ]
    result = extract_drm_from_links(links)
    assert 'LCP' in result, f"Expected 'LCP DRM', got '{result}'"
    print("  ✓ LCP DRM detected")
    
    # Test None (no DRM)
    links = [
        {'rel': 'http://opds-spec.org/acquisition', 'type': 'application/epub+zip', 'href': 'test.epub'}
    ]
    result = extract_drm_from_links(links)
    assert result == 'None', f"Expected 'None', got '{result}'"
    print("  ✓ No DRM detected")
    
    # Test Bearer Token
    links = [
        {'rel': 'http://opds-spec.org/acquisition/bearer-token', 'type': 'application/epub+zip', 'href': 'test.epub'}
    ]
    result = extract_drm_from_links(links)
    assert 'Bearer Token' in result, f"Expected 'Bearer Token', got '{result}'"
    print("  ✓ Bearer Token detected")

def test_author_extraction():
    """Test author extraction from metadata."""
    print("\nTesting author extraction...")
    
    # String author
    metadata = {'author': 'John Doe'}
    result = extract_author(metadata)
    assert result == 'John Doe', f"Expected 'John Doe', got '{result}'"
    print("  ✓ String author extracted")
    
    # List of authors
    metadata = {'authors': [{'name': 'Jane Smith'}, {'name': 'Bob Jones'}]}
    result = extract_author(metadata)
    assert 'Jane Smith' in result and 'Bob Jones' in result, f"Expected authors, got '{result}'"
    print("  ✓ Multiple authors extracted")

def test_csv_generation():
    """Test CSV generation."""
    print("\nTesting CSV generation...")
    
    inventory = [
        {
            'identifier': 'urn:isbn:1234567890',
            'title': 'Test Book',
            'author': 'Test Author',
            'publisher': 'Test Publisher',
            'format': 'EPUB',
            'drm': 'None'
        }
    ]
    
    csv_output = generate_inventory_csv(inventory)
    assert 'identifier,title,author,publisher,format,drm' in csv_output, "CSV header missing"
    assert 'Test Book' in csv_output, "Test data missing"
    assert 'Test Author' in csv_output, "Author missing"
    print("  ✓ CSV generated successfully")
    print(f"    Sample:\n{csv_output[:200]}...")

def test_xml_generation():
    """Test Excel generation (replaces XML)."""
    print("\nTesting Excel generation...")
    
    inventory = [
        {
            'identifier': 'urn:isbn:1234567890',
            'title': 'Test Book',
            'author': 'Test Author',
            'publisher': 'Test Publisher',
            'format': 'EPUB',
            'drm': 'None'
        },
        {
            'identifier': 'urn:isbn:0987654321',
            'title': 'Another Book',
            'author': 'Another Author',
            'publisher': 'Another Publisher',
            'format': 'PDF',
            'drm': 'LCP DRM'
        }
    ]
    
    excel_content = generate_inventory_excel(inventory)
    
    # Verify it's bytes
    assert isinstance(excel_content, bytes), "Excel output should be bytes"
    
    # Verify it contains valid Excel structure (should start with PK for zip)
    assert excel_content[:2] == b'PK', "Excel file should be valid XLSX (zip format)"
    
    # Verify reasonable size
    assert len(excel_content) > 1000, "Excel file seems too small"
    
    print("  ✓ Excel generated successfully")
    print(f"    File size: {len(excel_content)} bytes")
    print(f"    Contains {len(inventory)} records")

def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("OPDS Inventory Generator - Unit Tests")
    print("=" * 60)
    
    try:
        test_format_extraction()
        test_drm_extraction()
        test_author_extraction()
        test_csv_generation()
        test_xml_generation()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
