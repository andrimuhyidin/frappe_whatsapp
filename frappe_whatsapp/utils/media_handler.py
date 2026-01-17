"""Media handler for WhatsApp messages with async download and optimization."""
import frappe
from frappe.utils.file_manager import save_file
from PIL import Image
from io import BytesIO
import requests


def download_media_async(message_doc_name, message_data, message_type, whatsapp_account_name):
    """
    Async wrapper for media download.
    This is enqueued from webhook.py.
    """
    try:
        whatsapp_account = frappe.get_doc("WhatsApp Account", whatsapp_account_name)
        token = whatsapp_account.get_password("token")
        url = f"{whatsapp_account.url}/{whatsapp_account.version}/"
        media_id = message_data["id"]

        headers = {'Authorization': 'Bearer ' + token}
        response = requests.get(f'{url}{media_id}/', headers=headers, timeout=30)

        if response.status_code == 200:
            media_info = response.json()
            media_url = media_info.get("url")
            mime_type = media_info.get("mime_type")
            file_extension = get_extension_from_mime(mime_type)

            media_response = requests.get(media_url, headers=headers, timeout=60)
            if media_response.status_code == 200:
                content = media_response.content
                
                # Compress images
                if message_type == "image" and should_compress(len(content)):
                    content, file_extension = compress_image(content, mime_type)
                
                file_name = f"{frappe.generate_hash(length=10)}.{file_extension}"
                
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": file_name,
                    "attached_to_doctype": "WhatsApp Message",
                    "attached_to_name": message_doc_name,
                    "content": content,
                    "attached_to_field": "attach"
                }).insert(ignore_permissions=True)

                frappe.db.set_value("WhatsApp Message", message_doc_name, "attach", file_doc.file_url)
                frappe.db.commit()
                
    except Exception as e:
        frappe.log_error(f"Media download failed for {message_doc_name}: {str(e)}", "WhatsApp Media Error")


def get_extension_from_mime(mime_type):
    """Get file extension from MIME type."""
    if not mime_type:
        return "bin"
    
    extensions = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "video/mp4": "mp4",
        "video/3gpp": "3gp",
        "audio/aac": "aac",
        "audio/mp4": "m4a",
        "audio/mpeg": "mp3",
        "audio/ogg": "ogg",
        "application/pdf": "pdf",
        "application/vnd.ms-excel": "xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx"
    }
    
    return extensions.get(mime_type, mime_type.split('/')[-1] if '/' in mime_type else "bin")


def should_compress(file_size_bytes):
    """Check if image should be compressed based on size."""
    # Compress if larger than 500KB
    return file_size_bytes > 500 * 1024


def compress_image(content, mime_type, max_size=(1920, 1920), quality=85):
    """
    Compress image while maintaining reasonable quality.
    
    Args:
        content: Raw image bytes
        mime_type: Original MIME type
        max_size: Maximum dimensions (width, height)
        quality: JPEG quality (0-100)
    
    Returns:
        Tuple of (compressed_content, extension)
    """
    try:
        img = Image.open(BytesIO(content))
        
        # Convert to RGB if necessary (for PNG with transparency)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Resize if larger than max dimensions
        if img.width > max_size[0] or img.height > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save to buffer
        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        
        return output.getvalue(), 'jpg'
        
    except Exception as e:
        frappe.log_error(f"Image compression failed: {e}", "WhatsApp Media")
        # Return original if compression fails
        return content, get_extension_from_mime(mime_type)


def generate_thumbnail(content, size=(200, 200)):
    """Generate thumbnail for image preview."""
    try:
        img = Image.open(BytesIO(content))
        
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        output = BytesIO()
        img.save(output, format='JPEG', quality=70)
        
        return output.getvalue()
        
    except Exception:
        return None
