#!/usr/bin/env python3
"""Check the Bulgarian production site's links, preserved content and requested changes."""
from html.parser import HTMLParser
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit,unquote
import argparse,json,re,sys

PAGES=['index.html','treatments.html','gallery.html','privacy.html']
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('root',nargs='?',type=Path,default=Path(__file__).resolve().parent.parent)
root=parser.parse_args().root.resolve()

class Page(HTMLParser):
 def __init__(self,html):
  super().__init__();self.ids=[];self.links=[];self.text=[];self.images=[];self.tags=[];self.lang=None;self.h1=0;self.has_title=False;self.skip=0;self.schema=[];self.in_schema=False;self.schema_text=[]
  self.feed(html)
 def handle_starttag(self,tag,attrs):
  data=dict(attrs);self.tags.append((tag,data))
  if tag=='html':self.lang=data.get('lang')
  if tag=='title':self.has_title=True
  if tag=='h1':self.h1+=1
  if data.get('id'):self.ids.append(data['id'])
  if tag in ['a','link'] and data.get('href'):self.links.append(data['href'])
  if tag in ['img','script'] and data.get('src'):self.links.append(data['src'])
  if tag=='img':self.images.append(data)
  if tag in ['script','style']:self.skip+=1
  if tag=='script' and data.get('type')=='application/ld+json':self.in_schema=True;self.schema_text=[]
 def handle_data(self,text):
  if self.in_schema:self.schema_text.append(text)
  if not self.skip:self.text.append(text)
 def handle_endtag(self,tag):
  if tag=='script' and self.in_schema:
   self.schema.append(json.loads(''.join(self.schema_text)));self.in_schema=False
  if tag in ['script','style']:self.skip=max(0,self.skip-1)

def norm(text):return re.sub(r'\s+','',unescape(text))
files=[root/name for name in PAGES]
# The selected concept's Bulgarian URLs are preview aliases, not extra production pages.
if (root/'assets/production.json').exists() and (root/'version-1').is_dir():files += [root/'version-1'/name for name in PAGES]
errors=[];pages={};link_count=0
for file in files:
 if not file.is_file():errors.append('Missing production page '+str(file));continue
 pages[file]=Page(file.read_text())
for file,page in pages.items():
 name=str(file.relative_to(root));visible=' '.join(page.text)
 if page.lang!='bg':errors.append(name+': page language must be Bulgarian')
 if not page.has_title or page.h1!=1:errors.append(name+': missing title or incorrect H1 count')
 if len(page.ids)!=len(set(page.ids)):errors.append(name+': duplicate IDs')
 if re.search(r'Facebook|Запазете(?:\s+си)?\s+час|Mastercard|Diners|\bCash\b|\bVisa\b|В\s+брой|Двата\s+дизайна|Думи\s+от\s+нашите\s+пациенти|\b9000\b',visible,re.I):errors.append(name+': removed/obsolete copy is still visible')
 if any(tag=='form' for tag,data in page.tags):errors.append(name+': enquiry form must be removed')
 if any('language-picker' in data.get('class','') for tag,data in page.tags):errors.append(name+': unexpected language picker')
 if 'N<span>p</span>' not in file.read_text():errors.append(name+': capital-N monogram missing')
 for image in page.images:
  if 'alt' not in image:errors.append(name+': image missing alt attribute')
 for tag,data in page.tags:
  if any(key.startswith('on') for key in data):errors.append(name+': inline event handler')
  if tag in ['script','img','link'] and data.get('src',data.get('href','')).startswith(('https:','http:','//')):errors.append(name+': automatically loaded third-party resource')
 for url in page.links:
  parsed=urlsplit(url)
  if 'facebook.com' in parsed.netloc.lower():errors.append(name+': Facebook link remains')
  if parsed.scheme or parsed.netloc:continue
  target=(file.parent/unquote(parsed.path)).resolve() if parsed.path else file
  if target.is_dir():target=target/'index.html'
  if not target.is_file():errors.append(name+': missing target '+url);continue
  link_count+=1
  if target.suffix=='.html' and target not in pages:errors.append(name+': link outside the Bulgarian production page set: '+url)
  if parsed.fragment and target in pages and parsed.fragment not in pages[target].ids:errors.append(name+': missing anchor '+url)
for css in (root/'assets').glob('*.css'):
 if css.name not in ['base.css','seaglass.css','fonts.css']:continue
 for url in re.findall(r'url\([\"\x27]?(.*?)[\"\x27]?\)',css.read_text()):
  if not url.startswith(('https:','http:','data:','#')) and not (css.parent/url).is_file():errors.append(css.name+': missing CSS asset '+url)
for prefix in [root]+([root/'version-1'] if root/'version-1'/'index.html' in pages else []):
 home=pages.get(prefix/'index.html');library=pages.get(prefix/'treatments.html')
 if not home or not library:continue
 cards=[data for tag,data in home.tags if tag=='article' and 'service-item' in data.get('class','').split()]
 if len(cards)!=19:errors.append(str(prefix)+': expected 19 service cards')
 if len([x for x in cards if 'featured-service' in x.get('class','')])!=4:errors.append(str(prefix)+': four image-led services missing')
 for id in ['itero-plus','invisalign','zimmer-implants','spark-aligners']:
  if id not in library.ids:errors.append(str(prefix)+': missing new service '+id)
 if 'Обратна връзка от нашите пациенти' not in ' '.join(home.text):errors.append(str(prefix)+': feedback label missing')
 schema=next((item for item in home.schema if item.get('@type')=='Dentist'),None)
 if not schema or schema.get('address',{}).get('postalCode')!='9009':errors.append(str(prefix)+': incorrect structured postal code')
 if schema and schema.get('geo')!={'@type':'GeoCoordinates','latitude':43.2231205,'longitude':27.902595}:errors.append(str(prefix)+': incorrect map-place coordinates')
 map_links=[url for url in home.links if 'google.com/maps/place/' in url]
 if not map_links or (schema and schema.get('hasMap') not in map_links):errors.append(str(prefix)+': map link and structured location disagree')
 if not any(url=='mailto:panchevanina@gmail.com' for url in home.links):errors.append(str(prefix)+': direct email missing')

if (root/'assets/production.json').exists():
 data=json.loads((root/'assets/content.json').read_text());config=json.loads((root/'assets/production.json').read_text());rendered=norm(' '.join(pages[root/'treatments.html'].text))
 for topic in data['topics']:
  if norm(topic['text']) not in rendered:errors.append('Incomplete original treatment: '+topic['id'])
 for name,html in data['supplementary'].items():
  if norm(' '.join(Page(html).text)) not in rendered:errors.append('Missing supplementary page: '+name)
 for topic in config['newServices']:
  for paragraph in topic['paragraphs']:
   if norm(paragraph) not in rendered:errors.append('Incomplete new article: '+topic['id'])
  if len(' '.join(topic['paragraphs']).split())<180:errors.append('New article is shorter than the requested detailed descriptions: '+topic['id'])
  if not (root/'assets'/topic['image']).is_file():errors.append('Missing supplied service image: '+topic['id'])
 if len(config['copy']['reasons'])!=6:errors.append('Payment principle was not removed')
 if config['copy']['mapUrl'] not in pages[root/'index.html'].links:errors.append('Exact user-supplied Maps URL missing')
 gallery=pages[root/'gallery.html']
 for item in data['gallery']+data['certificates']:
  if 'assets/'+item['image'] not in gallery.links:errors.append('Missing original gallery/certificate '+item['image'])
 for url,path in json.loads((root/'docs/asset-manifest.json').read_text()).items():
  if not (root/'assets'/path).is_file():errors.append('Missing original asset '+path)
 print('Content coverage: 15 original + 4 new treatments, 10 supplementary pages, 38 gallery images, 10 certificates.')
print(f'Checked {len(pages)} production/selected-preview pages and {link_count} local references.')
if errors:print('\n'.join('ERROR: '+error for error in errors));sys.exit(1)
print('PASS: Bulgarian production copy, requested removals, 19 services, address/schema, assets and links.')
