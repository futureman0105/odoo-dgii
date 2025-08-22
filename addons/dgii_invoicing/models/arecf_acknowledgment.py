from odoo import models, fields
from lxml import etree
from .digital_signature import DGII_XMLSigner


class DGIIARECFAcknowledgment(models.Model):
    _name = 'dgii.arecf'
    _description = 'DGII Acknowledgment of Receipt'

    invoice_id = fields.Many2one('account.move', required=True)
    rnc_emisor = fields.Char(required=True)
    rnc_buyer = fields.Char(required=True)
    ncf = fields.Char(string='NCF', required=True)
    received = fields.Boolean(string='Received', default=True)
    reason_code = fields.Selection([
        ('1', 'Structure error'),
        ('2', 'Signature error'),
        ('3', 'Duplicated NCF'),
        ('4', 'Incorrect RNC')
    ], string='Rejection Reason')
    datetime_ack = fields.Datetime(required=True, default=fields.Datetime.now)
    dgii_status = fields.Selection([
        ('draft', 'Draft'),
        ('signed', 'Signed'),
        ('sent', 'Sent'),
        ('error', 'Error')
    ], default='draft')

    signed_xml = fields.Binary('Signed XML')
    signature_text = fields.Text('Base64 Signature')

    def action_generate_signed_xml(self):
        for ack in self:
            xml_str = ack._generate_arecf_xml()
            signed_xml = DGII_XMLSigner(ack.invoice_id.company_id).sign_xml(xml_str)
            ack.signed_xml = signed_xml
            ack.dgii_status = 'signed'

    def _generate_arecf_xml(self):
        root = etree.Element("AcknowledgementDetail")
        etree.SubElement(root, "Version").text = "1.0"
        etree.SubElement(root, "RNCEmisor").text = self.rnc_emisor
        etree.SubElement(root, "RNCComprador").text = self.rnc_buyer
        etree.SubElement(root, "NCF").text = self.ncf
        etree.SubElement(root, "Estado").text = '0' if self.received else '1'

        if not self.received and self.reason_code:
            etree.SubElement(root, "CodigoMotivoNoRecibido").text = self.reason_code

        etree.SubElement(root, "FechaHoraAcuseRecibo").text = self.datetime_ack.strftime("%d-%m-%Y %H:%M:%S")

        # Placeholder for <Signature> block (will be signed separately)
        etree.SubElement(root, "Signature")

        return etree.tostring(root, pretty_print=True, encoding='UTF-8', xml_declaration=True)
