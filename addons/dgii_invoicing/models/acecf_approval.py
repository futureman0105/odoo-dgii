from odoo import models, fields
from lxml import etree
from .digital_signature import DGII_XMLSigner


class DGIIACECFApproval(models.Model):
    _name = 'dgii.acecf'
    _description = 'DGII Commercial Approval'

    invoice_id = fields.Many2one('account.move', required=True)
    rnc_emisor = fields.Char(required=True)
    rnc_buyer = fields.Char(required=True)
    ncf = fields.Char(string='NCF', required=True)
    accepted = fields.Boolean(string='Approved', default=True)
    reason_code = fields.Selection([
        ('1', 'Errors in the invoice'),
        ('2', 'Inconsistency in values'),
        ('3', 'Rejected by policy'),
        ('4', 'Duplicate NCF')
    ], string='Rejection Reason')
    datetime_approval = fields.Datetime(required=True, default=fields.Datetime.now)
    dgii_status = fields.Selection([
        ('draft', 'Draft'),
        ('signed', 'Signed'),
        ('sent', 'Sent'),
        ('error', 'Error')
    ], default='draft')

    signed_xml = fields.Binary('Signed XML')
    signature_text = fields.Text('Base64 Signature')

    def action_generate_signed_xml(self):
        for rec in self:
            xml_str = rec._generate_acecf_xml()
            signed_xml = DGII_XMLSigner(rec.invoice_id.company_id).sign_xml(xml_str)
            rec.signed_xml = signed_xml
            rec.dgii_status = 'signed'

    def _generate_acecf_xml(self):
        root = etree.Element("DetailApprovalCommercial")
        etree.SubElement(root, "Version").text = "1.0"
        etree.SubElement(root, "RNCEmisor").text = self.rnc_emisor
        etree.SubElement(root, "RNCComprador").text = self.rnc_buyer
        etree.SubElement(root, "NCF").text = self.ncf
        etree.SubElement(root, "MontoTotal").text = str(round(self.invoice_id.amount_total, 2))
        etree.SubElement(root, "Estado").text = '0' if self.accepted else '1'

        if not self.accepted and self.reason_code:
            etree.SubElement(root, "CodigoMotivo").text = self.reason_code

        etree.SubElement(root, "FechaHoraAprobacion").text = self.datetime_approval.strftime("%d-%m-%Y %H:%M:%S")

        # Placeholder for <Signature>
        etree.SubElement(root, "Signature")

        return etree.tostring(root, pretty_print=True, encoding='UTF-8', xml_declaration=True)
