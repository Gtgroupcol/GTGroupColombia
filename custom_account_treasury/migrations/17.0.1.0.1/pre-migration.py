def migrate(cr, version):
    """Pre-migration script to clean up change_destination_account field values"""
    
    # Update empty strings to '0' to avoid conversion errors
    cr.execute("""
        UPDATE account_payment 
        SET change_destination_account = '0' 
        WHERE change_destination_account = '' 
           OR change_destination_account IS NULL
    """)
    
    # Update any non-numeric values to '0'
    cr.execute("""
        UPDATE account_payment 
        SET change_destination_account = '0' 
        WHERE change_destination_account !~ '^[0-9]+$'
           AND change_destination_account IS NOT NULL
    """)
