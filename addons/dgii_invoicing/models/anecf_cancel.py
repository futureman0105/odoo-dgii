from odoo import models, fields, api
from lxml import etree
from .digital_signature import DGII_XMLSigner


class DGIIANECFCancel(models.Model):
    _name = 'dgii.anecf'
    _description = 'DGII e-CF Sequence Cancellation'

    name = fields.Char('Cancellation Reference', required=True, default=lambda self: self.env['ir.sequence'].next_by_code('dgii.anecf'))
    rnc_emisor = fields.Char(required=True)
    canceled_count = fields.Integer(string='Number of NCFs', required=True)
    datetime_cancel = fields.Datetime(string='Cancellation Date', required=True, default=fields.Datetime.now)

    sequence_lines = fields.One2many('dgii.anecf.line', 'cancel_id', string='Canceled Ranges')
    signed_xml = fields.Binary('Signed XML')
    dgii_status = fields.Selection([
        ('draft', 'Draft'),
        ('signed', 'Signed'),
        ('sent', 'Sent'),
        ('error', 'Error')
    ], default='draft')

    def action_generate_signed_xml(self):
        for rec in self:
            xml_str = rec._generate_anecf_xml()
            signed_xml = DGII_XMLSigner(self.env.company).sign_xml(xml_str)
            rec.signed_xml = signed_xml
            rec.dgii_status = 'signed'

    def _generate_anecf_xml(self):
        root = etree.Element("CancelacionSecuencia")

        header = etree.SubElement(root, "Encabezado")
        etree.SubElement(header, "Version").text = "1.0"
        etree.SubElement(header, "RNCEmisor").text = self.rnc_emisor
        etree.SubElement(header, "CantidadComprobantesAnulados").text = str(self.canceled_count)
        etree.SubElement(header, "FechaHoraGeneracion").text = self.datetime_cancel.strftime("%d-%m-%Y %H:%M:%S")

        detalle = etree.SubElement(root, "DetalleAnulacion")
        for i, line in enumerate(self.sequence_lines, start=1):
            linea = etree.SubElement(detalle, "Anulacion")
