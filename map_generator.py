#!/usr/bin/env python3
"""
Kids Activity Locator - Map Generator

This script takes the extracted activity information and generates an HTML file
with a Google Map showing all the activity locations, with filtering capabilities
for dates and time-of-day.
"""

import os
import json
import re
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Google API key from environment
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', 'YOUR_API_KEY')

# Define constants
INPUT_DIR = "input"  # Add input directory for image sources
APP_NAME = "kid_activity"
OUTPUT_DIR = "output"
JSON_FILE = "activities.json"
HTML_FILE = "map.html"

# Define time-of-day periods
MORNING = (0, 12)    # 12 AM - 11:59 AM
AFTERNOON = (12, 17) # 12 PM - 4:59 PM
EVENING = (17, 24)   # 5 PM - 11:59 PM

# Define pin colors for different time-of-day
PIN_COLORS = {
    "morning": "#4285F4",   # Blue
    "afternoon": "#FBBC05", # Yellow
    "evening": "#34A853",   # Green
    "unknown": "#EA4335"    # Red
}

def extract_address(location_str: Optional[str]) -> Optional[str]:
    """
    Extract a clean address from the location string.
    
    Args:
        location_str (str): Raw location string
        
    Returns:
        Optional[str]: Cleaned address or None if no address found
    """
    if not location_str:
        return None
    
    # If it already looks like an address, return it
    if re.search(r'\d+\s+[A-Za-z\s]+(?:Avenue|Ave|Street|St|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl|Circle|Cir)', location_str):
        return location_str
    
    # Try to extract the address from the location string
    address_patterns = [
        r'(?:at|located at|address[:]?)\s+(.+)',  # "at" or "located at" followed by address
        r'(?:Address[:]?)\s+(.+)',  # "Address:" followed by address
        r'(.+?),\s*(?:[A-Z]{2}|[A-Za-z]+)\s*\d{5}',  # Part before zip code
    ]
    
    for pattern in address_patterns:
        match = re.search(pattern, location_str, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # If no specific pattern matches, just return the whole string
    return location_str

def generate_google_maps_url(address: str) -> str:
    """
    Generate a Google Maps URL for the given address.
    
    Args:
        address (str): Address to map
        
    Returns:
        str: Google Maps URL
    """
    return f"https://www.google.com/maps/search/?api=1&query={quote(address)}"

def parse_date(date_str: Optional[str]) -> Optional[datetime.date]:
    """
    Parse date string into date object for filtering.
    
    Args:
        date_str (str): Date string to parse
        
    Returns:
        Optional[datetime.date]: Parsed date object or None if parsing fails
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
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
            
    return None

def parse_time_period(time_str: Optional[str]) -> str:
    """
    Determine if a time string is morning, afternoon, or evening.
    
    Args:
        time_str (str or dict): Time string (e.g., "3:00 PM - 5:00 PM") or dict with 'start' and 'end' keys
        
    Returns:
        str: "morning", "afternoon", "evening", or "unknown"
    """
    if not time_str:
        return "unknown"
    
    # Handle case where time_str is a dictionary with 'start' and 'end' keys
    if isinstance(time_str, dict) and 'start' in time_str:
        # Use the start time for classification
        start_time = time_str.get('start', '')
        if not start_time:
            return "unknown"
            
        # Try to extract hour from the start time in format "HH:MM"
        match = re.search(r'^(\d{1,2}):(\d{2})$', start_time)
        if match:
            hour = int(match.group(1))
        else:
            return "unknown"
    
    # Handle case where time_str is not actually a string
    elif not isinstance(time_str, str):
        print(f"Warning: Time value is not a string or a recognized format: {time_str}")
        return "unknown"
    
    # Standard string processing for time ranges
    else:
        # Try to extract start time
        am_pm_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)'
        hours_24_pattern = r'(\d{1,2})(?::(\d{2}))?(?:\s*h)?'
        
        # First try AM/PM format
        match = re.search(am_pm_pattern, time_str)
        if match:
            hour = int(match.group(1))
            if match.group(3).lower() == 'pm' and hour < 12:
                hour += 12
            elif match.group(3).lower() == 'am' and hour == 12:
                hour = 0
        else:
            # Try 24-hour format
            match = re.search(hours_24_pattern, time_str)
            if match:
                hour = int(match.group(1))
            else:
                return "unknown"
    
    # Classify by time period
    if MORNING[0] <= hour < MORNING[1]:
        return "morning"
    elif AFTERNOON[0] <= hour < AFTERNOON[1]:
        return "afternoon"
    elif EVENING[0] <= hour < EVENING[1]:
        return "evening"
    else:
        return "unknown"

def get_unique_dates(activities: List[Dict]) -> List[str]:
    """
    Get a sorted list of unique dates from activities.
    For dates where all activities are archived, they will be excluded from the list.
    
    Args:
        activities (List[Dict]): List of activity dictionaries
    
    Returns:
        List[str]: Sorted list of unique date strings from active activities
    """
    # Group activities by date
    date_groups = {}
    for activity in activities:
        date_str = activity.get('date')
        is_archived = activity.get('is_archived', False)
        
        if date_str:
            if date_str not in date_groups:
                date_groups[date_str] = {'activities': 0, 'archived': 0}
            
            date_groups[date_str]['activities'] += 1
            if is_archived:
                date_groups[date_str]['archived'] += 1
    
    # Keep only dates that have at least one non-archived activity
    active_dates = []
    for date_str, stats in date_groups.items():
        if stats['activities'] > stats['archived']:
            active_dates.append(date_str)
    
    # Try to sort dates chronologically
    sorted_dates = []
    date_objects = []
    
    for date_str in active_dates:
        date_obj = parse_date(date_str)
        if date_obj:
            date_objects.append((date_str, date_obj))
    
    # Sort by the actual date objects
    date_objects.sort(key=lambda x: x[1])
    sorted_dates = [date_tuple[0] for date_tuple in date_objects]
    
    # Add any dates that couldn't be parsed at the end
    for date_str in active_dates:
        if date_str not in sorted_dates:
            sorted_dates.append(date_str)
    
    return sorted_dates

def generate_html(activities: List[Dict], base_url: str = "") -> str:
    """
    Generate an HTML file with a Google Map showing all activity locations with filtering options.
    
    Args:
        activities (List[Dict]): List of activity dictionaries
        base_url (str): Optional base URL for GitHub Pages or other hosted environment
        
    Returns:
        str: HTML content
    """
    # Filter activities to only include those with locations and that are not archived
    activities_with_locations = [
        activity for activity in activities 
        if activity.get('location') and extract_address(activity.get('location'))
        and not activity.get('is_archived', False)  # Only include non-archived activities
    ]
    
    if not activities_with_locations:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Kids Activities Map</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <!-- Google tag (gtag.js) -->
            <script async src="https://www.googletagmanager.com/gtag/js?id=G-5831K3EZ32"></script>
            <script>
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());

            gtag('config', 'G-5831K3EZ32');
            </script>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
                h1 { color: #333; }
            </style>
        </head>
        <body>
            <h1>No Activities with Locations Found</h1>
            <p>No current activities with valid location information were found in the data.</p>
        </body>
        </html>
        """
    
    # Extract dates directly from the filtered activities that will be displayed on the map
    # This ensures the date filter only shows dates for activities that are actually visible
    active_dates = []
    for activity in activities_with_locations:
        date_str = activity.get('date')
        if date_str and date_str not in active_dates:
            active_dates.append(date_str)
    
    # Sort dates chronologically
    date_objects = []
    for date_str in active_dates:
        date_obj = parse_date(date_str)
        if date_obj:
            date_objects.append((date_str, date_obj))
    
    # Sort by the actual date objects
    date_objects.sort(key=lambda x: x[1])
    unique_dates = [date_tuple[0] for date_tuple in date_objects]
    
    # Add any dates that couldn't be parsed at the end
    for date_str in active_dates:
        if date_str not in unique_dates:
            unique_dates.append(date_str)
    
    # Prepare marker data with additional attributes for filtering
    markers_data = []
    for activity in activities_with_locations:
        name = activity.get('activity_name', 'Unnamed Activity')
        location = activity.get('location', '')
        date_str = activity.get('date')
        time_str = activity.get('time', 'Time not specified')
        description = activity.get('description', '')
        additional_details = activity.get('additional_details', '')
        source_file = activity.get('source_file', '')
        source_url = activity.get('source_url', '')
        
        # Parse additional data for filtering
        time_period = parse_time_period(time_str)
        
        # Get color based on time period
        color = PIN_COLORS.get(time_period, PIN_COLORS["unknown"])
        
        markers_data.append({
            "name": name,
            "address": extract_address(location),
            "full_location": location,
            "date": date_str,
            "time": time_str,
            "description": description,
            "additional_details": additional_details,
            "source_file": source_file,
            "source_url": source_url,
            "time_period": time_period,
            "color": color
        })
    
    # Start HTML content
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Kids Activities Map</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <!-- Google tag (gtag.js) -->
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-5831K3EZ32"></script>
        <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());

        gtag('config', 'G-5831K3EZ32');
        </script>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 0; }
            #map { height: 500px; width: 100%; }
            .controls { background: #fff; padding: 10px; border-bottom: 1px solid #ddd; }
            .sidebar { padding: 20px; height: 500px; overflow-y: auto; }
            .activity { margin-bottom: 15px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }
            .activity h3 { margin-top: 0; color: #333; cursor: pointer; }
            .activity h3:hover { color: #0078d7; text-decoration: underline; }
            .activity p { margin: 5px 0; }
            .activity a { color: #0078d7; text-decoration: none; }
            .activity a:hover { text-decoration: underline; }
            .filter-group { margin-right: 20px; display: inline-block; }
            .filter-title { font-weight: bold; margin-bottom: 5px; }
            .time-indicator { display: inline-block; width: 15px; height: 15px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }
            .morning { background-color: #4285F4; }   /* Blue */
            .afternoon { background-color: #FBBC05; } /* Yellow */
            .evening { background-color: #34A853; }   /* Green */
            .unknown { background-color: #EA4335; }   /* Red */
            .legend { margin-top: 10px; }
            .legend-item { margin-right: 15px; display: inline-block; }
            .source-link { color: #666; text-decoration: none; }
            .source-link:hover { text-decoration: underline; }
            .activity-number {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 25px;
                height: 25px;
                border-radius: 50%;
                background-color: #666;
                color: white;
                font-weight: bold;
                margin-right: 10px;
                font-size: 14px;
            }
            .marker-label {
                position: relative !important;
                top: 0px !important;
                left: 0px !important;
                z-index: 100;
                text-align: center;
                text-shadow: none;
                font-weight: bold !important;
                pointer-events: none;
            }
        </style>
    </head>
    <body>
        <div class="controls">
            <div class="filter-group">
                <div class="filter-title">Filter by Date:</div>
                <select id="date-filter" onchange="filterMarkers()">
                    <option value="all">All Dates</option>
    """
    
    # Add date filter options
    for date in unique_dates:
        html += f'                    <option value="{date}">{date}</option>\n'
    
    html += """
                </select>
            </div>
            
            <div class="filter-group">
                <div class="filter-title">Filter by Time of Day:</div>
                <label><input type="checkbox" value="morning" checked onchange="filterMarkers()"> <span class="time-indicator morning"></span>Morning</label>
                <label><input type="checkbox" value="afternoon" checked onchange="filterMarkers()"> <span class="time-indicator afternoon"></span>Afternoon</label>
                <label><input type="checkbox" value="evening" checked onchange="filterMarkers()"> <span class="time-indicator evening"></span>Evening</label>
                <label><input type="checkbox" value="unknown" checked onchange="filterMarkers()"> <span class="time-indicator unknown"></span>Unknown Time</label>
            </div>
            
            <div class="legend">
                <span class="legend-title">Legend: </span>
                <span class="legend-item"><span class="time-indicator morning"></span>Morning (12 AM - 11:59 AM)</span>
                <span class="legend-item"><span class="time-indicator afternoon"></span>Afternoon (12 PM - 4:59 PM)</span>
                <span class="legend-item"><span class="time-indicator evening"></span>Evening (5 PM - 11:59 PM)</span>
                <span class="legend-item"><span class="time-indicator unknown"></span>Unknown Time</span>
            </div>
        </div>
        
        <div id="map"></div>
        
        <div class="sidebar">
            <h2>Kids Activities</h2>
            <div id="activities-list">
    """
    
    # Add activities to sidebar
    for i, marker in enumerate(markers_data):
        source_link = ""
        if marker['source_file']:
            # Create a link to the original image if source file exists
            image_path = os.path.join(INPUT_DIR, marker['source_file'])
            if os.path.exists(image_path):
                source_link = f"<a href='{base_url}/{APP_NAME}/{INPUT_DIR}/{marker['source_file']}' target='_blank' class='source-link'>{marker['source_file']}</a>"
            else:
                source_link = marker['source_file']
        elif marker['source_url']:
            # Use source_url for web-scraped activities
            source_link = f"<a href='{marker['source_url']}' target='_blank' class='source-link'>{marker['source_url']}</a>"
        else:
            source_link = "Unknown"
        
        html += f"""
        <div class="activity" data-date="{marker['date'] or ''}" data-time-period="{marker['time_period']}" id="activity-{i}">
            <h3 onclick="showMarker({i})"><span class="activity-number" style="background-color: {marker['color']};">{i + 1}</span>{marker['name']}</h3>
            <p><strong>Date:</strong> {marker['date'] or 'Not specified'}</p>
            <p><strong>Time:</strong> {marker['time']}</p>
            <p><strong>Location:</strong> {marker['full_location']}</p>
        """
        
        if marker['description']:
            html += f"            <p><strong>Description:</strong> {marker['description']}</p>\n"
            
        if marker['additional_details']:
            html += f"            <p><strong>Additional Details:</strong> {marker['additional_details']}</p>\n"
            
        html += f"            <p><strong>Source:</strong> {source_link}</p>\n"
        html += f'            <p><a href="https://www.google.com/maps/search/?api=1&query={quote(marker["address"])}" target="_blank">View on Google Maps</a></p>\n'
        html += "        </div>\n"
    
    html += """
            </div>
        </div>
        
        <script>
            // Store markers globally for reference
            let markers = [];
            let map;
            
            function initMap() {
                // Initialize map
                map = new google.maps.Map(document.getElementById('map'), {
                    zoom: 10,
                    center: {lat: 30.2672, lng: -97.7431}, // Austin, TX coordinates
                    mapTypeId: 'roadmap'
                });
                
                // Add markers to the map
                const bounds = new google.maps.LatLngBounds();
                const geocoder = new google.maps.Geocoder();
                
                // Loop through marker data and create map markers
                const markerData = [
    """
    
    # Add marker data as JSON
    for i, marker in enumerate(markers_data):
        html += f"""
                    {{
                        name: "{marker['name'].replace('"', '\\"')}",
                        address: "{marker['address'].replace('"', '\\"')}",
                        date: "{marker['date'] or ''}",
                        timePeriod: "{marker['time_period']}",
                        color: "{marker['color']}"
                    }}{'' if i == len(markers_data) - 1 else ','}
        """
    
    html += """
                ];
                
                // Geocode addresses and add markers
                let completedMarkers = 0;
                markerData.forEach((data, index) => {
                    geocoder.geocode({ 'address': data.address }, function(results, status) {
                        if (status === 'OK') {
                            // Create a custom marker with a number label inside a colored circle
                            const markerNumber = index + 1;
                            const marker = new google.maps.Marker({
                                map: map,
                                position: results[0].geometry.location,
                                title: data.name,
                                label: {
                                    text: markerNumber.toString(),
                                    color: 'white',
                                    fontSize: '12px',
                                    fontWeight: 'bold',
                                    fontFamily: 'Arial',
                                    className: 'marker-label'
                                },
                                icon: {
                                    path: 'M10,16 C10,15 10.8,14 11.6,14 L14,14 C14.8,13 16.4,13 17.2,9 C18.8,7 23.6,7 26.8,7 C30,7 34,9 35.6,13 L38.8,13 C38.8,13 40.4,14 40.4,16 L40.4,19 C40.4,19 38.8,19 38.8,21 L38.8,24 L34.8,24 L34.8,22 C34.8,22 30,23 24.8,23 C19.6,23 14.8,22 14.8,22 L14.8,24 L10.8,24 L10.8,21 C10.8,19 10,19 10,19 L10,16 Z M15.4,17 C15.4,15 13,15 13,17 C13,19 15.4,19 15.4,17 Z M35.4,17 C35.4,15 33,15 33,17 C33,19 35.4,19 35.4,17 Z',
                                    fillColor: data.color,
                                    fillOpacity: 1.0,
                                    strokeWeight: 0,
                                    scale: 1,
                                    anchor: new google.maps.Point(24, 16),
                                    labelOrigin: new google.maps.Point(24, 16)
                                },
                                optimized: true
                            });
                            
                            // Store additional data with the marker, including the activity index for correlation
                            marker.date = data.date;
                            marker.timePeriod = data.timePeriod;
                            marker.activityIndex = index; // Store the activity index for proper correlation
                            
                            // Add click event to marker
                            marker.addListener('click', function() {
                                document.getElementById('activity-' + index).scrollIntoView({behavior: 'smooth', block: 'center'});
                                // Highlight the activity in the sidebar
                                const activities = document.querySelectorAll('.activity');
                                activities.forEach(activity => activity.style.backgroundColor = '');
                                document.getElementById('activity-' + index).style.backgroundColor = '#f0f0f0';
                            });
                            
                            // Add marker to the global array
                            markers.push(marker);
                            
                            // Extend bounds to include this marker
                            bounds.extend(results[0].geometry.location);
                            
                            // Count completed markers
                            completedMarkers++;
                            
                            // Fit map to bounds if all markers are done
                            if (completedMarkers === markerData.length) {
                                map.fitBounds(bounds);
                                // Initial filtering should only happen once all markers are created
                                filterMarkers();
                            }
                        } else {
                            console.error('Geocode failed for address:', data.address, status);
                            // Count failed markers too so we can still proceed
                            completedMarkers++;
                            
                            // Check if all markers are done even with failures
                            if (completedMarkers === markerData.length) {
                                // Try to fit bounds if we have any successful markers
                                if (markers.length > 0) {
                                    map.fitBounds(bounds);
                                }
                                // Initial filtering
                                filterMarkers();
                            }
                        }
                    });
                });
                
                // Don't call filterMarkers here - will be called when all markers are loaded
            }
            
            function showMarker(index) {
                // Find the marker that corresponds to this activity index
                const marker = markers.find(m => m.activityIndex === index);
                if (marker) {
                    // Center map on marker
                    map.setCenter(marker.getPosition());
                    map.setZoom(15); // Zoom in a bit
                    
                    // Highlight the activity in the sidebar
                    const activities = document.querySelectorAll('.activity');
                    activities.forEach(activity => activity.style.backgroundColor = '');
                    document.getElementById('activity-' + index).style.backgroundColor = '#f0f0f0';
                }
            }
            
            function filterMarkers() {
                const dateFilter = document.getElementById('date-filter').value;
                const timeFilters = Array.from(document.querySelectorAll('input[type="checkbox"]:checked'))
                    .map(input => input.value)
                    .filter(value => ['morning', 'afternoon', 'evening', 'unknown'].includes(value));
                
                // Filter markers based on selected criteria
                markers.forEach(marker => {
                    const activityIndex = marker.activityIndex;
                    const activityElement = document.getElementById('activity-' + activityIndex);
                    if (!activityElement) return;
                    
                    // Using only the marker date for filtering - matching what's in the dropdown
                    const dateMatch = dateFilter === 'all' || marker.date === dateFilter;
                    const timeMatch = timeFilters.includes(marker.timePeriod);
                    
                    // Show/hide based on filter criteria
                    marker.setVisible(dateMatch && timeMatch);
                    
                    // Update sidebar activity visibility
                    activityElement.style.display = dateMatch && timeMatch ? 'block' : 'none';
                });
            }
        </script>
        <script async defer src="https://maps.googleapis.com/maps/api/js?key=GOOGLE_API_KEY&callback=initMap"></script>
    </body>
    </html>
    """.replace('GOOGLE_API_KEY', GOOGLE_API_KEY)
    
    return html

def main():
    """
    Main function to parse arguments and generate the HTML map file.
    """
    parser = argparse.ArgumentParser(description="Generate a Google Map HTML file from activities JSON")
    parser.add_argument('--base-url', type=str, default="", 
                        help="Optional base URL for GitHub Pages (e.g., '/repo-name')")
    # We're keeping the analytics parameter for backward compatibility but it's no longer needed
    parser.add_argument('--analytics-id', type=str, default="", 
                        help="[DEPRECATED] Google Analytics tracking ID is now hardcoded")
    args = parser.parse_args()
    
    # Check if output directory exists, create if not
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    
    # Read the JSON file
    json_path = os.path.join(OUTPUT_DIR, JSON_FILE)
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found. Run activity_extractor.py first.")
        return 1
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print(f"Error: Unable to parse {json_path}. The file may be corrupted.")
        return 1
    
    # Generate HTML (analytics code is now hardcoded in the template)
    html_content = generate_html(data, args.base_url)
    
    # If analytics ID is provided, display a notice that it's no longer needed
    if args.analytics_id:
        print("Note: The --analytics-id parameter is no longer needed as the Google Analytics code is now hardcoded.")
    
    # Write the HTML file
    html_path = os.path.join(OUTPUT_DIR, HTML_FILE)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Map generated successfully at {html_path}")
    print("Google Analytics tracking code (G-5831K3EZ32) has been automatically added.")
    
    if GOOGLE_API_KEY == "YOUR_API_KEY":
        print("\nWarning: Using default Google API key. For a proper map:")
        print("1. Get a Google Maps JavaScript API key from https://console.cloud.google.com/")
        print("2. Add it to your .env file as GOOGLE_API_KEY=your_key_here")
    
    return 0

if __name__ == "__main__":
    exit(main()) 