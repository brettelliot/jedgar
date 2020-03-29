from bs4 import BeautifulSoup
import requests
import sys

class Jedgar():

    def __init__(self):
        print('Hello')

def main():
    jedgar = Jedgar()

    # Access page
    cik = '0000051143' # IBM
    #cik = '0001341439' # Oracle
    type = '10-Q'
    dateb = '20160101'

    # Obtain HTML for search page
    base_url = "https://www.sec.gov/cgi-bin/browse-edgar" \
        "?action=getcompany&CIK={}&type={}&dateb={}"
    url = base_url.format(cik, type, dateb)
    print(url)
    edgar_resp = requests.get(url)
    edgar_str = edgar_resp.text

    # Find the document link
    doc_link = ''
    soup = BeautifulSoup(edgar_str, 'html.parser')
    table_tag = soup.find('table', class_='tableFile2')
    rows = table_tag.find_all('tr')
    for row in rows:
        cells = row.find_all('td')
        if len(cells) > 3:
            #print(cells[1].a['href'])
            if '2015' in cells[3].text:
                doc_link = 'https://www.sec.gov' + cells[1].a['href']
                print(doc_link)
                break

    # Exit if document link couldn't be found
    if doc_link == '':
        print("Couldn't find the document link")
        sys.exit()

    # Obtain HTML for document page
    doc_resp = requests.get(doc_link)
    doc_str = doc_resp.text

    # Find the XBRL link
    xbrl_link = ''
    soup = BeautifulSoup(doc_str, 'html.parser')
    table_tag = soup.find('table', class_='tableFile', summary='Data Files')
    rows = table_tag.find_all('tr')
    for row in rows:
        cells = row.find_all('td')
        if len(cells) > 3:
            if 'INS' in cells[3].text:
                xbrl_link = 'https://www.sec.gov' + cells[2].a['href']

    # Obtain XBRL text from document
    xbrl_resp = requests.get(xbrl_link)
    xbrl_str = xbrl_resp.text

    # Find and print stockholder's equity
    soup = BeautifulSoup(xbrl_str, 'lxml')
    tag_list = soup.find_all()
    #breakpoint()
    for tag in tag_list:
        if tag.name == 'us-gaap:stockholdersequity':
            print("ContextRef: " + tag['contextref'] + " Stockholder's equity: " + tag.text)

main()
