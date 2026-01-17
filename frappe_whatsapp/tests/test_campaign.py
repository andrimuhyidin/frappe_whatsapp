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

    def test_tagged_contacts_population(self):
        # 1. Create a tag
        if not frappe.db.exists("WhatsApp Contact Tag", "Test Tag"):
            frappe.get_doc({
                "doctype": "WhatsApp Contact Tag",
                "tag_name": "Test Tag"
            }).insert(ignore_permissions=True)
            
        # 2. Assign tag to contact
        self.contact.append("tags", {"tag_name": "Test Tag"})
        self.contact.save(ignore_permissions=True)
        
        # 3. Create campaign targeting this tag
        campaign = frappe.new_doc("WhatsApp Campaign")
        campaign.campaign_name = "Tagged Campaign"
        campaign.template = self.template.name
        campaign.whatsapp_account = self.account.name
        campaign.audience_type = "Tagged Contacts"
        campaign.append("target_tags", {"tag_name": "Test Tag"})
        campaign.status = "Draft"
        campaign.insert(ignore_permissions=True)
        
        # 4. Run populate recipients
        # This will use our new optimized SQL query
        populate_recipients(campaign)
        
        campaign.reload()
        
        # 5. Verify results
        self.assertEqual(len(campaign.recipients), 1)
        self.assertEqual(campaign.recipients[0].mobile_no, "9999999999")
        
        # 6. Verify non-match
        campaign.target_tags = [] # Clear tags
        campaign.append("target_tags", {"tag_name": "Non Existent Tag"})
        populate_recipients(campaign)
        campaign.reload()
        self.assertEqual(len(campaign.recipients), 0)
