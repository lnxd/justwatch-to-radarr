#!/usr/bin/env python3

import requests
import schedule
import time
import os
from datetime import datetime

RADARR_URL = os.getenv('RADARR_URL', 'http://localhost:7878')
RADARR_API_KEY = os.getenv('RADARR_API_KEY', '')
TMDB_API_KEY = os.getenv('TMDB_API_KEY', '')
ROOT_FOLDER = os.getenv('ROOT_FOLDER', '/movies/')
QUALITY_PROFILE_ID = int(os.getenv('QUALITY_PROFILE_ID', '1'))
SYNC_HOURS = int(os.getenv('SYNC_HOURS', '6'))
MOVIE_LIMIT = int(os.getenv('MOVIE_LIMIT', '100'))
TAG_NAME = os.getenv('TAG_NAME', 'popular')
COUNTRY = os.getenv('COUNTRY', 'AU')
LANGUAGE = os.getenv('LANGUAGE', 'en')
RELEASE_YEAR_MIN = int(os.getenv('RELEASE_YEAR_MIN', '2010'))
RELEASE_YEAR_MAX = int(os.getenv('RELEASE_YEAR_MAX', '2030'))

# Genre/country codes to exclude (JustWatch shortcodes)
EXCLUDED_GENRES = [x for x in os.getenv('EXCLUDED_GENRES', 'hrr,ani').split(',') if x]
EXCLUDED_COUNTRIES = [x for x in os.getenv('EXCLUDED_COUNTRIES', 'IN,JP,CN,FR,DE,IT,ES').split(',') if x]

tag_id = None


def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def ensure_tag():
    global tag_id
    headers = {'X-Api-Key': RADARR_API_KEY}
    try:
        resp = requests.get(f"{RADARR_URL}/api/v3/tag", headers=headers, timeout=10)
        resp.raise_for_status()
        for t in resp.json():
            if t['label'].lower() == TAG_NAME.lower():
                tag_id = t['id']
                return
        resp = requests.post(f"{RADARR_URL}/api/v3/tag", headers=headers,
                             json={"label": TAG_NAME}, timeout=10)
        resp.raise_for_status()
        tag_id = resp.json()['id']
        log(f"Created tag '{TAG_NAME}' (id: {tag_id})")
    except requests.RequestException as e:
        log(f"Tag setup failed: {e}")


def get_justwatch_popular():
    resp = requests.post('https://apis.justwatch.com/graphql', timeout=30, headers={
        'User-Agent': 'Mozilla/5.0',
        'Accept': '*/*',
        'Referer': 'https://www.justwatch.com/',
        'content-type': 'application/json',
        'Origin': 'https://www.justwatch.com',
    }, json={
        "operationName": "GetPopularTitles",
        "variables": {
            "allowSponsoredRecommendations": {
                "appId": "3.8.2-webapp#7141b04",
                "country": COUNTRY,
                "language": LANGUAGE,
                "pageType": "VIEW_POPULAR",
                "placement": "POPULAR_VIEW",
                "platform": "WEB",
                "supportedObjectTypes": ["MOVIE", "SHOW", "GENERIC_TITLE_LIST"],
                "supportedFormats": ["IMAGE", "VIDEO"],
            },
            "country": COUNTRY,
            "first": MOVIE_LIMIT,
            "language": LANGUAGE,
            "popularTitlesFilter": {
                "ageCertifications": [],
                "excludeGenres": EXCLUDED_GENRES,
                "excludeProductionCountries": EXCLUDED_COUNTRIES,
                "objectTypes": ["MOVIE"],
                "productionCountries": [],
                "genres": [],
                "packages": [],
                "excludeIrrelevantTitles": False,
                "presentationTypes": [],
                "monetizationTypes": [],
                "releaseYear": {"min": RELEASE_YEAR_MIN, "max": RELEASE_YEAR_MAX},
                "searchQuery": "",
            },
            "popularTitlesSortBy": "POPULAR",
        },
        "query": "query GetPopularTitles($allowSponsoredRecommendations: SponsoredRecommendationsInput!, $country: Country!, $first: Int!, $language: Language!, $popularTitlesFilter: TitleFilter!, $popularTitlesSortBy: PopularTitlesSorting!) {\n  popularTitles(allowSponsoredRecommendations: $allowSponsoredRecommendations, country: $country, filter: $popularTitlesFilter, first: $first, sortBy: $popularTitlesSortBy, offset: null, after: \"\") {\n    edges {\n      node {\n        content(country: $country, language: $language) {\n          title\n          externalIds {\n            imdbId\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
    })
    resp.raise_for_status()
    data = resp.json()

    movies = []
    for edge in data.get('data', {}).get('popularTitles', {}).get('edges', []):
        content = edge.get('node', {}).get('content', {})
        imdb_id = content.get('externalIds', {}).get('imdbId')
        if imdb_id:
            movies.append({'title': content.get('title', 'Unknown'), 'imdbid': imdb_id})

    return movies


def imdb_to_tmdb(imdb_id):
    resp = requests.get(f"https://api.themoviedb.org/3/find/{imdb_id}",
                        params={'api_key': TMDB_API_KEY, 'external_source': 'imdb_id'},
                        timeout=10)
    if resp.status_code != 200:
        return None, None
    results = resp.json().get('movie_results', [])
    if not results:
        return None, None
    return results[0]['id'], results[0].get('release_date', '')[:4]


def sync():
    log(f"Starting sync with tag '{TAG_NAME}'...")

    if tag_id is None:
        ensure_tag()
        if tag_id is None:
            log("Warning: tag setup failed, movies will be added without tag")

    try:
        movies = get_justwatch_popular()
    except Exception as e:
        log(f"JustWatch fetch failed: {e}")
        return

    if not movies:
        log("No movies returned")
        return

    log(f"Found {len(movies)} movies (limit: {MOVIE_LIMIT})")

    added, skipped, failed = 0, 0, 0
    added_titles = []
    headers = {'X-Api-Key': RADARR_API_KEY}

    for movie in movies:
        if not movie.get('imdbid'):
            failed += 1
            continue

        try:
            tmdb_id, year = imdb_to_tmdb(movie['imdbid'])
        except requests.RequestException:
            failed += 1
            continue
        if not tmdb_id:
            failed += 1
            continue

        year = year or str(datetime.now().year)

        try:
            resp = requests.post(f"{RADARR_URL}/api/v3/movie", headers=headers, timeout=30, json={
                "title": movie['title'],
                "qualityProfileId": QUALITY_PROFILE_ID,
                "tmdbId": tmdb_id,
                "imdbId": movie['imdbid'],
                "year": int(year),
                "rootFolderPath": ROOT_FOLDER,
                "monitored": True,
                "tags": [tag_id] if tag_id else [],
                "addOptions": {"searchForMovie": True},
            })
            if resp.status_code == 201:
                added_titles.append(f"{movie['title']} ({year})")
                added += 1
            elif resp.status_code == 400 and "MovieExistsValidator" in resp.text:
                skipped += 1
            else:
                failed += 1
        except requests.RequestException:
            failed += 1

    if added_titles:
        log(f"Added {len(added_titles)} movies:")
        for title in added_titles:
            log(f"  - {title}")

    log(f"Complete. Added: {added}, Skipped: {skipped}, Failed: {failed}")


if __name__ == '__main__':
    log(f"Starting. Sync every {SYNC_HOURS}h, years {RELEASE_YEAR_MIN}-{RELEASE_YEAR_MAX}, "
        f"country {COUNTRY}, tag '{TAG_NAME}'")

    sync()
    schedule.every(SYNC_HOURS).hours.do(sync)

    while True:
        schedule.run_pending()
        time.sleep(60)
