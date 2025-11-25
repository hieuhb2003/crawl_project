import os
import re
import json

def sanitize_filename(name):
    """
    Sanitizes a string to be safe for use as a filename.
    Removes or replaces characters that are illegal in filenames.
    """
    # Replace invalid characters with underscores
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    # Remove leading/trailing whitespace and dots
    name = name.strip().strip('.')
    # Truncate if too long (max 255 usually, but let's be safe with 200)
    return name[:200]

def ensure_dir(directory):
    """
    Ensures that a directory exists.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)

def save_document(output_dir, doc_metadata, content):
    """
    Saves the document content and metadata to a file.
    Structure:
    output_dir/
        [Agency]/
            [Type]/
                [Sanitized_Title].txt
    """
    agency = doc_metadata.get('agency', 'Unknown_Agency')
    doc_type = doc_metadata.get('type', 'Unknown_Type')
    title = doc_metadata.get('title', 'Untitled')
    
    # Sanitize directory names
    agency_dir = sanitize_filename(agency)
    type_dir = sanitize_filename(doc_type)
    
    # Create full path
    full_dir_path = os.path.join(output_dir, agency_dir, type_dir)
    ensure_dir(full_dir_path)
    
    # Extract ItemID from URL for uniqueness
    import re
    item_id_match = re.search(r'ItemID=(\d+)', doc_metadata.get('url', ''))
    item_id = item_id_match.group(1) if item_id_match else "unknown_id"

    # Filename: [Title]_[ItemID].txt
    filename = f"{sanitize_filename(title)}_{item_id}.txt"
    file_path = os.path.join(full_dir_path, filename)
    
    # Content to write
    file_content = f"Title: {title}\n"
    file_content += f"Agency: {agency}\n"
    file_content += f"Type: {doc_type}\n"
    file_content += f"Date: {doc_metadata.get('date', 'N/A')}\n"
    file_content += f"Link: {doc_metadata.get('url', 'N/A')}\n"
    file_content += "-" * 40 + "\n\n"
    file_content += content
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)
        print(f"Saved: {file_path}")
        return True
    except Exception as e:
        print(f"Error saving {file_path}: {e}")
        return False
