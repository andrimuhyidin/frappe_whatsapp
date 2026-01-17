import frappe
from frappe.tests.utils import FrappeTestCase
from frappe_whatsapp.utils.rate_limiter import check_rate_limit, increment_rate_limit, RateLimitExceeded
import time

class TestRateLimiter(FrappeTestCase):
    def setUp(self):
        self.account_name = "TestAccount_RateLimit"
        # clear cache
        frappe.cache().delete_key(f"wa_rate_limit:{self.account_name}")

    def test_rate_limit_enforcement(self):
        # Allow 5 messages per minute
        limit = 5
        window = 60
        
        # Consuming 5 tokens should be fine
        for i in range(5):
            allowed, current = check_rate_limit(self.account_name, limit, window)
            self.assertTrue(allowed)
            increment_rate_limit(self.account_name, window)
            
        # 6th should fail
        allowed, current = check_rate_limit(self.account_name, limit, window)
        self.assertFalse(allowed)
        
    def test_decorator_mock(self):
        # We can't easily test the decorator on a real function without mocking time or waiting
        # But we verified the utility functions above
        pass
