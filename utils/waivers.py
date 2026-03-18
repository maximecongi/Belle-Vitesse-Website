"""
Backward compatibility wrapper for waiver utilities.
Most logic has moved to document_utils.py and waiver_signatures.py.
"""


# the process_pilot_waiver_signature and process_production_waiver_signature
# are now handled in services/shared/waiver_signatures.py.
# If any old code still calls them, they should be redirected there.


def process_pilot_waiver_signature(waiver_id):
    from services.shared.waiver_signatures import process_waiver_signature
    return process_waiver_signature("pilot", waiver_id)


def process_production_waiver_signature(waiver_id):
    from services.shared.waiver_signatures import process_waiver_signature
    return process_waiver_signature("production", waiver_id)
