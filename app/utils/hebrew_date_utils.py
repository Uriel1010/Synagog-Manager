# file: app/utils/hebrew_date_utils.py (Using Correct Class Names)
from datetime import datetime
# Corrected imports based on dir(hdate) output:
from hdate import HebrewDate, Location, Zmanim # Use HebrewDate instead of HDate

# Define a default location (adjust as needed)
# Doing this once avoids recreating it in both functions
DEFAULT_LOCATION = Location(latitude=31.77, longitude=35.21, timezone="Asia/Jerusalem", name="Jerusalem")

def get_hebrew_date_string(gregorian_dt: datetime):
    """Takes a datetime object and returns a formatted Hebrew date string using hdate."""
    try:
        # Instantiate HebrewDate directly from the Python datetime object
        # Location might not be strictly necessary for just the date string,
        # but providing it is safer if underlying methods depend on it.
        hd = HebrewDate(gregorian_dt, location=DEFAULT_LOCATION)
        # Format the Hebrew date
        return hd.hebrew_date_str(hebrew=False) # Set hebrew=True for Hebrew month names if desired
    except Exception as e:
        print(f"Error getting Hebrew date with hdate: {e}")
        return "N/A"

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