import base64
from odoo import api, models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    dgii_username = fields.Char(string="DGII Username")
    dgii_password = fields.Char(string="DGII Password")

    dgii_cert_file = fields.Binary(string="Certificate File")
    dgii_cert_password = fields.Char(string="Certificate Password")
    
    dgii_environment = fields.Selection([
        ('test', 'Test Environment'),
        ('production', 'Production Environment'),
    ], string="Environment", default='test')