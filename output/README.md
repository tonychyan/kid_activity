# Kids Activity Locator - Output

This directory contains the extracted information from your activity screenshots.

## Files

- `activities.md`: A human-readable markdown file containing all the activities sorted by date.
- `activities.json`: A machine-readable JSON file containing all the raw extracted data.
- `map.html`: An interactive map showing all activity locations on Google Maps.

## Format

### Markdown File

The markdown file organizes activities in the following format:

```
# Kids Activities

## [Activity Name]

**Date:** YYYY-MM-DD

**Time:** Start Time - End Time

**Location:** Full address

**Description:** Brief description of the activity

**Additional Details:** Registration information, cost, etc.

**Source:** Original image filename

---
```

### JSON File

The JSON file contains an array of activity objects with the following structure:

```json
[
  {
    "activity_name": "Soccer Practice",
    "location": "123 Park Avenue, City, State, ZIP",
    "date": "2023-10-15",
    "time": "3:00 PM - 5:00 PM",
    "description": "Weekly soccer practice for kids ages 5-7",
    "additional_details": "Bring water and wear appropriate footwear. Cost: $10 per session.",
    "source_file": "original_screenshot.jpg"
  },
  ...
]
```

### Map File

The HTML map file provides an interactive Google Maps view with:

- Markers for each activity location
- Clickable markers that show activity details
- A sidebar listing all activities with dates, times, and descriptions
- Direct links to Google Maps for each location

**Interactive Features:**
- Click on activity titles in the sidebar to center the map on the corresponding pin
- View source images by clicking on the source filename links
- When you click a pin on the map, the corresponding activity is highlighted and scrolled into view in the sidebar
- Filter activities by date and time of day using the controls at the top
- Color-coded pins indicate the time of day (blue: morning, yellow: afternoon, green: evening, red: unknown)

To use the map:
1. The Google Maps JavaScript API key is automatically pulled from your .env file
2. Open the HTML file in a web browser 