import frappe

def is_app_installed(app_name):
    """Check if an app is installed."""
    return app_name in frappe.get_installed_apps()

def get_integration_method(app_name, method_path):
    """
    Safely retrieve a method from another app if installed.
    Returns None if app or method is missing.
    Usage:
        func = get_integration_method("erpnext", "erpnext.crm.doctype.lead.lead.make_lead")
        if func:
            func(args)
    """
    if not is_app_installed(app_name):
        return None
    
    try:
        return frappe.get_attr(method_path)
    except Exception:
        frappe.log_error(f"Integration Method Not Found: {method_path}", "WhatsApp Integration Error")
        return None

def has_doctype(doctype):
    """Check if DocType exists via Meta (Cached)."""
    try:
        frappe.get_meta(doctype)
        return True
    except frappe.DoesNotExistError:
        return False
