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


def replace_links(s):
    return pattern.sub(lambda x: f'https://cdn.saslo.fun/{x.group(1)}.gif', s)


for d in data:
    d['condition'] = d['condition'].replace('https://problems.ru/https://problems.ru', 'https://problems.ru')
    d['solution'] = d['solution'].replace('https://problems.ru/https://problems.ru', 'https://problems.ru')
    d['answer'] = d['answer'].replace('https://problems.ru/https://problems.ru', 'https://problems.ru')
    links |= set(map(int, pattern.findall(d['condition'])))
    links |= set(map(int, pattern.findall(d['solution'])))
    links |= set(map(int, pattern.findall(d['answer'])))
    d['condition'] = replace_links(' '.join(d['condition'].split()))
    d['solution'] = replace_links(' '.join(d['solution'].split()))
    d['answer'] = replace_links(' '.join(d['answer'].split()))
    d['subcategory'] = sorted([x for x in set(d['subcategory']) if x != 'Неопределено'])

with open(name + '.json', 'w', encoding='utf8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

for i, id in enumerate(links):
    url = f'https://problems.ru/show_document.php?id={id}'
    print(f'downloading document {url} {i + 1}/{len(links)}')
    if os.path.isfile(f'documents/{id}.gif'):
        continue
    r = requests.get(url)
    if r.status_code == 200:
        with open(f'documents/{id}.gif', 'wb') as f:
            f.write(r.content)
            time.sleep(random.randint(3, 5))
    else:
        print('error')
