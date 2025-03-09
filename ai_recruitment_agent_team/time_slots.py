import json
import re
from datetime import datetime, timedelta, timezone
import pytz
from collections import defaultdict
import requests
import os

with open('api_key.txt') as f:
    api_key = f.read().strip()

# Map of common timezone names/abbreviations to IANA timezone names
TIMEZONE_MAPPING = {
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "IST": "Asia/Kolkata",
    "CET": "Europe/Berlin",
    "CEST": "Europe/Berlin",
    "GMT": "Etc/GMT",
    "UTC": "Etc/UTC",
    "BST": "Europe/London",
    "JST": "Asia/Tokyo",
    "AEDT": "Australia/Sydney",
    "AEST": "Australia/Sydney",
    "New York": "America/New_York",
    "India": "Asia/Kolkata",
    "Berlin": "Europe/Berlin",
    "London": "Europe/London",
    "Tokyo": "Asia/Tokyo",
    "Sydney": "Australia/Sydney",
    "US/Eastern": "America/New_York",
    "US/Central": "America/Chicago",
    "US/Mountain": "America/Denver",
    "US/Pacific": "America/Los_Angeles",
    "US/Hawaii": "Pacific/Honolulu",
    "US/Alaska": "America/Anchorage",
    "Europe/Paris": "Europe/Paris",
    "Europe/Rome": "Europe/Rome",
    "Europe/Madrid": "Europe/Madrid",
    "Asia/Singapore": "Asia/Singapore",
    "Asia/Hong_Kong": "Asia/Hong_Kong",
    "Asia/Dubai": "Asia/Dubai",
}

def get_timezone(timezone_str):
    """Convert timezone string to pytz timezone object."""
    if not timezone_str:
        return pytz.UTC  # Default to UTC
    
    # Try direct mapping
    tz_name = TIMEZONE_MAPPING.get(timezone_str)
    if tz_name:
        return pytz.timezone(tz_name)
    
    # Try as IANA timezone name
    try:
        return pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        # If we can't determine timezone, default to UTC
        print(f"Unknown timezone: {timezone_str}, defaulting to UTC")
        return pytz.UTC

def parse_availability_with_claude(availability_text, attendee_timezone=None):
    """Use Claude API to parse availability text into structured format."""
    #api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    prompt = f"""
    Parse the following availability text: "{availability_text}"
    
    The attendee's timezone is: {attendee_timezone if attendee_timezone else "Not specified (assume local time)"}
    
    Return a JSON object with the following structure:
    ```json
    {{
        "days": ["monday", "tuesday", ...],  // List of days the person is available
        "start_time": {{"hour": 14, "minute": 0}},  // Start time in 24-hour format
        "end_time": {{"hour": 17, "minute": 0}}  // End time in 24-hour format
    }}
    ```
    
    For "working days" or "weekdays", include Monday through Friday.
    Convert all times to 24-hour format (e.g., 2 pm = 14:00).
    """
    
    payload = {
        "model": "claude-3-7-sonnet-20250219",
        "max_tokens": 1000,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=payload
    )
    
    if response.status_code != 200:
        raise Exception(f"API request failed: {response.text}")
    
    # Extract JSON from response
    response_data = response.json()
    content = response_data["content"][0]["text"]
    
    # Extract JSON object from content
    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
    if not json_match:
        json_match = re.search(r"({[\s\S]*})", content)
        if not json_match:
            raise Exception("Failed to extract JSON from API response")
    
    parsed_data = json.loads(json_match.group(1))
    
    # Convert to our internal format
    availability = []
    days_of_week = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 
        'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
    }
    
    for day in parsed_data["days"]:
        day_code = days_of_week.get(day.lower(), -1)
        if day_code != -1:
            start_time = (parsed_data["start_time"]["hour"], parsed_data["start_time"]["minute"])
            end_time = (parsed_data["end_time"]["hour"], parsed_data["end_time"]["minute"])
            availability.append((day_code, start_time, end_time))
    
    return availability

def parse_availability_fallback(availability_text):
    """Parse availability text to determine available time slots (fallback method)."""
    availability = []
    
    # Common patterns
    days_of_week = {
        'monday': 0, 'mon': 0, 
        'tuesday': 1, 'tue': 1, 'tues': 1,
        'wednesday': 2, 'wed': 2, 'weds': 2,
        'thursday': 3, 'thu': 3, 'thurs': 3,
        'friday': 4, 'fri': 4,
        'saturday': 5, 'sat': 5,
        'sunday': 6, 'sun': 6
    }
    
    # Extract working days pattern
    working_days_pattern = re.search(r'(every|all)\s+working\s+day', availability_text.lower())
    if working_days_pattern:
        # Working days are Monday-Friday
        days = [0, 1, 2, 3, 4]
    else:
        # Extract specific days
        days = []
        for day, code in days_of_week.items():
            if re.search(fr'\b{day}s?\b', availability_text.lower()):
                days.append(code)
    
    # Extract time range
    time_pattern = re.search(r'(\d+)(?::(\d+))?\s*(am|pm)\s*to\s*(\d+)(?::(\d+))?\s*(am|pm)', availability_text.lower())
    if time_pattern:
        start_hour = int(time_pattern.group(1))
        start_minute = int(time_pattern.group(2)) if time_pattern.group(2) else 0
        start_ampm = time_pattern.group(3)
        
        end_hour = int(time_pattern.group(4))
        end_minute = int(time_pattern.group(5)) if time_pattern.group(5) else 0
        end_ampm = time_pattern.group(6)
        
        # Convert to 24-hour format
        if start_ampm == 'pm' and start_hour < 12:
            start_hour += 12
        if start_ampm == 'am' and start_hour == 12:
            start_hour = 0
            
        if end_ampm == 'pm' and end_hour < 12:
            end_hour += 12
        if end_ampm == 'am' and end_hour == 12:
            end_hour = 0
        
        start_time = (start_hour, start_minute)
        end_time = (end_hour, end_minute)
        
        # Create availability for each day
        for day in days:
            availability.append((day, start_time, end_time))
    
    return availability

def convert_to_target_timezone(day_of_week, start_time, end_time, source_tz, target_tz):
    """Convert time from source timezone to target timezone, accounting for day changes."""
    # Create a datetime object for next occurrence of the day of week
    now = datetime.now()
    days_ahead = day_of_week - now.weekday()
    if days_ahead < 0:  # Target day already happened this week
        days_ahead += 7
    
    # Create source datetime objects
    source_date = now.date() + timedelta(days=days_ahead)
    source_start_dt = datetime.combine(source_date, datetime.min.time().replace(
        hour=start_time[0], minute=start_time[1]
    ))
    source_end_dt = datetime.combine(source_date, datetime.min.time().replace(
        hour=end_time[0], minute=end_time[1]
    ))
    
    # Localize to source timezone
    source_tz = get_timezone(source_tz)
    source_start_dt = source_tz.localize(source_start_dt)
    source_end_dt = source_tz.localize(source_end_dt)
    
    # Convert to target timezone
    target_tz = get_timezone(target_tz)
    target_start_dt = source_start_dt.astimezone(target_tz)
    target_end_dt = source_end_dt.astimezone(target_tz)
    
    # Extract day, hour, and minute
    target_day = target_start_dt.weekday()
    target_start_time = (target_start_dt.hour, target_start_dt.minute)
    target_end_time = (target_end_dt.hour, target_end_dt.minute)
    
    # Handle day change
    if target_start_dt.date() != target_end_dt.date():
        # If time spans midnight, return two separate slots
        return [
            (target_day, target_start_time, (23, 59)),
            ((target_day + 1) % 7, (0, 0), target_end_time)
        ]
    
    return [(target_day, target_start_time, target_end_time)]

def parse_teams_calendar(calendar_data, attendee_timezone=None, target_timezone="UTC"):
    """Parse Teams calendar data to determine available time slots."""
    # For this example, assuming a simplified format where calendar_data is a list of
    # {'day': 0-6, 'start': (hour, minute), 'end': (hour, minute)} for busy slots
    busy_slots = []
    
    # Process and convert timezone for each busy slot
    for slot in calendar_data:
        if attendee_timezone and target_timezone:
            converted_slots = convert_to_target_timezone(
                slot['day'], slot['start'], slot['end'], 
                attendee_timezone, target_timezone
            )
            for conv_day, conv_start, conv_end in converted_slots:
                busy_slots.append({
                    'day': conv_day,
                    'start': conv_start,
                    'end': conv_end
                })
        else:
            busy_slots.append(slot)
    
    # Create availability as the inverse of busy slots (simplified)
    availability = []
    for day in range(7):  # 0-6 for Monday-Sunday
        day_busy = [slot for slot in busy_slots if slot['day'] == day]
        
        # Default working hours (9am to 5pm)
        work_start = (9, 0)
        work_end = (17, 0)
        
        # Find available slots between busy meetings
        if not day_busy:
            # If no meetings, entire work day is available
            availability.append((day, work_start, work_end))
        else:
            # Sort busy slots by start time
            day_busy.sort(key=lambda x: x['start'])
            
            # Check for availability at the start of the day
            if day_busy[0]['start'] > work_start:
                availability.append((day, work_start, day_busy[0]['start']))
            
            # Check for gaps between meetings
            for i in range(len(day_busy) - 1):
                if day_busy[i]['end'] < day_busy[i + 1]['start']:
                    availability.append((day, day_busy[i]['end'], day_busy[i + 1]['start']))
            
            # Check for availability at the end of the day
            if day_busy[-1]['end'] < work_end:
                availability.append((day, day_busy[-1]['end'], work_end))
    
    return availability

def get_date_range(start_date, end_date):
    """Generate a list of dates between start_date and end_date."""
    date_range = []
    current_date = start_date
    while current_date <= end_date:
        date_range.append(current_date)
        current_date += timedelta(days=1)
    return date_range

def find_available_slots(attendees, date_range, target_timezone="UTC", duration_minutes=60):
    """Find time slots where all attendees are available."""
    all_availability = []
    
    for date in date_range:
        # Get day of week (0-6, where 0 is Monday)
        day_of_week = date.weekday()
        
        # Check each attendee's availability for this day
        day_slots = defaultdict(int)  # Count of attendees available for each time slot
        
        for attendee in attendees:
            # Combine availability from text and calendar
            combined_availability = []
            
            attendee_timezone = attendee.get('timezone')
            
            if 'availability_text' in attendee and attendee['availability_text']:
                try:
                    # Try to use Claude API for parsing
                    text_availability = parse_availability_with_claude(
                        attendee['availability_text'], attendee_timezone
                    )
                except Exception as e:
                    print(f"Claude API error: {e}. Using fallback parser.")
                    # Fallback to regex-based parsing
                    text_availability = parse_availability_fallback(attendee['availability_text'])
                
                # Convert timezone if needed
                if attendee_timezone and target_timezone:
                    converted_availability = []
                    for avail_day, start_time, end_time in text_availability:
                        converted_slots = convert_to_target_timezone(
                            avail_day, start_time, end_time, 
                            attendee_timezone, target_timezone
                        )
                        converted_availability.extend(converted_slots)
                    combined_availability.extend(converted_availability)
                else:
                    combined_availability.extend(text_availability)
            
            if 'teams_calendar' in attendee and attendee['teams_calendar']:
                calendar_availability = parse_teams_calendar(
                    attendee['teams_calendar'], 
                    attendee_timezone, 
                    target_timezone
                )
                combined_availability.extend(calendar_availability)
            
            # If no availability info is provided, assume standard work hours in their timezone
            if not combined_availability:
                print(f"No availability info for {attendee.get('name', 'an attendee')}. Assuming standard work hours.")
                # Standard work hours: Mon-Fri, 9am-5pm
                for day in range(5):  # Monday to Friday
                    if attendee_timezone and target_timezone:
                        converted_slots = convert_to_target_timezone(
                            day, (9, 0), (17, 0), 
                            attendee_timezone, target_timezone
                        )
                        combined_availability.extend(converted_slots)
                    else:
                        combined_availability.append((day, (9, 0), (17, 0)))
            
            # Check if attendee is available on this day
            for avail_day, start_time, end_time in combined_availability:
                if avail_day == day_of_week:
                    # Convert to minutes for easier calculation
                    start_minutes = start_time[0] * 60 + start_time[1]
                    end_minutes = end_time[0] * 60 + end_time[1]
                    
                    # Check each potential meeting slot (30-minute increments)
                    for slot_start in range(start_minutes, end_minutes - duration_minutes + 1, 30):
                        slot_key = (date, slot_start)
                        day_slots[slot_key] += 1
        
        # Add slots where all attendees are available
        for slot_key, count in day_slots.items():
            if count == len(attendees):
                date, start_minutes = slot_key
                all_availability.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'start_time': f"{start_minutes // 60:02d}:{start_minutes % 60:02d}",
                    'end_time': f"{(start_minutes + duration_minutes) // 60:02d}:{(start_minutes + duration_minutes) % 60:02d}",
                    'attendees': len(attendees),
                    'timezone': target_timezone
                })
    
    return all_availability

def analyze_meeting_preferences_with_claude(attendees_info, target_timezone="UTC"):
    """Use Claude API to analyze meeting preferences from attendee information."""
    #api_key = os.environ.get("ANTHROPIC_API_KEY")
    

    if not api_key:
        # Skip this step if no API key is available
        return None
    
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    # Extract relevant information for analysis
    attendee_details = []
    for attendee in attendees_info:
        detail = {
            "name": attendee.get('name', 'Unknown'),
            "timezone": attendee.get('timezone', 'Unknown')
        }
        
        if 'availability_text' in attendee:
            detail["availability_text"] = attendee['availability_text']
        
        attendee_details.append(detail)
    
    if not attendee_details:
        return None
    
    prompt = f"""
    Analyze the following attendee information for a meeting:
    {json.dumps(attendee_details, indent=2)}
    
    Target timezone for the meeting: {target_timezone}
    
    Based on this information, identify:
    1. Optimal time ranges for meetings considering timezone differences
    2. Best days of the week
    3. Any notable constraints or preferences
    
    Return your analysis as a JSON object with the following structure:
    ```json
    {{
        "preferred_time_ranges": [
            {{"start": {{"hour": 10, "minute": 0}}, "end": {{"hour": 12, "minute": 0}}}},
            {{"start": {{"hour": 14, "minute": 0}}, "end": {{"hour": 16, "minute": 0}}}}
        ],
        "preferred_days": ["monday", "tuesday", ...],
        "notes": "Additional observations and recommendations based on timezone differences..."
    }}
    ```
    
    Consider timezone overlap for international attendees when determining optimal meeting times.
    All times should be in the target timezone ({target_timezone}).
    """
    
    payload = {
        "model": "claude-3-7-sonnet-20250219",
        "max_tokens": 1000,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            return None
        
        # Extract JSON from response
        response_data = response.json()
        content = response_data["content"][0]["text"]
        
        # Extract JSON object from content
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if not json_match:
            json_match = re.search(r"({[\s\S]*})", content)
            if not json_match:
                return None
        
        return json.loads(json_match.group(1))
    
    except Exception as e:
        print(f"Error analyzing preferences: {e}")
        return None

def score_time_slot(slot, preferred_times=None, preferred_days=None):
    """Score a time slot based on various factors."""
    # Default scoring parameters
    if preferred_times is None:
        preferred_times = [
            ((10, 0), (12, 0)),  # Morning: 10am-12pm
            ((14, 0), (16, 0))   # Afternoon: 2pm-4pm
        ]
    
    if preferred_days is None:
        preferred_days = [0, 1, 2, 3, 4]  # Monday to Friday
    
    score = 0
    
    # Parse date and time
    date = datetime.strptime(slot['date'], '%Y-%m-%d')
    start_hour, start_minute = map(int, slot['start_time'].split(':'))
    
    # Prefer weekdays (Monday to Friday)
    if date.weekday() < 5:
        score += 10
    
    # Avoid early morning and late afternoon
    slot_time = start_hour + start_minute / 60
    if slot_time < 8:  # Before 8am
        score -= 20
    elif slot_time > 16:  # After 4pm
        score -= 10
    
    # Prefer preferred time ranges
    for start, end in preferred_times:
        preferred_start = start[0] + start[1] / 60
        preferred_end = end[0] + end[1] / 60
        if preferred_start <= slot_time <= preferred_end:
            score += 15
    
    # Prefer preferred days
    if date.weekday() in preferred_days:
        score += 5
    
    # Prefer mid-week days (Tuesday, Wednesday, Thursday)
    if 1 <= date.weekday() <= 3:
        score += 3
    
    return score

def convert_claude_preferred_times(claude_preferred_times):
    """Convert Claude API time range forme_ranges(clauat to internal format."""
    converted = []
    for time_range in claude_preferred_times:
        start = (time_range["start"]["hour"], time_range["start"]["minute"])
        end = (time_range["end"]["hour"], time_range["end"]["minute"])
        converted.append((start, end))
    return converted

def convert_claude_preferred_days(claude_preferred_days):
    """Convert day names to day codes (0=Monday, 6=Sunday)."""
    days_of_week = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 
        'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
    }
    return [days_of_week.get(day.lower(), -1) for day in claude_preferred_days if day.lower() in days_of_week]

def find_best_meeting_times(input_data, meeting_duration=60):
    """Find the best meeting times based on attendee availability."""
    attendees = input_data['attendees']
    start_date = datetime.strptime(input_data['date_range']['start'], '%Y-%m-%d')
    end_date = datetime.strptime(input_data['date_range']['end'], '%Y-%m-%d')
    target_timezone = input_data.get('target_timezone', "UTC")
    
    date_range = get_date_range(start_date, end_date)
    
    # Use Claude to analyze preferences (optional)
    preferences = analyze_meeting_preferences_with_claude(attendees, target_timezone)
    preferred_times = None
    preferred_days = None
    
    if preferences:
        try:
            preferred_times = convert_claude_preferred_times(preferences.get("preferred_time_ranges", []))
            preferred_days = convert_claude_preferred_days(preferences.get("preferred_days", []))
        except Exception as e:
            print(f"Error processing preferences: {e}")
    
    # Get all available slots
    available_slots = find_available_slots(attendees, date_range, target_timezone, meeting_duration)
    
    # Score and sort slots
    scored_slots = [(slot, score_time_slot(slot, preferred_times, preferred_days)) for slot in available_slots]
    scored_slots.sort(key=lambda x: x[1], reverse=True)
    
    # Take top 3 slots
    best_slots = [slot for slot, score in scored_slots[:3]] if scored_slots else []
    
    result = {
        'best_meeting_times': best_slots,
        'meeting_duration_minutes': meeting_duration,
        'timezone': target_timezone
    }
    
    # Include analysis notes if available
    if preferences and "notes" in preferences:
        result["analysis_notes"] = preferences["notes"]
    
    return result

# Example usage
if __name__ == "__main__":
    # Sample input with timezone information
    sample_input = {
        "attendees": [
            {
                "name": "John Doe",
                "availability_text": "every working day 2 pm to 5 pm",
                #"timezone": "America/New_York"  # EST
                "timezone": "Asia/Kolkata",  # India

            },
            {
                "name": "Jane Smith",
                "availability_text": "Mondays and Tuesdays between 8 am to 3 pm",
                "timezone": "Asia/Kolkata",  # India
                "teams_calendar": [
                    {"day": 0, "start": (10, 0), "end": (11, 0)},  # Monday 10-11am meeting
                    {"day": 1, "start": (14, 0), "end": (15, 0)}   # Tuesday 2-3pm meeting
                ]
            },
            {
                "name": "Bob Johnson",
                #"timezone": "Europe/Berlin",  # Berlin
                "timezone": "Asia/Kolkata",  # India
                "teams_calendar": [
                    {"day": 0, "start": (9, 0), "end": (10, 30)},  # Monday 9-10:30am meeting
                    {"day": 0, "start": (13, 0), "end": (14, 0)},  # Monday 1-2pm meeting
                    {"day": 2, "start": (11, 0), "end": (12, 0)}   # Wednesday 11am-12pm meeting
                ]
            }
        ],
        "date_range": {
            "start": "2025-03-01",
            "end": "2025-03-07"
        },
        "target_timezone": "UTC"  # All times will be converted to this timezone
    }
    
    result = find_best_meeting_times(sample_input)
    print(json.dumps(result, indent=2))