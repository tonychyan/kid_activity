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
    
    activities = []
    
    # NEW APPROACH: Handle both featured events and list events
    
    # 1. Extract featured events (those with "— Event Name" pattern)
    print("Extracting featured events...")
    featured_events = extract_featured_events(main_content, url)
    activities.extend(featured_events)
    print(f"Found {len(featured_events)} featured events")
    
    # 2. Extract list events (from "More events to explore" section)
    print("Extracting list events...")
    list_events = extract_list_events(main_content, url)
    activities.extend(list_events)
    print(f"Found {len(list_events)} list events")
    
    print(f"Total weekend activities found: {len(activities)}")
    return activities


def extract_featured_events(main_content, url: str) -> List[Dict]:
    """
    Extract featured events that have the "— Event Name" pattern and full descriptions.
    """
    activities = []
    
    # Look for paragraphs with "— Event Name" pattern
    paragraphs = main_content.find_all('p')
    
    for i, p in enumerate(paragraphs):
        text = p.get_text(strip=True)
        
        # Check for "— Event Name" pattern
        event_name_match = re.match(r'^[\u2013\u2014\-—]\s*(.+)$', text)
        if event_name_match:
            event_name_text = event_name_match.group(1).strip()
            
            # Extract event name and location from the text
            # Handle patterns like "Family Day @ UMLAUF" or "Event Name @ Location"
            if ' @ ' in event_name_text:
                event_name, location_hint = event_name_text.split(' @ ', 1)
                event_name = event_name.strip()
                location_hint = location_hint.strip()
            else:
                event_name = event_name_text
                location_hint = None
            
            # Try to find a link inside this paragraph
            event_link = None
            link = p.find('a')
            if link and link.get('href'):
                event_link = link.get('href')
                # Use the link text as event name if it's more descriptive
                link_text = link.get_text(strip=True)
                if link_text and len(link_text) > len(event_name):
                    event_name = link_text
            
            # Look for date and description in the following paragraphs
            event_date = None
            event_description = []
            
            # Check the next few paragraphs for date and description
            for j in range(1, 5):  # Check up to 4 paragraphs ahead
                if i + j >= len(paragraphs):
                    break
                    
                next_p = paragraphs[i + j]
                next_text = next_p.get_text(strip=True)
                
                # Skip empty paragraphs
                if not next_text:
                    continue
                
                # Check if this is a date paragraph (often in italic)
                em = next_p.find('em')
                if em and not event_date:
                    date_text = em.get_text(strip=True)
                    if date_text and is_likely_date(date_text):
                        event_date = date_text
                        continue
                
                # Check if this is another event (starts with "—" or "More events")
                if (next_text.startswith('—') or 
                    'more events' in next_text.lower() or
                    next_text.startswith('•')):
                    break
                
                # Add to description
                event_description.append(next_text)
            
            # Create the activity entry
            if event_name:
                description_text = '\n'.join(event_description)
                
                activity = {
                    'activity_name': event_name,
                    'raw_content': description_text,
                    'raw_datetime': event_date or extract_date_from_text(description_text),
                    'source': 'do512family.com/this-weekend',
                    'source_url': event_link or url,
                    'extraction_date': datetime.now().strftime('%Y-%m-%d')
                }
                
                # Add location hint if found
                if location_hint:
                    activity['location_hint'] = location_hint
                else:
                    # Try to extract location from description
                    location_match = re.search(r'@\s*(.+?)(?:\||\n|$)', description_text)
                    if location_match:
                        activity['location_hint'] = location_match.group(1).strip()
                
                activities.append(activity)
    
    return activities


def extract_list_events(main_content, url: str) -> List[Dict]:
    """
    Extract events from bulleted lists (like "More events to explore this weekend").
    """
    activities = []
    
    # Look for unordered lists that might contain events
    lists = main_content.find_all('ul')
    
    for ul in lists:
        # Check if this list contains events (look for links to family.do512.com)
        list_items = ul.find_all('li')
        has_event_links = any(
            li.find('a') and li.find('a').get('href') and 
            'family.do512.com/events' in li.find('a').get('href')
            for li in list_items
        )
        
        if has_event_links:
            print(f"Found event list with {len(list_items)} items")
            
            for li in list_items:
                link = li.find('a')
                if link and link.get('href'):
                    event_link = link.get('href')
                    event_name = link.get_text(strip=True)
                    
                    # Extract location from the text after the link
                    li_text = li.get_text(strip=True)
                    location_hint = None
                    
                    # Look for "@ Location" pattern
                    if ' @ ' in li_text:
                        parts = li_text.split(' @ ', 1)
                        if len(parts) > 1:
                            location_hint = parts[1].strip()
                    
                    # Create activity entry
                    if event_name:
                        activity = {
                            'activity_name': event_name,
                            'raw_content': li_text,
                            'raw_datetime': '',  # List events typically don't have dates in the text
                            'source': 'do512family.com/this-weekend',
                            'source_url': event_link,
                            'extraction_date': datetime.now().strftime('%Y-%m-%d')
                        }
                        
                        if location_hint:
                            activity['location_hint'] = location_hint
                        
                        activities.append(activity)
    
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

def extract_date_from_url(url: str) -> str:
    """
    Extract date from do512 URL pattern.
    
    Args:
        url (str): URL to extract date from
        
    Returns:
        str: Date in YYYY-MM-DD format or empty string if not found
    """
    # Pattern: https://family.do512.com/events/2025/7/12/event-name
    match = re.search(r'/events/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    
    # Handle weekly events - get next occurrence
    weekly_match = re.search(r'/events/weekly/(\w{3})/', url)
    if weekly_match:
        day_abbr = weekly_match.group(1).lower()
        day_mapping = {
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 
            'fri': 4, 'sat': 5, 'sun': 6
        }
        
        if day_abbr in day_mapping:
            today = datetime.now().date()
            target_weekday = day_mapping[day_abbr]
            days_ahead = target_weekday - today.weekday()
            
            if days_ahead <= 0:  # Target day already happened this week
                days_ahead += 7
                
            target_date = today + timedelta(days=days_ahead)
            return target_date.strftime("%Y-%m-%d")
    
    return ""

def extract_location_from_content(content: str) -> str:
    """
    Extract location/address from HTML content.
    
    Args:
        content (str): HTML content to parse
        
    Returns:
        str: Extracted location or empty string
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Try various selectors for location
    location_selectors = [
        '[data-testid="event-venue"]',
        '.venue-name',
        '.location',
        '.address',
        'address',
        '[class*="venue"]',
        '[class*="location"]',
        '[class*="address"]'
    ]
    
    for selector in location_selectors:
        elem = soup.select_one(selector)
        if elem:
            location = elem.get_text(strip=True)
            if location and len(location) > 5:  # Basic validation
                return location
    
    # Look for patterns in text
    text = soup.get_text()
    
    # Look for "@ Location" patterns first - more specific patterns
    at_patterns = [
        r'@\s*([A-Za-z\s\'&]+(?:Brewing|Brewery))',
        r'@\s*([A-Za-z\s\'&]+(?:Museum|Gallery))',
        r'@\s*([A-Za-z\s\'&]+(?:Library|Center))',
        r'@\s*([A-Za-z\s\'&]+(?:Park|Gardens?))',
        r'@\s*([A-Za-z\s\'&]+(?:Church|School|Hall))',
        r'@\s*([A-Za-z\s\'&]+(?:Stadium|Arena|Theatre|Theater))',
        r'@\s*([A-Za-z\s\'&]+(?:Retreat|House|Kitchen))',
        r'@\s*([A-Za-z\s\'&]+(?:Restaurant|Cafe|Coffee|Bar|Grill|Tavern))',
        r'@\s*([A-Za-z\s\'&]+(?:Club|Studio|Shop|Store|Market))',
        r'@\s*([A-Za-z\s\'&]+(?:Farm|Ranch|Resort|Hotel|Lodge|Inn))',
        r'@\s*([A-Za-z\s\'&]+(?:Spa|Gym|Fitness|Yoga|Dance|Music|Art))',
        r'@\s*([A-Za-z\s\'&]+(?:Academy|Institute|University|College))'
    ]
    
    for pattern in at_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            if location and len(location) > 3:
                # Add generic location info for Austin area
                if 'Austin' not in location and 'TX' not in location:
                    location += ', Austin, TX'
                return location
    
    # Look for address patterns (numbers + street names)
    address_patterns = [
        r'\d+\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Blvd|Boulevard|Pkwy|Parkway|Ln|Lane|Ct|Court|Cir|Circle|Way|Pl|Place)\b[^.]*?(?:Austin|Round Rock|Cedar Park|Pflugerville|Georgetown|Leander|Hutto|Manor|Lakeway|Bee Cave|Dripping Springs|Liberty Hill|TX|Texas)',
        r'[A-Za-z\s]+(?:Park|Center|Museum|Library|Church|School|Hall|Stadium|Arena|Theatre|Theater|Gallery|Gardens?)\b[^.]*?(?:Austin|Round Rock|Cedar Park|Pflugerville|Georgetown|Leander|Hutto|Manor|Lakeway|Bee Cave|Dripping Springs|Liberty Hill|TX|Texas)'
    ]
    
    for pattern in address_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    
    # Look for venue names without addresses - more specific patterns
    venue_patterns = [
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Brewing|Brewery))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Museum|Gallery))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Library|Center))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Park|Gardens?))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Church|School|Hall))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Stadium|Arena|Theatre|Theater))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Retreat|House|Kitchen))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Restaurant|Cafe|Coffee|Bar|Grill|Tavern))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Club|Studio|Shop|Store|Market))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Farm|Ranch|Resort|Hotel|Lodge|Inn))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Spa|Gym|Fitness|Yoga|Dance|Music|Art))',
        r'(?:at|@)\s*([A-Za-z\s\'&]+(?:Academy|Institute|University|College))'
    ]
    
    for pattern in venue_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            if location and len(location) > 3:
                # Add generic location info for Austin area
                if 'Austin' not in location and 'TX' not in location:
                    location += ', Austin, TX'
                return location
    
    return ""

def extract_time_from_content(content: str) -> str:
    """
    Extract time from HTML content.
    
    Args:
        content (str): HTML content to parse
        
    Returns:
        str: Extracted time or empty string
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text()
    
    # Look for time patterns
    time_patterns = [
        r'\d{1,2}:\d{2}\s*[ap]m\s*[-–]\s*\d{1,2}:\d{2}\s*[ap]m',
        r'\d{1,2}\s*[ap]m\s*[-–]\s*\d{1,2}\s*[ap]m',
        r'\d{1,2}:\d{2}\s*[ap]m',
        r'\d{1,2}\s*[ap]m'
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    
    return ""

async def process_activities_with_direct_parsing(activities: List[Dict]) -> List[Dict]:
    """
    Process activities with direct parsing instead of LLM.
    
    Args:
        activities (List[Dict]): List of activities with raw information
        
    Returns:
        List[Dict]: List of activities with structured information
    """
    processed_activities = []
    
    for activity in activities:
        print(f"Processing activity: {activity['activity_name']}")
        
        # Extract date from URL
        if 'source_url' in activity:
            date = extract_date_from_url(activity['source_url'])
            if date:
                activity['date'] = date
                print(f"  Date extracted: {date}")
            else:
                print(f"  No date found in URL: {activity['source_url']}")
        
        # Extract location from content
        if 'raw_content' in activity:
            location = extract_location_from_content(activity['raw_content'])
            if location:
                activity['location'] = location
                print(f"  Location extracted: {location}")
            else:
                print(f"  No location found in content")
        
        # If no location found in content, try to extract from activity name
        if 'location' not in activity or not activity['location']:
            location = extract_location_from_content(activity['activity_name'])
            if location:
                activity['location'] = location
                print(f"  Location extracted from title: {location}")
            else:
                # Simple fallback: extract anything after "@" in the title
                title_match = re.search(r'@\s*(.+)', activity['activity_name'])
                if title_match:
                    location = title_match.group(1).strip()
                    if 'Austin' not in location and 'TX' not in location:
                        location += ', Austin, TX'
                    activity['location'] = location
                    print(f"  Location extracted from title (simple): {location}")
                else:
                    print(f"  No location found in title either")
        
        # Extract time from content
        if 'raw_content' in activity:
            time = extract_time_from_content(activity['raw_content'])
            if time:
                activity['time'] = time
                print(f"  Time extracted: {time}")
            else:
                print(f"  No time found in content")
        
        # Extract basic info from raw content
        if 'raw_content' in activity:
            soup = BeautifulSoup(activity['raw_content'], 'html.parser')
            text = soup.get_text()
            
            # Look for cost information
            cost_patterns = [
                r'(?:cost|price|fee|admission)[:\s]*\$?\d+',
                r'free(?:\s+admission)?',
                r'\$\d+(?:\.\d{2})?'
            ]
            
            for pattern in cost_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    activity['cost'] = match.group(0).strip()
                    break
            
            # Look for age information
            age_patterns = [
                r'age[s]?\s*\d+[-–]\d+',
                r'age[s]?\s*\d+\s*(?:and\s*)?(?:up|under|over)',
                r'all\s*ages',
                r'family[-\s]friendly'
            ]
            
            for pattern in age_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    activity['age_range'] = match.group(0).strip()
                    break
            
            # Use first few sentences as description
            sentences = text.split('.')[:2]
            if sentences:
                activity['description'] = '. '.join(sentences).strip()
                if activity['description'] and not activity['description'].endswith('.'):
                    activity['description'] += '.'
        
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
    
    # 2. Process with direct parsing (no LLM needed)
    processed_activities = await process_activities_with_direct_parsing(raw_activities)
    
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
    
    # Process with direct parsing
    processed_events = await process_activities_with_direct_parsing(all_events)
    
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