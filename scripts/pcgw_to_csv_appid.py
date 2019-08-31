import xml.etree.ElementTree as ET
from glob import glob
import csv
import re


# Set up regex
PATTERN_APPIDS = re.compile(r'^\|steam appid(?: side)? *= *([\d\t, ]*)', re.MULTILINE)

# Set up CSV
with open('../data_pcgw/pcgw_appids.csv', mode='w', newline='', encoding='utf-8') as f:
    csvw = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

    ns = {'mw': 'http://www.mediawiki.org/xml/export-0.10/'}
    for filename in glob('../data_pcgw/pcgw_games_*.xml'):
        tree = ET.parse(filename)
        root = tree.getroot()
        pages = root.findall('mw:page', ns)
        for page in pages:
            page_title = page.find('mw:title', ns).text
            page_contents = page.find('mw:revision', ns).find('mw:text', ns).text
            
            for m in re.finditer(PATTERN_APPIDS, page_contents):
                # Found some appids, write name and first appid to file
                first_appid = m.group(1).split(',')[0]
                if len(first_appid) > 0:
                    csvw.writerow([page_title, first_appid])