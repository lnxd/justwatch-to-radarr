# justwatch-to-radarr

Fetches popular movies from [JustWatch](https://www.justwatch.com/) and adds them to [Radarr](https://github.com/Radarr/Radarr). Runs on a schedule, tags added movies for easy filtering.

## How it works

1. Queries the JustWatch GraphQL API for popular movies in your country
2. Converts IMDB IDs to TMDB IDs (required by Radarr)
3. Adds any missing movies to Radarr with a configurable tag
4. Repeats every N hours (default: 6)

## Usage

### Docker

```bash
docker build -t justwatch-to-radarr .

docker run -d \
  -e RADARR_URL=http://radarr:7878 \
  -e RADARR_API_KEY=your_key \
  -e TMDB_API_KEY=your_key \
  -e ROOT_FOLDER=/movies/ \
  justwatch-to-radarr
```

### Kubernetes

Add your API keys to the Secret in `k8s.yaml`, then `kubectl apply -f k8s.yaml`.

### Standalone

```bash
pip install -r requirements.txt
RADARR_API_KEY=your_key TMDB_API_KEY=your_key python justwatch_to_radarr.py
```

## Configuration

All config is via environment variables. See the top of `justwatch_to_radarr.py` for the full list and defaults.

The main ones you'll need to set: `RADARR_URL`, `RADARR_API_KEY`, `TMDB_API_KEY`, `ROOT_FOLDER`.

You'll also need a [TMDB API key](https://www.themoviedb.org/settings/api).
