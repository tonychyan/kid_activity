#!/usr/bin/env python3
"""
Kids Activity Locator - Image Extractor

This script extracts kids' activity information (location, date, time) from screenshots
and organizes it in a markdown file ordered by time.
"""

import os
import glob
import re
import shutil
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Dict, List, Tuple, Optional
import json
import calendar

# Add the current directory to the path to ensure we can import from tools
sys.path.append('.')
from tools.llm_api import query_llm

# Define constants
INPUT_DIR = "input"
NEW_INPUT_DIR = os.path.join(INPUT_DIR, "new")  # Directory for new images
OUTPUT_DIR = "output"
OUTPUT_FILE = "activities.md"
JSON_FILE = "activities.json"

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(NEW_INPUT_DIR, exist_ok=True)

def extract_activity_info(image_path: str, save_raw: bool = False) -> List[Dict]:
    """
    Extract activity information from an image using the vision model.
    
    Args:
        image_path (str): Path to the image file
        save_raw (bool): Whether to save the raw LLM response to a file
        
    Returns:
        List[Dict]: List of dictionaries containing extracted information (location, date, time, etc.)
    """
    print(f"Processing image: {image_path}")
    
    prompt = """
    Please analyze this image of a kids' activity announcement and extract the following information in JSON format:
    
    1. Activity name (if available)
    2. Location (full address if possible, including name of venue, street address, city, state, and ZIP code - ZIP code is required, make your best guess if needed)
    3. Date (in YYYY-MM-DD format if possible)
    4. Time (start and end if available, in format like "3:00 PM - 5:00 PM")
    5. Description/Highlight (brief description of the activity, including age range if mentioned)
    6. Additional details (any other important information like cost, registration info, indoor/outdoor, etc.)
    7. Raw date/time (the exact text from the image that describes when the event occurs, like "Sunday, April 13" or "This Friday at 7 PM")
    
    If there are multiple activities shown in the image, please return an array of objects, with each object containing the details for one activity.
    
    If you're uncertain about any information, provide your best guess but include a note about the uncertainty.
    
    For the 'raw_datetime' field, please preserve the exact date and time text as shown in the image, even if you've already formatted it in the date and time fields.
    
    For locations, if the ZIP code is not visible in the image, please try to determine it based on the city and state, or use a reasonable guess for the area. All locations should include a ZIP code.
    
    Respond with a valid JSON object or array. If a field is not available, use null as the value.
    
    Example for a single activity:
    {
        "activity_name": "Soccer Practice",
        "location": "City Park Recreation Center, 123 Park Avenue, City, State, ZIP",
        "date": "2023-10-15",
        "time": "3:00 PM - 5:00 PM",
        "description": "Weekly soccer practice for kids ages 5-7",
        "additional_details": "Bring water and wear appropriate footwear. Cost: $10 per session.",
        "raw_datetime": "Sunday, October 15th from 3-5 PM"
    }
    
    Example for multiple activities:
    [
        {
            "activity_name": "Soccer Practice",
            "location": "City Park Recreation Center, 123 Park Avenue, City, State, ZIP",
            "date": "2023-10-15",
            "time": "3:00 PM - 5:00 PM",
            "description": "Weekly soccer practice for kids ages 5-7",
            "additional_details": "Cost: $10 per session.",
            "raw_datetime": "Sunday, October 15th from 3-5 PM"
        },
        {
            "activity_name": "Swimming Lessons",
            "location": "Community Pool, 456 Main Street, City, State, ZIP",
            "date": "2023-10-16",
            "time": "4:00 PM - 5:30 PM",
            "description": "Swimming lessons for beginners, ages 4-10",
            "additional_details": "Cost: $15 per session.",
            "raw_datetime": "Monday, October 16th at 4:00-5:30 PM"
        }
    ]
    """
    
    # Use vision model to extract information
    try:
        response = query_llm(prompt, provider="openai", image_path=image_path)
        
        # Save raw response if requested
        if save_raw:
            base_name = os.path.basename(image_path)
            file_name = os.path.splitext(base_name)[0]
            raw_dir = os.path.join(OUTPUT_DIR, "raw_responses")
            os.makedirs(raw_dir, exist_ok=True)
            raw_file_path = os.path.join(raw_dir, f"{file_name}_response.json")
            
            try:
                with open(raw_file_path, "w") as f:
                    f.write(response)
                print(f"Saved raw LLM response to {raw_file_path}")
            except Exception as e:
                print(f"Error saving raw response: {e}")
        
        # Extract JSON from response
        try:
            # Try to parse the entire response as JSON first
            try:
                data = json.loads(response)
                
                # Handle both single objects and arrays
                if isinstance(data, dict):
                    # Check if it has an 'activities' field with an array
                    if 'activities' in data and isinstance(data['activities'], list):
                        return data['activities']  # Return the activities array directly
                    else:
                        return [data]  # Convert single object to a list for consistent handling
                elif isinstance(data, list):
                    return data
                else:
                    raise ValueError("Unexpected JSON structure")
                
            except json.JSONDecodeError:
                # If that fails, look for JSON object or array pattern in the response
                json_pattern = re.search(r'(\[.*\]|\{.*\})', response, re.DOTALL)
                if json_pattern:
                    json_str = json_pattern.group(1)
                    data = json.loads(json_str)
                    
                    # Handle both single objects and arrays
                    if isinstance(data, dict):
                        # Check if it has an 'activities' field with an array
                        if 'activities' in data and isinstance(data['activities'], list):
                            return data['activities']  # Return the activities array directly
                        else:
                            return [data]  # Convert single object to a list for consistent handling
                    elif isinstance(data, list):
                        return data
                    else:
                        raise ValueError("Unexpected JSON structure")
                else:
                    raise ValueError("No JSON object or array found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing JSON response for {image_path}: {e}")
            print(f"Response: {response}")
            return [{
                "activity_name": None,
                "location": None,
                "date": None,
                "time": None,
                "description": None,
                "additional_details": None,
                "raw_datetime": None,
                "error": f"Failed to parse response: {str(e)}",
                "source_file": os.path.basename(image_path)
            }]
    
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return [{
            "activity_name": None,
            "location": None,
            "date": None,
            "time": None,
            "description": None,
            "additional_details": None,
            "raw_datetime": None,
            "error": str(e),
            "source_file": os.path.basename(image_path)
        }]

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse date string into datetime object for sorting.
    
    Args:
        date_str (str): Date string to parse
        
    Returns:
        Optional[datetime]: Parsed datetime object or None if parsing fails
    """
    if not date_str:
        return None
    
    # Try various date formats
    date_formats = [
        "%Y-%m-%d",      # 2023-10-15
        "%m/%d/%Y",      # 10/15/2023
        "%m/%d/%y",      # 10/15/23
        "%B %d, %Y",     # October 15, 2023
        "%b %d, %Y",     # Oct 15, 2023
        "%d %B %Y",      # 15 October 2023
        "%d %b %Y",      # 15 Oct 2023
        "%A, %B %d",     # Monday, October 15
        "%A, %b %d",     # Monday, Oct 15
        "%a, %B %d",     # Mon, October 15
        "%a, %b %d",     # Mon, Oct 15
        "%B %d",         # October 15
        "%b %d",         # Oct 15
    ]
    
    # For formats without year, assume current year
    current_year = datetime.now().year
    
    for fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            
            # If the format doesn't include a year, add the current year
            if "%Y" not in fmt and "%y" not in fmt:
                date_obj = date_obj.replace(year=current_year)
                
                # If the date is in the past by more than 6 months, assume it's next year
                if (datetime.now() - date_obj).days > 180:
                    date_obj = date_obj.replace(year=current_year + 1)
                    
            return date_obj
        except ValueError:
            continue
    
    # Try to extract date using regex patterns
    patterns = [
        r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})',  # MM/DD/YYYY or DD/MM/YYYY
        r'(\w+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})',  # Month DD, YYYY
        r'(\d{1,2})(?:st|nd|rd|th)?\s+(\w+),?\s+(\d{4})',  # DD Month YYYY
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 3:
                # Try various interpretations
                try:
                    # MM/DD/YYYY
                    month, day, year = groups
                    if len(year) == 2:
                        year = f"20{year}"
                    return datetime(int(year), int(month), int(day))
                except (ValueError, TypeError):
                    try:
                        # DD/MM/YYYY
                        day, month, year = groups
                        if len(year) == 2:
                            year = f"20{year}"
                        return datetime(int(year), int(month), int(day))
                    except (ValueError, TypeError):
                        try:
                            # Month name formats
                            if groups[0].isalpha():  # Month DD, YYYY
                                month_name, day, year = groups
                                month_dict = {
                                    "jan": 1, "january": 1,
                                    "feb": 2, "february": 2,
                                    "mar": 3, "march": 3,
                                    "apr": 4, "april": 4,
                                    "may": 5, "may": 5,
                                    "jun": 6, "june": 6,
                                    "jul": 7, "july": 7,
                                    "aug": 8, "august": 8,
                                    "sep": 9, "september": 9,
                                    "oct": 10, "october": 10,
                                    "nov": 11, "november": 11,
                                    "dec": 12, "december": 12
                                }
                                month = month_dict.get(month_name.lower()[:3])
                                if month:
                                    return datetime(int(year), month, int(day))
                            elif groups[1].isalpha():  # DD Month YYYY
                                day, month_name, year = groups
                                month_dict = {
                                    "jan": 1, "january": 1,
                                    "feb": 2, "february": 2,
                                    "mar": 3, "march": 3,
                                    "apr": 4, "april": 4,
                                    "may": 5, "may": 5,
                                    "jun": 6, "june": 6,
                                    "jul": 7, "july": 7,
                                    "aug": 8, "august": 8,
                                    "sep": 9, "september": 9,
                                    "oct": 10, "october": 10,
                                    "nov": 11, "november": 11,
                                    "dec": 12, "december": 12
                                }
                                month = month_dict.get(month_name.lower()[:3])
                                if month:
                                    return datetime(int(year), month, int(day))
                        except (ValueError, TypeError):
                            pass
    
    print(f"Warning: Could not parse date: {date_str}")
    return None

def parse_time_range(time_str: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parse time range string to extract start and end times.
    
    Args:
        time_str: String containing time range (e.g., "3:00 PM - 5:00 PM")
        
    Returns:
        Tuple of (start_time, end_time) as datetime objects, or (None, None) if parsing fails
    """
    if not time_str:
        return None, None
    
    # Try to find a time range pattern
    time_range_patterns = [
        r'(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)?\s*[-–—to]+\s*(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)?',  # 3:00 PM - 5:00 PM
        r'(\d{1,2})\s*(am|pm|AM|PM)\s*[-–—to]+\s*(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)?',  # 3 PM - 5:00 PM
        r'(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)?\s*[-–—to]+\s*(\d{1,2})\s*(am|pm|AM|PM)?',  # 3:00 PM - 5 PM
    ]
    
    for pattern in time_range_patterns:
        match = re.search(pattern, time_str)
        if match:
            groups = match.groups()
            
            if len(groups) >= 4:  # We have at least start and end hour
                try:
                    # Parse start time
                    start_hour = int(groups[0])
                    start_minute = int(groups[1]) if groups[1] else 0
                    start_ampm = groups[2].lower() if groups[2] else None
                    
                    # Convert to 24-hour format
                    if start_ampm == 'pm' and start_hour < 12:
                        start_hour += 12
                    elif start_ampm == 'am' and start_hour == 12:
                        start_hour = 0
                    
                    # Parse end time
                    end_idx = 3
                    end_hour = int(groups[end_idx])
                    end_minute = int(groups[end_idx + 1]) if groups[end_idx + 1] and groups[end_idx + 1].isdigit() else 0
                    end_ampm = groups[end_idx + 2].lower() if len(groups) > end_idx + 2 and groups[end_idx + 2] else None
                    
                    # If end_ampm is not specified, use the same as start_ampm
                    if end_ampm is None and start_ampm is not None:
                        end_ampm = start_ampm
                    
                    # Convert to 24-hour format
                    if end_ampm == 'pm' and end_hour < 12:
                        end_hour += 12
                    elif end_ampm == 'am' and end_hour == 12:
                        end_hour = 0
                    
                    # If end time is earlier than start time, assume it's AM/PM confusion
                    if end_hour < start_hour and abs(end_hour - start_hour) < 12:
                        end_hour += 12
                    
                    # Create datetime objects for today with the specified times
                    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    start_time = today.replace(hour=start_hour, minute=start_minute)
                    end_time = today.replace(hour=end_hour, minute=end_minute)
                    
                    return start_time, end_time
                except (ValueError, TypeError, IndexError):
                    pass
    
    # If no range is found, try to find a single time
    time_patterns = [
        r'(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)?',  # 3:00 PM or 15:00
        r'(\d{1,2})\s*(am|pm|AM|PM)',  # 3 PM
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, time_str)
        if match:
            groups = match.groups()
            try:
                hour = int(groups[0])
                minute = int(groups[1]) if groups[1] and groups[1].isdigit() else 0
                ampm = groups[2].lower() if len(groups) > 2 and groups[2] else None
                
                # Convert to 24-hour format
                if ampm == 'pm' and hour < 12:
                    hour += 12
                elif ampm == 'am' and hour == 12:
                    hour = 0
                
                # Create datetime objects
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                time_obj = today.replace(hour=hour, minute=minute)
                
                # For a single time, assume it's a 1-hour event
                return time_obj, time_obj.replace(hour=time_obj.hour + 1)
            except (ValueError, TypeError):
                pass
    
    return None, None

def validate_location(activities: List[Dict]) -> List[Dict]:
    """
    Validate and enhance location data to ensure it includes ZIP code information.
    
    Args:
        activities (List[Dict]): List of activity dictionaries
        
    Returns:
        List[Dict]: Updated list with validated location data
    """
    zip_code_pattern = r'\b\d{5}(?:-\d{4})?\b'  # Basic US ZIP code pattern (5 digits or 5+4)
    
    for activity in activities:
        if not isinstance(activity, dict):
            continue
            
        location = activity.get('location')
        
        # Skip if no location or if location already has a ZIP code
        if not location or not isinstance(location, str):
            continue
            
        # Check if ZIP code already exists
        if re.search(zip_code_pattern, location):
            continue
            
        # If no ZIP code found, try to enhance the location
        activity_name = activity.get('activity_name', '')
        if activity_name is None: activity_name = ''
        
        # First, try to see if we have any other activities at the same location but with ZIP code
        similar_locations = []
        for other_activity in activities:
            if other_activity is activity:  # Skip self
                continue
                
            other_location = other_activity.get('location', '')
            if not other_location or not isinstance(other_location, str):
                continue
                
            # If other location has a ZIP code and contains our location string
            if re.search(zip_code_pattern, other_location) and location in other_location:
                similar_locations.append(other_location)
        
        # If we found a similar location with ZIP code, use that
        if similar_locations:
            activity['location'] = similar_locations[0]
            print(f"Enhanced location: '{location}' -> '{similar_locations[0]}'")
            continue
            
        # If Texas is not mentioned, add it as a reasonable assumption for this dataset
        if "TX" not in location and "Texas" not in location:
            # Keep track of the original for logging purposes
            original_location = location
            
            # Add Texas and a placeholder ZIP code
            # Placeholder approach 1: Add generic Austin area code
            activity['location'] = f"{location}, Austin, TX 78701"
            print(f"Added state/zip to location: '{original_location}' -> '{activity['location']}'")
            
            # Mark this location as uncertain
            activity['location_uncertain'] = True
            
        # If TX is mentioned but no ZIP, add a placeholder ZIP
        elif re.search(r'\b(TX|Texas)\b', location) and not re.search(zip_code_pattern, location):
            original_location = location
            activity['location'] = f"{location} 78701"  # Add generic Austin area code
            print(f"Added zip to location: '{original_location}' -> '{activity['location']}'")
            activity['location_uncertain'] = True
    
    return activities

def generate_markdown(activities: List[Dict]) -> str:
    """
    Generate a markdown file from the extracted activities.
    
    Args:
        activities (List[Dict]): List of activity dictionaries
        
    Returns:
        str: Markdown content
    """
    # Sort activities by date
    def get_activity_date(activity):
        date_obj = parse_date(activity.get("date"))
        return date_obj if date_obj else datetime.max
    
    sorted_activities = sorted(activities, key=get_activity_date)
    
    # Generate markdown
    markdown = "# Kids Activities\n\n"
    
    for activity in sorted_activities:
        activity_name = activity.get("activity_name") or "Unnamed Activity"
        markdown += f"## {activity_name}\n\n"
        
        if activity.get("date"):
            markdown += f"**Date:** {activity['date']}\n\n"
            
        if activity.get("time"):
            markdown += f"**Time:** {activity['time']}\n\n"
            
        if activity.get("location"):
            location_text = activity['location']
            if activity.get('location_uncertain', False):
                location_text += " *(ZIP code estimated)*"
            markdown += f"**Location:** {location_text}\n\n"
            
        if activity.get("description"):
            markdown += f"**Description:** {activity['description']}\n\n"
            
        if activity.get("additional_details"):
            markdown += f"**Additional Details:** {activity['additional_details']}\n\n"
            
        markdown += f"**Source:** {activity.get('source_file', 'Unknown')}\n\n"
        
        markdown += "---\n\n"
    
    return markdown

def sanitize_dates(activities: List[Dict]) -> List[Dict]:
    """
    Sanitize dates in activities to ensure they're not in the past.
    Activities without a year or with dates before the current year will be updated to the current year.
    For activities with null dates, use raw_datetime or other text to infer the most likely date.
    
    Args:
        activities (List[Dict]): List of activity dictionaries
        
    Returns:
        List[Dict]: Updated list with sanitized dates
    """
    from datetime import datetime, timedelta
    import calendar
    
    current_year = 2025  # Hardcoded to 2025 as per requirements
    today = datetime.now()
    
    # Given the seasonal nature of the events, most are likely in April 2025
    default_month = "04"  # April
    default_day = "15"    # Mid-month default
    
    # Helper function to find the next occurrence of a day of the week
    def next_day_of_week(day_name):
        day_name = day_name.lower()
        # Map day names to their corresponding index (0 = Monday, 6 = Sunday)
        days = {
            'monday': 0, 'mon': 0, 'm': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1, 't': 1,
            'wednesday': 2, 'wed': 2, 'w': 2,
            'thursday': 3, 'thu': 3, 'thurs': 3, 'th': 3,
            'friday': 4, 'fri': 4, 'f': 4,
            'saturday': 5, 'sat': 5, 'sa': 5, 's': 5,
            'sunday': 6, 'sun': 6, 'su': 6
        }
        
        if day_name not in days:
            return None
            
        target_day_idx = days[day_name]
        current_day_idx = today.weekday()  # 0 = Monday, 6 = Sunday
        
        # Calculate days until next occurrence
        days_ahead = (target_day_idx - current_day_idx) % 7
        if days_ahead == 0:  # Today
            days_ahead = 7  # Next week
            
        # Return the date of the next occurrence
        next_date = today + timedelta(days=days_ahead)
        return next_date.strftime("%Y-%m-%d")
    
    for activity in activities:
        # Skip invalid activities
        if not isinstance(activity, dict):
            print(f"Warning: Skipping invalid activity (not a dictionary): {activity}")
            continue
            
        date_str = activity.get('date')
        raw_datetime = activity.get('raw_datetime', '')
        
        # Handle None values safely
        if raw_datetime is None:
            raw_datetime = ''
        
        # Case 1: Handle dates with years not equal to current year
        if date_str:
            # Skip if already has the current year
            if str(current_year) in date_str:
                continue
                
            # Try to parse the date
            try:
                # Extract year, month, day components with regex
                year_pattern = r'(\d{4})-(\d{2})-(\d{2})'
                match = re.match(year_pattern, date_str)
                
                if match:
                    year, month, day = match.groups()
                    # If year is not current year, update it
                    if int(year) < current_year:
                        # Create new date string with current year
                        new_date = f"{current_year}-{month}-{day}"
                        activity['date'] = new_date
                        print(f"Sanitized date: {date_str} -> {new_date}")
            except (ValueError, TypeError) as e:
                print(f"Error sanitizing date {date_str}: {e}")
        
        # Case 2: Handle null dates
        else:
            # Get all text fields that might contain date information
            name_str = activity.get('activity_name', '')
            if name_str is None: name_str = ''
            
            time_str = activity.get('time', '')
            if time_str is None: time_str = ''
            
            description_str = activity.get('description', '')
            if description_str is None: description_str = ''
            
            details_str = activity.get('additional_details', '')
            if details_str is None: details_str = ''
            
            # Convert all strings to lowercase for matching
            name_str = name_str.lower() if isinstance(name_str, str) else ''
            time_str = time_str.lower() if isinstance(time_str, str) else ''
            description_str = description_str.lower() if isinstance(description_str, str) else ''
            details_str = details_str.lower() if isinstance(details_str, str) else ''
            raw_datetime = raw_datetime.lower() if isinstance(raw_datetime, str) else ''
            
            # Prioritize raw_datetime if available
            all_text = raw_datetime if raw_datetime else ' '.join([name_str, time_str, description_str, details_str])
            
            # APPROACH 1: Look for day names in the text
            day_pattern = r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thurs|fri|sat|sun)\b'
            match = re.search(day_pattern, all_text, re.IGNORECASE)
            
            if match:
                day_name = match.group(1)
                next_date = next_day_of_week(day_name)
                
                if next_date:
                    activity['date'] = next_date
                    print(f"Added date for {day_name}: {next_date} to activity: {activity.get('activity_name')}")
                    continue  # Skip to next activity
            
            # APPROACH 2: Look for month names with days
            month_day_pattern = r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?\b'
            match = re.search(month_day_pattern, all_text, re.IGNORECASE)
            
            if match:
                month_name, day_num = match.groups()
                month_map = {
                    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                    'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                    'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
                }
                
                month_short = month_name.lower()[:3]
                if month_short in month_map:
                    month_num = month_map[month_short]
                    # Ensure day has leading zero if needed
                    day_num_padded = day_num.zfill(2) if len(day_num) == 1 else day_num
                    specific_date = f"{current_year}-{month_num}-{day_num_padded}"
                    
                    activity['date'] = specific_date
                    print(f"Added date from month+day: {specific_date} to activity: {activity.get('activity_name')}")
                    continue
            
            # APPROACH 3: If we can identify a specific month, just log a warning
            month_pattern = r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b'
            match = re.search(month_pattern, all_text, re.IGNORECASE)
            
            if match:
                month_name = match.group(1)
                month_map = {
                    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                    'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                    'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
                }
                
                month_short = month_name.lower()[:3]
                if month_short in month_map:
                    print(f"Warning: Found month '{month_name}' but no specific day for activity: {activity.get('activity_name')}")
                    continue
    return activities

def main():
    # Set up command line arguments
    parser = argparse.ArgumentParser(description='Extract activity information from images')
    parser.add_argument('--new-only', action='store_true', help='Process only new images from input/new directory')
    parser.add_argument('--sanitize-only', action='store_true', help='Only sanitize dates in existing activities without processing images')
    parser.add_argument('--validate-locations', action='store_true', help='Only validate and enhance locations in existing activities without processing images')
    parser.add_argument('--save-raw', action='store_true', help='Save raw LLM responses to files for later reprocessing')
    parser.add_argument('--from-raw', action='store_true', help='Process activities from saved raw responses instead of calling the LLM')
    args = parser.parse_args()
    
    # Load existing activities if available
    json_output_path = os.path.join(OUTPUT_DIR, JSON_FILE)
    existing_activities = []
    
    if os.path.exists(json_output_path):
        try:
            with open(json_output_path, "r") as f:
                existing_activities = json.load(f)
            print(f"Loaded {len(existing_activities)} existing activities from {json_output_path}")
        except json.JSONDecodeError:
            print(f"Error loading existing activities from {json_output_path}. Starting with empty list.")
    
    # If sanitize-only mode or validate-locations mode, skip image processing
    if args.sanitize_only or args.validate_locations:
        all_activities = existing_activities
        if args.sanitize_only:
            print(f"Sanitize-only mode: Sanitizing dates in {len(all_activities)} existing activities...")
        elif args.validate_locations:
            print(f"Validate-locations mode: Validating locations in {len(all_activities)} existing activities...")
    elif args.from_raw:
        # Process saved raw responses
        raw_dir = os.path.join(OUTPUT_DIR, "raw_responses")
        if not os.path.exists(raw_dir):
            print(f"Error: Raw responses directory not found at {raw_dir}")
            return
            
        new_activities = []
        raw_files = glob.glob(os.path.join(raw_dir, "*.json"))
        
        if not raw_files:
            print(f"No raw response files found in {raw_dir}")
            return
            
        print(f"Found {len(raw_files)} raw response files to process")
        
        for raw_file in raw_files:
            try:
                with open(raw_file, "r") as f:
                    response = f.read()
                    
                # Extract file name (which came from the original image name)
                base_name = os.path.basename(raw_file)
                original_image = base_name.replace("_response.json", "")
                    
                # Try to parse the entire response as JSON
                try:
                    data = json.loads(response)
                    
                    # Handle both single objects and arrays
                    if isinstance(data, dict):
                        if 'activities' in data and isinstance(data['activities'], list):
                            activities = data['activities']
                        else:
                            activities = [data]
                    elif isinstance(data, list):
                        activities = data
                    else:
                        print(f"Unexpected JSON structure in {raw_file}")
                        continue
                        
                    # Add source file for reference to each activity
                    for activity in activities:
                        activity["source_file"] = f"{original_image}.jpg"  # Assume jpg extension
                        new_activities.append(activity)
                        
                except json.JSONDecodeError:
                    # Try to extract JSON from text
                    json_pattern = re.search(r'(\[.*\]|\{.*\})', response, re.DOTALL)
                    if json_pattern:
                        json_str = json_pattern.group(1)
                        try:
                            data = json.loads(json_str)
                            
                            # Handle both single objects and arrays
                            if isinstance(data, dict):
                                if 'activities' in data and isinstance(data['activities'], list):
                                    activities = data['activities']
                                else:
                                    activities = [data]
                            elif isinstance(data, list):
                                activities = data
                            else:
                                print(f"Unexpected JSON structure in {raw_file}")
                                continue
                                
                            # Add source file for reference to each activity
                            for activity in activities:
                                activity["source_file"] = f"{original_image}.jpg"  # Assume jpg extension
                                new_activities.append(activity)
                                
                        except json.JSONDecodeError:
                            print(f"Could not parse JSON in {raw_file}")
                    else:
                        print(f"No JSON found in {raw_file}")
                        
            except Exception as e:
                print(f"Error processing raw response file {raw_file}: {e}")
                
        print(f"Processed {len(new_activities)} activities from raw responses")
        all_activities = existing_activities + new_activities
    else:
        # Determine which directory to process
        process_dir = NEW_INPUT_DIR if args.new_only else INPUT_DIR
        
        # Get image files from the selected directory
        image_files = []
        for ext in ['jpg', 'jpeg', 'png', 'JPG', 'JPEG', 'PNG']:
            if args.new_only:
                image_files.extend(glob.glob(os.path.join(process_dir, f"*.{ext}")))
            else:
                # When processing all images, don't include images in the 'new' subdirectory
                image_files.extend(glob.glob(os.path.join(process_dir, f"*.{ext}")))
                # Also don't include any other subdirectories
                image_files = [f for f in image_files if os.path.dirname(f) == process_dir]
        
        if not image_files:
            print(f"No image files found in {process_dir} directory.")
            if not existing_activities:
                return
            print("Will proceed with sanitizing existing activities only.")
            all_activities = existing_activities
        else:
            print(f"Found {len(image_files)} image files to process.")
            
            # Process each image
            new_activities = []
            for image_file in image_files:
                activity_info_list = extract_activity_info(image_file, save_raw=args.save_raw)
                
                # Add source file for reference to each activity
                for activity_info in activity_info_list:
                    activity_info["source_file"] = os.path.basename(image_file)
                    new_activities.append(activity_info)
                
                # If processing new images, move the processed image to the main input directory
                if args.new_only:
                    dest_path = os.path.join(INPUT_DIR, os.path.basename(image_file))
                    print(f"Moving processed image to {dest_path}")
                    shutil.move(image_file, dest_path)
            
            # Combine existing and new activities
            all_activities = existing_activities + new_activities
    
    # Sanitize dates - make sure no dates are in the past and handle weekday mentions
    if not args.validate_locations:  # Skip date sanitization if only validating locations
        try:
            print("Sanitizing dates...")
            all_activities = sanitize_dates(all_activities)
        except Exception as e:
            print(f"Error during date sanitization: {e}")
            import traceback
            traceback.print_exc()
            # Save the current state in case of error
            error_file = os.path.join(OUTPUT_DIR, "activities_error.json")
            with open(error_file, "w") as f:
                json.dump(all_activities, f, indent=2)
            print(f"Saved current state to {error_file}")
            return
    
    # Validate and enhance location data
    try:
        print("Validating location data...")
        all_activities = validate_location(all_activities)
    except Exception as e:
        print(f"Error during location validation: {e}")
        import traceback
        traceback.print_exc()
        # Save the current state in case of error
        error_file = os.path.join(OUTPUT_DIR, "locations_error.json")
        with open(error_file, "w") as f:
            json.dump(all_activities, f, indent=2)
        print(f"Saved current state to {error_file}")
        # Continue with the process even if location validation fails
    
    # Generate markdown
    try:
        markdown_content = generate_markdown(all_activities)
        
        # Write to output files
        output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
        with open(output_path, "w") as f:
            f.write(markdown_content)
    except Exception as e:
        print(f"Error generating markdown: {e}")
    
    # Save JSON
    with open(json_output_path, "w") as f:
        json.dump(all_activities, f, indent=2)
    
    print(f"Activity information saved to {output_path}")
    print(f"Raw data saved to {json_output_path}")
    
    if args.sanitize_only:
        print(f"Date sanitization completed for {len(all_activities)} activities.")
    elif args.validate_locations:
        print(f"Location validation completed for {len(all_activities)} activities.")
    elif args.from_raw:
        print(f"Processed {len(all_activities)} total activities from raw responses.")
    elif args.new_only:
        print(f"Processed and moved {len(image_files)} new images.")
        print(f"Added {len(new_activities)} new activities to the existing {len(existing_activities)} activities.")
    else:
        print(f"Extracted {len(all_activities)} total activities from {len(image_files)} images.")

if __name__ == "__main__":
    main() 