import xml.etree.ElementTree as ET
import re
import pickle
import pywikibot
import json
import logging
import os


def parse_sitemap():
	# https://www.greenmangaming.com/Sitemap.xml
	ET.parse('../gmg_data/Sitemap.xml')

def parse_gmg_data():

	gmg_data = set()
	
	# https://s3.amazonaws.com/gmg-epilive/US%20Dollar.xml
	# https://s3.amazonaws.com/gmg-epilive/Sterling.xml
	# https://s3.amazonaws.com/gmg-epilive/Euro.xml
	region_files = ( \
		'US Dollar.xml', \
		'Sterling.xml', \
		'Euro.xml', \
	)
	for region_file in region_files:
        region_file = '../gmg_data/' + region_file
		gmg_data_usd = ET.parse(region_file)
		products = gmg_data_usd.getroot()
		for product in products:
			steam_id = product.find('steamapp_id')
			if steam_id is None:
				continue
			try:
				steam_id = int(steam_id.text)
			except:
				continue
			if steam_id == 0:
				continue
			
			drm = product.find('drm')
			if drm is None:
				continue
			drm = drm.text
			
			if drm in ['Steam', 'Uplay', 'Origin']:
				pass
			elif drm == 'Playfire':
				drm = 'Playfire Client'
			elif drm == 'Battle net':
				drm = 'Battle.net'
			elif drm == 'New Uplay':
				drm = 'Uplay'
			elif drm == 'Oculus Home':
				drm = 'Oculus'
			elif drm == 'Epic Games':
				drm = 'Epic Games Store'
			else:
				# Unknown drm
				drm = 'Unknown'			
			
			m = re.search(r'/games/([^/]+)/', product.find('deep_link').text)
			if m is None:
				continue
			
			gmg_id = m.group(1)
			gmg_data.update([(gmg_id, steam_id, drm)])
	pickle.dump(gmg_data, open('../gmg_data/gmg_data.p', 'wb'))
	return gmg_data

	# return pickle.load(open('gmg_data.p', 'rb'))

if __name__ == '__main__':
	

	logger = logging.getLogger('gmg2pcgw')
	logger.setLevel(logging.WARNING)

	fh = logging.FileHandler('../gmg2pcgw.log')
	fh.setLevel(logging.WARNING)

	ch = logging.StreamHandler()
	ch.setLevel(logging.ERROR)
	
	formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	fh.setFormatter(formatter)
	ch.setFormatter(formatter)
	logger.addHandler(fh)
	logger.addHandler(ch)

	gmg_data = parse_gmg_data()
	
	REGEX_STEAM_IDS = re.compile(r'\|steam appid *= *([^\r\n\|]+)', re.IGNORECASE)
	REGEX_STORE_GMG_FIND = re.compile(r'^{{Availability\/Row\|\s*(?:1\s*=\s*)?([^\|]+?)\s*\|\s*(?:1\s*=\s*)?([^\s]+).+', re.MULTILINE | re.IGNORECASE)
	REGEX_STORE_STEAM_OSES = re.compile(r'{{Availability\/Row\|\s*(?:1\s*=\s*)?Steam.+\|\s*([^}]+?)\s*}}', re.IGNORECASE)
	
	os.environ['PYWIKIBOT2_DIR'] = '../private/'
	site = pywikibot.Site('PCGW')
	gmg_data = sorted(gmg_data, key=lambda tup: tup[1])
	for gmg_id, steam_id, drm in gmg_data:
		if steam_id <= 31840:
			continue
		print(steam_id)
		params = {
			'action': 'askargs',
			'conditions': 'Steam AppID::' + str(steam_id),
			'printouts': 'Steam AppID',
		}
		req = site._simple_request(**params)
		data = req.submit()
		
		results = data.get('query').get('results')
		
		for page_title in results:
			print(page_title)
			page = pywikibot.Page(site, page_title)
			page_text = page.text
			m = re.search(REGEX_STEAM_IDS, page_text)
			if m is None:
				# Couldn't find appid for this page,
				# probably not the main appid
				continue
			pcgw_steam_ids = [int(x.strip()) for x in m.group(1).split(',')]
			if steam_id not in pcgw_steam_ids:
				# Not the main appid (DLC or something)
				continue
			
			# Does PCGW already link to GMG?
			ms = re.finditer(REGEX_STORE_GMG_FIND, page_text)
			gmg_count = 0
			store_offset = dict()
			early_quit = False
			for m in ms:
				store = m.group(1).lower()
				if store not in store_offset.keys():
					store_offset[store] = m.span()
				else:
					# Update end
					store_offset[store] = (store_offset[store][0], m.end())
				if store == 'gmg':
					gmg_count += 1
					if str(gmg_id) == m.group(2):
						# Got what we wanted, nothing to do for this page
						early_quit = True
						break
			if early_quit:
				break
			
			# Our link doesn't exist :(
			
			if gmg_count > 0:
				logger.warning('PCGW links to GMG, but not how we want it to for page %s, appid %d and gmg id %s' % (page_title, steam_id, gmg_id))
				continue
			
			# Figure out where to add our ID
			insert_after = ['gog', 'gog.com', 'gamersgate', 'epic games store', 'discord', 'bethesda.net', 'battle.net', 'amazon.co.uk', 'amazon.com', 'amazon', 'official', 'publisher', 'retail']
			insert_before = ['humble bundle', 'humble', 'itch.io', 'macapp', 'mac app store', 'microsoft store', 'oculus', 'oculus store', 'origin', 'steam', 'steam-sub', 'twitch', 'uplay', 'viveport']
			insert_at = 0
			for thing in insert_after:
				if thing in store_offset.keys():
					insert_at = store_offset[thing][1] + 1 # After new line
					break
			for thing in insert_before:
				if thing in store_offset.keys():
					insert_at = store_offset[thing][0]
					break
			if insert_at == 0:
				logger.warning('Couldn\'t find place to put GMG link for page %s, appid %d and gmg id %s' % (page_title, steam_id, gmg_id))
				continue
			
			# Steal OS list from Steam
			m = re.search(REGEX_STORE_STEAM_OSES, page_text)
			if m is None:
				# Couldn't steal OSes :/
				logger.warning('Couldn\'t steal OSes from Steam for page %s, appid %d and gmg id %s' % (page_title, steam_id, gmg_id))
				continue
				
			OSes = m.group(1)
			
			new_text = page_text[:insert_at] + '{{Availability/row| GMG | ' + gmg_id + ' | ' + drm + ' |  |  | ' + OSes + ' }}\n' + page_text[insert_at:]
			page.text = new_text
			page.save(u'Add GMG')
