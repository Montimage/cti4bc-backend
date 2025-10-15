

def aggregate(events):
    if (len(events) == 0):
        return None

    # Aggregate date TODO
    date = events[0].get("date")

    # Aggregate info TODO
    info = events[0].get("info") 

    # Aggregate analysis TODO
    analysis = events[0].get("analysis")

    # Event creator email TODO
    email = ""

    # Aggregate threat level id TODO
    threat_level_id = 4

    # Aggregate attributes
    unique_attributes = []
    seen_attributes = set()

    for event in events:
        for attribute in event.get("Attribute", []):
            attr_tuple = (attribute["category"], attribute["type"], attribute["value"])
            if attr_tuple not in seen_attributes:
                unique_attributes.append(attribute)
                seen_attributes.add(attr_tuple)

    # Create new event
    new_event = {"date": date,
     "info": info,
     "analysis": analysis,
     "threat_level_id": threat_level_id,
     "org_id": '1', # Default value
     "orgc_id": '1', # Default value
     "distribution": 0, # Default value
     "published": False, # Default value
     "disable_correlation": False, # Default value
     "proposal_email_lock": False, # Default value
     "Attribute": unique_attributes,
     "email": email}

    return new_event