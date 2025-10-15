import requests
import json
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse


class GoogleFormsService:
    """Service to import Google Forms data via Google Apps Script API"""
    
    # URL of your deployed Google Apps Script Web App
    # TODO: Replace with the actual URL of your deployed Web App
    APPS_SCRIPT_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbw6H4_lPcl7XLkzLJ6zBj-abGWIUb94ravezu7Amd2FIKLqE2oQNYIH4B9FwpD_rdzh/exec"
    
    @staticmethod
    def extract_form_id(url: str) -> Optional[str]:
        """Extract form ID from Google Forms URL"""
        try:
            patterns = [
                r'/forms/d/([a-zA-Z0-9-_]+)',
                r'formResponse\?.*entry\.([0-9]+)',
                r'viewform\?.*id=([a-zA-Z0-9-_]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            
            parsed = urlparse(url)
            path_parts = parsed.path.split('/')
            if 'forms' in path_parts and 'd' in path_parts:
                idx = path_parts.index('d')
                if idx + 1 < len(path_parts):
                    return path_parts[idx + 1]
                    
            return None
        except Exception:
            return None

    @staticmethod
    def import_from_url(url: str) -> Dict[str, Any]:
        """
        Import a Google Form from URL via Google Apps Script Web App
        """
        try:
            # Validate URL format first
            if not url or not isinstance(url, str):
                raise Exception("URL must be a non-empty string")
            
            # Check if it's a Google Forms URL
            if 'docs.google.com/forms' not in url:
                raise Exception("URL must be a Google Forms URL (docs.google.com/forms)")
            
            # Extract form ID to validate URL format
            form_id = GoogleFormsService.extract_form_id(url)
            if not form_id:
                raise Exception("Invalid Google Forms URL format. Please provide a valid Google Forms URL.")
            
            # Call Google Apps Script Web App
            response = requests.post(
                GoogleFormsService.APPS_SCRIPT_WEB_APP_URL,
                json={"formUrl": url},
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code != 200:
                raise Exception(f"Apps Script Web App returned status {response.status_code}: {response.text}")
            
            result = response.json()
            
            if 'error' in result:
                raise Exception(f"Apps Script error: {result['error']}")
            
            return result
            
        except requests.RequestException as e:
            raise Exception(f"Network error calling Apps Script: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response from Apps Script: {str(e)}")
        except Exception as e:
            raise Exception(f"Error importing form from URL: {str(e)}")

    @staticmethod
    def transform_apps_script_json_to_internal_fields(apps_script_json: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Transform Apps Script JSON format to internal form fields format
        """
        internal_fields = []
        
        if not apps_script_json or "items" not in apps_script_json:
            return []
        
        for item in apps_script_json["items"]:
            # Skip non-question items (section headers, page breaks, etc.)
            item_type = item.get("type", "").upper()
            if item_type in ["SECTION_HEADER", "PAGE_BREAK", "IMAGE", "VIDEO"]:
                continue
            
            # Map Google Forms types to internal types
            field_type = "text"  # Default
            field_options = []
            
            if item_type == "TEXT":
                field_type = "text"
            elif item_type == "PARAGRAPH_TEXT":
                field_type = "textarea"
            elif item_type == "MULTIPLE_CHOICE":
                field_type = "radio"
                field_options = item.get("choices", [])
            elif item_type == "CHECKBOX":
                field_type = "checkbox"
                field_options = item.get("choices", [])
            elif item_type == "LIST":
                field_type = "select"
                field_options = item.get("choices", [])
            elif item_type == "SCALE":
                field_type = "number"
            elif item_type == "DATE":
                field_type = "date"
            elif item_type == "TIME":
                field_type = "time"
            elif item_type == "DATETIME":
                field_type = "datetime"
            elif item_type == "FILE_UPLOAD":
                field_type = "file"
            
            # Generate unique field name from item ID or index
            field_name = f"field_{item.get('id', item.get('index', len(internal_fields)))}"
            
            # Create field object
            field = {
                "name": field_name,
                "label": item.get("title", f"Question {item.get('index', len(internal_fields) + 1)}"),
                "type": field_type,
                "required": item.get("isRequired", False),
                "options": field_options
            }
            
            # Add help text if available
            if item.get("helpText"):
                field["help_text"] = item.get("helpText")
            
            internal_fields.append(field)
        
        return internal_fields

    @staticmethod
    def get_form_creation_data(apps_script_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract form creation data from Apps Script JSON
        """
        metadata = apps_script_json.get("metadata", {})
        
        return {
            "title": metadata.get("title", "Imported Google Form"),
            "description": metadata.get("description", ""),
            "fields": GoogleFormsService.transform_apps_script_json_to_internal_fields(apps_script_json)
        }
