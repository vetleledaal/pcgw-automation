import xml.etree.ElementTree as ET
import re
import pickle
import os

os.environ['PYWIKIBOT2_DIR'] = '../private/'
import pywikibot
import json
import logging
import MySQLdb


from collections import namedtuple
WikiGame = namedtuple('WikiGame', ('name', 'gapl_id', 'drm', 'steam_id', 'win', 'osx', 'lin'))
SteamID = namedtuple('SteamID', ('type', 'id'), defaults=(None, None))

def parse_gapl_data():
	
	gapl_data = []
	
	tree = ET.parse('../data_gapl/feed.xml')
	products = tree.getroot()
	
	for product in products:
		# Steam ID can exist regardless of delivery type
		gapl_steam_id = product.find('steam_id').text
		
		try:
			steam_id = SteamID(*gapl_steam_id.split('/'))
		except (ValueError, AttributeError):
			# Ignore bare Steam IDs as we don't know their type
			steam_id = SteamID()
		
		if steam_id.type == 'app':
			pass
		elif steam_id.type == 'sub':
			pass
		elif steam_id.type == 'bundle':
			pass

		# DRM can be (in order of occurences):
		# steam, uplay, origin, download, rockstarsocial, zenimax,
		# bethesdanet, giants, external, battlenet, arenanet, gog
		gapl_drm = product.find('delivery_type').text

		if gapl_drm == 'steam':
			drm = 'Steam'
		elif gapl_drm == 'uplay':
			drm = 'Uplay'
		elif gapl_drm == 'origin':
			drm = 'Origin'
		elif gapl_drm == 'bethesdanet':
			drm = 'Bethesda.net'
		elif gapl_drm == 'battlenet':
			drm = 'Battle.net'
		elif gapl_drm == 'gog':
			drm = 'GOG.com'
		else:
			# download, rockstarsocial, zenimax, giants, external, arenanet, ++
			drm = 'Unknown'
		
		platforms = product.find('platforms')
		win = platforms.find('pc').text == 'true'
		osx = platforms.find('mac').text == 'true'
		lin = platforms.find('linux').text == 'true'
		
		gapl_data.append(WikiGame(
			product.find('name').text,
			product.find('uid').text,
			drm,
			steam_id,
			win,
			osx,
			lin			
		))
	return gapl_data

if __name__ == '__main__':
	

	logger = logging.getLogger('gamesplanet2pcgw')
	logger.setLevel(logging.WARNING)

	fh = logging.FileHandler('../gamesplanet2pcgw.log')
	fh.setLevel(logging.WARNING)

	ch = logging.StreamHandler()
	ch.setLevel(logging.ERROR)
	
	formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	fh.setFormatter(formatter)
	ch.setFormatter(formatter)
	logger.addHandler(fh)
	logger.addHandler(ch)

	gapl_data = parse_gapl_data()
	
	REGEX_STEAM_IDS = re.compile(r'\|steam appid *= *([^\r\n\|]+)', re.IGNORECASE)
	REGEX_STORE_FIND = re.compile(r'^{{Availability\/Row\|\s*(?:1\s*=\s*)?([^\|]+?)\s*\|\s*(?:1\s*=\s*)?([^\s]+).+', re.MULTILINE | re.IGNORECASE)
	REGEX_STORE_STEAM_OSES = re.compile(r'{{Availability\/Row\|\s*(?:1\s*=\s*)?Steam.+\|\s*([^}]+?)\s*}}', re.IGNORECASE)
	REGEX_STORE_UPLAY_OSES = re.compile(r'{{Availability\/Row\|\s*(?:1\s*=\s*)?Uplay.+\|\s*([^}]+?)\s*}}', re.IGNORECASE)
	REGEX_STORE_ORIGIN_OSES = re.compile(r'{{Availability\/Row\|\s*(?:1\s*=\s*)?Origin.+\|\s*([^}]+?)\s*}}', re.IGNORECASE)
	
	with open('../private/mysql_passwd', 'r') as f:
		mysql_passwd = f.readline().rstrip()
	db = MySQLdb.connect(user='root', passwd=mysql_passwd, db='steamdb2')
	c = db.cursor()

	os.environ['PYWIKIBOT2_DIR'] = '../private/'
	site = pywikibot.Site('PCGW')
	gapl_data = sorted(gapl_data, key=lambda tup: tup[0])
	for wiki_game in gapl_data:	
		# Ignore apps without Steam for now
		if wiki_game.steam_id.type != 'app':
			if wiki_game.steam_id.type:
				#logger.warning('No Steam ID of type app, Title: %s, DRM: %s, GAPL ID: %s, Steam ID Type: %s, Steam ID: %s' % (wiki_game.name, wiki_game.drm, wiki_game.gapl_id, wiki_game.steam_id.type, wiki_game.steam_id.id))
				pass
			else:
				logger.warning('No Steam ID at all, Title: %s, DRM: %s, GAPL ID: %s' % (wiki_game.name, wiki_game.drm, wiki_game.gapl_id))
			continue
			
		# Check if 'parent', 'dlcforappid' or 'mustownapptopurchase' exist.
		# is a DLC if it does
		rows_returned = c.execute('''
		SELECT 0 FROM `appsinfo` WHERE `AppID` = %s AND (`Key` = 10 OR `Key` = 14 OR `Key` = 28)
		''', (wiki_game.steam_id.id,))
		if rows_returned > 0:
			#logger.warning('DLC, Title: %s, DRM: %s, GAPL ID: %s, Steam ID Type: %s, Steam ID: %s' % (wiki_game.name, wiki_game.drm, wiki_game.gapl_id, wiki_game.steam_id.type, wiki_game.steam_id.id))
			continue

		# Temporary: skip the thing, because we want to catch *everthing else*
		continue
		params = {
			'action': 'askargs',
			'conditions': 'Steam AppID::' + str(wiki_game.steam_id.id),
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
			pcgw_steam_ids = [x.strip() for x in m.group(1).split(',')]
			if wiki_game.steam_id.id not in pcgw_steam_ids:
				# Not the main appid (DLC or something)
				continue
			
			# Does PCGW already link to Gamesplanet?
			ms = re.finditer(REGEX_STORE_FIND, page_text)
			gapl_count = 0
			store_offset = dict()
			early_quit = False
			for m in ms:
				store = m.group(1).lower()
				if store not in store_offset.keys():
					store_offset[store] = m.span()
				else:
					# Update end
					store_offset[store] = (store_offset[store][0], m.end())
				if store == 'gamesplanet':
					gapl_count += 1
					if wiki_game.gapl_id == m.group(2):
						# Got what we wanted, nothing to do for this page
						early_quit = True
						break
			if early_quit:
				continue
			
			# Our link doesn't exist :(
			
			if gapl_count > 0:
				logger.warning('PCGW links to GAPL, but not how we want it to for page %s, Steam ID %s and GAPL ID %s' % (page_title, wiki_game.steam_id.id, wiki_game.gapl_id))
				continue
			
			# Figure out where to add our ID
			insert_after = ['gamersgate', 'epic games store', 'discord', 'bethesda.net', 'battle.net', 'amazon.co.uk', 'amazon.com', 'amazon', 'official', 'publisher', 'retail']
			insert_before = ['gog', 'gog.com', 'gmg', 'humble bundle', 'humble', 'itch.io', 'macapp', 'mac app store', 'microsoft store', 'oculus', 'oculus store', 'origin', 'steam', 'steam-sub', 'twitch', 'uplay', 'viveport']
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
				logger.warning('Couldn\'t find place to put GAPL link for page %s, Steam ID %s and GAPL ID %s' % (page_title, wiki_game.steam_id.id, wiki_game.gapl_id))
				continue
			
			# Steal OS list from Steam
			if wiki_game.drm == 'Steam':
				m = re.search(REGEX_STORE_STEAM_OSES, page_text)
			elif wiki_game.drm == 'Uplay':
				m = re.search(REGEX_STORE_UPLAY_OSES, page_text)
			elif wiki_game.drm == 'Origin':
				m = re.search(REGEX_STORE_ORIGIN_OSES, page_text)
			else:
				m = None

			if m is None:
				# Couldn't steal OSes :/
				logger.warning('Couldn\'t steal OSes from %s for page %s, Steam ID %s and GAPL ID %s' % (wiki_game.drm, page_title, wiki_game.steam_id.id, wiki_game.gapl_id))
				continue
				
			OSes = m.group(1)
			
			new_text = page_text[:insert_at] + '{{Availability/row| Gamesplanet | ' + wiki_game.gapl_id + ' | ' + wiki_game.drm + ' |  |  | ' + OSes + ' }}\n' + page_text[insert_at:]
			page.text = new_text
			page.save(u'Add Gamesplanet')
			break
