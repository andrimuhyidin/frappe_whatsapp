"""Scheduler for WhatsApp messages."""
import frappe
from frappe.utils import now_datetime, get_datetime


def process_scheduled_messages():
    """
    Scheduled job to process pending scheduled messages.
    Should run every minute or very frequently.
    """
    current_time = now_datetime()
    
    # Find active messages scheduled for now or past
    messages = frappe.get_all(
        "WhatsApp Message",
        filters={
            "is_scheduled": 1,
            "scheduled_time": ["<=", current_time],
            "scheduling_status": "Pending",
            "status": ["!=", "Sent"] # Double check status
        },
        fields=["name"]
    )
    
    for msg in messages:
        try:
            doc = frappe.get_doc("WhatsApp Message", msg.name)
            
            # Verify status again
            if doc.scheduling_status != "Pending":
                continue
                
            # Send message
            doc.send()
            
            # Update status
            doc.scheduling_status = "Sent"
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(f"Failed to send scheduled message {msg.name}: {e}", "WhatsApp Scheduler")
            
            # Mark as failed in logs but maybe retry later?
            # For now just log error.


@frappe.whitelist()
def schedule_message(to, message, scheduled_time, whatsapp_account=None):
    """API to schedule a message."""
    
    if get_datetime(scheduled_time) <= now_datetime():
        frappe.throw("Scheduled time must be in the future")

    doc = frappe.get_doc({
        "doctype": "WhatsApp Message",
        "type": "Outgoing",
        "to": to,
        "message": message,
        "whatsapp_account": whatsapp_account,
        "is_scheduled": 1,
        "scheduled_time": scheduled_time,
        "scheduling_status": "Pending",
        "status": "Queued"
    })
    
    doc.insert(ignore_permissions=True)
    return doc.name


@frappe.whitelist()
def cancel_scheduled_message(message_name):
    """Cancel a pending scheduled message."""
    doc = frappe.get_doc("WhatsApp Message", message_name)
    
    if not doc.is_scheduled or doc.scheduling_status != "Pending":
        frappe.throw("Message is not in pending schedule state")
        
    doc.scheduling_status = "Cancelled"
    doc.status = "Cancelled"
    doc.save(ignore_permissions=True)
    
    return True
