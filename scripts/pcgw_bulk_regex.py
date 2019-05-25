import os 
import re
import sys

os.environ['PYWIKIBOT2_DIR'] = '../private/'
import pywikibot

# Task config

PAGE_LIST_FILE = 'pages.txt'

PATTERNS = (
	# find, replacement, reason = None, expected occurences = 0, flags = 0
	(r'<noinclude>\[\[Category:Series]]<\/noinclude>', '<noinclude>[[Category:Series]]{{Series/ask}}</noinclude>', 'spice up the series page', 0), # Fix Series pages
	#(r'(?<!\[\[Category:Pages with corrupt images\]\])$', '\n[[Category:Pages with corrupt images]]', 'add category: [[Category:Pages with corrupt images]]', 1), # Add corrupt images category, if not already set
	(r'^([\ \t]*\|(?:(?!notes).)+?=[\ \t]*)yes$', r'\1true', 'replace yes/no with true/false', 0, re.MULTILINE),
	(r'^([\ \t]*\|(?:(?!notes).)+?=[\ \t]*)no$', r'\1false', 'replace yes/no with true/false', 0, re.MULTILINE),
	(r'^\|gogcom page\s*= ', r'|gogcom id    = ', 'update gogcom id', 0, re.MULTILINE),
	(r'^\|gogcom page side\s*= ', r'|gogcom id side = ', 'update gogcom id', 0, re.MULTILINE),
	(r'^(\|notes\s*= )(\s*\|fan\s*=[\ \t]*)\n\|fan notes\s*=[\ \t]*([^\n]*)', r'\1\3\2', 'move fan notes', 0, re.MULTILINE),
	(r'^(\|notes\s*= )([^\s]+?)\.?(\s*\|fan\s*=[\ \t]*)\n\|fan notes\s*=\s*([^\n]*?)\.?(?:$|\n)', r'\1\2. \4.\3', 'move fan notes', 0, re.MULTILINE),
	
	
)

REASON_OVERRIDE = None
#REASON_OVERRIDE = ''

# Task config END

class Patterns(object):
	def __init__(self, patterns):
		self.patterns = patterns
	
	def __iter__(self):
		self.n = 0
		return self
	
	def __next__(self):
		if self.n < len(self.patterns):
			n = self.patterns[self.n]
			self.n += 1
			return (
				n[0],
				n[1],
				n[2] if 2 < len(n) else None,
				n[3] if 3 < len(n) else 0,
				n[4] if 4 < len(n) else 0,
			)
		else:
			raise StopIteration

# Expects a list of unique reasons
def summarizer(reasons):
	summary = [r[0].upper() + r[1:] + '.' for r in reasons]

	# TODO: reduce summary text and add "+ x more rules applied." if length > 255
	# get total length: sum(len(s) for s in summary)
	return ' '.join(summary)[:255]

def save_callback(page, exception_instance):
	success = exception_instance is None
	print('\033[3%dm[%s]\033[0m %s' % (2 if success else 1, 'OK' if success else 'FAIL', page.title()), flush=True)

if __name__ == '__main__':
	# PWB setup
	site = pywikibot.Site('PCGW')

	# Prepare patterns
	patterns = Patterns(PATTERNS)

	# Read pages to process
	with open(PAGE_LIST_FILE, encoding='utf8') as f:
		page_titles = [l.rstrip() for l in f]
	
	print('To process:', page_titles[:5])
	bad_pages = {}
	
	try:
		# For each page to process ...
		for page_title in page_titles:
			# Get a PWB object for that page
			page = pywikibot.Page(site, page_title)

			# Get page contents
			page_content = page.text
			print('Got page with', len(page_content), 'bytes')
			
			# Does the page exists? We don't use .exists() since we can't really
			# do anything with an empty page and it's already cached
			if page_content == '':
				bad_pages.setdefault('page_not_found', []).append(page_title)
				print(bad_pages['page_not_found'][-1])
				continue

			
			page_content_new = page_content
			reasons = []
			
			# Actually replace content
			for find, repl, reason, exp, re_flags in patterns:
				page_content_new_2, repl_count = re.subn(find, repl, page_content_new, flags=re_flags)
				
				# Don't make changes if the expected replacements don't match
				if exp != 0 and exp != repl_count:
					bad_pages.setdefault('unexpected_count', []).append((repl_count, page_title))
					print(bad_pages['unexpected_count'][-1])
					continue
				
				# Keep changes
				page_content_new = page_content_new_2

				# Add reason, if this pattern did something
				if repl_count > 0 and reason is not None and reason not in reasons:
					reasons.append(reason)
			
			# Commit changes, if anything has changed
			if page_content != page_content_new:
				page.text = page_content_new
				page.save(summarizer(reasons), quiet=True, callback=save_callback)
			else:
				print('No changes?')
				print(reasons)
	except KeyboardInterrupt:
		pass

	# TODO: save to file or something
	print(bad_pages)