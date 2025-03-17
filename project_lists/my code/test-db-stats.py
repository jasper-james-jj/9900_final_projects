import requests
from bs4 import BeautifulSoup
import csv
import os
import time
import re
from datetime import datetime

# Configuration
BASE_URL = "https://www.austlii.edu.au/cgi-bin/viewdb/au/cases/wa/WASAT/"
OUTPUT_DIR = "wasat_data"
CASES_CSV = "wasat_cases.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/91.0.4472.124 Safari/537.36"
}

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)


def fetch_page(url):
    """Fetch a web page with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Failed to fetch {url} after {max_retries} attempts")
                return None


def extract_db_stats(html):
    """Extract database statistics from the page"""
    soup = BeautifulSoup(html, 'html.parser')

    # Find the database statistics section
    stats_section = soup.select_one('.side-statistics .db-stats')
    if not stats_section:
        print("Database statistics section not found")
        return None

    # Initialize stats dictionary
    stats = {
        'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'last_updated': None,
        'most_recent_document': None,
        'number_of_documents': None,
        'yearly_accesses': None
    }

    # Extract each statistic
    last_updated = stats_section.select_one('.last-updated strong')
    if last_updated:
        stats['last_updated'] = last_updated.text.strip()

    most_recent = stats_section.select_one('.most-recent strong')
    if most_recent:
        stats['most_recent_document'] = most_recent.text.strip()

    num_docs = stats_section.select_one('.number-docs strong')
    if num_docs:
        stats['number_of_documents'] = num_docs.text.strip().replace(',', '')

    yearly_access = stats_section.select_one('.accesses-yearly strong')
    if yearly_access:
        stats['yearly_accesses'] = yearly_access.text.strip().replace(',', '')

    return stats


def extract_years(html):
    """Extract available years from the year dropdown"""
    soup = BeautifulSoup(html, 'html.parser')

    # Find the year options list
    year_section = soup.select_one('.year-specific-options')
    if not year_section:
        print("Year options section not found")
        return []

    years = []
    # Look for all year links in the dropdown
    for year_link in year_section.select('li h5 a'):
        href = year_link.get('href', '')
        year_match = re.search(r'(\d{4})/?$', href)
        if year_match:
            years.append(year_match.group(1))

    return sorted(years, reverse=True)  # Most recent first


def extract_cases_by_year(year_url, year):
    """Extract case information from a specific year page"""
    print(f"Fetching cases for year {year} from {year_url}...")
    year_html = fetch_page(year_url)
    if not year_html:
        print(f"Failed to fetch year page for {year}")
        return []

    soup = BeautifulSoup(year_html, 'html.parser')
    cases = []

    # Find all sections (each section is a month)
    month_sections = soup.select('div.all-section')

    for section in month_sections:
        # Extract month name and year from the section title
        month_header = section.select_one('h2.card-title')
        if not month_header:
            continue

        month_year_text = month_header.text.strip()

        # Parse month name and year
        month_year_match = re.match(r'(\w+)\s+(\d{4})', month_year_text)
        if month_year_match:
            month_name = month_year_match.group(1)
            month_year = month_year_text

            # Convert month name to number
            month_names = ["January", "February", "March", "April", "May", "June",
                           "July", "August", "September", "October", "November", "December"]
            if month_name in month_names:
                month_num = str(month_names.index(month_name) + 1).zfill(2)
                formatted_date = f"{year}-{month_num}"  # YYYY-MM format
            else:
                formatted_date = month_year
        else:
            month_year = month_year_text
            formatted_date = month_year

        # Extract all case links in this section
        case_links = section.select('div.card ul li')

        for li in case_links:
            # Extract data-count if available (the number before the date)
            data_count = li.get('data-count', '')

            link = li.select_one('a')
            if not link:
                continue

            case_url = link.get('href', '')

            # Make sure the URL is absolute
            if case_url and not case_url.startswith('http'):
                if case_url.startswith('/'):
                    case_url = f"https://www.austlii.edu.au{case_url}"
                else:
                    case_url = f"https://www.austlii.edu.au/{case_url}"

            case_name = link.text.strip()

            # Extract case number using regex
            case_number_match = re.search(r'(\d+)\.html$', case_url)
            case_number = case_number_match.group(1) if case_number_match else "unknown"

            # Extract case date from the name if available
            date_match = re.search(r'\((\d+\s+\w+\s+\d{4})\)$', case_name)
            case_date = date_match.group(1) if date_match else ""

            # Format the case date if found
            if case_date:
                try:
                    date_parts = case_date.split()
                    if len(date_parts) == 3:
                        day, month_name, year = date_parts
                        month_names = ["January", "February", "March", "April", "May", "June",
                                       "July", "August", "September", "October", "November", "December"]
                        month_idx = month_names.index(month_name) + 1
                        formatted_case_date = f"{year}-{str(month_idx).zfill(2)}-{day.zfill(2)}"
                    else:
                        formatted_case_date = case_date
                except (ValueError, IndexError):
                    formatted_case_date = case_date
            else:
                formatted_case_date = ""

            cases.append({
                'year': year,
                'month_year': month_year,
                'formatted_date': formatted_date,
                'data_count': data_count,
                'case_name': case_name,
                'case_number': case_number,
                'case_date': case_date,
                'formatted_case_date': formatted_case_date,
                'url': case_url
            })

    print(f"Found {len(cases)} cases for year {year}")
    return cases


def collect_all_cases():
    """Collect information about all cases across all years"""
    print("Starting case collection...")
    all_cases = []

    # Fetch main page
    main_html = fetch_page(BASE_URL)
    if not main_html:
        print("Failed to fetch main page")
        return []

    # Extract database stats
    stats = extract_db_stats(main_html)
    if stats:
        print("Database Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Save database stats to CSV
        stats_csv = os.path.join(OUTPUT_DIR, "db_stats.csv")
        with open(stats_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=stats.keys())
            writer.writeheader()
            writer.writerow(stats)
        print(f"Saved database statistics to db_stats.csv")

    # Extract available years
    years = extract_years(main_html)
    if not years:
        print("No years found on the main page")
        return []

    print(f"Found {len(years)} years: {', '.join(years)}")

    # Save available years to CSV
    years_csv = os.path.join(OUTPUT_DIR, "available_years.csv")
    with open(years_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Year', 'URL'])
        for year in years:
            writer.writerow([year, f"{BASE_URL}{year}/"])
    print(f"Saved {len(years)} available years to available_years.csv")

    return 1
    # For each year, extract case information
    for year in years:
        year_url = f"{BASE_URL}{year}/"
        year_cases = extract_cases_by_year(year_url, year)
        all_cases.extend(year_cases)

        # Be nice to the server
        time.sleep(1)

    # Save all cases to CSV
    csv_path = os.path.join(OUTPUT_DIR, CASES_CSV)
    if all_cases:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'year',
                'month_year',
                'formatted_date',
                'data_count',
                'case_name',
                'case_number',
                'case_date',
                'formatted_case_date',
                'url'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_cases)

        print(f"Saved {len(all_cases)} cases to {CASES_CSV}")
    else:
        print("No cases found")

    return all_cases


if __name__ == "__main__":
    collect_all_cases()
