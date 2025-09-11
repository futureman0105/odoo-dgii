from odoo import models, fields


class DGIIANECFLine(models.Model):
    _name = 'dgii.anecf.line'
    _description = 'DGII e-CF Canceled Range'

    cancel_id = fields.Many2one('dgii.anecf', required=True, ondelete='cascade')
    cf_type = fields.Selection([
        ('31', 'Factura'),
        ('32', 'Consumo'),
        ('33', 'Nota Crédito'),
        ('34', 'Nota Débito'),
        ('41', 'Gubernamental'),
        ('44', 'Exportación'),
        ('47', 'Proveedores Informales')
    ], required=True)
    ncf_from = fields.Char(required=True)
    ncf_to = fields.Char(required=True)
    canceled_amount = fields.Integer(required=True)
