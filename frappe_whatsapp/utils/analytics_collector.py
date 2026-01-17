"""Analytics collector for WhatsApp messages and sessions."""
import frappe
from frappe.utils import today, add_days, now_datetime, get_datetime


def aggregate_daily_analytics():
    """
    Scheduled job to aggregate daily analytics.
    Should run once per day (e.g., at midnight or early morning).
    """
    yesterday = add_days(today(), -1)
    
    # Get all active WhatsApp accounts
    accounts = frappe.get_all(
        "WhatsApp Account",
        filters={"status": "Active"},
        pluck="name"
    )
    
    for account in accounts:
        try:
            aggregate_for_account(account, yesterday)
        except Exception as e:
            frappe.log_error(f"Analytics aggregation failed for {account}: {e}", "WhatsApp Analytics")
    
    frappe.db.commit()


def aggregate_for_account(account_name, date):
    """Aggregate analytics for a specific account and date."""
    
    # Check if already aggregated
    existing = frappe.db.exists("WhatsApp Analytics", {"date": date, "whatsapp_account": account_name})
    if existing:
        return  # Already done

    start_datetime = get_datetime(f"{date} 00:00:00")
    end_datetime = get_datetime(f"{date} 23:59:59")

    # Message counts
    messages_sent = frappe.db.count("WhatsApp Message", {
        "whatsapp_account": account_name,
        "type": "Outgoing",
        "creation": ["between", [start_datetime, end_datetime]]
    })

    messages_received = frappe.db.count("WhatsApp Message", {
        "whatsapp_account": account_name,
        "type": "Incoming",
        "creation": ["between", [start_datetime, end_datetime]]
    })

    messages_failed = frappe.db.count("WhatsApp Message", {
        "whatsapp_account": account_name,
        "status": "failed",
        "creation": ["between", [start_datetime, end_datetime]]
    })

    # Session counts (if chatbot module is installed)
    sessions_started = 0
    sessions_completed = 0
    sessions_transferred = 0
    sessions_timeout = 0

    try:
        if frappe.db.table_exists("WhatsApp Chatbot Session"):
            sessions_started = frappe.db.count("WhatsApp Chatbot Session", {
                "whatsapp_account": account_name,
                "creation": ["between", [start_datetime, end_datetime]]
            })

            sessions_completed = frappe.db.count("WhatsApp Chatbot Session", {
                "whatsapp_account": account_name,
                "status": "Completed",
                "completed_at": ["between", [start_datetime, end_datetime]]
            })

            sessions_timeout = frappe.db.count("WhatsApp Chatbot Session", {
                "whatsapp_account": account_name,
                "status": "Timeout",
                "completed_at": ["between", [start_datetime, end_datetime]]
            })

        if frappe.db.table_exists("WhatsApp Agent Transfer"):
            sessions_transferred = frappe.db.count("WhatsApp Agent Transfer", {
                "whatsapp_account": account_name if frappe.get_meta("WhatsApp Agent Transfer").has_field("whatsapp_account") else None,
                "creation": ["between", [start_datetime, end_datetime]]
            }) if frappe.get_meta("WhatsApp Agent Transfer").has_field("whatsapp_account") else 0
    except Exception:
        pass  # Chatbot module might not be installed

    # Calculate average response time (simplified)
    avg_response_time = calculate_avg_response_time(account_name, start_datetime, end_datetime)

    # Create analytics record
    analytics = frappe.new_doc("WhatsApp Analytics")
    analytics.date = date
    analytics.whatsapp_account = account_name
    analytics.messages_sent = messages_sent
    analytics.messages_received = messages_received
    analytics.messages_failed = messages_failed
    analytics.avg_response_time_seconds = avg_response_time
    analytics.sessions_started = sessions_started
    analytics.sessions_completed = sessions_completed
    analytics.sessions_transferred = sessions_transferred
    analytics.sessions_timeout = sessions_timeout
    analytics.ai_responses = 0  # Will be tracked separately
    analytics.kb_matches = 0
    analytics.ai_cache_hits = 0
    analytics.ai_errors = 0
    analytics.insert(ignore_permissions=True)


def calculate_avg_response_time(account_name, start_dt, end_dt):
    """
    Calculate average response time for the period.
    Simplified: time between incoming message and next outgoing message.
    """
    try:
        # Get pairs of incoming -> outgoing messages
        messages = frappe.db.sql("""
            SELECT type, creation, `from`, `to`
            FROM `tabWhatsApp Message`
            WHERE whatsapp_account = %s
            AND creation BETWEEN %s AND %s
            ORDER BY creation
        """, (account_name, start_dt, end_dt), as_dict=True)

        if len(messages) < 2:
            return 0

        response_times = []
        for i, msg in enumerate(messages):
            if msg.type == "Incoming":
                # Find next outgoing message to same contact
                for j in range(i + 1, min(i + 10, len(messages))):
                    next_msg = messages[j]
                    if next_msg.type == "Outgoing" and next_msg.get("to") == msg.get("from"):
                        delta = (next_msg.creation - msg.creation).total_seconds()
                        if delta > 0 and delta < 3600:  # Max 1 hour
                            response_times.append(delta)
                        break

        if response_times:
            return sum(response_times) / len(response_times)

    except Exception as e:
        frappe.log_error(f"Response time calculation error: {e}", "WhatsApp Analytics")

    return 0


def increment_counter(counter_name, account_name=None, date=None):
    """
    Utility to increment a specific counter in real-time.
    Used by other modules to track events.
    """
    date = date or today()
    
    # Get or create today's analytics record
    filters = {"date": date}
    if account_name:
        filters["whatsapp_account"] = account_name
    
    existing = frappe.db.get_value("WhatsApp Analytics", filters, "name")
    
    if existing:
        current = frappe.db.get_value("WhatsApp Analytics", existing, counter_name) or 0
        frappe.db.set_value("WhatsApp Analytics", existing, counter_name, current + 1)
    else:
        # Create a new record for today
        analytics = frappe.new_doc("WhatsApp Analytics")
        analytics.date = date
        analytics.whatsapp_account = account_name
        setattr(analytics, counter_name, 1)
        analytics.insert(ignore_permissions=True)
    
    frappe.db.commit()
