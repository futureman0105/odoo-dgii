{
    'name': 'DGII Electronic Invoicing (Dominican Republic)',
    'version': '1.0',
    'category': 'Accounting/Localizations',
    'summary': 'DGII e-CF XML, Signature & Submission',
    'description': 'Generates and sends e-CF XMLs to DGII with digital signing.',
    'author': 'SolutionProvider',
    'depends': ['account', 'l10n_do'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
        'views/settings_views.xml',
        'data/ir_sequence_data.xml',
        "data/ncf_sequence.xml",        # NCF sequences
        'views/report_invoice_document.xml',
        'views/report_credit_note_document.xml',
        # 'data/cron.xml',
    ],
    'installable': True,
    'application': True,
}
