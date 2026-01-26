import requests
from bs4 import BeautifulSoup, Comment
import json
import time
import random


def get_all_text_after(element):
    if not element:
        return ''

    result_text = ''

    next_element = element.next_sibling

    while next_element and not (
            next_element.name is not None and next_element.name.startswith('h')):
        # print('!' + str(next_element))
        # if next_element.string:
        #     result_text += next_element.string.strip()
        # elif next_element.name == 'p':
        #     result_text += next_element.get_text().strip()
        result_text += str(next_element).strip()
        # print('?' + result_text)
        next_element = next_element.next_sibling

    return result_text.replace('<p></p>', '').replace('\n', ' ').replace('\r', ' ').replace(
        'show_document.php', 'https://problems.ru/show_document.php').replace('/view_by_author.php', 'https://problems.ru/view_by_author.php').strip()


def parse_problem(p_id):
    url = f'https://problems.ru/view_problem_details_new.php?id={p_id}'
    page = requests.get(url)

    if page.status_code == 200:
        soup = BeautifulSoup(page.text, "lxml")

        for comment in soup.find_all(
                text=lambda text: isinstance(text, Comment)):
            comment.extract()
        # print(soup.prettify())

        condition_text = get_all_text_after(soup.find('h3', string='Условие'))
        solution_text = get_all_text_after(soup.find('h3', string='Решение'))
        answer_text = get_all_text_after(soup.find('h3', string='Ответ'))

        # print(condition_text)
        # print()
        # print(solution_text)
        # print()
        # print(answer_text)

        x = soup.find_all('a', class_='componentboxlink')
        # print(theme)
        subcategory = []
        for el in x:
            if el['href'] and el['href'].startswith(
                    '/view_by_subject_new.php'):
                subcategory.append(el.string.strip())

        # print()
        # print(subcategory)

        x = soup.find('td', class_='problemdetailsdifficulty')
        diff = -1

        if x:
            for c in x.children:
                if c.string and 'Сложность' in c.string:
                    diff = c.string.split(
                    )[-1].replace('-', '').replace('+', '')

        # print()
        # print(diff)

        return {
            'id': p_id,
            'condition': condition_text,
            'solution': solution_text,
            'answer': answer_text,
            'subcategory': subcategory,
            'difficulty': diff
        }
    else:
        # print(page.status_code)
        return {}


def parse_page(page_id, total):
    res = []
    cnt = 0
    running = True
    while running:
        try:
            req = requests.get(
                f'https://problems.ru/view_by_subject_new.php?parent={page_id}&start={cnt}')
        except Exception as e:
            print('!!')
            print(e)
            break

        if req.status_code == 200:
            soup = BeautifulSoup(req.text, 'lxml')

            for el in soup.find_all('a', class_='componentboxlink'):
                if el['href'] and el['href'].startswith(
                        '/view_problem_details_new.php'):
                    # print(el.string.strip())
                    s = el.string.strip()
                    if s.isnumeric():
                        cnt += 1
                        print(s, cnt)
                        res.append(parse_problem(int(s)))
                        with open('tasks.json', 'w', encoding='utf8') as f:
                            json.dump(res, f, indent=4, ensure_ascii=False)
                        time.sleep(random.randint(4, 10))
                        if cnt == total:
                            running = False
                            break
        else:
            print(req.status_code)


# parse_page(214, 3)
