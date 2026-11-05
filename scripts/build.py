#!/usr/bin/env python3
"""Generate the selected Bulgarian static site. Browsing needs no build or dependencies."""
from pathlib import Path
from html import escape as esc
import json,re

ROOT=Path(__file__).resolve().parent.parent
DATA=json.loads((ROOT/'assets/content.json').read_text())
CONFIG=json.loads((ROOT/'assets/production.json').read_text())
COPY=CONFIG['copy']
NEW=CONFIG['newServices']
ARROW='<span aria-hidden="true">↗</span>'
PAGES=['index.html','treatments.html','gallery.html','privacy.html']
TOPICS=[dict(t,featured=True) for t in NEW]
for index,topic in enumerate(DATA['topics']):
 TOPICS.append(dict(topic,title=COPY['treatmentNames'][index],summary=COPY['summaries'][index],featured=False))


def img(path,alt='',cls='',eager=False):
 thumb='thumbs/'+Path(path).stem+'.webp'
 return f'<img src="assets/{thumb}" alt="{esc(alt)}" class="{cls}" loading="{"eager" if eager else "lazy"}" decoding="async"'+(' fetchpriority="high"' if eager else '')+'>'
def label(text):return f'<p class="eyebrow">{text}</p>'
def btn(href,text):return f'<a class="button secondary" href="{href}">{text}{ARROW}</a>'
def zoom(path,alt):
 return f'<a class="zoom-image" href="assets/{path}" aria-label="{esc(alt)}">{img(path,alt)}<span class="zoom-mark" aria-hidden="true">+</span></a>'
def head(title,description):
 return f'''<!doctype html>
<html lang="bg"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{esc(description)}"><meta name="theme-color" content="#21675c"><title>{esc(title)} · {COPY['name']}</title><link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/fonts.css"><link rel="stylesheet" href="assets/base.css"><link rel="stylesheet" href="assets/seaglass.css"><script src="assets/site.js" defer></script></head>'''
def header():
 links=''.join(f'<a href="index.html#{anchor}">{text}</a>' for anchor,text in zip(['about','services','doctors','why_us','gallery','contact'],COPY['nav']))
 return f'''<body class="design-1" data-close="{COPY['close']}" data-previous="{COPY['previous']}" data-next="{COPY['next']}" data-image="{COPY['image']}"><a class="skip-link" href="#main">{COPY['skip']}</a><div class="utility"><div class="container utility-inner"><span>{COPY['location']}</span><span>{COPY['hours']}</span><a href="tel:+359899842980">+359 899 84 29 80</a></div></div><header class="site-header"><div class="container header-inner"><a href="index.html" class="brand" aria-label="{COPY['name']}"><span class="brand-monogram" aria-hidden="true">N<span>p</span><svg viewBox="0 0 48 10"><path d="M2 1 Q24 16 46 1"/></svg></span><span class="brand-caption">{COPY['name']}<small>{COPY['role']}</small></span></a><button class="menu-toggle" aria-label="{COPY['menu']}" aria-expanded="false" aria-controls="main-nav"><span></span><span></span></button><nav id="main-nav" aria-label="{COPY['menu']}">{links}</nav></div></header>'''
def footer():
 links=''.join(f'<a href="index.html#{anchor}">{text}</a>' for anchor,text in zip(['about','services','doctors','why_us','gallery','contact'],COPY['nav']))
 return f'''<footer class="footer"><div class="container"><div class="footer-top"><a class="footer-brand" href="index.html">Панчева<span>·</span></a><p>{COPY['footer']}</p><a href="mailto:panchevanina@gmail.com">panchevanina@gmail.com</a></div><div class="footer-links">{links}<a href="treatments.html">{COPY['library']}</a><a href="privacy.html">{COPY['privacy']}</a></div><div class="footer-bottom"><span>© 2026 {COPY['name']}</span><span>{COPY['location']}</span></div></div></footer></body></html>'''
def hero():
 return f'''<section class="hero"><div class="container hero-grid"><div class="hero-copy">{label(COPY['location'])}<h1>{COPY['hero1']}</h1><p class="hero-intro">{COPY['intro']}</p><div class="hero-buttons"><a class="text-link" href="#services">{COPY['explore']} <span aria-hidden="true">↓</span></a></div><a class="scroll-link" href="#about"><span aria-hidden="true">↓</span>{COPY['scroll']}</a></div><div class="hero-visual">{img(DATA['hero'],COPY['comfort'],'hero-photo',True)}<div class="hero-note"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 12c-8-9-21-4-18 8 2 8 4 22 10 22 5 0 2-14 8-14s3 14 8 14c6 0 8-14 10-22 3-12-10-17-18-8Z"/></svg><p>{COPY['heroNote']}</p></div><span class="photo-index" aria-hidden="true">{COPY['location']}</span></div></div></section><div class="trust-strip"><div class="container"><span><b>2012</b>{COPY['since']}</span><span><span class="trust-symbol" aria-hidden="true">✧</span>{COPY['comfort']}</span><span><span class="trust-symbol" aria-hidden="true">↗</span>{COPY['nhif']}</span></div></div>'''
def clinic_image():return next(x['image'] for x in DATA['gallery'] if 'be448' in x['image'])
def about():
 return f'''<section class="section about-section" id="about"><div class="container about-grid"><div>{label(COPY['aboutLabel'])}<h2>{COPY['aboutTitle']}</h2></div><div class="about-text">{''.join('<p>'+p+'</p>' for p in COPY['about'])}<a class="text-link" href="#doctors">{COPY['nav'][2]} {ARROW}</a></div><div class="practice-image">{img(clinic_image(),COPY['location'])}<span>{COPY['location']}</span></div></div></section>'''
def filters():
 return '<div class="filters" aria-label="Услуги по категории">'+''.join(f'<button class="filter-button" data-filter="{category}" aria-pressed="{str(index==0).lower()}">{name}</button>' for index,(category,name) in enumerate(COPY['categories']))+'</div>'
def services():
 featured=[];regular=[]
 for index,topic in enumerate(TOPICS):
  href='treatments.html#'+topic['id'];title=topic['title']
  if topic['featured']:
   media=f'<a class="service-visual fit-{topic["imageFit"]}" href="{href}" aria-label="{esc(title)}">{img(topic["image"],title)}</a>'
   card=f'<article class="service-item featured-service" data-category="{topic["category"]}">{media}<div class="featured-service-copy"><span class="service-number">{index+1:02}</span><h3><a href="{href}">{title}</a></h3><p>{topic["summary"]}</p><a class="service-arrow" href="{href}" aria-label="{esc(COPY["read"]+": "+title)}">↗</a></div></article>'
   featured.append(card)
  else:
   regular.append(f'<article class="service-item" data-category="{topic["category"]}"><span class="service-number">{index+1:02}</span><div class="service-info"><h3><a href="{href}">{title}</a></h3><p>{topic["summary"]}</p></div><a class="service-arrow" href="{href}" aria-label="{esc(COPY["read"]+": "+title)}">↗</a></article>')
 return f'''<section class="section services-section" id="services"><div class="container"><div class="section-heading"><div>{label(COPY['servicesLabel'])}<h2>{COPY['servicesTitle']}</h2></div><p>{COPY['servicesIntro']}</p></div>{filters()}<div class="featured-services-grid">{''.join(featured)}</div><div class="services-grid">{''.join(regular)}</div><div class="section-bottom">{btn('treatments.html',COPY['allTreatments'])}</div></div></section>'''
def doctor():
 return f'''<section class="section doctor-section" id="doctors"><div class="container doctor-grid"><div class="doctor-portrait">{img(DATA['portrait'],COPY['name'])}<span class="portrait-caption">{COPY['name']}<small>{COPY['role']}</small></span></div><div class="doctor-copy">{label(COPY['doctorLabel'])}<h2>{COPY['doctorTitle']}</h2><p class="lead">{COPY['doctorIntro']}</p><ol class="timeline">{''.join('<li><strong>'+year+'</strong><p>'+text+'</p></li>' for year,text in COPY['bio'])}</ol><p>{COPY['training']}</p>{btn('gallery.html#certificates',COPY['certificates'])}</div></div></section>'''
def reasons():
 items=''.join(f'<details class="reason"><summary><span>{index+1:02}</span><h3>{title}</h3><span class="plus" aria-hidden="true">+</span></summary><p>{text}</p></details>' for index,(title,text) in enumerate(COPY['reasons']))
 return f'<section class="section reasons-section" id="why_us"><div class="container reasons-grid"><div>{label(COPY["whyLabel"])}<h2>{COPY["whyTitle"]}</h2><p class="principle-mark" aria-hidden="true">✳</p></div><div>{items}</div></div></section>'
def gallery_intro():
 manifest=json.loads((ROOT/'docs/asset-manifest.json').read_text());pick=lambda name:next(p for u,p in manifest.items() if u.split('/')[-1]==name)
 pairs=[('before_2.jpg','after_2.jpg'),('before21_1.jpg','after21_1.jpg')];cases=[]
 for index,(before,after) in enumerate(pairs):
  photos=''.join('<div>'+zoom(pick(name),COPY['case']+' '+str(index+1)+' · '+state)+'<span>'+state+'</span></div>' for name,state in [(before,COPY['before']),(after,COPY['after'])])
  cases.append('<figure class="case-pair"><div class="case-photos">'+photos+'</div><figcaption>'+COPY['case']+' / 0'+str(index+1)+'</figcaption></figure>')
 return f'''<section class="section gallery-section" id="gallery"><div class="container"><div class="section-heading"><div>{label(COPY['galleryLabel'])}<h2>{COPY['galleryTitle']}</h2></div><p>{COPY['galleryIntro']}</p></div><div class="case-grid photo-gallery">{''.join(cases)}</div><div class="section-bottom">{btn('gallery.html',COPY['galleryAll'])}</div></div></section>'''
def reviews():
 quotes=[]
 for review in DATA['reviews']:
  quote=review['quote'][:-len(review['name'])].strip().strip('“„” ');name=review['name']
  quotes.append(f'<figure class="review"><span class="quote-mark" aria-hidden="true">“</span><blockquote>{esc(quote)}</blockquote><figcaption><span class="avatar" aria-hidden="true">{esc(name[:1])}</span>{esc(name)}</figcaption></figure>')
 return f'<section class="section reviews-section"><div class="container">{label(COPY["reviewsLabel"])}<h2>{COPY["reviewsTitle"]}</h2><div class="reviews-track">{"".join(quotes)}</div></div></section>'
def contact():
 return f'''<section class="section contact-section" id="contact"><div class="container contact-grid"><div class="contact-copy">{label(COPY['contactLabel'])}<h2 id="consultation">{COPY['contactTitle']}</h2><p>{COPY['contactIntro']}</p><dl class="contact-details"><div><dt>{COPY['phone']}</dt><dd><a href="tel:+359899842980">+359 899 84 29 80</a></dd></div><div><dt>{COPY['email']}</dt><dd><a href="mailto:panchevanina@gmail.com">panchevanina@gmail.com</a></dd></div><div><dt>{COPY['hoursLabel']}</dt><dd>{COPY['hours']}</dd></div></dl></div><div class="location-card">{img(clinic_image(),'Кабинетът на д-р Нина Панчева във Варна')}<div class="location-card-copy">{label(COPY['addressLabel'])}<h3>{COPY['address']}</h3><p>{COPY['address2']}</p><a class="text-link" href="{esc(COPY['mapUrl'])}" target="_blank" rel="noopener noreferrer">{COPY['map']}{ARROW}</a></div></div></div></section>'''
def main_page():
 schema={'@context':'https://schema.org','@type':'Dentist','name':COPY['name'],'telephone':'+359899842980','email':'panchevanina@gmail.com','address':{'@type':'PostalAddress','streetAddress':'ул. „Академик Андрей Сахаров“ 27, етаж 2, кабинет 206','addressLocality':'Варна','postalCode':'9009','addressCountry':'BG'},'geo':{'@type':'GeoCoordinates','latitude':43.2231205,'longitude':27.902595},'hasMap':COPY['mapUrl'],'openingHours':'Mo-Fr 10:00-19:00'}
 return head(COPY['location'],COPY['intro'])+header()+f'<script type="application/ld+json">{json.dumps(schema,ensure_ascii=False)}</script><main id="main">'+hero()+''.join(fn() for fn in [about,services,doctor,reasons,gallery_intro,reviews,contact])+'</main>'+footer()
def library():
 nav=[];articles=[]
 for index,topic in enumerate(TOPICS):
  title=topic['title'];nav.append(f'<a href="#{topic["id"]}" data-topic-link="{topic["id"]}">{title}</a>')
  if topic['featured']:
   body=f'<figure class="service-detail-image">{zoom(topic["image"],title)}</figure>'+''.join('<p>'+esc(p)+'</p>' for p in topic['paragraphs'])
   body+=''.join(f'<p class="product-link"><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{text} ↗</a></p>' for url,text in topic['links'])
  else:body=topic['html']
  if topic['id']=='sinus-lift':
   body=re.sub(r'<img\b[^>]*>','',body)
   body+=f'<details class="surgery-media"><summary>{COPY["showPhotos"]}</summary><p>{COPY["surgeryNotice"]}</p><div class="clinical-photos photo-gallery">'+''.join(zoom(x,COPY['surgeryPhotos']) for x in dict.fromkeys(topic['images']))+'</div></details>'
  body=re.sub(r'<img src="\.\./assets/images/([^\"]+)"',lambda match:'<img src="assets/thumbs/'+Path(match[1]).stem+'.webp"',body)
  articles.append(f'<details class="treatment-article" id="{topic["id"]}" data-category="{topic["category"]}"><summary><span class="article-index">{index+1:02}</span><h2>{title}</h2><span aria-hidden="true">+</span></summary><div class="article-body">{body}</div></details>')
 source_names={'aesthetic':'Естетична стоматология','prosthetic':'Протетична стоматология','surgery':'Хирургия','zirconia':'Циркониеви коронки','fillings':'Естетични пломби','veneers':'Керамични фасети','whitening':'Избелване на зъби','inlays':'Керамични инлеи','crowns':'Коронки и мостове','extraction':'Вадене на зъб'}
 extras=''.join(f'<details class="source-page" id="source-{name}"><summary lang="bg">{source_names[name]}</summary><div class="article-body">{html}</div></details>' for name,html in DATA['supplementary'].items())
 body=f'<main id="main"><section class="page-title"><div class="container">{label(COPY["location"])}<h1>{COPY["library"]}</h1><p>{COPY["libraryIntro"]}</p><a class="text-link" href="index.html">← {COPY["back"]}</a></div></section><section class="section library-section"><div class="container"><div class="library-controls"><label class="search-label" for="treatment-search">{COPY["search"]}<input type="search" id="treatment-search" placeholder="{COPY["search"]}" autocomplete="off"></label>{filters()}</div><div class="library-layout"><nav class="library-nav" aria-label="{COPY["library"]}">{"".join(nav)}</nav><div class="article-list">{"".join(articles)}<p class="no-results" role="status" hidden>{COPY["noResults"]}</p></div></div><details class="source-pages"><summary>{COPY["sourcePages"]}</summary>{extras}</details></div></section></main>'
 return head(COPY['library'],COPY['libraryIntro'])+header()+body+footer()
def gallery_page():
 photos=''.join('<figure>'+zoom(item['image'],COPY['image']+' '+str(index+1))+f'<figcaption>{COPY["image"]} {index+1:02}</figcaption></figure>' for index,item in enumerate(DATA['gallery']))
 certs=''.join('<figure>'+zoom(item['image'],COPY['certificateLabel']+' '+str(index+1))+f'<figcaption>{COPY["certificateLabel"]} {index+1:02}</figcaption></figure>' for index,item in enumerate(DATA['certificates']))
 body=f'<main id="main"><section class="page-title"><div class="container">{label(COPY["galleryLabel"])}<h1>{COPY["galleryAll"]}</h1><p>{COPY["galleryIntro"]}</p><a class="text-link" href="index.html">← {COPY["back"]}</a></div></section><section class="section"><div class="container"><div class="photo-gallery full-gallery">{photos}</div></div></section><section class="section certificates-section" id="certificates"><div class="container">{label(COPY["doctorLabel"])}<h2>{COPY["certificateLabel"]}</h2><p>{COPY["training"]}</p><div class="photo-gallery certificate-grid">{certs}</div></div></section></main>'
 return head(COPY['galleryAll'],COPY['galleryIntro'])+header()+body+footer()
def privacy_page():
 return head(COPY['privacy'],COPY['privacyText'])+header()+f'<main id="main"><section class="page-title"><div class="container">{label(COPY["location"])}<h1>{COPY["privacy"]}</h1></div></section><section class="section"><div class="container prose"><p>{COPY["privacyText"]}</p><p><a href="mailto:panchevanina@gmail.com">panchevanina@gmail.com</a> · <a href="tel:+359899842980">+359 899 84 29 80</a></p><a class="text-link" href="index.html">← {COPY["back"]}</a></div></section></main>'+footer()

for name,render in zip(PAGES,[main_page,library,gallery_page,privacy_page]):
 html=render().replace('../assets/','assets/')
 (ROOT/name).write_text(html)
 # Keep the selected prototype's Bulgarian URLs current for existing local preview links.
 if (ROOT/'version-1').is_dir():
  (ROOT/'version-1'/name).write_text(html.replace('assets/','../assets/'))
print('Generated four production pages and four matching Bulgarian option-1 preview pages; 19 services.')
