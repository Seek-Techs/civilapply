from datetime import date

MAX_APPLICATIONS_PER_DAY = 5

_application_counter = {
    "date": date.today().isoformat(),
    "count": 0
}

def can_apply():
    today = date.today().isoformat()

    if _application_counter["date"] != today:
        _application_counter["date"] = today
        _application_counter["count"] = 0

    return _application_counter["count"] < MAX_APPLICATIONS_PER_DAY


def register_application():
    _application_counter["count"] += 1
