# lastfmcache
lastfmcache is a caching interface library for last.fm, written in Python. It meshes data retrieved from the API (via [pylast]([http://github.com/pylast])) with data retreived directly from the website.

Retrieved data is optionally cached in a local file, using sqlite.

This library bypasses several long-term unfixed issues with the last.fm API, including:
- Missing artist artwork
- Release date not populated
- Release tags not populated
- Certain release tags not populated on the API, others not populated on the website
- Track listing not available

## Usage
```
from lastfmcache import LastfmCache

lastfm_api_key = ""
lastfm_shared_secret = ""

lastfm = LastfmCache(lastfm_api_key, lastfm_shared_secret)
lastfm.enable_file_cache()  # optional

artist = lastfm.get_artist("Pink Floyd")
release = lastfm.get_release("Pink Floyd", "Dark Side of the Moon")

top_releases = lastfm.get_top_user_releases("username")

```

### Artist class:
```
artist.artist_name: str
artist.listener_count: int
artist.play_count: int
artist.biography: str
artist.cover_image: str
artist.tags: OrderedDict[str, int]      # tag -> weight
```
### Release class:
```
release_name: str
artist_name: str
release_date: datetime
listener_count: int
play_count: int
cover_image: str
has_cover_image: bool
tags = OrderedDict[str, int]            # tag -> weight
tracks = OrderedDict[int, Track]        # track number -> track
```

### Track class
```
track_number: int
track_name: str
artist_name: str
listener_count: int
```

### Top release class
```
index: int          # ranking of the release
scrobbles: int
artist: str
title: str
```

## Installation

`pip install lastfmcache`
