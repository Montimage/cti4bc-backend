from datetime import datetime
import ipaddress
import logging
from cryptography.fernet import Fernet
import base64
from dateutil import parser


_FERNET = None

def _configure(crypto_key_path=None):
    """
    Configure the anonymization module.
    """
    global _FERNET
    # Configure encryption
    try:
        with open(crypto_key_path, 'rb') as key_file:
            key = key_file.read()
        _FERNET = Fernet(key)
    except(FileNotFoundError, RuntimeError) as e:
        logging.error(f"Failed to configure anonymization module: {e}")

def generelize_date(event):
    original_date = event.get("date", {}).get("value")
    format_output = event.get("date", {}).get("action")

    if not original_date:
        return event
    
    try:
        dt = parser.parse(original_date)
        formated_value = dt.strftime(format_output)
        event["date"] = complete_date(formated_value) # Update the complete date field 
    except Exception as e:
        logging.error(f"Error parsing date: {e}")
        return event
    
    # Add attribute to indicate that the date was anonymized
    attribute = {
                'category': 'Other',
                'type': 'text',
                'value': formated_value,
                'to_ids': False,
                'comment': 'Generalized date',
            }
    event["Attribute"]["AWARE4BC"].append(attribute)
    return event

def complete_date(generalized_date):
    date_parts = generalized_date.split('-')
    if len(date_parts) == 1:
        return f"{generalized_date}-01-01" # Append default month and day
    elif len(date_parts) == 2:
        return f"{generalized_date}-01"  # Append default day
    else:
        return generalized_date

def mask_ip(ip, subnet_mask=24):
    try:
        # Convert the IP address to a network with the given subnet mask
        network = ipaddress.ip_network(f"{ip}/{subnet_mask}", strict=False)
        # Return the network in CIDR notation
        return str(network)
    except ValueError as e:
        print(f"Error: {e}")
        return ip


def process_attributes(attributes):
    """
    Process attributes for anonymization (simplified - no encryption)
    """
    processed_attributes = []
    
    for attribute in attributes:        
        # Get the action (what to do with this attribute)
        action = attribute.get("action", {})
        action_type = action.get("type", None)
        action_option = action.get("option", None)
        
        value = attribute.get("value", "")
        
        if action_type == "bfv":
            new_value = str(value)  # Simplified: just return the value as string
            attribute.setdefault("Tag", []).append({"name": f"bfv-{attribute['category']}-{attribute['type']}"})
            attribute["type"] = "anonymised"
            attribute["category"] = "Other" 
        elif action_type == "ckks":
            new_value = str(value)
            attribute.setdefault("Tag", []).append({"name": f"encrypted-ckks-{attribute['type']}"})
            attribute["type"] = "other"

        elif action_type == "encrypt":
            new_value = encrypt_text(value)
            attribute.setdefault("Tag", []).append({"name": f"encrypted-{attribute['category']}-{attribute['type']}"})
            attribute["type"] = "anonymised"
            attribute["category"] = "Other"

        elif action_type == "ipmask":
            if action_option == "none" or action_option is None:
                action_option = 24
            attribute.setdefault("Tag", []).append({"name": f"ipmask-{attribute['category']}-{attribute['type']}"})
            new_value = mask_ip(value, action_option)
        else:
            new_value = value

        attribute["value"] = new_value
        attribute.pop("action", None)
        processed_attributes.append(attribute)
    
    return processed_attributes

def encrypt_text(value):
    "Encrypt text using the cryptography library"
    if _FERNET is None:
        logging.error("Encryption attempted before _FERNET was configured.")
        return value

    token = None
    try:
        value = value.encode()
        token = _FERNET.encrypt(value)
        to_string = base64.b64encode(token).decode()
    except TypeError as e:
        logging.error(e)
    return to_string
