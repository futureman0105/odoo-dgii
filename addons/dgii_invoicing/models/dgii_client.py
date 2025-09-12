import requests
from lxml import etree
from signxml import XMLSigner, SignatureConstructionMethod
from cryptography.hazmat.primitives.serialization import load_pem_private_key, pkcs12, Encoding, PrivateFormat, NoEncryption
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates
from cryptography.hazmat.backends import default_backend
import OpenSSL
import logging
import os
import json
from OpenSSL import crypto

class DGIICFService:
    def __init__(self, dgii_env='cert', company_id=None, env=None):
        """
        Initialize the DGII service with environment, company, and config data.
        """
        self._logger = logging.getLogger(__name__)

        if not company_id:
            raise ValueError("Company ID is required")
        
        # "http://localhost:8080/api/sign" 
        self.sign_url = "http://148.230.114.180:8080/sign-xml-0.0.1-SNAPSHOT/api/sign"
        self.base_url = {
            'test': 'https://ecf.dgii.gov.do/testeCF',
            'cert': 'https://ecf.dgii.gov.do/CerteCF'
        }[dgii_env]
        
        self.env = env

        # Fetch DGII credentials from company settings
        company = self.env['res.company'].browse(company_id)
        self.dgii_username = company.dgii_username
        self.dgii_password = company.dgii_password
        self.cert_password = company.dgii_cert_password
        self.codigo_seguridad = ""

        # Read the .p12 certificate from the module path
        try:
            cert_file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'certificate.p12')
            with open(cert_file_path, 'rb') as cert_file:
                self.p12_data = cert_file.read()

            self._logger.info(f"Successfully read .p12 file from path: {cert_file_path}, size: {len(self.p12_data)} bytes")
        except Exception as e:
            self._logger.error(f"Failed to read .p12 file from path: {e}")
            self.p12_data = None

        if self.p12_data:
            try:
                # Extract certificate and private key from the .p12 file
                # self.cert_data, self.key_data = self.extract_cert_key_from_p12(self.p12_data, company.dgii_cert_password)
                # self.key_data, self.cert_data, _ = pkcs12.load_key_and_certificates(self.p12_data, company.dgii_cert_password.encode())
                self._logger.info("DGII: cert pwd length=%s", len(company.dgii_cert_password or ""))
                p12 = crypto.load_pkcs12(self.p12_data, company.dgii_cert_password.encode())

                self.cert_data = p12.get_certificate()
                self.key_data = p12.get_privatekey()

            except Exception as e:
                self._logger.error(f"Error extracting certificate and key from .p12 file: {str(e)}")
                self.cert_data = self.key_data = None

        # Password for private key if necessary
        self.password = company.dgii_cert_password

    def extract_cert_key_from_p12(self, p12_data, password=None):
        """
        Extract the certificate and private key from the .p12 file.
        """
        
        if not p12_data:
            self._logger.error("The .p12 file is empty or invalid!")
            raise ValueError("Invalid .p12 file data.")
        
        self._logger.info(f".p12 password: {password} ")

        # Load the .p12 file
        p12 = OpenSSL.crypto.load_pkcs12(p12_data, password.encode() if password else None)
        
        # Extract the private key and certificate
        cert = p12.get_certificate().to_cryptography()
        key = p12.get_privatekey().to_cryptography_key()
        
        return cert, key

    def get_semilla(self):
        """
        Fetch the seed (semilla) from DGII for authentication.
        """
                
        url = f"{self.base_url}/Autenticacion/api/Autenticacion/Semilla"
        
        self._logger.info(f"DGII User Name: {self.dgii_username}")
        self._logger.info(f"DGII Password: {self.dgii_password}")
        self._logger.info(f"Semilla URL: {url}")

        res = requests.get(url, auth=(self.dgii_username, self.dgii_password))

        self._logger.info(f"Semilla response from DGII: {res.content}")

        if res.status_code == 200:
            tree = etree.fromstring(res.content)
            return res.content
        else:
            raise Exception("Error fetching semilla from DGII: " + res.text)

    def sign_semilla(self, semilla):
        """
        Sign the 'semilla' using the provided certificate and private key.
        """
        signed_xml = self.custom_sign_xml(semilla)

        return signed_xml

    def validate_semilla(self):
        """
        Validate the signed 'semilla' with DGII using their validation endpoint.
        """

        xml_file_path = os.path.join(os.path.dirname(__file__), '..', 'data/signed.xml')

        with open(xml_file_path, 'rb') as f:
            files = {'xml': ('signed.xml', f, 'text/xml')}
            headers = {'accept': 'application/json'}
            
            res = requests.post(
                'https://ecf.dgii.gov.do/testecf/Autenticacion/api/Autenticacion/ValidarSemilla',
                files=files,
                headers=headers
            )

            self._logger.info(f"Validar Semilla response from DGII: {res.content}")

            if res.status_code == 200:
                response_data = json.loads(res.content.decode('utf-8'))
                token = response_data['token']
                return token
            else:
                raise Exception("Error validating certificate with DGII: " + res.text)
        
    def custom_sign_xml(self, semilla, type='semilla'):
        """
        Sign the XML for 'semilla' using the private key and certificate.
        """

        headers = { "Content-Type": "application/xml",}

        if type == 'semilla':
            xml_str = semilla.decode('utf-8').strip()
        else:
            xml_str = semilla
            
        res = requests.post(self.sign_url, data=xml_str, headers=headers)

        if type == 'semilla':
            path = os.path.join(os.path.dirname(__file__), '..', 'data/signed.xml')
        else:
            path = os.path.join(os.path.dirname(__file__), '..', 'data/signed_invoice.xml')
        
        with open(path, 'wb') as f:
                f.write(res.content)

        return res.content
    
    def sign_xml(self, xml_data):
        signed_xml = self.custom_sign_xml(xml_data, type='invoice')
        return signed_xml

    def submit_ecf(self, signed_xml, token):
        """
        Submit the signed e-CF XML to DGII.
        """

        xml_file_path = os.path.join(os.path.dirname(__file__), '..', 'data/signed_invoice.xml')

        with open(xml_file_path, 'rb') as f:
            files = {'xml': ('signed.xml', f, 'text/xml')}
            headers = {
                'accept': 'application/json',
                "Authorization": f"Bearer {token}"
            }
            
            res = requests.post(
                f"{self.base_url}/Recepcion/api/FacturasElectronicas",
                files=files,
                headers=headers
            )

            self._logger.info(f"Validar Semilla response from DGII: {res.content}")

            return res
        
    def track_ecf(self, trackid, token):
        """
        Track e-CF status from DGII.
        """

        data = {'trackid': trackid}
        headers = {
            'accept': 'application/json',
            "Authorization": f"Bearer {token}"
        }
        
        res = requests.get(
            f"{self.base_url}/consultaresultado/api/consultas/estado?trackid={trackid}",
            headers=headers
        )

        self._logger.info(f"Track response from DGII: {res.content}")

        return res
