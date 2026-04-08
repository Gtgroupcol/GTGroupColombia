{
    'name': 'Woompi Payment Provider',
    'version': '1.0',
    'category': 'Accounting/Payment Providers',
    "summary": "Pagos en línea con ComboPay",
    'author': 'JZOLUTIONS',
    'maintainer': 'JZOLUTIONS',
    'website': 'www.jzolutions.com',
    'description': '''Payment Provider: Woompi''',
    'license': 'OPL-1',
    'price': 200.00,
    'currency': 'USD',
    'depends': [
        'payment',
        'sale',
        'website_payment',
        'website_sale',
    ],
    'data': [
        'data/payment_templates.xml',
        # 'views/js_files_link.xml',
        'views/payment_provider_views.xml',

        # 'views/sale_order.xml',
        #'views/payment_transaction_view.xml',
        'data/payment_provider_data.xml',
        #'data/mail_data.xml',
    ],
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    #'assets': {
    #    'web.assets_frontend': [
    #        'payment_nuvei/static/src/js/payment.js',
    #    ],
    #},
    #"support": "jzolution@gmail.com",
}
