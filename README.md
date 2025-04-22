# Kid Activity Locator

This project contains scripts to extract information about kids' activities from screenshots or images and visualize them on a map.

## Features

- **Data Extraction**
  - Extract activity information from images using vision AI
  - Process all images at once or only new images incrementally
  - Organize activities by date in a markdown file
  - Accumulate data over time in JSON format

- **Interactive Map**
  - Visualize all activity locations on Google Maps
  - Filter activities by date and time of day
  - Color-coded pins based on time of day
  - Clickable activity titles that highlight corresponding map pins
  - Source image links that open the original screenshots
  - Two-way synchronization between map pins and activity list

## How to Use

### Phase 1: Activity Information Extraction

1. Place your screenshots or images in the `input` folder (or in `input/new` for incremental processing)
2. Set up your OpenAI API key in the `.env` file
3. Run the extraction script with one of the following options:
```bash
# Activate the virtual environment
source .venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Run the activity extractor (processes all images in input/)
python activity_extractor.py

# Process only new images from input/new/ and append to existing data
python activity_extractor.py --new-only

# Only sanitize dates in existing activities.json file without processing any images
# Use this to fix dates without creating duplicates
python activity_extractor.py --sanitize-only
```
4. View the organized activity information in `output/activities.md`

### Command-line Options

- `--new-only`: Process only new images from the `input/new` directory and add them to existing data
- `--sanitize-only`: Only sanitize dates in the existing activities.json file without processing images
  - Corrects years that are not 2025
  - Assigns dates to activities with null dates by using a priority-based approach:
    1. Extracts day names (Monday, Tuesday, etc.) from raw date/time text
    2. Detects month and day mentions (e.g., "April 15")
    3. Identifies month-only mentions and assigns a mid-month date
    4. Recognizes seasonal references (spring, summer, etc.)
    5. Assigns a reasonable default date if no hints are available
- `--save-raw`: Save the raw LLM responses to JSON files (in `output/raw_responses/`)
  - This preserves the exact API responses to avoid paying for duplicate LLM calls
  - Useful when debugging or if you want to reprocess later without incurring API costs
- `--from-raw`: Process activities from saved raw responses instead of calling the LLM
  - Allows you to recover from errors without paying for API calls again
  - Useful if the original processing failed but you already have the raw responses

### Error Recovery Process

If the processing fails (especially during date sanitization), the script saves the current state to `output/activities_error.json`. You can recover by following these steps:

1. If you used `--save-raw` when running the original extraction, run:
   ```bash
   python activity_extractor.py --from-raw
   ```

2. If you didn't save the raw responses, you can still recover by fixing the JSON:
   ```bash
   # Manually edit the activities_error.json file to fix any issues
   # Then run sanitization on the fixed file
   mv output/activities_error.json output/activities.json
   python activity_extractor.py --sanitize-only
   ```

This multi-stage approach ensures you never lose API call results, even if there are errors in processing.

### Date Processing

The system extracts date information from images using two complementary approaches:

1. **Raw Date Extraction**: The LLM vision model captures the exact date/time text from the image (e.g., "This Sunday at 2pm") and stores it in the `raw_datetime` field.

2. **Structured Date Format**: The LLM also attempts to standardize the date in YYYY-MM-DD format when possible.

3. **Date Sanitization**: The sanitize process ensures all dates:
   - Use the correct year (2025)
   - Have valid values for null dates based on textual clues
   - Map day names (like "Friday") to actual calendar dates

This multi-layered approach ensures reliable date information even when images contain ambiguous or partial dates.

### Phase 2: Map Visualization

1. After running the activity extractor, run the map generator:
```bash
# Make sure the virtual environment is activated
source .venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Run the map generator
python map_generator.py
```
2. Get a Google Maps JavaScript API key from the [Google Cloud Console](https://console.cloud.google.com/) if you don't have one already
3. Add your Google Maps API key to the `.env` file as `GOOGLE_API_KEY=your_key_here`
4. Open `output/map.html` in a web browser to view the map

## Deploying to GitHub Pages

You can share the Kid Activity Locator with non-technical people by hosting it on GitHub Pages. This provides a free, accessible web page that anyone can view without installing anything.

### Steps to Deploy:

1. **Create a GitHub Repository**:
   - Create a new repository on GitHub (e.g., `kid_activity`)
   - The repository can be public since no API keys are included in the output files

2. **Generate the Map with the Correct Base URL**:
   ```bash
   # Replace 'your-repo-name' with your actual repository name
   python map_generator.py --base-url /your-repo-name
   ```
   This ensures image links work correctly on GitHub Pages.

   Google Analytics tracking (G-5831K3EZ32) is now automatically included in all generated maps, so there's no need to specify an analytics ID.

3. **Upload Your Files**:
   - Copy or commit these files to your repository:
     - `output/map.html` (rename to `index.html` at the repository root)
     - `output/activities.json`
     - `input/` directory (with all your image files)

4. **Enable GitHub Pages**:
   - Go to your repository settings
   - Navigate to the "Pages" section
   - Select "main" as the source branch
   - Save the changes

5. **Access Your Website**:
   - After a few minutes, your site will be available at:
     `https://yourusername.github.io/your-repo-name/`

### Tracking Visitor Statistics

Your site automatically includes Google Analytics tracking (G-5831K3EZ32). To view visitor statistics:

1. **Access Google Analytics Dashboard**:
   - Go to https://analytics.google.com/
   - Sign in with the Google account that has access to the G-5831K3EZ32 property
   - Navigate to the reporting section to view visitor data

### Updating the Website

When you have new activities:
1. Run the extraction and map generation scripts locally
2. Regenerate the map with the correct base URL:
   ```bash
   python map_generator.py --base-url /your-repo-name
   ```
3. Copy the updated files to your GitHub repository
4. Commit and push the changes

Your website will automatically update with the new activities!

## Requirements

- Python 3.6 or higher
- OpenAI API key with access to vision models (for activity extraction)
- Google Maps JavaScript API key (for map visualization)
- Dependencies listed in `requirements.txt`

## Output Files

- `activities.md`: A human-readable markdown file with activities sorted by date
- `activities.json`: A machine-readable JSON file with all extracted data
- `map.html`: An interactive map showing all activity locations

See the `output/README.md` for more details on the output format.
