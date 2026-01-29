from lxml import etree

def validate_onix(xml_path, xsd_path):
    try:
        with open(xml_path, 'rb') as xml_file:
            xml_doc = etree.parse(xml_file)
    except etree.XMLSyntaxError as e:
        return False, [f"XML parsing error: {e}"]

    with open(xsd_path, 'rb') as xsd_file:
        schema_doc = etree.parse(xsd_file)
        schema = etree.XMLSchema(schema_doc)

    is_valid = schema.validate(xml_doc)
    errors = [str(e) for e in schema.error_log]

    return is_valid, errors
