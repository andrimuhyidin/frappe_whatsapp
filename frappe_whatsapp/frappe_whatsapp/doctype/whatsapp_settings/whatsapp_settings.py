# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document

class WhatsAppSettings(Document):
	"""
	WhatsApp Settings for global integration configuration.
	
	Single DocType storing WhatsApp Business API credentials,
	webhook URLs, and other global settings.
	"""

	pass
