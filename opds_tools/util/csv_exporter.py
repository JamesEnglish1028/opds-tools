import csv
import io
import logging

logger = logging.getLogger(__name__)

def generate_csv(data):
    logger.info("generating csv")
    fieldnames = [
        'title', 'subtitle', 'author', 'identifier', 'alt_identifier',
        'publisher', 'published', 'language', 'subjects',
        'accessibility_conformsTo', 'accessibility_certification',
        'accessibility_accessMode', 'accessibility_accessModeSufficient',
        'accessibility_feature', 'accessibility_hazard', 'accessibility_summary',
        'belongs_to', 'image'
    ]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()

    for item in data:
        row = {key: item.get(key, '') for key in fieldnames}

        # Flatten list fields
        row['subjects'] = ', '.join(item.get('subjects', []))
        row['alt_identifier'] = ', '.join(i.get('value', '') for i in item.get('alt_identifier', []))
        row['belongs_to'] = '; '.join(
            f"{b.get('label')}: {b.get('name')} ({b.get('url')})" if b.get('url') else f"{b.get('label')}: {b.get('name')}"
            for b in item.get('belongs_to', [])
        )

        # Accessibility fields
        access = item.get('accessibility', {})
        row['accessibility_conformsTo'] = access.get('conformsTo', '')
        row['accessibility_certification'] = access.get('certification', '')
        row['accessibility_accessMode'] = access.get('accessMode', '')
        row['accessibility_accessModeSufficient'] = access.get('accessModeSufficient', '')
        row['accessibility_feature'] = access.get('feature', '')
        row['accessibility_hazard'] = access.get('hazard', '')
        row['accessibility_summary'] = access.get('summary', '')

        writer.writerow(row)

    return output.getvalue()
