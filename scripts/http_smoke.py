#!/usr/bin/env python3
"""Serve a checkout/export briefly on loopback and check HTTP paths under a repo prefix."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,urlopen
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from tempfile import TemporaryDirectory
from threading import Thread
import argparse,re,sys
p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',nargs='?',type=Path,default=Path(__file__).resolve().parent.parent);a=p.parse_args();root=a.root.resolve()
class Links(HTMLParser):
 def __init__(self,text):super().__init__();self.urls=[];self.feed(text)
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  for k in ('href','src'):
   if d.get(k):self.urls.append(d[k])
class QuietHandler(SimpleHTTPRequestHandler):
 def log_message(self,*args):pass
urls=set();pages=[]
for file in (root/name for name in ['index.html','treatments.html','gallery.html','privacy.html']):
 rel=file.relative_to(root)
 if not file.is_file():continue
 path='/pancheva/'+rel.as_posix();pages.append(path);urls.add(path)
 for u in Links(file.read_text()).urls:
  parsed=urlsplit(u)
  if parsed.scheme or parsed.netloc:continue
  urls.add(urlsplit(urljoin(path,u)).path)
for css in (root/'assets').glob('*.css'):
 path='/pancheva/'+css.relative_to(root).as_posix()
 for u in re.findall(r'url\([\"\x27]?(.*?)[\"\x27]?\)',css.read_text()):
  if not urlsplit(u).scheme:urls.add(urljoin(path,u))
errors=[]
with TemporaryDirectory(prefix='pancheva-http-') as temp:
 (Path(temp)/'pancheva').symlink_to(root,target_is_directory=True)
 handler=lambda *args,**kwargs:QuietHandler(*args,directory=temp,**kwargs)
 server=ThreadingHTTPServer(('127.0.0.1',0),handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  base='http://127.0.0.1:'+str(server.server_port)
  for path in sorted(urls):
   try:
    with urlopen(Request(base+path,method='HEAD'),timeout=10) as response:
     if response.status!=200:errors.append(path+': '+str(response.status))
     if path.endswith('.html') and response.headers.get_content_type()!='text/html':errors.append(path+': incorrect HTML MIME type')
   except Exception as e:errors.append(path+': '+str(e))
  with urlopen(base+'/pancheva/index.html',timeout=10) as response:
   if b'<!doctype html>' not in response.read().lower():errors.append('Homepage is not HTML')
 finally:server.shutdown();server.server_close();thread.join()
print(f'HTTP smoke: {len(pages)} pages and {len(urls)} unique paths under /pancheva/. Server stopped.')
if errors:print('\n'.join(errors));sys.exit(1)
print('PASS: every requested local page/asset returned HTTP 200; HTML MIME types are correct.')
