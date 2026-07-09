# Known attribute sources used across the platform. The event `Attribute`
# field is an object keyed by these sources, each holding a list of attributes.
SOURCES = ["AWARE4BC", "RISK4BC", "SOAR4BC", "SOAR4BC_RESULT"]


def _iter_source_attrs(attribute_field):
    """Yield (source, attribute) pairs.

    Supports both the source-keyed dict structure used by the platform
    (``{"AWARE4BC": [...], "RISK4BC": [...], ...}``) and a legacy flat
    list of attributes (attributed to AWARE4BC).
    """
    if isinstance(attribute_field, dict):
        for source, attrs in attribute_field.items():
            if isinstance(attrs, list):
                for attr in attrs:
                    yield source, attr
    elif isinstance(attribute_field, list):
        for attr in attribute_field:
            yield "AWARE4BC", attr


def aggregate(events):
    if len(events) == 0:
        return None

    # Date / analysis: keep the first event's values as a baseline.
    date = events[0].get("date")
    analysis = events[0].get("analysis")
    email = ""

    # Info: combine the source events' descriptions.
    info_parts = [e.get("info") for e in events if e.get("info")]
    info = (
        "Aggregated event ({} source events): {}".format(len(events), " | ".join(info_parts))
        if info_parts
        else "Aggregated event"
    )

    # Threat level: keep the most severe across events (1=High is the most
    # severe; 4=Undefined is ignored when other levels are present).
    levels = []
    for e in events:
        try:
            lvl = int(e.get("threat_level_id"))
        except (TypeError, ValueError):
            continue
        if lvl in (1, 2, 3):
            levels.append(lvl)
    threat_level_id = str(min(levels)) if levels else "4"

    # Aggregate & de-duplicate attributes, preserving the source-keyed
    # structure the frontend expects.
    aggregated = {src: [] for src in SOURCES}
    seen = set()
    for event in events:
        for source, attribute in _iter_source_attrs(event.get("Attribute", {})):
            if not isinstance(attribute, dict):
                continue
            key = (source, attribute.get("category"), attribute.get("type"), attribute.get("value"))
            if key in seen:
                continue
            seen.add(key)
            aggregated.setdefault(source, []).append(attribute)

    # Create new event
    new_event = {
        "date": date,
        "info": info,
        "analysis": analysis,
        "threat_level_id": threat_level_id,
        "org_id": '1',                  # Default value
        "orgc_id": '1',                 # Default value
        "distribution": 0,              # Default value
        "published": False,             # Default value
        "disable_correlation": False,   # Default value
        "proposal_email_lock": False,   # Default value
        "Attribute": aggregated,
        "email": email,
    }

    return new_event
