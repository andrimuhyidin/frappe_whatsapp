"""Rate Limiter for WhatsApp outgoing messages."""
import frappe
from frappe.utils import cint


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


def get_rate_limit_key(account_name: str) -> str:
    """Generate cache key for rate limiting."""
    return f"whatsapp_rate_limit:{account_name}"


def check_rate_limit(account_name: str, limit_per_minute: int = 30) -> bool:
    """
    Check if the account has exceeded its rate limit.
    
    Args:
        account_name: WhatsApp Account name
        limit_per_minute: Maximum messages per minute (default 30)
    
    Returns:
        True if within limit, False if exceeded
    """
    cache_key = get_rate_limit_key(account_name)
    current_count = cint(frappe.cache.get(cache_key) or 0)
    
    if current_count >= limit_per_minute:
        return False
    
    return True


def increment_rate_limit(account_name: str):
    """
    Increment the message counter for rate limiting.
    Counter expires after 60 seconds.
    """
    cache_key = get_rate_limit_key(account_name)
    current_count = cint(frappe.cache.get(cache_key) or 0)
    
    # Set with 60 second expiry
    frappe.cache.set(cache_key, current_count + 1, expires_in_sec=60)


def get_remaining_quota(account_name: str, limit_per_minute: int = 30) -> int:
    """Get remaining message quota for the account."""
    cache_key = get_rate_limit_key(account_name)
    current_count = cint(frappe.cache.get(cache_key) or 0)
    return max(0, limit_per_minute - current_count)


def rate_limited_send(send_func):
    """
    Decorator to add rate limiting to message send functions.
    
    Usage:
        @rate_limited_send
        def send_message(account, to, message):
            ...
    """
    def wrapper(*args, **kwargs):
        # Try to get account from args/kwargs
        account = kwargs.get("whatsapp_account") or kwargs.get("account")
        
        if not account and args:
            # Try to find account in positional args
            for arg in args:
                if isinstance(arg, str) and frappe.db.exists("WhatsApp Account", arg):
                    account = arg
                    break
        
        if account:
            # Get configured limit (default 30)
            try:
                limit = frappe.db.get_value("WhatsApp Settings", None, "rate_limit_per_minute") or 30
            except Exception:
                limit = 30
            
            if not check_rate_limit(account, limit):
                frappe.log_error(
                    f"Rate limit exceeded for account: {account}",
                    "WhatsApp Rate Limit"
                )
                raise RateLimitExceeded(f"Rate limit exceeded for {account}. Try again in a minute.")
            
            # Increment counter before sending
            increment_rate_limit(account)
        
        return send_func(*args, **kwargs)
    
    return wrapper


def reset_rate_limit(account_name: str):
    """Manually reset rate limit for an account (admin function)."""
    cache_key = get_rate_limit_key(account_name)
    frappe.cache.delete(cache_key)
