# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class WhatsAppNotificationLog(Document):
	"""
	WhatsApp Notification Log for tracking sent notifications.
	
	Records history of WhatsApp notifications triggered by
	document events or scheduled tasks with delivery status.
	"""

	pass
