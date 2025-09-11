from odoo import models, fields
from lxml import etree
from .digital_signature import DGII_XMLSigner


class DGIIRFCESummary(models.Model):
    _name = 'dgii.rfce'
    _description = 'DGII Consumer Summary Report'

    name = fields.Char(default=lambda self: self.env['ir.sequence'].next_by_code('dgii.rfce'))
    report_date = fields.Date(required=True, default=fields.Date.context_today)
    rnc_emisor = fields.Char(required=True)
    invoice_ids = fields.Many2many('account.move', string='Invoices')
    dgii_status = fields.Selection([
        ('draft', 'Draft'),
        ('signed', 'Signed'),
        ('sent', 'Sent'),
        ('error', 'Error')
    ], default='draft')
    signed_xml = fields.Binary('Signed XML')

    def action_generate_signed_xml(self):
        for rec in self:
            xml_str = rec._generate_rfce_xml()
            signed_xml = DGII_XMLSigner(self.env.company).sign_xml(xml_str)
            rec.signed_xml = signed_xml
            rec.dgii_status = 'signed'

    def _generate_rfce_xml(self):
        root = etree.Element("ResumenFacturasConsumo")

        encabezado = etree.SubElement(root, "Encabezado")
        etree.SubElement(encabezado, "Version").text = "1.0"
        etree.SubElement(encabezado, "RNCEmisor").text = self.rnc_emisor
        etree.SubElement(encabezado, "FechaEmision").text = self.report_date.strftime("%d-%m-%Y")

        # Totals
        total_itbis = sum(inv.amount_tax for inv in self.invoice_ids)
        total_exempt = sum(inv.amount_untaxed for inv in self.invoice_ids if not inv.amount_tax)
        total_total = sum(inv.amount_total for inv in self.invoice_ids)

        totales = etree.SubElement(root, "Totales")
        etree.SubElement(totales, "TotalITBIS").text = f"{total_itbis:.2f}"
        etree.SubElement(totales, "MontoExento").text = f"{total_exempt:.2f}"
        etree.SubElement(totales, "MontoTotal").text = f"{total_total:.2f}"

        etree.SubElement(root, "Signature")

        return etree.tostring(root, pretty_print=True, encoding='UTF-8', xml_declaration=True)
