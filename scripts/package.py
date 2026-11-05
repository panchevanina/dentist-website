#!/usr/bin/env python3
"""Export the selected Bulgarian production site as a standalone folder and ZIP."""
from pathlib import Path
import argparse,shutil,zipfile

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True,help='New output directory; existing data is never overwritten')
args=parser.parse_args();out=args.output.resolve();archive=out.with_name(out.name+'.zip')
if out.is_relative_to(ROOT/'assets'):parser.error('Output must be outside assets to avoid recursively copying the source assets.')
if out.exists() or archive.exists():parser.error('The output directory or ZIP already exists. Choose a new path.')
out.mkdir(parents=True)
for name in ['index.html','treatments.html','gallery.html','privacy.html']:
 shutil.copy2(ROOT/name,out/name)
for folder in ['images','thumbs','fonts']:
 shutil.copytree(ROOT/'assets'/folder,out/'assets'/folder)
for name in ['base.css','fonts.css','seaglass.css','site.js','favicon.svg']:
 shutil.copy2(ROOT/'assets'/name,out/'assets'/name)
(out/'.nojekyll').touch()
(out/'README.md').write_text('''# Д-р Нина Панчева — сайт на български

HTML, CSS и JavaScript без библиотеки, инсталиране или компилиране.

Качете съдържанието на тази папка в GitHub хранилище. В Settings → Pages изберете Deploy from a branch, съответния клон и / (root). Запазете файла .nojekyll. Относителните връзки работят и когато сайтът е в подпапка на хранилище.

За локален преглед отворете index.html или изпълнете `python3 -m http.server 8000 --bind 127.0.0.1` в тази папка. Спрете сървъра с Ctrl+C.

Няма формуляр за изпращане на данни. Контактите са чрез телефон и имейл. Снимките и шрифтовете се зареждат локално; картата и продуктовите страници се отварят само при избор на съответната връзка.

Шрифтовете Manrope и Lora са с лиценз SIL Open Font License. Лицензите са в assets/fonts/.
''')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as zip_file:
 for file in sorted(out.rglob('*')):
  if file.is_file():zip_file.write(file,file.relative_to(out))
print('Production site:',out)
print('ZIP:',archive)
