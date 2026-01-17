import frappe
from frappe_whatsapp.integrations.core import get_integration_method

def notify_invoice_submission(doc, method=None):
    """
    Hook: Sales Invoice > on_submit
    Sends notification with Payment Link if unpaid.
    """
    if doc.status == "Paid":
        return

    # Use format_number from utils if available
    # For now assuming simple logic or using frappe_whatsapp core send function
    
    # We need to find the customer's mobile number
    customer_mobile = frappe.db.get_value("Customer", doc.customer, "mobile_no")
    if not customer_mobile:
        return

    message = f"Hello {doc.customer_name},\nYour invoice {doc.name} for {doc.grand_total} is ready."
    
    # If payment link integration exists, add it
    # payment_url = doc.get_url() # simplified
    
    send_whatsapp(customer_mobile, message, doc.name, doc.doctype)

def notify_payment_received(doc, method=None):
    """
    Hook: Payment Entry > on_submit
    """
    if doc.payment_type != "Receive":
        return

    party_mobile = None
    if doc.party_type == "Customer":
        party_mobile = frappe.db.get_value("Customer", doc.party, "mobile_no")
    
    if not party_mobile:
        return

    message = f"Payment Received! \nAmount: {doc.paid_amount}\nRef: {doc.name}\nThank you!"
    send_whatsapp(party_mobile, message, doc.name, doc.doctype)

def notify_travel_booking(doc, method=None):
    """
    Hook: Travel Booking > on_update
    Trigger when status becomes 'Confirmed'
    """
    if doc.status != "Confirmed":
        return
        
    # Check if this is a status CHANGE (optimization)
    # db_status = frappe.db.get_value("Travel Booking", doc.name, "status")
    # if db_status == "Confirmed": return # Already confirmed
    # Using on_update might trigger multiple times, checking 'doc.has_changed' equivalent if available
    # Or simple idempotency check in message history.
    
    customer_mobile = frappe.db.get_value("Customer", doc.customer, "mobile_no")
    if not customer_mobile:
        return

    tour_name = doc.tour or "your trip"
    message = f"Hooray! 🏝️\nYour trip to {tour_name} is CONFIRMED.\nRef: {doc.name}\nSee you soon!"
    send_whatsapp(customer_mobile, message, doc.name, doc.doctype)

def send_whatsapp(mobile, message, doc_name, doc_type):
    """
    Helper to send generic message via frappe_whatsapp.
    """
    try:
        # Create WhatsApp Message DocType
        # This queues it automatically in the new architecture
        wa_msg = frappe.new_doc("WhatsApp Message")
        wa_msg.to_number = mobile
        wa_msg.message = message
        wa_msg.reference_doctype = doc_type
        wa_msg.reference_name = doc_name
        wa_msg.insert(ignore_permissions=True)
        # wa_msg.send() # Auto-sent via queue/scheduler usually, or we can force it
        # Assuming new architecture queues it on insert or we call send()
        
        # Check standard implementation
        # usually wa_msg.save() triggers validation, then we might need to enqueue
        frappe.enqueue("frappe_whatsapp.utils.send_message", queue="short", doc=wa_msg)
        
    except Exception as e:
        frappe.log_error(f"Failed to send Commerce Notification: {e}", "WhatsApp Commerce Integration")
