import os 
import re

os.environ['PYWIKIBOT2_DIR'] = '../private/'
import pywikibot

# Task config

PAGE_LIST_FILE = 'pages.txt'

PATTERNS = (
	# find, replacement = '', reason = None, expected occurences = 0, flags = 0
	(r'$', '\nsomething', 'append something'),
	(r'8', 'eight', 'replace numbers with words')
)

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

if __name__ == '__main__':
	# PWB setup
	site = pywikibot.Site('PCGW')

	# Prepare patterns
	patterns = Patterns(PATTERNS)

	# Read pages to process
	page_titles = [l.rstrip() for l in open(PAGE_LIST_FILE)]

	bad_pages = {}
	
	# For each page to process ...
	for page_title in page_titles:
	
		# Get a PWB object for that page
		page = pywikibot.Page(site, page_title)

		# Does the page exists? We don't use .exists() since we can't really
		# do anything with an empty page and it's being cached for later
		if page.text == '':
			bad_pages.setdefault('page_not_found', []).append(page_title)
			continue

		
		page_content_new = page.text
		reasons = []
		
		# Actually replace content
		for find, repl, reason, exp, re_flags in patterns:
			page_content_new_2, repl_count = re.subn(find, repl, page_content_new, flags = re_flags)
			
			# Don't make changes if the expected replacements don't match
			if exp != 0 and exp != repl_count:
				bad_pages.setdefault('unexpected_count', []).append((repl_count, page_title))
				continue
			
			# Keep changes
			page_content_new = page_content_new_2

			# Add reason, if this pattern did something
			if repl_count > 0 and reason is not None and reason not in reasons:
				reasons.append(reason)
		
		# Commit changes
		page.text = page_content_new
		page.save(summarizer(reasons))
	
	# TODO: save to file or something
	print(bad_pages)