import requests
from odoo import models, fields, api
import base64
from lxml import etree
from .digital_signature import DGII_XMLSigner
from odoo.exceptions import UserError
from .dgii_client import DGIICFService
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
import json
import io
import qrcode
import re
import os
from xml.dom import minidom

class AccountMove(models.Model):
    _inherit = 'account.move'

    dgii_submission_status = fields.Selection([
        ('not_sent', 'Not Sent'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('error', 'Error')
    ], string='DGII Submission Status', default='not_sent')
    dgii_response_log = fields.Text('DGII Response Log')
    dgii_response_code = fields.Char('DGII Response Code')
    dgii_response_message = fields.Text('DGII Response Message')
    dgii_codigo_seguridad = fields.Char(string="DGII Codigo Seguridad")
    dgii_qr_data = fields.Char(string="DGII QR Data")
    dgii_token = fields.Char("DGII Token")
    dgii_track_id = fields.Char("DGII Track ID")
    dgii_ncf = fields.Char(string="e-NCF", readonly=True, copy=False)
    dgii_status = fields.Selection([
        ('draft', 'Draft'),
        ('en_proceso', 'En Proceso'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
    ], default='draft')
    dgii_rejection_reason = fields.Text("DGII Rejection Reason")

    # selection field for NCF type (store=True so user can pick before posting)
    l10n_do_ncf_type = fields.Selection([
        ('31', 'Tax Credit Invoice'),
        ('32', 'Consumer Invoice'),
        ('33', 'Electronic Credit Note'),
        ('34', 'Electronic Debit Note'),
        ('41', 'Government Invoice'),
        ('43', 'Special Regime'),
        ('44', 'Export Invoice'),
        ('45', 'Electronic Invoice'),
        ('46', 'Free Zone Invoice'),
        ('47', 'Informal Supplier Invoice'),
    ], string='NCF Type', default='31', required=True,
       help='Select the type of NCF for this invoice')
    
    qr_code = fields.Binary("QR Code", compute="_compute_qr_code")

    test_ncf = fields.Char(string="test-e-NCF")
    test_ncf = "E410000000013" 
    dgii_codigo_seguridad = "rk7z0i"

    # test_ncf = "E450000000009" 
    # dgii_codigo_seguridad = "HNf/6X"
    
    def action_post(self):
        doc_type_names = {
            '31': 'Factura de Crédito Fiscal Electrónica',
            '32': 'Factura de Consumo Electrónica',
            '33': 'Nota de Débito Electrónica',
            '34': 'Nota de Crédito Electrónica',
            '41': 'Comprobante de Compras Electrónica',
            '43': 'Gastos Menores Electrónica',
            '44': 'Regímenes Especiales Electrónica',
            '45': 'Comprobante Gubernamental Electrónica',
            '46': 'Comprobante de Exportación Electrónica',
            '47': 'Pagos en el Exterior Electrónica',
        }

        for move in self:
            # Require document type before confirming
            if not move.l10n_latam_document_type_id:
                raise UserError("You must select a Document Type before confirming this invoice.")

        for move in self:
            if move.l10n_latam_document_type_id:
                e_ncf = self.get_next_ncf()
                cf_code = str(move.l10n_latam_document_type_id.code)
                temp = doc_type_names.get(cf_code, '/')
                move.name = f'{temp}({e_ncf})'
            else:
                move.name = '/'

        res = super().action_post()

        return res

    def get_next_ncf(self) : 
        _logger = logging.getLogger(__name__)

        print("Getting Next NCF...")
        
        cf_code = self.l10n_latam_document_type_id.code
        _logger.info(f'CF Code: {cf_code}')
        seq_code = f"e.ncf.{cf_code}"
        seq = self.env['ir.sequence'].search([('code', '=', f'{seq_code}')], limit=1)

        key = f'e_ncf_{cf_code}_last_number'
        
        param = self.env['ir.config_parameter'].sudo()
        last_number = int(param.get_param(key, 0))
        seq.number_next = last_number + 1

        param.set_param(key, str(seq.number_next))

        ##############################################################
        ####    force-save the parameter before continuing:    #######
        ##############################################################

        self.env.cr.commit() 

        ##############################################################
        ##############################################################
        ##############################################################

        next_ncf_number = seq.next_by_id()
        _logger.info(f'next e-NCF : {next_ncf_number}')

        self.dgii_ncf = next_ncf_number

        return self.dgii_ncf

    def get_ncf(self) : 
        _logger = logging.getLogger(__name__)

        _logger.info("Getting NCF...")
        
        cf_code = self.l10n_latam_document_type_id.code
        _logger.info(f'CF Code: {cf_code}')
        seq_code = f"e.ncf.{cf_code}"
        seq = self.env['ir.sequence'].search([('code', '=', f'{seq_code}')])
        
        key = f'e_ncf_{cf_code}_last_number'
        
        last_number = int(self.env['ir.config_parameter'].sudo().get_param(key, 0))
        seq.number_next = last_number

        ncf_number = seq.next_by_id()

        self.dgii_ncf = ncf_number

        return self.dgii_ncf

    def _compute_qr_code(self):
        for move in self:
            invoice_date = move.invoice_date.strftime("%d-%m-%Y")

            qr_dict = {
                "RNC Emisor": move.company_id.vat,
                "Razón Social Emisor": move.company_id.name,
                "RNC Comprador": move.partner_id.vat or "",
                "Razón Social Comprador": move.partner_id.name or "",
                "e-NCF": move.test_ncf,
                "Fecha de Emisión": str(invoice_date),
                "Total de ITIBS": str(move.amount_tax),
                # "Total de ITIBS": "16,016.95",
                "Monto Total": str(move.amount_total),
                # "Monto Total": "17,565.78",
                "Estado": "Aceptado",
            }

            # move.get_code_signature("xml_str")

            _logger = logging.getLogger(__name__)
            _logger.info(f'QR code RNC Emisor : {move.company_id.vat}')
            _logger.info(f'QR code Razón Social Emisor : {move.company_id.name}')
            _logger.info(f'QR code RNC Comprador : {move.partner_id.vat}')
            _logger.info(f'QR code Razón Social Comprador : {move.partner_id.name}')
            _logger.info(f'QR code e-NCF : {invoice_date}')
            _logger.info(f'QR code Total de ITIBS : {move.amount_tax}')
            _logger.info(f'QR code Monto Total : {move.amount_total}')

            qr_data = json.dumps(qr_dict, ensure_ascii=False)
            qr_img = qrcode.make(qr_data)

            buffer = io.BytesIO()
            qr_img.save(buffer, format="PNG")
            move.qr_code = base64.b64encode(buffer.getvalue())

    def action_send_to_dgii(self):
        _logger = logging.getLogger(__name__)
        for invoice in self:
            if invoice.move_type != 'out_invoice':
                raise UserError("Only customer invoices can be submitted to DGII.")

            # Ensure that the invoice has a valid company
            if not invoice.company_id:
                raise ValueError("Invoice is not linked to a company.")

            # Get the company ID from the invoice
            company_id = invoice.company_id.id
            _logger.info(f"Processing invoice with company ID: {invoice.company_id.id}")

            e_ncf = self.get_ncf()
            _logger.info(f"ENCF: {e_ncf}")

            # try:
            #     dgii_service = DGIICFService(dgii_env='test', company_id=company_id, env=self.env)

            #     # Step 1: Get the seed
            #     semilla = dgii_service.get_semilla()
            #     if not semilla:
            #         raise UserError("Failed to retrieve semilla from DGII.")
                
            #     _logger.info(f"Received semilla: {semilla}")

            #     # Step 2: Sign the semilla
            #     signed_semilla = dgii_service.sign_semilla(semilla)

            #     _logger.info(f"Signed semilla: {signed_semilla}")

            #     # Step 3: Validate the signed semilla and get the token
            #     token = dgii_service.validate_semilla(signed_semilla)
            #     if not token:
            #         raise UserError("Failed to validate semilla with DGII and obtain token.")
                
            #     _logger.info(f"Received token: {token}")

            #     # Step 4: Generate and sign e-CF XML
            #     xml_str = invoice._generate_ecf_xml()
            #     _logger.info(f"invoice xml: {xml_str}")

            #     signed_xml = dgii_service.sign_xml(xml_str)
            #     _logger.info(f"signed invoice xml: {signed_xml}")

            #     # dgii_codigo_seguridad = invoice.get_code_signature(signed_xml)
            #     # _logger.info(f"Codigo Sseguridad: {dgii_codigo_seguridad}")

            #     # Step 5: Submit the signed e-CF XML to DGII using the token
            #     response = dgii_service.submit_ecf(signed_xml, token)
            #     trackId = ""
            #     # Log the response and update the invoice status
            #     if response.status_code == 200:
            #         invoice.dgii_submission_status = 'sent'
                    
            #         response_data = json.loads(response.content.decode('utf-8'))
            #         # invoice.dgii_ncf = "E310000000000001"
            #         invoice.dgii_response_log = "Submitted to DGII, response: trackId: " + response_data['trackId']
            #         invoice.message_post(body="✅ e-CF sent to DGII. trackId: " + response_data['trackId'])
            #         _logger.info(f"Successfully sent invoice {invoice.name} to DGII")
            #         trackId = response_data['trackId']
            #     else:
            #         invoice.dgii_submission_status = 'error'
            #         invoice.dgii_response_log = f"Error from DGII: {response.text}"
            #         invoice.message_post(body="❌ Error sending e-CF to DGII: " + response.text)
            #         _logger.error(f"Error submitting invoice {invoice.name} to DGII: {response.text}")

            #     # Step 5: Track the status of e-CF to DGII using the token
            #     response = dgii_service.track_ecf(trackId, token)
            #     _logger.info(f"track result: {response.content}")
                
            #     response_data = json.loads(response.content.decode('utf-8'))
            #     self.write({
            #         "dgii_track_id": trackId,
            #         "dgii_token": token,
            #     })

            # except Exception as e:
            #     _logger.exception(f"Failed to process invoice {invoice.name}: {str(e)}")
            #     invoice.dgii_submission_status = 'error'
            #     invoice.dgii_response_log = f"Error processing invoice: {str(e)}"
            #     invoice.message_post(body="❌ Error processing invoice.")

    def get_code_signature(self, xml_str) :
        _logger = logging.getLogger(__name__)

        import re

        # Extract the SignatureValue content
        match = re.search(r"<SignatureValue>(.*?)</SignatureValue>", xml_str, re.DOTALL)
        if match:
            signature_value = match.group(1).replace("\n", "").strip()  # remove line breaks
            dgii_codigo_seguridad = signature_value[:6]
        else:
            print("No SignatureValue found")

        return dgii_codigo_seguridad

    def _generate_ecf_xml(self):
        """Generate DGII-compliant XML from an Odoo invoice."""
        # Create root element with namespaces
        root = ET.Element('ECF', {
            'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'xmlns:ds': 'http://www.w3.org/2000/09/xmldsig#',
            'xsi:schemaLocation': 'https://ecf.dgii.gov.do/esquemas/ecf/1.1'
        })

        # 1. Encabezado
        encabezado = ET.SubElement(root, 'Encabezado')
        ET.SubElement(encabezado, 'Version').text = '1.0'

        e_ncf = self.get_ncf()

        # IdDoc
        id_doc = ET.SubElement(encabezado, 'IdDoc')
        ET.SubElement(id_doc, 'TipoeCF').text = self.l10n_latam_document_type_id.code or "32"
        ET.SubElement(id_doc, 'eNCF').text = e_ncf  # must be filled from NCF sequence
        ET.SubElement(id_doc, 'IndicadorMontoGravado').text = '1'
        if self.invoice_date_due:
            ET.SubElement(id_doc, 'FechaLimitePago').text = str(self.invoice_date_due)
        ET.SubElement(id_doc, 'TerminoPago').text = 'Credito' if self.invoice_payment_term_id else 'Contado'

        emisor = ET.SubElement(encabezado, 'Emisor')
        ET.SubElement(emisor, 'RNCEmisor').text = self.company_id.vat or ''
        ET.SubElement(emisor, 'RazonSocialEmisor').text = self.company_id.name or ''
        ET.SubElement(emisor, 'NombreComercial').text = self.company_id.name or ''
        ET.SubElement(emisor, 'DireccionEmisor').text = self.company_id.street or ''
        ET.SubElement(emisor, 'Municipio').text = self.company_id.city or 'N/A'
        ET.SubElement(emisor, 'Provincia').text = self.company_id.state_id.name if self.company_id.state_id else 'N/A'

        # Phones
        tabla_tel = ET.SubElement(emisor, 'TablaTelefonoEmisor')
        tel1 = ET.SubElement(tabla_tel, 'TelefonoEmisor')
        ET.SubElement(tel1, 'NumeroTelefono').text = re.sub(r'\D', '', self.company_id.phone or '8090000000')
        ET.SubElement(tel1, 'TipoTelefono').text = '1'  # 1=landline, 2=mobile

        ET.SubElement(emisor, 'CorreoEmisor').text = self.company_id.email or ''
        ET.SubElement(emisor, 'WebSite').text = self.company_id.website or ''

        ET.SubElement(emisor, 'ActividadEconomica').text = "VENTA AL POR MENOR"
        ET.SubElement(emisor, 'CodigoVendedor').text = self.user_id.login or 'VEN001'
        ET.SubElement(emisor, 'NumeroFacturaInterna').text = self.name or ''
        ET.SubElement(emisor, 'NumeroPedidoInterno').text = self.invoice_origin or ''
        ET.SubElement(emisor, 'ZonaVenta').text = 'N/A'
        ET.SubElement(emisor, 'RutaVenta').text = 'N/A'

        info_adic = ET.SubElement(emisor, 'InformacionAdicionalEmisor')
        ET.SubElement(info_adic, 'InformacionAdicional', {
            'nombre': 'Sucursal',
            'texto': self.company_id.city or 'Principal'
        })

        ET.SubElement(emisor, 'FechaEmision').text = self.invoice_date.strftime('%d-%m-%Y') if self.invoice_date else fields.Date.today().strftime('%d-%m-%Y')

        # Comprador (Customer)
        comprador = ET.SubElement(encabezado, 'Comprador')
        ET.SubElement(comprador, 'RNCComprador').text = self.partner_id.vat or ""
        ET.SubElement(comprador, 'RazonSocialComprador').text = self.partner_id.name or ""
        if self.partner_id.street:
            ET.SubElement(comprador, 'DireccionComprador').text = self.partner_id.street

        # Informaciones adicionales
        info_adicional = ET.SubElement(encabezado, 'InformacionesAdicionales')
        ET.SubElement(info_adicional, 'InformacionAdicional', {
            'nombre': 'Observaciones',
            'texto': self.narration or "Factura generada desde Odoo"
        })

        # Transporte (required even if empty)
        ET.SubElement(encabezado, 'Transporte')

        # Totales (inside Encabezado if not present yet)
        if not encabezado.find('Totales'):
            totales = ET.SubElement(encabezado, 'Totales')
            ET.SubElement(totales, 'MontoTotal').text = "%.2f" % self.amount_total
            ET.SubElement(totales, 'ValorPagar').text = "%.2f" % self.amount_total
            ET.SubElement(totales, 'TotalITBISRetenido').text = "0.00"
            ET.SubElement(totales, 'TotalISRRetencion').text = "0.00"
            ET.SubElement(totales, 'TotalITBISPercepcion').text = "0.00"

        # 2. Detalles (Line Items)
        detalles = ET.SubElement(root, 'Detalles')
        for line in self.invoice_line_ids:
            if line.display_type:  # skip section/note lines
                continue
            item = ET.SubElement(detalles, 'Item')
            ET.SubElement(item, 'Descripcion').text = line.name or ""
            ET.SubElement(item, 'Cantidad').text = str(line.quantity)
            ET.SubElement(item, 'PrecioUnitario').text = "%.2f" % line.price_unit
            # ITBIS calculation
            tax_amount = sum(t.amount for t in line.tax_ids if "ITBIS" in t.name.upper())
            line_itbis = (line.price_subtotal * tax_amount / 100.0) if tax_amount else 0
            ET.SubElement(item, 'ITBIS').text = "%.2f" % line_itbis
            ET.SubElement(item, 'MontoItem').text = "%.2f" % line.price_total

        # 3. Totales (must be direct child of ECF)
        totales_root = ET.SubElement(root, 'Totales')
        ET.SubElement(totales_root, 'MontoTotal').text = "%.2f" % self.amount_total
        ET.SubElement(totales_root, 'ITBISTotal').text = "%.2f" % self.amount_tax

        # Convert to XML string
        xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')

        rough_string = ET.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml_as_str = reparsed.toprettyxml(indent="  ", encoding='utf-8')

        path = os.path.join(os.path.dirname(__file__), '..', 'data/row_invoice.xml')
        
        with open(path, 'wb') as f:
            f.write(pretty_xml_as_str)
        
        # Convert to lxml for signing
        return xml_str
    
    def generate_dummy_dgii_xml(self):
        """Generate fully compliant DGII dummy XML for immediate client demo"""
        root = ET.Element('ECF', {
            'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
            'xmlns:ds': 'http://www.w3.org/2000/09/xmldsig#',
            'xsi:schemaLocation': 'https://ecf.dgii.gov.do/esquemas/ecf/1.1'
        })

        # 1. Encabezado (Header) - Correct structure
        encabezado = ET.SubElement(root, 'Encabezado')
        
        # Required elements
        ET.SubElement(encabezado, 'Version').text = '1.1'
        
        id_doc = ET.SubElement(encabezado, 'IdDoc')
        ET.SubElement(id_doc, 'TipoeCF').text = "32"
        ET.SubElement(id_doc, 'eNCF').text = self.dgii_ncf
        ET.SubElement(id_doc, 'IndicadorMontoGravado').text = '1'  # 1=Yes, 0=No
        ET.SubElement(id_doc, 'FechaLimitePago').text = '2025-08-30'  # Optional
        ET.SubElement(id_doc, 'TerminoPago').text = 'Contado'  # "Contado" or "Crédito"
        
        emisor = ET.SubElement(encabezado, 'Emisor')
        ET.SubElement(emisor, 'RNCEmisor').text = '132456789'
        ET.SubElement(emisor, 'RazonSocialEmisor').text = 'EMPRESA DEMO SRL'
        ET.SubElement(emisor, 'NombreComercial').text = 'DEMO COMERCIAL'
        
        # Required address elements
        ET.SubElement(emisor, 'DireccionEmisor').text = 'Calle Principal #123'
        ET.SubElement(emisor, 'Municipio').text = 'Distrito Nacional'
        ET.SubElement(emisor, 'Provincia').text = 'Santo Domingo'
        
        # Contact information
        telefono = ET.SubElement(emisor, 'TablaTelefonoEmisor')
        
        # First phone number (landline)
        telefono1 = ET.SubElement(telefono, 'TelefonoEmisor')
        ET.SubElement(telefono1, 'NumeroTelefono').text = '8095551234'  # No hyphens
        ET.SubElement(telefono1, 'TipoTelefono').text = '1'  # 1 for landline

        ET.SubElement(emisor, 'CorreoEmisor').text = 'info@empresademo.com'
        ET.SubElement(emisor, 'WebSite').text = 'www.empresademo.com'
        
        # Economic information
        ET.SubElement(emisor, 'ActividadEconomica').text = 'VENTA AL POR MENOR'
        ET.SubElement(emisor, 'CodigoVendedor').text = 'VEN001'
        
        # Optional but recommended
        ET.SubElement(emisor, 'NumeroFacturaInterna').text = 'FAC-1001'
        ET.SubElement(emisor, 'NumeroPedidoInterno').text = 'PED-5001'
        ET.SubElement(emisor, 'ZonaVenta').text = 'ZONA 1'
        ET.SubElement(emisor, 'RutaVenta').text = 'RUTA A'
        
        # Additional info
        info_adicional = ET.SubElement(emisor, 'InformacionAdicionalEmisor')
        ET.SubElement(info_adicional, 'InformacionAdicional', {
            'nombre': 'Sucursal',
            'texto': 'Principal'
        })

        ET.SubElement(emisor, 'FechaEmision').text = "10-10-2020"
        
        comprador = ET.SubElement(encabezado, 'Comprador')
        ET.SubElement(comprador, 'RNCComprador').text = '987654321'
        ET.SubElement(comprador, 'RazonSocialComprador').text = 'CLIENTE DEMOSTRACION'

        # Critical fix: Correct order of elements
        info_adicional = ET.SubElement(encabezado, 'InformacionesAdicionales')
        ET.SubElement(info_adicional, 'InformacionAdicional', {
            'nombre': 'Observaciones',
            'texto': 'DEMO PARA CLIENTE - NO ES FACTURA REAL'
        })
        
        ET.SubElement(encabezado, 'Transporte')  # Required empty element

        if not encabezado.find('Totales'):  # Only add if not present
            totales = ET.SubElement(encabezado, 'Totales')
            ET.SubElement(totales, 'MontoTotal').text = '1180.00'  # Required
            ET.SubElement(totales, 'ValorPagar').text = '1180.00'  # Required
            ET.SubElement(totales, 'TotalITBISRetenido').text = '0.00'  # Required for B2B
            ET.SubElement(totales, 'TotalISRRetencion').text = '0.00'  # Required for services
            ET.SubElement(totales, 'TotalITBISPercepcion').text = '0.00'  # Optional

        # 2. Detalles (Line Items)
        detalles = ET.SubElement(root, 'Detalles')
        
        # Sample product 1
        item1 = ET.SubElement(detalles, 'Item')
        ET.SubElement(item1, 'Descripcion').text = 'SERVICIO DE DEMOSTRACION'
        ET.SubElement(item1, 'Cantidad').text = '1'
        ET.SubElement(item1, 'PrecioUnitario').text = '1000.00'
        ET.SubElement(item1, 'ITBIS').text = '180.00'  # 18%
        ET.SubElement(item1, 'MontoItem').text = '1180.00'

        # 3. Totales (Must be direct child of ECF)
        totales = ET.SubElement(root, 'Totales')
        ET.SubElement(totales, 'MontoTotal').text = '1180.00'
        ET.SubElement(totales, 'ITBISTotal').text = '180.00'

        # Return formatted XML
        xml_str = ET.tostring(root, encoding='utf-8').decode('utf-8')
        return xml_str

    def _attach_signed_xml(self, signed_xml):
        attachment_name = f'eCF_{self.name or "invoice"}.xml'
        self.env['ir.attachment'].create({
            'name': attachment_name,
            'res_model': 'account.move',
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'application/xml',
            'datas': base64.b64encode(signed_xml),
            'description': 'Signed e-CF XML for DGII',
        })

    def action_check_dgii_status(self):
        _logger = logging.getLogger(__name__)
        for inv in self.search([('dgii_status', '=', 'en_proceso'), ('dgii_track_id', '!=', False)]):
            try:
                # 🔹 Call DGII Tracking API (replace with real URL + auth)

                data = {'trackid': inv.dgii_track_id}
                headers = {
                    'accept': 'application/json',
                    "Authorization": f"Bearer {inv.dgii_token}"
                }
                
                response = requests.get(
                    f"{self.base_url}/consultaresultado/api/consultas/estado?trackid={inv.dgii_track_id}",
                    headers=headers,
                    timeout=30
                )

                result = response.json()

                estado = result.get("estado")
                mensajes = result.get("mensajes", [])

                if estado == "Aceptado":
                    inv.dgii_status = "aceptado"
                    inv.dgii_submission_status = "accepted"
                elif estado == "Rechazado":
                    inv.dgii_status = "rechazado"
                    inv.dgii_submission_status = "rejected"
                    inv.dgii_rejection_reason = "\n".join([m.get("valor", "") for m in mensajes])
                else:
                    inv.dgii_status = "en_proceso"

            except Exception as e:
                _logger.error(f"DGII Tracking API error: {e}")