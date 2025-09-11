from cryptography.hazmat.primitives.serialization import load_pem_private_key
from signxml import XMLSigner, methods
from lxml import etree
import base64


class DGII_XMLSigner:
    def __init__(self, company):
        self.cert_data = base64.b64decode(company.dgii_cert_file or b"")
        self.key_data = base64.b64decode(company.dgii_private_key or b"")

        # Only pass password if it's non-empty
        self.password = company.dgii_cert_password.encode('utf-8') if company.dgii_cert_password else None

    def sign_xml(self, xml_data):
        root = etree.fromstring(xml_data)

        signer = XMLSigner(
            method=methods.enveloped,
            digest_algorithm="sha256"
        )

        private_key = load_pem_private_key(self.key_data, password=self.password)

        signed_root = signer.sign(
            root,
            key=private_key,
            cert=self.cert_data
        )

        return etree.tostring(signed_root, pretty_print=True, encoding='UTF-8', xml_declaration=True)
