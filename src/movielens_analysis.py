import os
import sys
import urllib.request
import requests
from bs4 import BeautifulSoup
import json
import pytest
import collections
import functools
import datetime
import re

# ==========================================
# Вспомогательные функции (Общие)
# ==========================================

def parse_csv_line(line):
    """Разбирает строку CSV с учётом кавычек."""
    pattern = re.compile(r',(?=(?:[^"]*"[^"]*")*[^"]*$)')
    parts = pattern.split(line.strip())
    return [p.strip('"') for p in parts]

def read_csv_limited(path, limit=1000):
    """Читает первые N строк CSV файла."""
    if not os.path.exists(path):
        return []
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    if not lines:
        return []

    headers = parse_csv_line(lines[0])
    # limit+1 потому что есть строка заголовка
    data_lines = lines[1:limit+1]
    
    for line in data_lines:
        if not line.strip():
            continue
        values = parse_csv_line(line)
        if len(values) == len(headers):
            row = {headers[i]: values[i] for i in range(len(headers))}
            data.append(row)
    return data

class ResultVisualizer:
    def __init__(self, data, headers=None): # Добавляем параметр headers
        self.data = data
        self.headers = headers

    def _repr_html_(self):
        if not self.data:
            return "<i>Нет данных для отображения.</i>"

        # 1. Профессиональный CSS для таблицы
        style = """
        <style>
            .ml-table { border-collapse: collapse; width: 100%; font-family: 'Segoe UI', Tahoma, sans-serif; }
            .ml-table th { background-color: #2e7d32; color: white; padding: 12px; text-align: left; }
            .ml-table td { border: 1px solid #ddd; padding: 10px; color: #888; }
            .ml-table tr:nth-child(even) { background-color: #f9f9f9; }
            .ml-table tr:hover { background-color: #e8f5e9; color: yellow;}
        </style>
        """
        html = style + "<table class='ml-table'>"

        # 2. Логика для определения структуры данных и построения строк
        
        # СЛУЧАЙ A: Словарь словарей (например, movies.movies)
        # Структура: { ID: { 'title': '...', 'genres': '...' } }
        if isinstance(self.data, dict):
            # Смотрим на первый элемент, чтобы понять, вложенный ли это словарь
            first_key = next(iter(self.data))
            first_val = self.data[first_key]

            if isinstance(first_val, dict):
                # Формируем заголовки из ID + ключи внутреннего словаря
                inner_keys = list(first_val.keys())
                html += "<tr><th>ID</th>" + "".join(f"<th>{k.capitalize()}</th>" for k in inner_keys) + "</tr>"
                
                for movie_id, info in self.data.items():
                    row_data = "".join(f"<td>{info.get(k, 'N/A')}</td>" for k in inner_keys)
                    html += f"<tr><td><b>{movie_id}</b></td>{row_data}</tr>"
            
            # СЛУЧАЙ B: Простое распределение (например, { 1995: 50, 1996: 30 })
            else:
                html += "<tr><th>Ключ</th><th>Значение</th></tr>"
                for k, v in self.data.items():
                    html += f"<tr><td>{k}</td><td>{v}</td></tr>"

        # СЛУЧАЙ C: Список списков (например, links.get_imdb)
        elif isinstance(self.data, list):
            if self.data and isinstance(self.data[0], list):
                # Если есть заголовки, создаём строку <th>
                if self.headers:
                    html += "<tr style='background-color: #f2f2f2;'>" + "".join(f"<th>{h}</th>" for h in self.headers) + "</tr>"
                
                for row in self.data:
                    html += "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
            else:
                # Простой список строк (например, tags.longest)
                html += "<tr><th>Элементы</th></tr>"
                for item in self.data:
                    html += f"<tr><td>{item}</td></tr>"

        html += "</table>"
        return html

# ==========================================
# Определения классов
# ==========================================

# --- ЧАСТЬ АЛЕКСАНДРА (Фильмы, Теги) ---

class Movies:
    def __init__(self, path_to_the_file, limit=1000):
        self.movies = {}
        self.limit = limit
        
        # ИСПРАВЛЕНИЕ: Получаем директорию, в которой находится файл movies
        base_dir = os.path.dirname(path_to_the_file)
        ratings_path = os.path.join(base_dir, 'ratings.csv')
        tags_path = os.path.join(base_dir, 'tags.csv')
        
        valid_ids = set()
        
        # ИСПРАВЛЕНИЕ: Используем ratings_path вместо 'ratings.csv'
        if os.path.exists(ratings_path):
            with open(ratings_path, 'r', encoding='utf-8') as f:
                next(f)
                for i, line in enumerate(f):
                    if i >= self.limit: break
                    parts = line.strip().split(',')
                    if len(parts) >= 2: valid_ids.add(int(parts[1]))
        
        # ИСПРАВЛЕНИЕ: Используем tags_path вместо 'tags.csv'
        if os.path.exists(tags_path):
            with open(tags_path, 'r', encoding='utf-8') as f:
                next(f)
                for i, line in enumerate(f):
                    if i >= self.limit: break
                    parts = parse_csv_line(line)
                    if len(parts) >= 2: valid_ids.add(int(parts[1]))

        # 2. Загружаем фильмы, если их id есть в valid_ids
        if os.path.exists(path_to_the_file):
            with open(path_to_the_file, 'r', encoding='utf-8') as f:
                next(f)
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    try:
                        parts = parse_csv_line(line)
                        if len(parts) < 2: continue
                        movie_id = int(parts[0])
                        
                        # ФИЛЬТРАЦИЯ ПРИМЕНЯЕТСЯ ЗДЕСЬ
                        if movie_id not in valid_ids:
                            continue
                            
                        title = parts[1]
                        genres = parts[2] if len(parts) > 2 else ""
                        year = None
                        match = re.search(r'\((\d{4})\)$', title.strip())
                        if match:
                            year = int(match.group(1))

                        self.movies[movie_id] = {
                            'title': title,
                            'genres': genres,
                            'year': year
                        }
                    except Exception as e:
                        continue

    def show(self, data, fields=None):
        headers = None
        if isinstance(data, list) and fields is not None:
            # Вручную определяем первые две колонки как ID и Название
            headers = ["ID фильма", "Название"] + fields
        return ResultVisualizer(data, headers=headers)
    
    def dist_by_release(self):
        """
        Возвращает dict или OrderedDict, где ключи - годы, а значения - количество фильмов.
        Сортировка по убыванию количества.
        """
        years = [m['year'] for m in self.movies.values() if m['year'] is not None]
        c = collections.Counter(years)
        # Сортировка по убыванию количества
        return dict(sorted(c.items(), key=lambda x: x[1], reverse=True))
    
    def dist_by_genres(self):
        """
        Возвращает dict, где ключи - жанры, а значения - количество фильмов.
        Сортировка по убыванию количества.
        """
        genre_counter = collections.Counter()
        for info in self.movies.values():
            if info['genres'] and info['genres'] != '(no genres listed)':
                genres = info['genres'].split('|')
                genre_counter.update(genres)
        return dict(sorted(genre_counter.items(), key=lambda x: x[1], reverse=True))
        
    def most_genres(self, n):
        """
        Возвращает dict с топ-n фильмами, где ключи - названия фильмов,
        а значения - количество жанров у фильма. Сортировка по убыванию количества.
        """
        counts = {}
        for m in self.movies.values():
            g_str = m['genres']
            if not g_str or g_str == '(no genres listed)':
                count = 0
            else:
                count = len(g_str.split('|'))
            counts[m['title']] = count
        
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_counts[:n])


class Tags:
    """
    Анализ данных из tags.csv
    """
    def __init__(self, path_to_the_file, limit=1000):
        self.tags_data = [] # Список строк (тегов)
        self.rows = [] # Исходные строки
        self.limit = limit
        
        if os.path.exists(path_to_the_file):
            with open(path_to_the_file, 'r', encoding='utf-8') as f:
                next(f)
                for i, line in enumerate(f):
                    if i >= limit:
                        break
                    parts = parse_csv_line(line)
                    if len(parts) >= 3:
                        # userId,movieId,tag,timestamp
                        tag_text = parts[2]
                        self.tags_data.append(tag_text)
                        self.rows.append(parts)

    def show(self, data):
        return ResultVisualizer(data)
    
    def most_words(self, n):
        """
        Топ-n тегов с наибольшим количеством слов внутри. Dict: тег -> количество слов.
        Удалить дубликаты. Сортировка по убыванию количества.
        """
        unique_tags = set(self.tags_data)
        res = {}
        for t in unique_tags:
            # Считаем слова, разделённые пробелами
            res[t] = len(t.split())
        
        sorted_res = sorted(res.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_res[:n])

    def longest(self, n):
        """
        Топ-n самых длинных тегов (символов). Список тегов.
        Удалить дубликаты. Сортировка по убыванию длины.
        """
        unique_tags = set(self.tags_data)
        # Сортируем по длине строки
        sorted_tags = sorted(list(unique_tags), key=lambda x: len(x), reverse=True)
        return sorted_tags[:n]

    def most_words_and_longest(self, n):
        """
        Пересечение между топ-n тегами с наибольшим количеством слов и топ-n самыми длинными тегами.
        Возвращает список тегов.
        """
        # Получаем top-n по количеству слов
        top_words_dict = self.most_words(n)
        set_words = set(top_words_dict.keys())
        
        # Получаем top-n по длине
        list_longest = self.longest(n)
        set_longest = set(list_longest)
        
        intersection = list(set_words & set_longest)
        return intersection
        
    def most_popular(self, n):
        """
        Самые популярные теги. Dict: тег -> количество.
        Удалить дубликаты? Нет, популярность подразумевает подсчёт дубликатов в исходных данных,
        но возвращаем уникальные ключи.
        Сортировка по убыванию количества.
        """
        c = collections.Counter(self.tags_data)
        return dict(c.most_common(n))
        
    def tags_with(self, word):
        """
        Уникальные теги, содержащие слово. Список тегов.
        Сортировка по алфавиту.
        """
        unique_tags = set(self.tags_data)
        result = []
        for t in unique_tags:
            # Поиск без учёта регистра, обычно подразумевается "содержит слово",
            # но в задаче не указано. Делаем без учёта регистра для лучших результатов.
            if word.lower() in t.lower():
                result.append(t)
        return sorted(result)


# --- ЧАСТЬ MERCEDEB (Логика оценок) ---

class Ratings:
    def __init__(self, path_to_the_file, path_to_movies_file="movies.csv", limit = 1000):
        self.ratings_path = path_to_the_file
        self.movies_path = path_to_movies_file
        self.limit = limit
        self._ratings = []
        self._movies_map = {}
        
        self.movies = self.Movies(self)
        self.users = self.Users(self)
        
        self._load_data()
    
    def _load_data(self): # Бонус
        """Читает оценки и названия фильмов в память."""
        if self._ratings: # Предотвращаем повторную загрузку, если уже загружено
            return

        # Загрузка оценок
        ratings_data = read_csv_limited(self.ratings_path, self.limit)
        for row in ratings_data:
            self._ratings.append({
                'userId': int(row['userId']),
                'movieId': int(row['movieId']),
                'rating': float(row['rating']),
                'timestamp': int(row['timestamp'])
            })

        # Загрузка названий фильмов для сопоставления (используется в top_by_ratings и др.)
        if os.path.exists(self.movies_path):
            movies_data = read_csv_limited(self.movies_path, self.limit)
            for row in movies_data:
                self._movies_map[int(row['movieId'])] = row['title']

    def show(self, data):
        return ResultVisualizer(data)
    
    # Вспомогательные математические функции
    @staticmethod
    def average(values): # Бонус
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def median(values): # Бонус
        if not values: return 0.0
        s = sorted(values)
        mid = len(s) // 2
        return float(s[mid]) if len(s) % 2 != 0 else (s[mid-1] + s[mid]) / 2.0

    @staticmethod
    def variance(values): # Бонус
        if not values: return 0.0
        avg = sum(values) / len(values)
        return sum((x - avg) ** 2 for x in values) / len(values)

    class Movies:
        def __init__(self, parent):
            self.parent = parent
        
        def dist_by_year(self):
            """Ключи: годы (из timestamp), Значения: количество. Сортировка по годам по возрастанию."""
            self.parent._load_data()
            c = collections.Counter()
            for r in self.parent._ratings:
                dt = datetime.datetime.fromtimestamp(r['timestamp'])
                c[dt.year] += 1
            return dict(sorted(c.items()))
        
        def dist_by_rating(self):
            """Ключи: оценки, Значения: количество. Сортировка по оценкам по возрастанию."""
            self.parent._load_data()
            c = collections.Counter()
            for r in self.parent._ratings:
                c[r['rating']] += 1
            return dict(sorted(c.items()))
        
        def top_by_num_of_ratings(self, n):
            """Dict: название -> количество. Сортировка по убыванию количества."""
            self.parent._load_data()
            c = collections.Counter()
            for r in self.parent._ratings:
                c[r['movieId']] += 1
            
            # Сопоставляем id с названиями
            res = {}
            for mid, count in c.most_common(n):
                title = self.parent._movies_map.get(mid, str(mid))
                res[title] = count
            return res
        
        def top_by_ratings(self, n, metric=None):
            """Dict: название -> значение_метрики. Сортировка по убыванию метрики. Округление до 2 знаков."""
            if metric is None: metric = self.parent.average
            self.parent._load_data()
            
            groups = collections.defaultdict(list)
            for r in self.parent._ratings:
                groups[r['movieId']].append(r['rating'])
            
            calc = []
            for mid, rates in groups.items():
                val = round(metric(rates), 2)
                calc.append((mid, val))
            
            calc.sort(key=lambda x: x[1], reverse=True)
            
            res = {}
            for mid, val in calc[:n]:
                title = self.parent._movies_map.get(mid, str(mid))
                res[title] = val
            return res
        
        def top_controversial(self, n):
            """Дисперсия оценок. Dict: название -> дисперсия. По убыванию."""
            self.parent._load_data()
            groups = collections.defaultdict(list)
            for r in self.parent._ratings:
                groups[r['movieId']].append(r['rating'])
                
            calc = []
            for mid, rates in groups.items():
                val = round(self.parent.variance(rates), 2)
                calc.append((mid, val))
            
            calc.sort(key=lambda x: x[1], reverse=True)
            res = {}
            for mid, val in calc[:n]:
                title = self.parent._movies_map.get(mid, str(mid))
                res[title] = val
            return res

    class Users(Movies):
        """Наследуется от Movies (внутренний класс)."""
        def __init__(self, parent):
            super().__init__(parent)
            
        def dist_by_num_of_ratings(self):
            """Распределение пользователей по количеству оценок."""
            self.parent._load_data()
            user_counts = collections.Counter()
            for r in self.parent._ratings:
                user_counts[r['userId']] += 1
            
            # Теперь распределение этих количеств
            dist = collections.Counter(user_counts.values())
            return dict(sorted(dist.items())) # Сортировка по количеству оценок (ключи) по возрастанию
            
        def dist_by_ratings(self, metric=None):
            """Распределение пользователей по средним/медианным оценкам."""
            if metric is None: metric = self.parent.average
            self.parent._load_data()
            
            user_ratings = collections.defaultdict(list)
            for r in self.parent._ratings:
                user_ratings[r['userId']].append(r['rating'])
            
            dist = collections.Counter()
            for uid, rates in user_ratings.items():
                val = round(metric(rates), 2)
                dist[val] += 1
            return dict(sorted(dist.items()))
            
        def top_controversial(self, n):
            """Топ пользователей с наибольшей дисперсией оценок."""
            self.parent._load_data()
            user_ratings = collections.defaultdict(list)
            for r in self.parent._ratings:
                user_ratings[r['userId']].append(r['rating'])
                
            calc = []
            for uid, rates in user_ratings.items():
                val = round(self.parent.variance(rates), 2)
                calc.append((uid, val))
            
            calc.sort(key=lambda x: x[1], reverse=True)
            return dict(calc[:n])


# --- ЧАСТЬ MARIONTR (Ссылки и скрапинг) ---

class Links:
    def __init__(self, path_to_the_file, limit=1000):
        self.limit = limit
        self.links_path = path_to_the_file # Сохраняем путь!
        self.links_data = read_csv_limited(path_to_the_file, self.limit)
        
        self.movie_imdb_map = {row['movieId']: row['imdbId'] for row in self.links_data if 'imdbId' in row}
        
        self.cache_file = "imdb_cache.json"
        self._cache = self._load_cache()
        self.titles = self._load_titles() # Теперь использует self.links_path
        
    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_cache(self):
        with open(self.cache_file, 'w') as f:
            json.dump(self._cache, f)

    def get_ids(self, n):
        """БОНУС/Помощник: Получает первые n ID фильмов из загруженных данных links."""
        # контроль в ячейках Jupyter, чтобы разбирать только 'n' фильмов
        return [row['movieId'] for row in self.links_data[:n]]

    def _load_titles(self):
        titles = {}
        base_dir = os.path.dirname(self.links_path)
        m_path = os.path.join(base_dir, 'movies.csv')
        
        if os.path.exists(m_path):
            data = read_csv_limited(m_path, self.limit)
            for row in data:
                titles[int(row['movieId'])] = row['title']
        return titles

    def _scrape_imdb(self, imdb_id):
        if imdb_id in self._cache:
            return self._cache[imdb_id]

        url = f"https://www.imdb.com/title/tt{imdb_id}/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        info = {
            'Director': None,
            'Budget': 0,
            'Cumulative Worldwide Gross': 0,
            'Runtime': 0
        }

        try:
            req = requests.get(url, headers=headers, timeout=3)
            if req.status_code == 200:
                soup = BeautifulSoup(req.content, 'html.parser')

                # --- Стратегия 1: JSON-LD ---
                json_ld = soup.find('script', type='application/ld+json')
                if json_ld:
                    try:
                        data = json.loads(json_ld.string)
                        if 'director' in data:
                            d = data['director']
                            if isinstance(d, list): info['Director'] = d[0].get('name')
                            elif isinstance(d, dict): info['Director'] = d.get('name')
                                    
                        if 'duration' in data:
                            dur = data['duration']
                            match = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?', dur)
                            if match:
                                h = int(match.group(1) or 0)
                                m = int(match.group(2) or 0)
                                info['Runtime'] = h * 60 + m
                    except: pass

                # --- Стратегия 2: Поиск в DOM (режиссёр) ---
                if not info['Director']:
                    director_label = soup.find(string=re.compile(r"^Director", re.IGNORECASE))
                    if director_label:
                        parent = director_label.find_parent('li')
                        if parent:
                            link = parent.find('a', href=re.compile(r'/name/'))
                            if link:
                                info['Director'] = link.get_text().strip()

                # --- Стратегия 3: Текстовые регулярные выражения для бюджета/сборов ---
                text = soup.get_text()
                
                # Бюджет: ищет "Budget" сразу перед валютой ИЛИ "Budget" ... валюта
                budget_match = re.search(r'Budget.*?([$€£][\d,]+)', text, re.IGNORECASE)
                if budget_match:
                    raw = budget_match.group(1)
                    info['Budget'] = float(re.sub(r'[^\d.]', '', raw))

                # Сборы: ищем "Gross worldwide" ИЛИ "Cumulative Worldwide Gross"
                gross_match = re.search(r'(?:Gross worldwide|Cumulative Worldwide Gross).*?([$€£][\d,]+)', text, re.IGNORECASE)
                if gross_match:
                    raw = gross_match.group(1)
                    info['Cumulative Worldwide Gross'] = float(re.sub(r'[^\d.]', '', raw))

        except Exception:
            pass 
        
        self._cache[imdb_id] = info
        self._save_cache()
        return info

    def _get_title(self, mid):
        return self.titles.get(int(mid), f"Фильм {mid}")

    def show(self, data):
        return ResultVisualizer(data)
    
    def get_imdb(self, list_of_movies, list_of_fields):
        result = []
        for mid in list_of_movies:
            # mid может быть строкой или int из get_ids()
            if str(mid) in self.movie_imdb_map:
                imdb_id = self.movie_imdb_map[str(mid)]
                data = self._scrape_imdb(imdb_id)
                
                # Получаем настоящее название с помощью исправленного помощника
                actual_title = self._get_title(mid)
                
                row = [str(mid), actual_title]
                for field in list_of_fields:
                    row.append(data.get(field, None))
                result.append(row)
        return sorted(result, key=lambda x: int(x[0]), reverse=True)
        
    def top_directors(self, n):
        counts = collections.defaultdict(int)
        for mid, imdb_id in self.movie_imdb_map.items():
            if imdb_id in self._cache:
                d = self._cache[imdb_id].get('Director')
                if d:
                    counts[d] += 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n])
        
    def most_expensive(self, n):
        budgets = {}
        for mid, imdb_id in self.movie_imdb_map.items():
            if imdb_id in self._cache:
                b = self._cache[imdb_id].get('Budget', 0)
                if b > 0:
                    budgets[self._get_title(mid)] = b
        return dict(sorted(budgets.items(), key=lambda x: x[1], reverse=True)[:n])
        
    def most_profitable(self, n):
        profits = {}
        for mid, imdb_id in self.movie_imdb_map.items():
            if imdb_id in self._cache:
                b = self._cache[imdb_id].get('Budget', 0)
                g = self._cache[imdb_id].get('Cumulative Worldwide Gross', 0)
                if b > 0 and g > 0:
                    profits[self._get_title(mid)] = g - b
        return dict(sorted(profits.items(), key=lambda x: x[1], reverse=True)[:n])
        
    def longest(self, n):
        runtimes = {}
        for mid, imdb_id in self.movie_imdb_map.items():
            if imdb_id in self._cache:
                r = self._cache[imdb_id].get('Runtime', 0)
                if r > 0:
                    runtimes[self._get_title(mid)] = r
        return dict(sorted(runtimes.items(), key=lambda x: x[1], reverse=True)[:n])
        
    def top_cost_per_minute(self, n):
        cpm = {}
        for mid, imdb_id in self.movie_imdb_map.items():
            if imdb_id in self._cache:
                b = self._cache[imdb_id].get('Budget', 0)
                r = self._cache[imdb_id].get('Runtime', 0)
                if b > 0 and r > 0:
                    val = round(b / r, 2)
                    cpm[self._get_title(mid)] = val
        return dict(sorted(cpm.items(), key=lambda x: x[1], reverse=True)[:n])


# ==========================================
# ТЕСТОВЫЙ КЛАСС
# ==========================================

class Tests:
    """
    Тесты с использованием PyTest для каждого метода классов.
    """
    @staticmethod
    def _create_dummy_csvs(base_dir):
        # Фильмы
        m_file = os.path.join(base_dir, "movies.csv")
        with open(m_file, 'w', encoding='utf-8') as f:
            f.write("movieId,title,genres\n")
            f.write("1,Toy Story (1995),Adventure|Animation|Children\n")
            f.write("2,Jumanji (1995),Adventure|Children|Fantasy\n")
            f.write("3,Grumpier Old Men (1995),Comedy|Romance\n")
            f.write("4,Waiting to Exhale (1995),Comedy|Drama|Romance\n")
            f.write("5,Long Title Movie (2020),Action|Drama|Thriller|War|Sci-Fi\n")

        # Оценки (Ratings)
        r_file = os.path.join(base_dir, "ratings.csv")
        ts = 964982703
        with open(r_file, 'w', encoding='utf-8') as f:
            f.write("userId,movieId,rating,timestamp\n")
            f.write(f"1,1,4.0,{ts}\n")
            f.write(f"1,3,4.0,{ts+100}\n")
            f.write(f"2,1,5.0,{ts+200}\n")
            f.write(f"2,2,3.0,{ts+300}\n")
            f.write(f"2,3,2.0,{ts+400}\n")
            f.write(f"3,1,4.0,{ts+500}\n")
            f.write(f"3,5,5.0,{ts+600}\n")
            
        # Теги
        t_file = os.path.join(base_dir, "tags.csv")
        with open(t_file, 'w', encoding='utf-8') as f:
            f.write("userId,movieId,tag,timestamp\n")
            f.write("1,1,pixar,1445714994\n")
            f.write("1,1,pixar,1445714999\n") # дубликат
            f.write("2,2,very scary,1445715207\n")
            f.write("2,2,animals,1445715200\n")
            f.write("3,3,old men,1445715054\n")
            f.write("3,3,funny,1445715051\n")

        # Ссылки
        l_file = os.path.join(base_dir, "links.csv")
        with open(l_file, 'w', encoding='utf-8') as f:
            f.write("movieId,imdbId,tmdbId\n")
            f.write("1,0114709,862\n") # Toy Story
            f.write("2,0113497,8844\n") # Jumanji
            f.write("3,0113228,15602\n") 
        
        return m_file, r_file, t_file, l_file

    # --- ТЕСТЫ ДЛЯ MOVIES ---
    def test_movies_dist_by_release(self, tmp_path):
        m, _, _, _ = Tests._create_dummy_csvs(tmp_path)
        movies = Movies(m)
        res = movies.dist_by_release()
        assert isinstance(res, dict)
        assert 1995 in res
        # Проверка сортировки (по убыванию количества)
        vals = list(res.values())
        assert all(vals[i] >= vals[i+1] for i in range(len(vals)-1))

    def test_movies_dist_by_genres(self, tmp_path):
        m, _, _, _ = Tests._create_dummy_csvs(tmp_path)
        movies = Movies(m)
        res = movies.dist_by_genres()
        assert isinstance(res, dict)
        assert 'Adventure' in res
        # Проверка сортировки
        vals = list(res.values())
        assert all(vals[i] >= vals[i+1] for i in range(len(vals)-1))

    def test_movies_most_genres(self, tmp_path):
        m, _, _, _ = Tests._create_dummy_csvs(tmp_path)
        movies = Movies(m)
        res = movies.most_genres(5)
        assert isinstance(res, dict)
        # Фильм 5 имеет 5 жанров
        assert res['Long Title Movie (2020)'] == 5
        # Проверка сортировки
        vals = list(res.values())
        assert all(vals[i] >= vals[i+1] for i in range(len(vals)-1))

    # --- ТЕСТЫ ДЛЯ TAGS ---
    def test_tags_methods(self, tmp_path):
        _, _, t, _ = Tests._create_dummy_csvs(tmp_path)
        tags = Tags(t)
        
        # most_words
        mw = tags.most_words(10)
        assert isinstance(mw, dict)
        assert mw['very scary'] == 2
        assert mw['pixar'] == 1
        
        # longest
        lg = tags.longest(10)
        assert isinstance(lg, list)
        assert 'very scary' in lg
        assert len(lg[0]) >= len(lg[-1])
        
        # most_words_and_longest (Пересечение)
        inter = tags.most_words_and_longest(5)
        assert isinstance(inter, list)
        
        # most_popular
        pop = tags.most_popular(5)
        assert isinstance(pop, dict)
        assert pop['pixar'] == 2 # был дублирован в csv
        
        # tags_with
        tw = tags.tags_with('scary')
        assert isinstance(tw, list)
        assert 'very scary' in tw
        # проверка алфавитной сортировки (если бы было больше)
        tw2 = tags.tags_with('a')
        assert tw2 == sorted(tw2)

    # --- ТЕСТЫ ДЛЯ RATINGS ---
    def test_ratings_movies(self, tmp_path):
        m, r_file, _, _ = Tests._create_dummy_csvs(tmp_path)
        ratings = Ratings(r_file, m)
        
        # dist_by_year
        dby = ratings.movies.dist_by_year()
        assert isinstance(dby, dict)
        assert 2000 in dby # из timestamp
        
        # dist_by_rating
        dbr = ratings.movies.dist_by_rating()
        assert isinstance(dbr, dict)
        assert 4.0 in dbr
        # проверка сортировки ключей по возрастанию
        keys = list(dbr.keys())
        assert all(keys[i] <= keys[i+1] for i in range(len(keys)-1))
        
        # top_by_num_of_ratings
        top_n = ratings.movies.top_by_num_of_ratings(3)
        assert isinstance(top_n, dict)
        assert 'Toy Story (1995)' in top_n
        # проверка сортировки значений по убыванию
        vals = list(top_n.values())
        assert all(vals[i] >= vals[i+1] for i in range(len(vals)-1))
        
        # top_by_ratings (avg)
        top_avg = ratings.movies.top_by_ratings(3, metric=Ratings.average)
        assert isinstance(top_avg, dict)
        
        # top_controversial
        top_var = ratings.movies.top_controversial(3)
        assert isinstance(top_var, dict)
        
    def test_ratings_users(self, tmp_path):
        m, r_file, _, _ = Tests._create_dummy_csvs(tmp_path)
        ratings = Ratings(r_file, m)
        
        # dist_by_num_of_ratings
        udist = ratings.users.dist_by_num_of_ratings()
        assert isinstance(udist, dict)
        
        # dist_by_ratings
        udist2 = ratings.users.dist_by_ratings(metric=Ratings.average)
        assert isinstance(udist2, dict)
        
        # top_controversial
        uvar = ratings.users.top_controversial(3)
        assert isinstance(uvar, dict)
        # Пользователь 2 оценил 1:5.0, 2:3.0, 3:2.0 -> имеет дисперсию
        assert 2 in uvar

    # Тесты для ЛИНКС:
    def _get_ready_links_object(self):
        l = Links("non_existent_file.csv")

        l.movie_imdb_map = {
            '10': 'tt1', 
            '20': 'tt2', 
            '30': 'tt3'
        }

        l.titles = {
            10: 'Movie A (Cheap)',
            20: 'Movie B (Expensive)',
            30: 'Movie C (Profitable)'
        }

        l._cache = {
            'tt1': { # Фильм A
                'Director': 'Director One',
                'Budget': 100.0,
                'Cumulative Worldwide Gross': 150.0, # Прибыль 50
                'Runtime': 100 # Стоимость в минуту = 1.0
            },
            'tt2': { # Фильм B
                'Director': 'Director One', # Тот же режиссёр, что и у A
                'Budget': 500.0, # Самый дорогой
                'Cumulative Worldwide Gross': 510.0, # Прибыль 10
                'Runtime': 100 # Стоимость в минуту = 5.0 (Наивысшая)
            },
            'tt3': { # Фильм C
                'Director': 'Director Two',
                'Budget': 100.0, 
                'Cumulative Worldwide Gross': 600.0, # Прибыль 500 (Самый прибыльный)
                'Runtime': 200 # Самый длинный
            }
        }
        return l

    def test_get_imdb(self):
        l = self._get_ready_links_object()
        
        result = l.get_imdb(['10', '20'], ['Director', 'Budget'])

        assert type(result) == list
        
        assert type(result[0]) == list
        assert type(result[0][0]) == str # MovieID
        
        assert result[0][0] == '20' 
        assert result[1][0] == '10'

    def test_top_directors(self):
        l = self._get_ready_links_object()
        
        result = l.top_directors(5)

        assert type(result) == dict
        
        assert result['Director One'] == 2
        
        counts = list(result.values())
        assert counts[0] >= counts[1]

    def test_most_expensive(self):
        l = self._get_ready_links_object()
        
        result = l.most_expensive(5)

        assert type(result) == dict
        
        first_budget = list(result.values())[0]
        assert isinstance(first_budget, (int, float))

        top_movie = list(result.keys())[0]
        assert top_movie == 'Movie B (Expensive)'

    def test_most_profitable(self):
        l = self._get_ready_links_object()
        
        result = l.most_profitable(5)

        assert type(result) == dict

        top_movie = list(result.keys())[0]
        assert top_movie == 'Movie C (Profitable)'
        assert result[top_movie] == 500.0

    def test_longest(self):
        l = self._get_ready_links_object()
        
        result = l.longest(5)

        assert type(result) == dict
        
        top_movie = list(result.keys())[0]
        assert top_movie == 'Movie C (Profitable)'
        assert result[top_movie] == 200

    def test_top_cost_per_minute(self):
        l = self._get_ready_links_object()
        
        result = l.top_cost_per_minute(5)

        assert type(result) == dict
        
        first_val = list(result.values())[0]
        assert isinstance(first_val, float)

        top_movie = list(result.keys())[0]
        assert top_movie == 'Movie B (Expensive)'
        assert result[top_movie] == 5.0

if __name__ == '__main__':
    # Запуск тестов
    sys.exit(pytest.main(["-q", __file__]))
