# run_onix_test.py

from opds_tools.util.onix_to_opds import parse_onix_file, save_opds_feed

onix_path = "data/AdventureKEEN_Metadata_20250214162853.xml"
output_path = "opds_tools/uploads/opds_catalog.json"

feed = parse_onix_file(onix_path)
save_opds_feed(feed, output_path)

print(f"✅ OPDS catalog saved to {output_path}")
