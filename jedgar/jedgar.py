from bs4 import BeautifulSoup
import requests
import sys
from datetime import datetime
from xbrl import XBRLParser, GAAP, GAAPSerializer, DEISerializer
import pprint
from io import StringIO

class Jedgar():

    def __init__(self):
        self.data_dict = {}
        self.data_dict['meta'] = {}
        self.data_dict['dei'] = {}
        self.data_dict['us-gaap'] = {}

    def _get_doc_link(self, cik, filing_type):

        # Obtain HTML for search page
        base_url = "https://www.sec.gov/cgi-bin/browse-edgar" \
            "?action=getcompany&CIK={}&type={}&dateb={}"
        today = datetime.today().strftime('%Y%m%d')
        url = base_url.format(cik, filing_type, today)
        self.data_dict['meta']['search url'] = url
        #print("SEC search page: ", url)
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
                filing_date = cells[3].text
                doc_link = 'https://www.sec.gov' + cells[1].a['href']
                self.data_dict['meta']['doc url'] = doc_link
                self.data_dict['meta']['filing_date'] = filing_date
                #print("doc_link: ", doc_link)
                #print("filing_date: ", filing_date)
                break

               # if '2015' in cells[3].text:
               #     doc_link = 'https://www.sec.gov' + cells[1].a['href']
               #     print(doc_link)
               #     break
        # Exit if document link couldn't be found
        if doc_link == '':
            print("Couldn't find the document link")
            sys.exit()

        return doc_link

    def _get_xbrl_link(self, doc_link):

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
                # Look for "EX-101.INS" or "XML" in type column
                if 'INS' in cells[3].text or 'XML' in cells[3].text:
                    xbrl_link = 'https://www.sec.gov' + cells[2].a['href']
                    self.data_dict['meta']['xbrl_link'] = xbrl_link
                    #print("xbrl_link: ", xbrl_link)
                    break

        # Exit if xbrl link couldn't be found
        if xbrl_link == '':
            print("Couldn't find the xbrl link")
            sys.exit()

        return xbrl_link

    def _parse_with_python_xbrl(self, xbrl_link):

        # Obtain XBRL text from document
        xbrl_resp = requests.get(xbrl_link)
        #xbrl_resp.raw.decode_content = True
        #xbrl_str = xbrl_resp.text

        xbrl_parser = XBRLParser(0)
        try:
            #xbrl = xbrl_parser.parse(xbrl_resp.raw)
            #xbrl_resp = xbrl_resp.read().decode('utf-8')
            xbrl = xbrl_parser.parse(StringIO(xbrl_resp.text))
        except Exception as e:
            print(e)
            exit()

        # Parse just the DEI data from the xbrl object
        dei_obj = xbrl_parser.parseDEI(xbrl)

        # Serialize the DEI data
        serializer = DEISerializer()
        result_dict = serializer.dump(dei_obj)
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(result_dict)
        #print(result_dict)

        try:
            #breakpoint()
            gaap_obj = xbrl_parser.parseGAAP(
                xbrl,
                #doc_date='20191231',
                doc_date='20200205',
                #doc_date=filing_date,
                #doc_date="20150930",
                #doc_date=today,
                #doc_date='20160101',
                context="current",
                ignore_errors=2
            )
        except Exception as e:
            #breakpoint()
            print(e)
            exit()

        # Serialize the GAAP data
        serializer = GAAPSerializer()
        result_dict2 = serializer.dump(gaap_obj)
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(result_dict2)

    def _parse_myself(self, xbrl_link):

        # Obtain XBRL text from document
        xbrl_resp = requests.get(xbrl_link)
        xbrl_str = xbrl_resp.text
        xbrl = BeautifulSoup(xbrl_str, 'lxml')
        tag_list = xbrl.find_all()

        # Get the first trading symbol
        for tag in tag_list:
            tag.name = tag.name.lower()
            if str('dei:TradingSymbol').lower() == tag.name:
                self.data_dict['dei']['trading_symbol'] = tag.text
                break

        for tag in tag_list:
            if str('dei:DocumentPeriodEndDate').lower() == tag.name:
                self.data_dict['dei']['document_period_end_date'] = tag.text
                self.data_dict['dei']['main_context'] = tag['contextref']
            elif str('dei:EntityRegistrantName').lower() == tag.name:
                self.data_dict['dei']['entity_registrant_name'] = tag.text
            elif str('dei:DocumentType').lower() == tag.name:
                self.data_dict['dei']['document_type'] = tag.text

        key_dict = {
            'revenues': 'revenues',
            'costofrevenue': 'cost_of_revenue',
            'earningspersharediluted': 'earnings_per_share_diluted',
            'deferredincometaxexpensebenefit':
            'deferred_income_tax_expense_benefit'

        }

        for tag in xbrl.find_all():
            if tag.has_attr('contextref') \
                and 'us-gaap' in tag.name \
                and self.data_dict['dei']['main_context'] == tag['contextref']:
                    short_name = tag.name[8:]
                    if short_name in key_dict:
                        try:
                            val = int(tag.text)
                        except ValueError:
                            val = float(tag.text)
                        self.data_dict['us-gaap'][key_dict[short_name]] = val


    def get_last_filing(self, cik, filing_type):

        doc_link = self._get_doc_link(cik, filing_type)

        xbrl_link = self._get_xbrl_link(doc_link)

        #self._parse_with_python_xbrl(xbrl_link)

        self._parse_myself(xbrl_link)

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.data_dict)



    def print_some_stuff(self, tag_list):

        for tag in tag_list:
            if 'dei' in tag.name:
                print("ContextRef: " + tag['contextref'] + " Name: " + tag.name
                      + " : "+ tag.text)

        #breakpoint()
        for tag in tag_list:
            if tag.name == 'us-gaap:stockholdersequity':
                print("ContextRef: " + tag['contextref'] + " Stockholder's equity: " + tag.text)

        count = 0
        for tag in tag_list:
            if tag.has_attr('contextref') \
                and 'us-gaap' in tag.name \
                and 'AS_OF_Dec31_2014_Entity_0000051143' in tag['contextref']:
                    count +=1
                    print(tag.name + ': ' + tag.text)
        print("Total: " + str(count))

def main():
    jedgar = Jedgar()

    # Access page
    cik = '0000051143' # IBM
    #cik = '0001341439' # Oracle
    #cik = '0001652044' # Google
    filing_type = '10-K'
    dateb = '20160101'

    jedgar.get_last_filing(cik, filing_type)


   # Obtain HTML for search page
   # base_url = "https://www.sec.gov/cgi-bin/browse-edgar" \
   #     "?action=getcompany&CIK={}&type={}&dateb={}"
   # url = base_url.format(cik, type, dateb)
   # print(url)
   # edgar_resp = requests.get(url)
   # edgar_str = edgar_resp.text

   # # Find the document link
   # doc_link = ''
   # soup = BeautifulSoup(edgar_str, 'html.parser')
   # table_tag = soup.find('table', class_='tableFile2')
   # rows = table_tag.find_all('tr')
   # for row in rows:
   #     cells = row.find_all('td')
   #     if len(cells) > 3:
   #         print(cells[1].a['href'])
   #         if '2015' in cells[3].text:
   #             doc_link = 'https://www.sec.gov' + cells[1].a['href']
   #             print(doc_link)
   #             break

   # # Exit if document link couldn't be found
   # if doc_link == '':
   #     print("Couldn't find the document link")
   #     sys.exit()

   # # Obtain HTML for document page
   # doc_resp = requests.get(doc_link)
   # doc_str = doc_resp.text

   # # Find the XBRL link
   # xbrl_link = ''
   # soup = BeautifulSoup(doc_str, 'html.parser')
   # table_tag = soup.find('table', class_='tableFile', summary='Data Files')
   # rows = table_tag.find_all('tr')
   # for row in rows:
   #     cells = row.find_all('td')
   #     if len(cells) > 3:
   #         if 'INS' in cells[3].text:
   #             xbrl_link = 'https://www.sec.gov' + cells[2].a['href']

   # # Obtain XBRL text from document
   # xbrl_resp = requests.get(xbrl_link)
   # xbrl_str = xbrl_resp.text

   # # Find and print stockholder's equity
   # soup = BeautifulSoup(xbrl_str, 'lxml')
   # tag_list = soup.find_all()
   # #breakpoint()
   # for tag in tag_list:
   #     if tag.name == 'us-gaap:stockholdersequity':
   #         print("ContextRef: " + tag['contextref'] + " Stockholder's equity: " + tag.text)

   # count = 0
   # for tag in tag_list:
   #     if tag.has_attr('contextref') \
   #         and 'us-gaap' in tag.name \
   #         and 'AS_OF_Dec31_2014_Entity_0000051143' in tag['contextref']:
   #             count +=1
   #             print(tag.name + ': ' + tag.text)
   # print("Total: " + str(count))




    '''
    xbrl = BeautifulSoup(xbrl_str, 'lxml')
    tag_list = xbrl.find_all()
    for tag in xbrl.find_all():
        tag.name = tag.name.lower()

    # self.print_some_stuff(tag_list)
    xbrl_parser = XBRLParser(0)

    # Parse just the DEI data from the xbrl object
    dei_obj = xbrl_parser.parseDEI(xbrl)

    # Serialize the DEI data
    serializer = DEISerializer()
    result_dict = serializer.dump(dei_obj)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(result_dict)
    #print(result_dict)

    # Serialize the GAAP data
    gaap_obj = xbrl_parser.parseGAAP(xbrl,
                             #doc_date="20131228",
                             doc_date=today,
                             context="current",
                             ignore_errors=0)

    result_dict = serializer.dump(gaap_obj)
    pp.pprint(result_dict)
    '''

main()

