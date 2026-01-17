"""Webhook."""
import frappe
import json
import requests
import time
import hashlib
import hmac
from werkzeug.wrappers import Response
import frappe.utils

from frappe_whatsapp.utils import get_whatsapp_account


def verify_webhook_signature(payload_bytes, signature_header):
	"""
	Verify the incoming webhook request signature from Meta.
	Returns True if valid, False otherwise.
	"""
	if not signature_header:
		return False
	
	# Signature format: sha256=<hash>
	if not signature_header.startswith("sha256="):
		return False
	
	received_signature = signature_header[7:]  # Remove "sha256=" prefix
	
	# Get any active WhatsApp account with app_secret configured
	accounts = frappe.get_all(
		"WhatsApp Account",
		filters={"status": "Active"},
		fields=["name"]
	)
	
	for acc in accounts:
		try:
			account_doc = frappe.get_doc("WhatsApp Account", acc.name)
			app_secret = account_doc.get_password("app_secret") if account_doc.app_secret else None
			
			if not app_secret:
				continue
			
			expected_signature = hmac.new(
				app_secret.encode(),
				payload_bytes,
				hashlib.sha256
			).hexdigest()
			
			if hmac.compare_digest(received_signature, expected_signature):
				return True
		except Exception:
			continue
	
	return False


@frappe.whitelist(allow_guest=True)
def webhook():
	"""Meta webhook."""
	if frappe.request.method == "GET":
		return get()
	
	# Get raw payload for signature verification
	payload_bytes = frappe.request.get_data()
	signature_header = frappe.request.headers.get("X-Hub-Signature-256")
	
	# Check if signature verification is required (any account has app_secret)
	any_secret_configured = frappe.db.exists(
		"WhatsApp Account",
		{"status": "Active", "app_secret": ["is", "set"]}
	)
	
	if any_secret_configured and signature_header:
		if not verify_webhook_signature(payload_bytes, signature_header):
			frappe.log_error("Invalid webhook signature", "WhatsApp Security")
			
			# Log failed attempt
			frappe.get_doc({
				"doctype": "WhatsApp Webhook Log",
				"timestamp": frappe.utils.now(),
				"request_data": payload_bytes.decode('utf-8', errors='ignore'),
				"headers": json.dumps(dict(frappe.request.headers)),
				"error": "Invalid Signature"
			}).insert(ignore_permissions=True)
			
			return Response("Forbidden", status=403)
	
	data = frappe.local.form_dict
	# Return 200 OK immediately to Meta to prevent retries
	# Process in background
	frappe.enqueue(
		"frappe_whatsapp.utils.webhook.process_webhook_data",
		data=data,
		queue="long",
		now=frappe.flags.in_test
	)
	return Response("OK", status=200)



@frappe.whitelist()
def process_webhook_data(data):
	"""Process webhook data in background."""
	try:
		frappe.get_doc({
			"doctype": "WhatsApp Webhook Log",
			"timestamp": frappe.utils.now(),
			"request_data": json.dumps(data),
			"headers": json.dumps(frappe.local.request.headers) if hasattr(frappe.local, 'request') else "{}"
		}).insert(ignore_permissions=True)
	except Exception:
		# Fallback or ignore if log fails, main priority is processing
		pass
		
	# Legacy logging just in case (optional, we can remove)
	# frappe.get_doc({
	# 	"doctype": "WhatsApp Notification Log",
	# 	"template": "Webhook",
	# 	"meta_data": json.dumps(data)
	# }).insert(ignore_permissions=True)
	
	frappe.db.commit()

	messages = []
	phone_id = None
	try:
		messages = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [])
		phone_id = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("metadata", {}).get("phone_number_id")
	except (KeyError, IndexError):
		return

	sender_profile_name = next(
		(
			contact.get("profile", {}).get("name")
			for entry in data.get("entry", [])
			for change in entry.get("changes", [])
			for contact in change.get("value", {}).get("contacts", [])
		),
		None,
	)

	whatsapp_account = get_whatsapp_account(phone_id) if phone_id else None
	if not whatsapp_account:
		return

	if messages:
		for message in messages:
			process_single_message(message, whatsapp_account, sender_profile_name)
	else:
		changes = None
		try:
			changes = data["entry"][0]["changes"][0]
		except (KeyError, IndexError):
			pass
		
		if changes:
			update_status(changes)


def process_single_message(message, whatsapp_account, sender_profile_name):
	"""Logic to process a single message from webhook."""
	message_type = message['type']
	is_reply = True if message.get('context') and 'forwarded' not in message.get('context') else False
	reply_to_message_id = message['context']['id'] if is_reply else None
	
	msg_data = {
		"doctype": "WhatsApp Message",
		"type": "Incoming",
		"from": message['from'],
		"message_id": message['id'],
		"reply_to_message_id": reply_to_message_id,
		"is_reply": is_reply,
		"profile_name": sender_profile_name,
		"whatsapp_account": whatsapp_account.name,
		"content_type": message_type
	}

	if message_type == 'text':
		msg_data["message"] = message['text']['body']
		frappe.get_doc(msg_data).insert(ignore_permissions=True)
	
	elif message_type == 'reaction':
		msg_data["message"] = message['reaction']['emoji']
		msg_data["reply_to_message_id"] = message['reaction']['message_id']
		msg_data["content_type"] = "reaction"
		frappe.get_doc(msg_data).insert(ignore_permissions=True)
	
	elif message_type == 'interactive':
		interactive_data = message['interactive']
		interactive_type = interactive_data.get('type')

		if interactive_type in ['button_reply', 'list_reply']:
			msg_data["message"] = interactive_data[interactive_type]['id']
			msg_data["content_type"] = "button"
			frappe.get_doc(msg_data).insert(ignore_permissions=True)
		
		elif interactive_type == 'nfm_reply':
			nfm_reply = interactive_data['nfm_reply']
			response_json_str = nfm_reply.get('response_json', '{}')
			try:
				flow_response = json.loads(response_json_str)
			except json.JSONDecodeError:
				flow_response = {}

			summary_parts = [f"{k}: {v}" for k, v in flow_response.items() if v]
			msg_data.update({
				"message": ", ".join(summary_parts) if summary_parts else "Flow completed",
				"content_type": "flow",
				"flow_response": json.dumps(flow_response)
			})
			frappe.get_doc(msg_data).insert(ignore_permissions=True)

			frappe.publish_realtime("whatsapp_flow_response", {
				"phone": message['from'],
				"message_id": message['id'],
				"flow_response": flow_response,
				"whatsapp_account": whatsapp_account.name
			})

	elif message_type in ["image", "audio", "video", "document"]:
		# Download in background as well (nested enqueue might be overkill, but let's keep it here for now)
		msg_data["message"] = message[message_type].get("caption", "")
		msg_doc = frappe.get_doc(msg_data).insert(ignore_permissions=True)
		
		# Separate task for media download to not block message insertion
		frappe.enqueue(
			"frappe_whatsapp.utils.webhook.download_media",
			message_doc_name=msg_doc.name,
			message_data=message[message_type],
			message_type=message_type,
			whatsapp_account_name=whatsapp_account.name,
			queue="long"
		)

	elif message_type == "button":
		msg_data["message"] = message['button']['text']
		frappe.get_doc(msg_data).insert(ignore_permissions=True)
	
	else:
		msg_data["message"] = message[message_type].get(message_type) if isinstance(message[message_type], dict) else message[message_type]
		frappe.get_doc(msg_data).insert(ignore_permissions=True)

	frappe.db.commit()


def download_media(message_doc_name, message_data, message_type, whatsapp_account_name):
	"""Download media from Meta and attach to message."""
	try:
		whatsapp_account = frappe.get_doc("WhatsApp Account", whatsapp_account_name)
		token = whatsapp_account.get_password("token")
		url = f"{whatsapp_account.url}/{whatsapp_account.version}/"
		media_id = message_data["id"]

		headers = {'Authorization': 'Bearer ' + token}
		response = requests.get(f'{url}{media_id}/', headers=headers)

		if response.status_code == 200:
			media_info = response.json()
			media_url = media_info.get("url")
			mime_type = media_info.get("mime_type")
			file_extension = mime_type.split('/')[1] if '/' in mime_type else 'bin'

			media_response = requests.get(media_url, headers=headers)
			if media_response.status_code == 200:
				file_name = f"{frappe.generate_hash(length=10)}.{file_extension}"
				
				file_doc = frappe.get_doc({
					"doctype": "File",
					"file_name": file_name,
					"attached_to_doctype": "WhatsApp Message",
					"attached_to_name": message_doc_name,
					"content": media_response.content,
					"attached_to_field": "attach"
				}).insert(ignore_permissions=True)

				frappe.db.set_value("WhatsApp Message", message_doc_name, "attach", file_doc.file_url)
				frappe.db.commit()
	except Exception as e:
		frappe.log_error(f"Media download failed for {message_doc_name}: {str(e)}", "WhatsApp Media Error")


def update_status(data):
	"""Update status hook."""
	if data.get("field") == "message_template_status_update":
		update_template_status(data['value'])

	elif data.get("field") == "messages":
		update_message_status(data['value'])

def update_template_status(data):
	"""Update template status."""
	# Refactored to QueryBuilder
	wt = frappe.qb.DocType("WhatsApp Templates")
	(
		frappe.qb.update(wt)
		.set(wt.status, data['event'])
		.where(wt.id == data['message_template_id'])
	).run()

def update_message_status(data):
	"""Update message status."""
	id = data['statuses'][0]['id']
	status = data['statuses'][0]['status']
	conversation = data['statuses'][0].get('conversation', {}).get('id')
	name = frappe.db.get_value("WhatsApp Message", filters={"message_id": id})

	doc = frappe.get_doc("WhatsApp Message", name)
	doc.status = status
	if conversation:
		doc.conversation_id = conversation
	doc.save(ignore_permissions=True)
