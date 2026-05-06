import json

with open('dishes_dataset_merged.json', encoding='utf-8') as f:
    data = json.load(f)

dishes = data if isinstance(data, list) else data.get('dishes', [])
print(f'Всего блюд: {len(dishes)}')

meat_kw = (
    'мяс','куриц','индейк','говядин','рыб','лосос','треск','морепродукт',
    'свинин','ветчин','колбас','сосиск','бекон','фарш','шашлык','шницел',
    'карбонар','болоньез','котлет','пельмен','манты','хинкал','тефтел',
    'буженин','окорок','грудинк','паштет','салями','прошутт','крылышк',
    'утк','гусь','гус','кролик','баранин','ягненок','ягнят',
)

print('\n--- Блюда с мясными словами в названии/тегах ---')
for d in dishes:
    name = d.get('name', '').lower().replace('ё', 'е')
    tags = ' '.join(d.get('tags', [])).lower().replace('ё', 'е')
    text = name + ' ' + tags
    if any(k in text for k in meat_kw):
        print(f"  {d.get('name'):40s} tags={d.get('tags')}")

print('\n--- Блюда БЕЗ мясных слов (потенциальные ошибки если мясные) ---')
suspicious = ['пельмен','манты','хинкал','лазань','болоньез','карбонар']
for d in dishes:
    name = d.get('name', '').lower().replace('ё', 'е')
    if any(s in name for s in suspicious):
        print(f"  {d.get('name'):40s} tags={d.get('tags')} allergens={d.get('allergens')}")
