import frappe
from frappe.tests.utils import FrappeTestCase
from frappe_whatsapp.utils.campaign_engine import start_campaign, process_campaign_batch, populate_recipients


class TestCampaign(FrappeTestCase):
    def setUp(self):
        # Create test contact
        self.contact = frappe.new_doc("WhatsApp Contact")
        self.contact.contact_name = "Campaign User"
        self.contact.mobile_no = "9999999999"
        self.contact.save(ignore_permissions=True)
        
        # Create test template (stub)
        self.template = frappe.new_doc("WhatsApp Templates")
        self.template.template_name = "test_template"
        self.template.language_code = "en"
        self.template.insert(ignore_permissions=True)
        
        # Create test account (stub)
        self.account = frappe.new_doc("WhatsApp Account")
        self.account.name = "Test Account"
        self.account.status = "Active"
        self.account.insert(ignore_permissions=True)

    def tearDown(self):
        frappe.db.delete("WhatsApp Contact", self.contact.name)
        frappe.db.delete("WhatsApp Templates", self.template.name)
        frappe.db.delete("WhatsApp Account", self.account.name)
        frappe.db.sql("DELETE FROM `tabWhatsApp Campaign`")

    def test_campaign_lifecycle(self):
        # Create campaign
        campaign = frappe.new_doc("WhatsApp Campaign")
        campaign.campaign_name = "Test Campaign"
        campaign.template = self.template.name
        campaign.whatsapp_account = self.account.name
        campaign.audience_type = "All Contacts"
        campaign.status = "Draft"
        campaign.insert(ignore_permissions=True)
        
        # Test start (Draft -> Running)
        start_campaign(campaign.name)
        
        campaign.reload()
        self.assertEqual(campaign.status, "Running")
        self.assertTrue(len(campaign.recipients) > 0)
        self.assertEqual(campaign.recipients[0].mobile_no, "9999999999")
        self.assertEqual(campaign.recipients[0].status, "Pending")
        
        # Test batch processing
        # Mocking finding template to avoid error
        process_campaign_batch(campaign.name, batch_size=1)
        
        campaign.reload()
        # Should be Completed if all processed
        self.assertEqual(campaign.status, "Completed")
        self.assertEqual(campaign.recipients[0].status, "Sent")
        self.assertEqual(campaign.sent_count, 1)

    def test_populate_recipients(self):
        # Test Tag filtering logic mock
        # We need a tagged contact
        pass
