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
        time_str (str): Time string (e.g., "3:00 PM - 5:00 PM")
        
    Returns:
        str: "morning", "afternoon", "evening", or "unknown"
    """
    if not time_str:
        return "unknown"
    
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
    
    Args:
        activities (List[Dict]): List of activity dictionaries
    
    Returns:
        List[str]: Sorted list of unique date strings
    """
    dates = []
    for activity in activities:
        date_str = activity.get('date')
        if date_str and date_str not in dates:
            dates.append(date_str)
    
    # Try to sort dates chronologically
    sorted_dates = []
    date_objects = []
    
    for date_str in dates:
        date_obj = parse_date(date_str)
        if date_obj:
            date_objects.append((date_str, date_obj))
    
    # Sort by the actual date objects
    date_objects.sort(key=lambda x: x[1])
    sorted_dates = [date_tuple[0] for date_tuple in date_objects]
    
    # Add any dates that couldn't be parsed at the end
    for date_str in dates:
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
    # Filter activities to only include those with locations
    activities_with_locations = [
        activity for activity in activities 
        if activity.get('location') and extract_address(activity.get('location'))
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
            <p>No activities with valid location information were found in the data.</p>
        </body>
        </html>
        """
    
    # Get unique dates for filtering
    unique_dates = get_unique_dates(activities_with_locations)
    
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
            html += f"<p><strong>Description:</strong> {marker['description']}</p>"
            
        if marker['additional_details']:
            html += f"<p><strong>Additional Details:</strong> {marker['additional_details']}</p>"
        
        html += f"""
            <p><a href="{generate_google_maps_url(marker['address'])}" target="_blank">View on Google Maps</a></p>
            <p><small>Source: {source_link}</small></p>
        </div>
        """
    
    # Close sidebar and add map script
    html += """
            </div>
        </div>

        <script>
        // Global variables
        let map;
        let markers = [];
        let activitiesData = [];
        let infowindow;
        
        function initMap() {
            // Create map
            map = new google.maps.Map(document.getElementById('map'), {
                zoom: 10,
                center: {lat: 0, lng: 0},  // Will be auto-centered based on markers
                mapTypeControl: true,
                streetViewControl: true,
                fullscreenControl: true
            });
            
            const bounds = new google.maps.LatLngBounds();
            const geocoder = new google.maps.Geocoder();
            infowindow = new google.maps.InfoWindow();
            
            // Define marker data
            activitiesData = [
    """
    
    # Add marker data as JavaScript array
    for i, marker in enumerate(markers_data):
        html += f"""
                {{
                    address: "{marker['address']}",
                    name: "{marker['name']}",
                    date: "{marker['date'] or ''}",
                    time: "{marker['time']}",
                    description: "{marker['description']}",
                    timePeriod: "{marker['time_period']}",
                    color: "{marker['color']}",
                    activityId: "activity-{i}",
                    content: `<h3><span style="display: inline-flex; align-items: center; justify-content: center; width: 25px; height: 25px; border-radius: 50%; background-color: {marker['color']}; color: white; font-weight: bold; margin-right: 10px; font-size: 14px;">{i + 1}</span>{marker['name']}</h3>
                            <p><strong>Date:</strong> {marker['date'] or 'Not specified'}</p>
                            <p><strong>Time:</strong> {marker['time']}</p>
                            <p><strong>Location:</strong> {marker['full_location']}</p>
                            <p><a href="{generate_google_maps_url(marker['address'])}" target="_blank">View on Google Maps</a></p>`
                }}{"," if i < len(markers_data) - 1 else ""}
        """
    
    html += """
            ];
            
            // Geocode and add markers
            activitiesData.forEach((markerData, index) => {
                geocodeAndAddMarker(geocoder, map, bounds, infowindow, markerData, index);
            });
        }
        
        function geocodeAndAddMarker(geocoder, map, bounds, infowindow, markerData, index) {
            geocoder.geocode({ 'address': markerData.address }, function(results, status) {
                if (status === 'OK') {
                    // Create custom marker with color from markerData
                    const markerIcon = {
                        path: google.maps.SymbolPath.CIRCLE,
                        fillColor: markerData.color,
                        fillOpacity: 0.9,
                        strokeWeight: 2,
                        strokeColor: "#ffffff",
                        scale: 10
                    };
                    
                    const marker = new google.maps.Marker({
                        map: map,
                        position: results[0].geometry.location,
                        title: markerData.name,
                        animation: google.maps.Animation.DROP,
                        icon: markerIcon,
                        label: {
                            text: (index + 1).toString(),
                            color: 'white',
                            fontSize: '10px'
                        }
                    });
                    
                    // Store additional data with marker
                    marker.date = markerData.date;
                    marker.timePeriod = markerData.timePeriod;
                    marker.activityId = markerData.activityId;
                    marker.dataIndex = index;  // Store the original index from activitiesData
                    
                    markers.push(marker);
                    bounds.extend(results[0].geometry.location);
                    
                    // Fit map to all markers
                    map.fitBounds(bounds);
                    
                    // Add info window
                    marker.addListener('click', function() {
                        infowindow.setContent(markerData.content);
                        infowindow.open(map, marker);
                        
                        // Scroll the activity into view in the sidebar
                        const activityElement = document.getElementById(marker.activityId);
                        if (activityElement) {
                            activityElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            highlightActivity(marker.activityId);
                        }
                    });
                    
                    // Adjust zoom if necessary
                    if (markers.length === activitiesData.length) {
                        google.maps.event.addListenerOnce(map, 'bounds_changed', function() {
                            if (map.getZoom() > 15) {
                                map.setZoom(15);
                            }
                        });
                    }
                } else {
                    console.error('Geocode was not successful for the following reason: ' + status);
                }
            });
        }
        
        // Function to show marker when title is clicked
        function showMarker(index) {
            // Find the marker that corresponds to this activity index
            const marker = markers.find(m => m.dataIndex === index);
            
            if (marker) {
                // Center the map on the marker
                map.setCenter(marker.getPosition());
                map.setZoom(14);
                
                // Open the info window
                infowindow.setContent(activitiesData[index].content);
                infowindow.open(map, marker);
                
                // Highlight the activity
                highlightActivity(marker.activityId);
            } else {
                console.error('Marker not found for index:', index);
            }
        }
        
        // Highlight the clicked activity
        function highlightActivity(activityId) {
            // Remove highlight from all activities
            document.querySelectorAll('.activity').forEach(el => {
                el.style.backgroundColor = '';
                el.style.borderColor = '#ddd';
            });
            
            // Add highlight to selected activity
            const activityElement = document.getElementById(activityId);
            if (activityElement) {
                activityElement.style.backgroundColor = '#f7f7f7';
                activityElement.style.borderColor = '#0078d7';
            }
        }
        
        function filterMarkers() {
            const dateFilter = document.getElementById('date-filter').value;
            const timeFilters = Array.from(document.querySelectorAll('input[type="checkbox"]:checked')).map(cb => cb.value);
            
            // Filter markers on map
            markers.forEach(marker => {
                const dateMatches = dateFilter === 'all' || marker.date === dateFilter;
                const timeMatches = timeFilters.includes(marker.timePeriod);
                marker.setVisible(dateMatches && timeMatches);
            });
            
            // Filter activities in sidebar
            const activityElements = document.querySelectorAll('.activity');
            activityElements.forEach(el => {
                const activityDate = el.getAttribute('data-date');
                const activityTime = el.getAttribute('data-time-period');
                
                const dateMatches = dateFilter === 'all' || activityDate === dateFilter;
                const timeMatches = timeFilters.includes(activityTime);
                
                el.style.display = (dateMatches && timeMatches) ? 'block' : 'none';
            });
        }
        </script>
        <script async defer
        src="https://maps.googleapis.com/maps/api/js?key={GOOGLE_API_KEY}&callback=initMap">
        </script>
    </body>
    </html>
    """
    
    # Replace the API key placeholder with the actual key
    html = html.replace("{GOOGLE_API_KEY}", GOOGLE_API_KEY)
    
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