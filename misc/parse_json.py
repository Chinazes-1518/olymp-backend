import json
from ntpath import isfile
import re
import requests
import time
import os
import random


with open('tasks.json', encoding='utf8') as f:
    data = json.load(f)

name = input('name> ')

links = set()

pattern = re.compile(r"https://problems.ru/show_document.php\?id=(\d+)")

for d in data:
    d['condition'] = ' '.join(d['condition'].split())
    d['solution'] = ' '.join(d['solution'].split())
    d['answer'] = ' '.join(d['answer'].split())
    d['subcategory'] = sorted([x for x in set(d['subcategory']) if x != 'Неопределено'])
    links |= set(map(int, pattern.findall(d['condition'])))
    links |= set(map(int, pattern.findall(d['solution'])))
    links |= set(map(int, pattern.findall(d['answer'])))

with open(name + '.json', 'w', encoding='utf8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

for id in links:
    url = f'https://problems.ru/show_document.php?id={id}'
    print(f'downloading document {url}')
    if os.path.isfile(f'documents/{id}.gif'):
        continue
    r = requests.get(url)
    if r.status_code == 200:
        with open(f'documents/{id}.gif', 'wb') as f:
            f.write(r.content)
            time.sleep(random.randint(3, 8))
    else:
        print('error')
