import os
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from datetime import datetime
import re
import argparse
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def mkdir(path):
    # Create a directory if it doesn't exist
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except FileExistsError:
            pass

# Set up the base directory to save downloaded papers
BASE_DIR = "Papers"
mkdir(BASE_DIR)

class Config:
    DEFAULT_QUERIES = ["fairness", "machine learning", "synthetic data generation"]
    DEFAULT_START_YEAR_MONTH = "202301"
    DEFAULT_END_YEAR_MONTH = "202312"
    DEFAULT_NUM_PAPERS = 5

# Set the path for the CSV file to save the list of downloaded papers
csv_path = os.path.join(BASE_DIR, "paper_list.csv")

# Create an empty CSV if it doesn't exist to store paper information
if not os.path.exists(csv_path):
    df = pd.DataFrame(columns=["Download Date", "YearMonth", "Title", "Journal", "First Author"])
    df.to_csv(csv_path, index=False)

def read_downloaded_papers():
    # Read the CSV file to get a list of already downloaded papers to avoid duplicates
    return pd.read_csv(csv_path)

def save_all_paper_info(all_paper_info):
    # Save all the gathered paper information into the CSV at once to minimize I/O operations
    df = read_downloaded_papers()
    new_df = pd.DataFrame(all_paper_info)
    df = pd.concat([df, new_df], ignore_index=True)
    df.to_csv(csv_path, index=False)

def fetch_arxiv_papers(queries, start_year_month, end_year_month=None, num_papers=5, downloaded_titles=[]):
    # If end_year_month is not provided, use the current year and month
    if not end_year_month:
        end_year_month = datetime.now().strftime("%Y%m")
    # Generate the search URL by joining multiple keywords
    # Enclose each query term in double quotes for exact phrase matching
    quoted_queries = [f'"{q}"' for q in queries]
    query_string = '+AND+'.join(quoted_queries)
    search_url = f"https://arxiv.org/search/?query={query_string}&searchtype=all&abstracts=show&order=-announced_date_first&size=200"
    # Use a Chrome driver to open the web page
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # run in headless mode to avoid opening a browser window
    chrome_options.add_argument("--disable-usb-log-level")  # disable logging
    chrome_options.add_argument("--log-level=3")  # set log level

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(search_url)
    
    # Wait for the page to fully load
    time.sleep(2)
    
    papers = []
    # Use BeautifulSoup to parse the HTML content
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    entries = soup.find_all('li', class_='arxiv-result')
    
    for entry in entries:
        if len(papers) >= num_papers:
            break

        title = entry.find('p', class_='title').text.strip()
        if title in downloaded_titles:
            continue
        
        # Extracting the year and month from the originally announced date
        published_info = entry.find('p', class_='is-size-7').text.strip()
        match = re.search(r'originally announced (\w+ \d{4})', published_info)
        if match:
            date_str = match.group(1)  # E.g., 'June 2024'
            year_month = datetime.strptime(date_str, "%B %Y").strftime("%Y%m")  # Convert to '202406'

            authors = entry.find('p', class_='authors').text.replace('Authors:', '').split(',')[0].strip()
            pdf_link_tag = entry.find('a', attrs={'href': lambda x: x and 'pdf' in x})
            if pdf_link_tag is None:
                continue
            pdf_link = pdf_link_tag['href']
            papers.append({
                "Download Date": datetime.today().strftime('%Y%m%d'),
                "YearMonth": year_month,
                "Title": title,
                "First Author": authors,
                "PDF Link": pdf_link,
                "Journal": "arXiv"
            })
    
    # Close the browser after fetching the papers
    driver.quit()
    return papers

def download_papers(papers, download_dir):
    # Download each paper from the list
    for paper in papers:
        title = paper['Title'].replace(':', '').replace('/', '-')
        pdf_path = os.path.join(download_dir, f"{paper['YearMonth']}_{title}.pdf")
        if not os.path.exists(pdf_path):
            response = requests.get(paper['PDF Link'])
            with open(pdf_path, 'wb') as file:
                file.write(response.content)
            print(f"Downloaded: {paper['YearMonth']} {title}")
        else:
            print(f"Already downloaded: {title}")

def main(queries, start_year_month, end_year_month, num_papers):
    today = datetime.today().strftime('%Y%m%d')
    download_dir = os.path.join(BASE_DIR, today)
    mkdir(download_dir)

    print("-"*50)
    print(f"[{today}] Crawling papers from arXiv from {start_year_month} to {end_year_month}")
    print("-"*50)

    downloaded_papers = read_downloaded_papers()
    downloaded_titles = downloaded_papers['Title'].tolist()

    papers = fetch_arxiv_papers(queries, start_year_month, end_year_month, num_papers=num_papers, downloaded_titles=downloaded_titles)
    download_papers(papers, download_dir)

    all_paper_info = []
    for paper in papers:
        all_paper_info.append({
            "Download Date": today,
            "YearMonth": paper['YearMonth'],
            "Title": paper['Title'],
            "Journal": paper['Journal'],
            "First Author": paper['First Author']
        })
    save_all_paper_info(all_paper_info)

    print("-"*25 + ' Done ' + "-"*25)

if __name__ == "__main__":
    queries_input = input(f"Enter keywords to search for papers (comma-separated, e.g., {Config.DEFAULT_QUERIES}): ")
    # Split by comma, strip whitespace, and remove leading/trailing quotes
    queries = [q.strip().strip("'").strip('"') for q in queries_input.split(',')] if queries_input else Config.DEFAULT_QUERIES

    start_year_month = input(f"Enter start year and month in YYYYMM format (default: {Config.DEFAULT_START_YEAR_MONTH}): ") or Config.DEFAULT_START_YEAR_MONTH
    end_year_month = input(f"Enter end year and month in YYYYMM format (default: {Config.DEFAULT_END_YEAR_MONTH}): ") or Config.DEFAULT_END_YEAR_MONTH
    
    while True:
        num_papers_input = input(f"Enter number of papers to download (default: {Config.DEFAULT_NUM_PAPERS}): ") or str(Config.DEFAULT_NUM_PAPERS)
        try:
            num_papers = int(num_papers_input)
            break
        except ValueError:
            print("Invalid input. Please enter a number for the number of papers.")

    main(queries, start_year_month, end_year_month, num_papers)
