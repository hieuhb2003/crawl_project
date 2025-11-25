import os
import re

def sanitize_filename(name):
    """
    Sanitizes a string to be safe for use as a filename.
    """
    name = re.sub(r'[\\/*?:"<>|]', '_', name)
    name = name.strip().strip('.')
    return name[:200]

def ensure_dir(directory):
    """
    Ensures that a directory exists.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)

def save_article(output_dir, metadata, content):
    """
    Saves article content and metadata.
    Structure: output_dir/Title.txt
    """
    ensure_dir(output_dir)
    
    title = metadata.get('title', 'Untitled')
    date = metadata.get('date', 'Unknown_Date')
    url = metadata.get('url', 'N/A')
    
    filename = f"{sanitize_filename(title)}.txt"
    file_path = os.path.join(output_dir, filename)
    
    # Avoid overwriting if possible, or append ID if available
    # For now, just save.
    
    file_content = f"Title: {title}\n"
    file_content += f"Date: {date}\n"
    file_content += f"URL: {url}\n"
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
