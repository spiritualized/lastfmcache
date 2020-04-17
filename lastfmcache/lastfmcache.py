from collections import OrderedDict
from typing import Dict, List

import pylast
from pylast import _Opus
import bs4
import requests
import datetime
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.event
import sqlalchemy.pool
from sqlalchemy.ext.declarative import declarative_base
import sqlite3


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if type(dbapi_connection) is sqlite3.Connection:  # play well with other DB backends
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


class LastfmArtist:

    def __init__(self) -> None:
        self.artist_name = None
        self.listener_count = None
        self.play_count = None
        self.biography = ""
        self.cover_image = None
        self.tags = OrderedDict()

    def __repr__(self) -> str:
        has_cover_image = "yes" if self.cover_image else "no"
        has_biography = "yes" if self.biography else "no"
        tags = ", ".join(self.tags)

        return """Artist name: {0}
                Listener count: {1}
                Play count: {2}
                Has cover image: {3}
                Has biography: {4}
                Tags: {5}""".format(self.artist_name, self.listener_count, self.play_count, has_cover_image,
                                    has_biography, tags)


class LastfmRelease:

    def __init__(self) -> None:
        self.release_name = None
        self.artist_name = None
        self.release_date = None
        self.listener_count = None
        self.play_count = None
        self.cover_image = None
        self.has_cover_image = False
        self.tags = OrderedDict()
        self.tracks = OrderedDict()

    def __repr__(self) -> str:
        has_cover_image = "yes" if self.has_cover_image else "no"
        tags = ", ".join(self.tags)

        return """Release name: {0}
                Listener count: {1}
                Play count: {2}
                Has cover image: {3}
                Release date: {4}
                Tags: {5}""".format(self.release_name, self.listener_count, self.play_count, has_cover_image,
                                    self.release_date, tags)


class LastfmTrack:

    def __init__(self, track_number: int, track_name: str, artist_name: str, listener_count: int) -> None:
        self.track_number = track_number
        self.track_name = track_name
        self.artist_name = artist_name
        self.listener_count = listener_count


class LastfmTopRelease:

    def __init__(self, index: int, scrobbles: int, artist: str, title: str) -> None:
        self.index = index
        self.scrobbles = scrobbles
        self.artist = artist
        self.title = title


class LastfmCache:

    def __init__(self, api_key: str, shared_secret: str) -> None:
        self.api_key = api_key
        self.shared_secret = shared_secret
        self.api = pylast.LastFMNetwork(api_key=api_key, api_secret=shared_secret)
        self.db = None
        self.cache_validity = None

    class LastfmCacheError(Exception):
        pass

    class ReleaseNotFoundError(Exception):
        def __init__(self, release_name, artist_name):
            self.release_name = release_name
            self.artist_name = artist_name

            super().__init__("Release '{0}' by {1} not found.".format(self.release_name, self.artist_name))

    class ArtistNotFoundError(Exception):
        def __init__(self, artist_name):
            self.artist_name = artist_name

            super().__init__("Artist '{0}' not found.".format(self.artist_name))


    __db_base__ = declarative_base()

    class Artist(__db_base__):
        __tablename__ = "artists"

        id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
        fetched = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
        artist_name = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False)
        listener_count = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True)
        play_count = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True)
        cover_image = sqlalchemy.Column(sqlalchemy.String(512), nullable=True)
        biography = sqlalchemy.Column(sqlalchemy.Text, nullable=False)

        tags = sqlalchemy.orm.relationship("ArtistTag", order_by="desc(ArtistTag.score)", cascade="all, delete-orphan")

        def __init__(self, artist_name: str, listener_count: int, play_count: int, cover_image: str,
                     biography: str) -> None:
            self.fetched = datetime.datetime.now()
            self.artist_name = artist_name
            self.listener_count = listener_count
            self.play_count = play_count
            self.cover_image = cover_image
            self.biography = biography
            self.tags = []

    class ArtistTag(__db_base__):
        __tablename__ = "artist_tags"

        artist_id = sqlalchemy.Column(sqlalchemy.ForeignKey("artists.id", ondelete='CASCADE', onupdate='CASCADE'),
                                      primary_key=True)
        tag = sqlalchemy.Column(sqlalchemy.String(100), nullable=False, primary_key=True)
        score = sqlalchemy.Column(sqlalchemy.Integer)

        def __init__(self, tag: str, score: int) -> None:
            self.tag = tag
            self.score = score

    class Release(__db_base__):
        __tablename__ = "releases"

        id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
        fetched = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
        artist_name = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False)
        release_name = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False)
        release_date = sqlalchemy.Column(sqlalchemy.String(10))
        listener_count = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True)
        play_count = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True)
        cover_image = sqlalchemy.Column(sqlalchemy.String(512))

        tags = sqlalchemy.orm.relationship("ReleaseTag", order_by="desc(ReleaseTag.score)",
                                           cascade="all, delete-orphan")
        tracks = sqlalchemy.orm.relationship("ReleaseTrack", order_by="ReleaseTrack.track_number",
                                             cascade="all, delete-orphan")

        def __init__(self, artist_name: str, release_name: str, release_date: datetime, listener_count: int,
                     play_count: int, cover_image: str) -> None:
            self.fetched = datetime.datetime.now()
            self.artist_name = artist_name
            self.release_name = release_name
            self.release_date = release_date
            self.listener_count = listener_count
            self.play_count = play_count
            self.cover_image = cover_image
            self.tags = []
            self.tracks = []

    class ReleaseTag(__db_base__):
        __tablename__ = "release_tags"

        release_id = sqlalchemy.Column(sqlalchemy.ForeignKey("releases.id", ondelete='CASCADE', onupdate='CASCADE'),
                                       primary_key=True)
        tag = sqlalchemy.Column(sqlalchemy.String(100), nullable=False, primary_key=True)
        score = sqlalchemy.Column(sqlalchemy.Integer)

        def __init__(self, tag: str, score: int) -> None:
            self.tag = tag
            self.score = score

    class ReleaseTrack(__db_base__):
        __tablename__ = "release_tracks"

        release_id = sqlalchemy.Column(sqlalchemy.ForeignKey("releases.id", ondelete='CASCADE', onupdate='CASCADE'),
                                       primary_key=True)
        track_number = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, primary_key=True)
        track_name = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False)
        track_artist = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=True)
        listener_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)

        def __init__(self, track_number: int, track_name: str, track_artist: str, listener_count: int) -> None:
            self.track_number = track_number
            self.track_name = track_name
            self.track_artist = track_artist
            self.listener_count = listener_count

    class TopUserRelease(__db_base__):
        __tablename__ = "top_user_releases"

        fetched = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
        username = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False, primary_key=True)
        index = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, primary_key=True)
        scrobbles = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
        artist = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False)
        title = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False)

        def __init__(self, fetched: datetime, username: str, index: int, scrobbles: int, artist: str,
                     title: str) -> None:
            self.fetched = fetched
            self.username = username
            self.index = index
            self.scrobbles = scrobbles
            self.artist = artist
            self.title = title

    class NotFoundArtist(__db_base__):
        __tablename__ = "not_found_artists"

        id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
        fetched = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
        artist_name = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False)

        def __init__(self, artist_name: str) -> None:
            self.fetched = datetime.datetime.now()
            self.artist_name = artist_name

    class NotFoundRelease(__db_base__):
        __tablename__ = "not_found_releases"

        id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
        fetched = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
        artist_name = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False)
        release_name = sqlalchemy.Column(sqlalchemy.String(512, collation='NOCASE'), nullable=False)

        def __init__(self, artist_name: str, release_name: str) -> None:
            self.fetched = datetime.datetime.now()
            self.artist_name = artist_name
            self.release_name = release_name

    # connect to database
    def enable_file_cache(self, cache_validity: int = 86400 * 28) -> None:

        engine = sqlalchemy.create_engine("sqlite:///cache.db?check_same_thread=False",
                                          poolclass=sqlalchemy.pool.SingletonThreadPool)
        LastfmCache.__db_base__.metadata.create_all(engine)

        db = sqlalchemy.orm.sessionmaker(engine)
        self.db = sqlalchemy.orm.scoped_session(db)
        self.cache_validity = cache_validity

    def get_artist(self, artist_name: str) -> LastfmArtist:

        artist = LastfmArtist()

        db_artist = None

        if self.db:
            db_artist = self.db.query(LastfmCache.Artist).filter_by(artist_name=artist_name).first()
            if db_artist and db_artist.fetched > datetime.datetime.now() - datetime.timedelta(
                    seconds=self.cache_validity):
                artist.artist_name = db_artist.artist_name
                artist.listener_count = db_artist.listener_count
                artist.play_count = db_artist.play_count
                artist.cover_image = db_artist.cover_image
                artist.biography = db_artist.biography
                for tag in db_artist.tags:
                    artist.tags[tag.tag] = tag.score

                return artist

            self.db.query(LastfmCache.NotFoundArtist).filter_by(artist_name=artist_name).first()
            if db_artist and db_artist.fetched > datetime.datetime.now() - datetime.timedelta(
                seconds=self.cache_validity):
                raise LastfmCache.ArtistNotFoundError(artist_name)

        try:
            api_artist = self.api.get_artist(artist_name)
            artist.artist_name = api_artist.get_name(properly_capitalized=True)
            artist.listener_count = api_artist.get_listener_count()
            artist.play_count = api_artist.get_playcount()
            artist.cover_image = api_artist.get_cover_image()
            artist.biography = api_artist.get_bio_content().split('<a href="https://www.last.fm/music/')[0].strip()

        except pylast.WSError as e:
            if e.details == "The artist you supplied could not be found":
                self.db.add(LastfmCache.NotFoundArtist(artist_name))
                self.db.commit()

                raise LastfmCache.ArtistNotFoundError(artist_name) from e

        except AttributeError:  # TODO remove this workaround for pylast failure on looking up an empty biography
            pass


        # Remove "star" images
        if artist.cover_image and "2a96cbd8b46e442fc41c2b86b821562f" in artist.cover_image:
            artist.cover_image = None

        for tag in api_artist.get_top_tags():
            artist.tags[tag.item.name.lower()] = tag.weight

        # only fetch the HTML page if the artist cover image is missing
        if not artist.cover_image:
            url_artist_name = LastfmCache.__lastfm_urlencode(artist_name)
            resp = requests.get("https://www.last.fm/music/{artist}".format(artist=url_artist_name))

            if resp.status_code == 404:
                raise LastfmCache.LastfmCacheError("Artist '{artist_name}' not found.".format(artist_name=artist_name))
            soup = bs4.BeautifulSoup(resp.content, 'html5lib')

            if soup.find(class_="header-new-background-image"):
                artist.cover_image = soup.find(class_="header-new-background-image").get("content")

        # update/create in the cache entry
        if self.db:
            if db_artist:
                db_artist.__init__(artist.artist_name, artist.listener_count, artist.play_count, artist.cover_image,
                                   artist.biography)
            else:
                db_artist = LastfmCache.Artist(artist.artist_name, artist.listener_count, artist.play_count,
                                               artist.cover_image, artist.biography)
                self.db.add(db_artist)
            for tag in artist.tags:
                db_artist.tags.append(LastfmCache.ArtistTag(tag, artist.tags[tag]))
            self.db.commit()

        return artist

    def get_release(self, artist_name: str, release_name: str) -> LastfmRelease:

        release = LastfmRelease()

        db_release = None

        if self.db:
            db_release = self.db.query(LastfmCache.Release).filter_by(artist_name=artist_name,
                                                                      release_name=release_name).first()
            if db_release and db_release.fetched > datetime.datetime.now() - datetime.timedelta(
                    seconds=self.cache_validity):
                release.artist_name = db_release.artist_name
                release.release_name = db_release.release_name
                release.release_date = db_release.release_date
                release.listener_count = db_release.listener_count
                release.play_count = db_release.play_count
                release.cover_image = db_release.cover_image
                for tag in db_release.tags:
                    release.tags[tag.tag] = tag.score
                for track in db_release.tracks:
                    release.tracks[track.track_number] = LastfmTrack(track.track_number, track.track_name,
                                                                     track.track_artist, track.listener_count)

                return release

            db_release = self.db.query(LastfmCache.NotFoundRelease).filter_by(artist_name=artist_name,
                                                                      release_name=release_name).first()
            if db_release and db_release.fetched > datetime.datetime.now() - datetime.timedelta(
                seconds=self.cache_validity):
                raise LastfmCache.ReleaseNotFoundError(artist_name, release_name)

        api_release = self.api.get_album(artist_name, release_name)
        try:
            release.release_name = api_release.get_title(properly_capitalized=True)
        except pylast.WSError as e:
            if e.details == "Album not found":
                self.db.add(LastfmCache.NotFoundRelease(release_name, artist_name))
                self.db.commit()
                raise LastfmCache.ReleaseNotFoundError(release_name, artist_name) from e

        release.artist_name = api_release.get_artist().get_name(properly_capitalized=True)
        release.listener_count = api_release.get_listener_count()
        release.play_count = api_release.get_playcount()
        release.cover_image = api_release.get_cover_image()

        api_tags = OrderedDict()
        for tag in api_release.get_top_tags():
            api_tags[tag.item.name.lower()] = tag.weight

        url_artist_name = LastfmCache.__lastfm_urlencode(artist_name)
        url_release_name = LastfmCache.__lastfm_urlencode(release_name)
        resp = requests.get("https://www.last.fm/music/{artist}/{release}"
                            .format(artist=url_artist_name, release=url_release_name))

        if resp.status_code == 404:
            raise LastfmCache.LastfmCacheError("Release '{0}' by {1} not found.".format(release_name, artist_name))

        soup = bs4.BeautifulSoup(resp.content, 'html5lib')

        if soup.find(class_="catalogue-metadata"):
            matches = [x for x in soup.find(class_="catalogue-metadata").findAll({"dt", "dd"})]
            pairs = [matches[i:i + 2] for i in range(0, len(matches), 2)]

            for pair in pairs:
                if pair[0].string == "Release Date":
                    release_date_str = pair[1].string
                    try:
                        release.release_date = datetime.datetime.strptime(release_date_str, "%d %B %Y").date().strftime(
                            "%Y-%m-%d")
                    except:
                        try:
                            release.release_date = datetime.datetime.strptime(release_date_str,
                                                                              "%B %Y").date().strftime("%Y-%m")
                        except:
                            release.release_date = datetime.datetime.strptime(release_date_str,
                                                                              "%Y").date().strftime("%Y")

        # tags are often not populated correctly/at all on the API
        web_tags = OrderedDict()
        if soup.find(class_="catalogue-tags"):
            next_weight = -1
            for match in soup.find(class_="catalogue-tags").findAll(class_="tag"):
                web_tags[str(match.string)] = next_weight
                next_weight -= 1

        # combine the two tag sets intelligently
        release.tags = LastfmCache.combine_tags(api_tags, web_tags)

        if soup.find(id="tracklist"):
            for row in soup.find(id="tracklist").find("tbody").findAll("tr"):
                track_number = int(row.find(class_="chartlist-index").string)
                track_name = row.find(class_="chartlist-name").find("a").get_text()
                listener_count = str(
                    row.find(class_="chartlist-count-bar").find(class_="chartlist-count-bar-value")
                    .next.replace(",", "")).strip()
                listener_count = str(listener_count) if listener_count else 0
                track_artist = None
                if row.find(class_="chartlist-artist").find("a"):
                    track_artist = row.find(class_="chartlist-artist").find("a").string
                release.tracks[track_number] = LastfmTrack(track_number, track_name, track_artist, listener_count)

        # update/create in the cache entry
        if self.db:
            if db_release:
                db_release.__init__(release.artist_name, release.release_name, release.release_date,
                                    release.listener_count, release.play_count, release.cover_image)
            else:
                db_release = LastfmCache.Release(release.artist_name, release.release_name, release.release_date,
                                                 release.listener_count, release.play_count, release.cover_image)
                self.db.add(db_release)
            for tag in release.tags:
                db_release.tags.append(LastfmCache.ReleaseTag(tag, release.tags[tag]))
            for track in release.tracks:
                db_release.tracks.append(
                    LastfmCache.ReleaseTrack(release.tracks[track].track_number, release.tracks[track].track_name,
                                             release.tracks[track].artist_name, release.tracks[track].listener_count))
            self.db.commit()

        return release

    def get_top_user_releases(self, username: str) -> List[LastfmTopRelease]:

        now = datetime.datetime.now()
        expiry = now - datetime.timedelta(seconds=self.cache_validity)
        top_releases = []

        if self.db:
            results = self.db.query(LastfmCache.TopUserRelease) \
                .filter_by(username=username) \
                .filter(LastfmCache.TopUserRelease.fetched > expiry) \
                .order_by(LastfmCache.TopUserRelease.index) \
                .all()

            if len(results):
                for curr in results:
                    top_releases.append(LastfmTopRelease(curr.index, curr.scrobbles, curr.artist, curr.title))

                return top_releases

        page_num = 1

        while True:
            resp = requests.get("https://www.last.fm/user/{username}/library/albums?page={page_num}"
                                .format(username=username, page_num=page_num), allow_redirects=False)
            if resp.status_code == 302:
                break
            elif resp.status_code != 200:
                continue

            soup = bs4.BeautifulSoup(resp.text, 'html5lib')

            if not soup.find(id="top-albums-section"):
                raise LastfmCache.LastfmCacheError("Could not find LastFM data")

            for row in soup.find(id="top-albums-section").findAll(class_="chartlist-row"):
                index = int(str(row.find(class_="chartlist-index").contents[0]).replace(",", ""))
                scrobbles = int(str(row.find(class_="chartlist-count-bar-value").contents[0]).replace(",", ""))
                title = str(row.find(class_="chartlist-name").find("a").contents[0])
                artist = str(row.find(class_="chartlist-artist").find("a").contents[0])

                top_releases.append(LastfmTopRelease(index, scrobbles, artist, title))

            page_num += 1

        if self.db:
            self.db.query(LastfmCache.TopUserRelease).filter(LastfmCache.TopUserRelease.username == username).delete()
            self.db.commit()

            for release in top_releases:
                self.db.add(LastfmCache.TopUserRelease(now, username, release.index,
                                                       release.scrobbles, release.artist, release.title))
                self.db.commit()

        return top_releases

    # web tags have no score, however API tags are frequently missing
    # sometimes API tags all have identical scores, yet web ordering is superior
    @staticmethod
    def combine_tags(api_tags: Dict[str, int], web_tags: Dict[str, int]) -> Dict[str, int]:

        combined_tags = api_tags.copy()

        for tag in web_tags:
            if tag not in combined_tags:
                combined_tags[tag] = web_tags[tag]

        partitions = []
        current_partition = OrderedDict()
        current_partition_score = None
        for tag in combined_tags:
            if combined_tags[tag] != current_partition_score:
                partitions.append(current_partition)
                current_partition = OrderedDict()
            current_partition_score = combined_tags[tag]
            current_partition[tag] = combined_tags[tag]
        partitions.append(current_partition)

        recombined_partitions = OrderedDict()

        # reorder equally scoring partitions according to the web order
        for partition in partitions:
            reordered_partition = OrderedDict()
            for tag in web_tags:
                if tag in partition:
                    reordered_partition[tag] = partition[tag]

            # add back any stragglers
            for tag in partition:
                if tag not in reordered_partition:
                    reordered_partition[tag] = partition[tag]

            # flatten the partitions back down
            recombined_partitions.update(reordered_partition)

        return recombined_partitions

    @staticmethod
    def __lastfm_urlencode(str_in: str) -> str:
        return str_in.replace("/", "%2F").replace("#", "%23")