#!/usr/bin/env python3
"""
Do512 Family Activity Scraper

This script scrapes kids' activities from do512family.com websites:
1. do512family.com/this-weekend/ - Curated weekend activities
2. family.do512.com - Calendar interface with more activities

Usage:
    python do512_scraper.py --source weekend  # Scrape only weekend activities
    python do512_scraper.py --source calendar  # Scrape only calendar activities
    python do512_scraper.py  # Scrape both sources
"""

import os
import sys
import json
import argparse
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

# Add the current directory to path to ensure we can import from tools
sys.path.append('.')
from tools.web_scraper import fetch_page

# Define constants
OUTPUT_DIR = "output"
JSON_FILE = os.path.join(OUTPUT_DIR, "do512_activities.json")
APP_JSON_FILE = os.path.join(OUTPUT_DIR, "activities.json")

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configure week day mapping for date parsing
DAY_MAPPING = {
    'monday': 0, 'mon': 0,
    'tuesday': 1, 'tue': 1, 'tues': 1,
    'wednesday': 2, 'wed': 2,
    'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
    'friday': 4, 'fri': 4,
    'saturday': 5, 'sat': 5,
    'sunday': 6, 'sun': 6
}

async def scrape_weekend_activities() -> List[Dict]:
    """
    Scrape activities from do512family.com/this-weekend/
    
    Returns:
        List[Dict]: List of activities with raw information
    """
    print("Scraping weekend activities from do512family.com/this-weekend/...")
    
    # Scrape the weekend page
    url = "https://do512family.com/this-weekend/"
    content = await fetch_page(url)
    
    if not content:
        print(f"Error: Could not fetch content from {url}")
        return []
    
    # Save raw HTML for debugging (if needed)
    debug_dir = os.path.join(OUTPUT_DIR, "debug")
    os.makedirs(debug_dir, exist_ok=True)
    with open(os.path.join(debug_dir, "weekend_raw.html"), "w", encoding="utf-8") as f:
        f.write(content)
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')
    
    # Extract the page title to help determine date range
    page_title = soup.find('title')
    page_title_text = page_title.text.strip() if page_title else None
    print(f"Page title: {page_title_text}")
    
    # Try to find the main article content
    article = soup.find('article')
    
    if not article:
        print("Error: Could not find article content, trying alternative approach")
        # Alternative approach - try to find the main content area
        main_content = soup.find('div', class_='entry-content')
        if not main_content:
            print("Error: Could not find main content area")
            return []
    else:
        main_content = article.find('div', class_='entry-content')
        if not main_content:
            print("Error: Could not find entry-content inside article")
            main_content = article
    
    # Event Extraction Strategy:
    # 1. Look for horizontal rules (<hr>) as event separators
    # 2. Extract event details from paragraphs between rules
    # 3. Look for patterns like "— Event Name" or links to events
    
    # Find all direct children of the main content - paragraphs, images, horizontal rules, etc.
    children = main_content.find_all(recursive=False)
    
    # Identify potential event sections by looking for <hr> tags or event heading patterns
    event_sections = []
    current_section = []
    
    for child in children:
        # Skip empty elements
        if not child.get_text(strip=True):
            continue
            
        # Check if this is a separator (horizontal rule)
        if child.name == 'hr':
            if current_section:
                event_sections.append(current_section)
                current_section = []
        else:
            current_section.append(child)
    
    # Add the last section if it exists
    if current_section:
        event_sections.append(current_section)
    
    print(f"Found {len(event_sections)} potential event sections")
    
    # Process each event section
    activities = []
    
    for section in event_sections:
        # Skip sections that are too short (less than 3 elements) or don't look like events
        if len(section) < 3:
            continue
        
        # Skip sections that are just intro paragraphs (typically at the beginning)
        is_intro = False
        for elem in section[:2]:  # Check first two elements
            if elem.name == 'p' and ('welcome' in elem.get_text().lower() or
                                    'weekend' in elem.get_text().lower() and 'picks' in elem.get_text().lower()):
                is_intro = True
                break
        if is_intro:
            continue
        
        # Extract event information from the section
        event_name = None
        event_link = None
        event_date = None
        event_description = []
        event_location = None
        
        # First look for the event name pattern: "— Event Name" or a link that might be an event
        for elem in section:
            if elem.name == 'p':
                text = elem.get_text(strip=True)
                
                # Check for "— Event Name" pattern
                event_name_match = re.match(r'^[\u2013\u2014\-—]\s*(.+)$', text)
                if event_name_match:
                    event_name = event_name_match.group(1).strip()
                    # Try to find a link inside this paragraph
                    link = elem.find('a')
                    if link and link.get('href'):
                        event_link = link.get('href')
                    continue
                
                # Check for date pattern in italic (common for events)
                em = elem.find('em')
                if em and not event_date:
                    date_text = em.get_text(strip=True)
                    if date_text and is_likely_date(date_text):
                        event_date = date_text
                        continue
                
                # Add to description if not already processed as name or date
                event_description.append(text)
            
            # Check if there's a link that might be to an event
            elif not event_link and (elem.name == 'a' or elem.find('a')):
                link = elem if elem.name == 'a' else elem.find('a')
                if link and link.get('href') and ('event' in link.get('href') or 'festival' in link.get('href')):
                    event_link = link.get('href')
                    if not event_name:
                        event_name = link.get_text(strip=True)
        
        # If we found event information, create an activity entry
        if event_name and (event_date or event_description):
            # Join description paragraphs into a single string
            description_text = '\n'.join(event_description)
            
            # Create the activity entry
            activity = {
                'activity_name': event_name,
                'raw_content': description_text,
                'raw_datetime': event_date or extract_date_from_text(description_text),
                'source': 'do512family.com/this-weekend',
                'source_url': event_link or url,
                'extraction_date': datetime.now().strftime('%Y-%m-%d')
            }
            
            # Extract location if available
            location_match = re.search(r'@\s*(.+?)(?:\||\n|$)', description_text)
            if location_match:
                activity['location_hint'] = location_match.group(1).strip()
            
            activities.append(activity)
    
    # If we didn't find any activities with the section-based approach,
    # try a paragraph-based approach as fallback
    if not activities:
        print("No activities found with section-based approach, trying paragraph-based approach")
        
        # Look for paragraphs containing event links or event names
        paragraphs = main_content.find_all('p')
        i = 0
        while i < len(paragraphs):
            p = paragraphs[i]
            
            # Skip empty paragraphs
            if not p.get_text(strip=True):
                i += 1
                continue
            
            # Check if this might be an event heading (starts with "—" or contains a link)
            is_event_heading = False
            event_name = None
            event_link = None
            
            # Check for "— Event Name" pattern
            text = p.get_text(strip=True)
            event_name_match = re.match(r'^[\u2013\u2014\-—]\s*(.+)$', text)
            if event_name_match:
                event_name = event_name_match.group(1).strip()
                is_event_heading = True
                
                # Try to find a link inside this paragraph
                link = p.find('a')
                if link and link.get('href'):
                    event_link = link.get('href')
            
            # If this looks like an event heading, try to collect info from following paragraphs
            if is_event_heading:
                event_date = None
                event_description = []
                
                # Look ahead for date and description (up to 3 paragraphs)
                for j in range(1, 4):
                    if i + j >= len(paragraphs):
                        break
                    
                    next_p = paragraphs[i + j]
                    next_text = next_p.get_text(strip=True)
                    
                    # Check if this is a date paragraph (often in italic)
                    em = next_p.find('em')
                    if em and not event_date:
                        date_text = em.get_text(strip=True)
                        if date_text and is_likely_date(date_text):
                            event_date = date_text
                            continue
                    
                    # Otherwise, add to description
                    event_description.append(next_text)
                
                # Create activity if we have enough information
                if event_name and (event_date or event_description):
                    description_text = '\n'.join(event_description)
                    
                    activity = {
                        'activity_name': event_name,
                        'raw_content': description_text,
                        'raw_datetime': event_date or extract_date_from_text(description_text),
                        'source': 'do512family.com/this-weekend',
                        'source_url': event_link or url,
                        'extraction_date': datetime.now().strftime('%Y-%m-%d')
                    }
                    
                    # Extract location if available
                    location_match = re.search(r'@\s*(.+?)(?:\||\n|$)', description_text)
                    if location_match:
                        activity['location_hint'] = location_match.group(1).strip()
                    
                    activities.append(activity)
                
                # Skip the paragraphs we've processed
                i += max(j, 1)
            else:
                i += 1
    
    print(f"Found {len(activities)} weekend activities")
    return activities

def is_likely_date(text: str) -> bool:
    """
    Check if text is likely to be a date.
    
    Args:
        text (str): Text to check
        
    Returns:
        bool: True if text is likely a date
    """
    # Check for common date patterns
    date_patterns = [
        r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\b',
        r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b',
        r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
        r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b',
        r'\b\d{1,2}:\d{2}\b',  # Time pattern
        r'\b(AM|PM)\b'  # AM/PM indicator
    ]
    
    for pattern in date_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False

def extract_date_from_text(text: str) -> str:
    """
    Extract date information from text using common patterns.
    
    Args:
        text (str): Text to search for date patterns
        
    Returns:
        str: Extracted date string or empty string if none found
    """
    # Common date patterns
    patterns = [
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?',  # Month Day
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?',  # Abbreviated Month Day
        r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+\w+\s+\d{1,2}',  # Day of week, Month Day
        r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+\w+\s+\d{1,2}',  # Day of week, Month Day
        r'(This|Next)\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|weekend)',  # Relative days
        r'\d{1,2}/\d{1,2}(?:/\d{2,4})?',  # MM/DD or MM/DD/YYYY
        r'(April|May|June|July|August|September|October|November|December)\s+\d{1,2}[-–]\d{1,2}',  # Month Day-Day
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept|Oct|Nov|Dec)\s+\d{1,2}[-–]\d{1,2}'  # Abbreviated Month Day-Day
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    
    return ""

async def process_activities_with_llm(activities: List[Dict]) -> List[Dict]:
    """
    Process activities with LLM to extract structured information.
    
    Args:
        activities (List[Dict]): List of activities with raw information
        
    Returns:
        List[Dict]: List of activities with structured information
    """
    from tools.llm_api import query_llm
    
    processed_activities = []
    
    for activity in activities:
        print(f"Processing activity: {activity['activity_name']}")
        
        prompt = f"""
        Extract structured information from this kids' activity description.
        
        Activity name: {activity['activity_name']}
        Raw content: {activity['raw_content']}
        Raw date/time: {activity.get('raw_datetime', '')}
        
        Please extract:
        1. Location (full address if possible, including venue name, city, state and ZIP)
        2. Date(s) (in YYYY-MM-DD format - if specific date can't be determined, use the closest upcoming {activity.get('raw_datetime', '')})
        3. Time (start and end if available)
        4. Age range for the activity
        5. Cost information
        6. Brief description (1-2 sentences)
        7. Any registration details
        
        Return as a JSON object with the following fields:
        - location
        - date (or date_start and date_end if it spans multiple days)
        - time
        - age_range
        - cost
        - description
        - registration_info
        
        For location, include a full address with city, state and ZIP code if possible. If the exact ZIP code isn't mentioned, make your best guess based on the city. 
        
        For the date, if only a day of week is mentioned (like "Saturday"), determine the date for the upcoming Saturday.
        
        Return only the JSON, no additional text.
        """
        
        try:
            # Call LLM API
            response = query_llm(prompt, provider="openai")
            
            # Parse JSON response
            try:
                # Extract JSON from response (in case there's additional text)
                json_match = re.search(r'(\{.*\})', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    extracted_data = json.loads(json_str)
                else:
                    extracted_data = json.loads(response)
                
                # Merge with original activity data
                activity.update(extracted_data)
                
            except json.JSONDecodeError as e:
                print(f"Error parsing LLM response for {activity['activity_name']}: {e}")
                print(f"Response: {response}")
                activity['extraction_error'] = "Failed to parse LLM response"
                
        except Exception as e:
            print(f"Error processing activity with LLM: {e}")
            activity['extraction_error'] = str(e)
        
        # Add standardized date if available
        if 'date' in activity and activity['date']:
            try:
                # Verify date format is YYYY-MM-DD
                datetime.strptime(activity['date'], '%Y-%m-%d')
            except ValueError:
                # If not, try to convert it
                activity['date'] = standardize_date(activity['date'])
                
        processed_activities.append(activity)
    
    return processed_activities

def standardize_date(date_str: str) -> str:
    """
    Convert various date formats to YYYY-MM-DD.
    
    Args:
        date_str (str): Date string to convert
        
    Returns:
        str: Date in YYYY-MM-DD format or original string if parsing fails
    """
    try:
        # Try various date formats
        formats = [
            "%m/%d/%Y",      # 10/15/2023
            "%m/%d/%y",      # 10/15/23
            "%B %d, %Y",     # October 15, 2023
            "%b %d, %Y",     # Oct 15, 2023
            "%A, %B %d",     # Monday, October 15
            "%B %d",         # October 15
            "%b %d",         # Oct 15
        ]
        
        for fmt in formats:
            try:
                # If the format doesn't include year, add the current year
                if "%Y" not in fmt and "%y" not in fmt:
                    date_obj = datetime.strptime(date_str, fmt).replace(year=datetime.now().year)
                else:
                    date_obj = datetime.strptime(date_str, fmt)
                
                # Check if the date is in the past, if so, it's probably next year
                if date_obj.date() < datetime.now().date():
                    date_obj = date_obj.replace(year=date_obj.year + 1)
                    
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue
                
        # If day of week (Monday, Tuesday, etc.)
        for day_name, offset in DAY_MAPPING.items():
            if day_name in date_str.lower():
                # Calculate the date for the next occurrence of this day
                today = datetime.now().date()
                today_weekday = today.weekday()
                
                days_ahead = offset - today_weekday
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                    
                target_date = today + timedelta(days=days_ahead)
                return target_date.strftime("%Y-%m-%d")
                
        # No standard format matched
        return date_str
        
    except Exception as e:
        print(f"Error standardizing date '{date_str}': {e}")
        return date_str

def adapt_to_app_format(activities: List[Dict]) -> List[Dict]:
    """
    Adapt activities to the format used by the app.
    
    Args:
        activities (List[Dict]): List of activities with extracted information
        
    Returns:
        List[Dict]: List of activities in app format
    """
    formatted_activities = []
    
    for activity in activities:
        # Skip activities with extraction errors
        if 'extraction_error' in activity:
            print(f"Skipping activity with extraction error: {activity['activity_name']}")
            continue
            
        # Skip activities without required fields
        if not activity.get('location') or not activity.get('date'):
            print(f"Skipping activity missing required fields: {activity['activity_name']}")
            continue
        
        # Format additional details
        details = []
        if activity.get('age_range'):
            details.append(f"Age: {activity['age_range']}")
        if activity.get('cost'):
            details.append(f"Cost: {activity['cost']}")
        if activity.get('registration_info'):
            details.append(f"Registration: {activity['registration_info']}")
        
        additional_details = ". ".join(details)
        
        # Format location as string if it's a dictionary
        location = activity.get('location', '')
        if isinstance(location, dict):
            # Convert location dictionary to string
            location_parts = []
            if location.get('venue_name'):
                location_parts.append(location['venue_name'])
            
            address_parts = []
            for key in ['street', 'address', 'city', 'state', 'ZIP']:
                if location.get(key):
                    address_parts.append(location[key])
            
            if address_parts:
                location_parts.append(', '.join(address_parts))
            
            location = ', '.join(location_parts)
        
        # Create app-formatted activity
        formatted = {
            'activity_name': activity.get('activity_name', ''),
            'location': location,
            'date': activity.get('date', ''),
            'time': activity.get('time', ''),
            'description': activity.get('description', ''),
            'additional_details': additional_details,
            'raw_datetime': activity.get('raw_datetime', ''),
            'source_url': activity.get('source_url', ''),
            'source_type': 'web_scrape',
            'source_name': activity.get('source', 'do512family')
        }
        
        formatted_activities.append(formatted)
    
    return formatted_activities

async def fetch_weekend_activities() -> List[Dict]:
    """
    Complete pipeline for fetching weekend activities.
    
    Returns:
        List[Dict]: List of formatted activities
    """
    # 1. Scrape raw activity data
    raw_activities = await scrape_weekend_activities()
    
    # 2. Process with LLM
    processed_activities = await process_activities_with_llm(raw_activities)
    
    # 3. Convert to app format
    app_activities = adapt_to_app_format(processed_activities)
    
    return app_activities

async def extract_event_urls(start_date=None) -> List[str]:
    """
    Extract event URLs from the calendar page.
    
    Args:
        start_date (str, optional): Start date in YYYY-MM-DD format
        
    Returns:
        List[str]: List of event URLs
    """
    # Default to current date if not provided
    if not start_date:
        start_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f"Extracting event URLs for date: {start_date}")
    
    # Format for the calendar URL
    calendar_url = f"https://family.do512.com/events?day={start_date}"
    
    # Scrape the calendar page
    content = await fetch_page(calendar_url)
    
    if not content:
        print(f"Error: Could not fetch content from {calendar_url}")
        return []
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')
    
    # Find all event links - initial implementation, will need adjusting
    # The exact selector will depend on the actual HTML structure
    event_links = soup.select('a[data-testid="event-card-title"]')
    
    if not event_links:
        # Try alternative selectors if the first one doesn't find anything
        event_links = soup.select('.ds-listing-event-title')
    
    if not event_links:
        # One more attempt with a more generic selector
        event_links = soup.select('a[href*="/events/"]')
    
    event_urls = []
    for link in event_links:
        url = link.get('href')
        if url:
            # Ensure URL is absolute
            if not url.startswith('http'):
                url = f"https://family.do512.com{url}"
            event_urls.append(url)
    
    print(f"Found {len(event_urls)} event URLs")
    return event_urls

async def scrape_event_details(event_url: str) -> Dict:
    """
    Scrape details from an event page.
    
    Args:
        event_url (str): URL of the event page
        
    Returns:
        Dict: Event details
    """
    print(f"Scraping event: {event_url}")
    
    # Scrape the event page
    content = await fetch_page(event_url)
    
    if not content:
        print(f"Error: Could not fetch content from {event_url}")
        return {
            'source_url': event_url,
            'extraction_error': 'Failed to fetch content'
        }
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(content, 'html.parser')
    
    # Initialize event dictionary
    event = {
        'source_url': event_url,
        'source': 'family.do512.com',
        'extraction_date': datetime.now().strftime('%Y-%m-%d')
    }
    
    # Extract event title (assuming it's an h1 element)
    title_elem = soup.select_one('h1')
    if title_elem:
        event['activity_name'] = title_elem.text.strip()
    
    # Extract event description
    desc_elem = soup.select_one('[data-testid="event-description"]')
    if desc_elem:
        event['raw_content'] = desc_elem.text.strip()
    
    # Extract date and time
    date_elem = soup.select_one('[data-testid="event-date"]')
    if date_elem:
        event['raw_datetime'] = date_elem.text.strip()
    
    # Extract venue information
    venue_elem = soup.select_one('[data-testid="event-venue"]')
    if venue_elem:
        venue_name = venue_elem.text.strip()
        event['venue'] = venue_name
    
    # Try to find address information
    address_elem = soup.select_one('[data-testid="event-address"]')
    if address_elem:
        event['address'] = address_elem.text.strip()
        if 'venue' in event:
            event['location'] = f"{event['venue']}, {event['address']}"
    
    return event

async def fetch_calendar_activities(days_to_fetch: int = 7) -> List[Dict]:
    """
    Fetch activities from the calendar interface.
    
    Args:
        days_to_fetch (int): Number of days to fetch from the calendar
        
    Returns:
        List[Dict]: List of formatted activities
    """
    print(f"Fetching calendar activities for {days_to_fetch} days...")
    
    all_events = []
    
    # Get today's date
    start_date = datetime.now()
    
    # Iterate through days
    for day_offset in range(days_to_fetch):
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Get event URLs for this date
        event_urls = await extract_event_urls(start_date=date_str)
        
        # Process each event
        for url in event_urls:
            try:
                # Add delay to avoid overloading the server
                await asyncio.sleep(1)
                
                # Scrape event details
                event = await scrape_event_details(url)
                
                # Add to our collection
                all_events.append(event)
            except Exception as e:
                print(f"Error processing event {url}: {e}")
                all_events.append({
                    'source_url': url,
                    'extraction_error': str(e)
                })
    
    # Process with LLM
    processed_events = await process_activities_with_llm(all_events)
    
    # Format activities to match app structure
    return adapt_to_app_format(processed_events)

async def merge_with_app_data(activities: List[Dict], app_file: str = APP_JSON_FILE) -> None:
    """
    Merge activities with existing app data.
    
    Args:
        activities (List[Dict]): New activities to merge
        app_file (str): Path to app data file
    """
    if not os.path.exists(app_file):
        print(f"App data file {app_file} not found. Creating new file.")
        with open(app_file, 'w') as f:
            json.dump(activities, f, indent=2)
        return
    
    try:
        # Load existing activities
        with open(app_file, 'r') as f:
            existing_activities = json.load(f)
        
        # Create a set of existing activity signatures for deduplication
        existing_signatures = {
            f"{a.get('activity_name')}_{a.get('date')}_{a.get('location')}"
            for a in existing_activities
        }
        
        # Add new activities if they don't already exist
        new_activities = []
        for activity in activities:
            signature = f"{activity.get('activity_name')}_{activity.get('date')}_{activity.get('location')}"
            if signature not in existing_signatures:
                new_activities.append(activity)
                existing_signatures.add(signature)
        
        # Only update if we have new activities
        if new_activities:
            print(f"Adding {len(new_activities)} new activities to app data")
            existing_activities.extend(new_activities)
            
            # Save updated activities
            with open(app_file, 'w') as f:
                json.dump(existing_activities, f, indent=2)
            
            print(f"Successfully merged activities with app data")
        else:
            print("No new activities to add")
            
    except Exception as e:
        print(f"Error merging with app data: {e}")
        print("You can manually integrate the activities later")

async def main():
    """Main function to run scraping and integrate with app data"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Scrape kids activities from do512family.com')
    parser.add_argument('--source', choices=['weekend', 'calendar', 'both'], default='both',
                      help='Source to scrape (weekend, calendar, or both)')
    parser.add_argument('--days', type=int, default=7,
                      help='Number of days to fetch from calendar')
    parser.add_argument('--output', default=JSON_FILE,
                      help='Output file for scraped activities')
    parser.add_argument('--no-merge', action='store_true',
                      help='Do not merge with app data')
    args = parser.parse_args()
    
    all_activities = []
    
    # Scrape weekend list if requested
    if args.source in ['weekend', 'both']:
        print("Starting weekend activity scraper...")
        weekend_activities = await fetch_weekend_activities()
        all_activities.extend(weekend_activities)
        print(f"Found {len(weekend_activities)} weekend activities")
    
    # Scrape calendar if requested
    if args.source in ['calendar', 'both']:
        print(f"Starting calendar activity scraper...")
        calendar_activities = await fetch_calendar_activities(days_to_fetch=args.days)
        all_activities.extend(calendar_activities)
        print(f"Found {len(calendar_activities)} calendar activities")
    
    # Save to file
    with open(args.output, 'w') as f:
        json.dump(all_activities, f, indent=2)
    
    print(f"Saved {len(all_activities)} activities to {args.output}")
    
    # Merge with app data if requested
    if not args.no_merge:
        await merge_with_app_data(all_activities)

if __name__ == "__main__":
    asyncio.run(main()) 