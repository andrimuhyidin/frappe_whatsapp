import frappe
from frappe.model.document import Document
from frappe_whatsapp.utils import webhook


class WhatsAppWebhookLog(Document):
    @frappe.whitelist()
    def replay_webhook(self):
        """Replay this webhook."""
        if not self.request_data:
            frappe.throw("No request data to replay")
            
        try:
            # We call the internal webhook processing function directly
            # This bypasses signature check usually, which is fine for replay if we trust the log
            # Or we can verify it again if headers are present
            
            data = frappe.parse_json(self.request_data)
            webhook.webhook(data)
            
            self.is_replayed = 1
            self.save(ignore_permissions=True)
            return "Replay Successful"
        except Exception as e:
            frappe.log_error(f"Replay failed: {e}", "WhatsApp Webhook Replay")
            return f"Replay Failed: {e}"
