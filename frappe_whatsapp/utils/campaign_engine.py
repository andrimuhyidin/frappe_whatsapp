"""Campaign engine for broadcast messaging."""
import frappe
from frappe.utils import now_datetime, get_datetime


def process_campaigns():
    """
    Scheduled job to process active campaigns.
    Drives the campaign lifecycle: Draft -> Scheduled -> Running -> Completed.
    """
    
    # 1. Start scheduled campaigns
    scheduled_campaigns = frappe.get_all(
        "WhatsApp Campaign",
        filters={
            "status": "Scheduled",
            "scheduled_time": ["<=", now_datetime()]
        },
        fields=["name"]
    )
    
    for camp in scheduled_campaigns:
        start_campaign(camp.name)
        
    # 2. Process running campaigns (send batches)
    running_campaigns = frappe.get_all(
        "WhatsApp Campaign",
        filters={"status": "Running"},
        fields=["name"]
    )
    
    for camp in running_campaigns:
        process_campaign_batch(camp.name)


def start_campaign(campaign_name):
    """Initialize a campaign and populate recipients."""
    try:
        doc = frappe.get_doc("WhatsApp Campaign", campaign_name)
        
        # Populate recipients if empty
        if not doc.recipients:
            populate_recipients(doc)
            
        doc.status = "Running"
        doc.total_recipients = len(doc.recipients)
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Failed to start campaign {campaign_name}: {e}", "WhatsApp Campaign")


def populate_recipients(doc):
    """Populate recipients based on audience type."""
    recipients = []
    
    if doc.audience_type == "All Contacts":
        contacts = frappe.get_all("WhatsApp Contact", fields=["contact_name", "mobile_no"])
        for c in contacts:
            recipients.append({
                "contact_name": c.contact_name,
                "mobile_no": c.mobile_no,
                "status": "Pending"
            })
            
    elif doc.audience_type == "Tagged Contacts":
        if not doc.target_tags:
            return
            
        target_tags = [t.tag_name for t in doc.target_tags]
        
        # This query is simplified; in real SQL might need JOIN or loop
        # For now assuming we fetch all and filter in python for flexibility
        all_contacts = frappe.get_all("WhatsApp Contact", fields=["name", "contact_name", "mobile_no"])
        
        # Need to fetch tags for each contact (or improve query performance later)
        for c in all_contacts:
            contact_doc = frappe.get_doc("WhatsApp Contact", c.name)
            contact_tags = [t.tag_name for t in contact_doc.tags]
            
            # Check overlap
            if any(tag in target_tags for tag in contact_tags):
                recipients.append({
                    "contact_name": c.contact_name,
                    "mobile_no": c.mobile_no,
                    "status": "Pending"
                })
    
    # Clear existing and add new
    doc.set("recipients", [])
    doc.extend("recipients", recipients)


def process_campaign_batch(campaign_name, batch_size=20):
    """Send a batch of messages for a running campaign."""
    try:
        doc = frappe.get_doc("WhatsApp Campaign", campaign_name)
        
        if doc.status != "Running":
            return

        # Find pending recipients
        pending = [r for r in doc.recipients if r.status == "Pending"]
        
        if not pending:
            # Campaign complete
            doc.status = "Completed"
            doc.save(ignore_permissions=True)
            return

        # Process batch
        count = 0
        for recipient in pending[:batch_size]:
            try:
                # Send template message
                # We reuse existing send_template logic or call API directly
                # Creating a proper Message Doc is better for tracking
                
                msg = frappe.get_doc({
                    "doctype": "WhatsApp Message",
                    "type": "Outgoing",
                    "to": recipient.mobile_no,
                    "message_type": "Template",
                    "template": doc.template,
                    "whatsapp_account": doc.whatsapp_account,
                    "bulk_message_reference": doc.name # Link back
                })
                msg.insert(ignore_permissions=True)
                # It will auto-send via before_insert hook
                
                recipient.status = "Sent"
                recipient.message_id = msg.name
                doc.sent_count += 1
                count += 1
                
            except Exception as e:
                recipient.status = "Failed"
                doc.failed_count += 1
                frappe.log_error(f"Campaign send failed for {recipient.mobile_no}: {e}", "WhatsApp Campaign")
        
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Campaign batch processing failed for {campaign_name}: {e}", "WhatsApp Campaign")
