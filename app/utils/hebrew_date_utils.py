# file: app/utils/hebrew_date_utils.py (Using Correct Class Names)
from datetime import datetime
# Corrected imports based on dir(hdate) output:
from hdate import HebrewDate, Location, Zmanim # Use HebrewDate instead of HDate
from convertdate import hebrew

# Define a default location (adjust as needed)
# Doing this once avoids recreating it in both functions
DEFAULT_LOCATION = Location(latitude=31.77, longitude=35.21, timezone="Asia/Jerusalem", name="Jerusalem")

# Hebrew month names
HEBREW_MONTH_NAMES = {
    1:  "ניסן",
    2:  "אייר",
    3:  "סיון",
    4:  "תמוז",
    5:  "אב",
    6:  "אלול",
    7:  "תשרי",
    8:  "חשוון",
    9:  "כסלו",
    10: "טבת",
    11: "שבט",
    12: "אדר",
    13: "אדר ב׳"
}

HEBREW_LETTERS = {
    1: "א", 2: "ב", 3: "ג", 4: "ד", 5: "ה", 6: "ו", 7: "ז", 8: "ח", 9: "ט",
    10: "י", 20: "כ", 30: "ל", 40: "מ", 50: "נ", 60: "ס", 70: "ע", 80: "פ", 90: "צ",
    100: "ק", 200: "ר", 300: "ש", 400: "ת"
}

def num_to_gematria(num):
    if num >= 1000:
        thousands = num // 1000
        rest = num % 1000
        return HEBREW_LETTERS[thousands] + "'" + _convert_gematria(rest)
    return _convert_gematria(num)

def _convert_gematria(num):
    parts = []
    for value in sorted(HEBREW_LETTERS.keys(), reverse=True):
        while num >= value:
            num -= value
            parts.append(HEBREW_LETTERS[value])
    # Handle special cases: 15 = ט״ו, 16 = ט״ז
    if parts == ["י", "ה"]:
        return "ט״ו"
    if parts == ["י", "ו"]:
        return "ט״ז"
    return "".join(parts[:-1]) + "״" + parts[-1] if parts else ""

def get_hebrew_date_string(date: datetime) -> str:
    h_year, h_month, h_day = hebrew.from_gregorian(date.year, date.month, date.day)

    if hebrew.leap(h_year) and h_month == 12:
        month_name = "אדר א׳"
    else:
        month_name = HEBREW_MONTH_NAMES.get(h_month, f"חודש {h_month}")

    day_str = num_to_gematria(h_day)
    year_str = num_to_gematria(h_year % 1000)

    return f"{day_str} {month_name} ה׳{year_str}"


def get_parsha_string(gregorian_dt: datetime):
    """Gets the weekly Parsha for a given Gregorian date (if it's Shabbat) using hdate."""
    try:
        # Instantiate HebrewDate with the location
        hd = HebrewDate(gregorian_dt, location=DEFAULT_LOCATION)

        dow = gregorian_dt.weekday() # Monday is 0, Sunday is 6

        # Check if it's Shabbat (Saturday == 5)
        if dow == 5:
            # Get Parsha info using recommended hdate method
            # Use hebrew=True for Hebrew names if desired
            parsha_str = hd.get_parasha_string(hebrew=False)

            if parsha_str:
                 # The get_parasha_string often combines regular and special parshiot
                return parsha_str

            # If no specific parsha string, check for holidays
            # Use hebrew=True for Hebrew names if desired
            holiday_info = hd.holiday_description(hebrew=False)
            if holiday_info:
                return holiday_info # Return the holiday name

            return "Shabbat (No specific Parsha/Holiday found)" # Fallback

        return None # Not Shabbat
    except Exception as e:
        print(f"Error getting Parsha with hdate: {e}")
        import traceback
        traceback.print_exc()
        return None