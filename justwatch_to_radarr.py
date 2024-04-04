import requests

release_year = 2024  # Year to set for movie release and filter
filter_year_min = 2024  # Minimum year for movies
filter_year_max = 2024  # Maximum year for movies
num_movies = 30  # Number of movies to fetch from JustWatch
radarr_url = "http://0.0.0.0:7878/api/v3/movie" # Set a valid Radarr url
quality_profile_id = 7  # Update this according to your quality profile ID in Radarr
root_folder_path = "/movies-en/"  # Update this to your Radarr movies root folder path
tmdb_api_key = ""
radarr_api_key = ""

justwatch_headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.justwatch.com/",
    "content-type": "application/json",
    "App-Version": "3.8.2-web-web",
    "Origin": "https://www.justwatch.com",
    "DNT": "1",
}

justwatch_query_data = {
    "operationName": "GetPopularTitles",
    "variables": {
        "allowSponsoredRecommendations": {
            "appId": "3.8.2-webapp#7141b04",
            "country": "AU",
            "language": "en",
            "pageType": "VIEW_POPULAR",
            "placement": "POPULAR_VIEW",
            "platform": "WEB",
            "supportedObjectTypes": ["MOVIE", "SHOW", "GENERIC_TITLE_LIST"],
            "supportedFormats": ["IMAGE", "VIDEO"],
        },
        "country": "AU",
        "first": num_movies,
        "language": "en",
        "popularTitlesFilter": {
            "ageCertifications": [],
            "excludeGenres": [],
            "excludeProductionCountries": [],
            "objectTypes": ["MOVIE"],
            "productionCountries": [],
            "genres": [],
            "packages": [],
            "excludeIrrelevantTitles": False,
            "presentationTypes": [],
            "monetizationTypes": [],
            "releaseYear": {"min": filter_year_min, "max": filter_year_max},
            "searchQuery": "",
        },
        "popularTitlesSortBy": "POPULAR",
    },
    "query": "...",
}


def get_popular_movies():
    """
    Get popular movies from JustWatch using their GraphQL API. This function returns a list of dictionaries
    that contain the title and IMDb ID of each movie. I was not aware that JustWatch had a public API when I
    wrote this script, so I reverse engineered their GraphQL API.
    """
    url = "https://apis.justwatch.com/graphql"

    response = requests.post(url, headers=justwatch_headers, json=justwatch_query_data)
    response_data = response.json()

    movies = []
    for edge in response_data["data"]["popularTitles"]["edges"]:
        title = edge["node"]["content"]["title"]
        imdb_id = edge["node"]["content"]["externalIds"]["imdbId"]
        movies.append({"title": title, "imdbid": imdb_id})

    return movies


def get_tmdb_id(imdb_id):
    """
    Get TMDb ID from IMDb ID using TMDb API. This function returns the TMDb ID of the movie if it exists,
    otherwise it returns None. This function can likely be replaced by collecting the TMDb IDs for all movies
    from the public JustWatch API directly, rather than making API requests to multiple services.
    """
    tmdb_url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={tmdb_api_key}&language=en-US&external_source=imdb_id"
    response = requests.get(tmdb_url)
    if response.status_code == 200:
        data = response.json()
        tmdb_id = (
            data.get("movie_results")[0].get("id")
            if data.get("movie_results")
            else None
        )
        return tmdb_id
    else:
        return None


def add_movies_to_radarr(movies):
    """
    Add movies to Radarr using Radarr API. This function takes a list of movies as input and adds them to
    Radarr if they do not already exist.
    """
    headers = {"Content-Type": "application/json", "X-Api-Key": radarr_api_key}

    for movie in movies:
        tmdb_id = get_tmdb_id(movie["imdbid"])
        if tmdb_id:
            radarr_movie_data = {
                "title": movie["title"],
                "qualityProfileId": quality_profile_id,
                "tmdbId": tmdb_id,
                "imdbId": movie["imdbid"],
                "year": release_year,
                "rootFolderPath": root_folder_path,
                "monitored": True,
                "addOptions": {"searchForMovie": True},
            }

            print(f"Trying to add: {movie['title']}")

            response = requests.post(
                radarr_url, headers=headers, json=radarr_movie_data
            )

            if response.status_code == 201:
                print(f"Movie '{movie['title']}' added successfully.")
            elif (
                response.status_code == 400 and "MovieExistsValidator" in response.text
            ):
                print("Movie already added. Skipping!")
            else:
                print(
                    f"Failed to add movie '{movie['title']}' with IMDb ID '{movie['imdbid']}' and TMDB ID '{tmdb_id}'."
                )
                if response.text:
                    print("Error message from server:", response.text)
                else:
                    print("No error message from server.")

                print(response)
        else:
            print(
                f"Failed to get TMDb ID for movie '{movie['title']}' with IMDb ID '{movie['imdbid']}'."
            )


if __name__ == "__main__":
    popular_movies = get_popular_movies()
    add_movies_to_radarr(popular_movies)
