import json
import time
import unicodedata
import urllib.parse
import urllib.request

import xbmcvfs


class XtreamError(Exception):
    pass


def _normalize(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.casefold()


class XtreamClient(object):
    def __init__(self, server, port, username, password, use_https, cache_dir, ttl_hours):
        scheme = "https" if use_https else "http"
        self.base_url = "%s://%s:%s" % (scheme, server, port)
        self.username = username
        self.password = password
        self.cache_dir = cache_dir
        self.ttl_seconds = int(ttl_hours) * 3600
        if not xbmcvfs.exists(self.cache_dir):
            xbmcvfs.mkdirs(self.cache_dir)

    # -- low level -----------------------------------------------------

    def _api_url(self, action, **params):
        q = {"username": self.username, "password": self.password}
        if action:
            q["action"] = action
        q.update(params)
        return "%s/player_api.php?%s" % (self.base_url, urllib.parse.urlencode(q))

    def _fetch_json(self, action, **params):
        url = self._api_url(action, **params)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
        except Exception as exc:
            raise XtreamError("Request to Platinum TV failed: %s" % exc)
        try:
            return json.loads(data)
        except Exception as exc:
            raise XtreamError("Bad response from Platinum TV: %s" % exc)

    def stream_url(self, kind, stream_id, extension):
        # kind is "movie" or "series"
        return "%s/%s/%s/%s/%s.%s" % (
            self.base_url, kind, self.username, self.password, stream_id, extension
        )

    # -- cache -----------------------------------------------------------

    def _cache_path(self, key):
        return self.cache_dir + key + ".json"

    def _read_cache(self, key, max_age=None):
        path = self._cache_path(key)
        if not xbmcvfs.exists(path):
            return None
        try:
            f = xbmcvfs.File(path)
            raw = f.read()
            f.close()
            envelope = json.loads(raw)
        except Exception:
            return None
        age = time.time() - envelope.get("fetched_at", 0)
        if max_age is not None and age > max_age:
            return None
        return envelope.get("data")

    def _write_cache(self, key, data):
        path = self._cache_path(key)
        envelope = {"fetched_at": time.time(), "data": data}
        f = xbmcvfs.File(path, "w")
        f.write(json.dumps(envelope))
        f.close()

    def _cached_or_fetch(self, key, action, force=False, **params):
        if not force:
            cached = self._read_cache(key, self.ttl_seconds)
            if cached is not None:
                return cached
        data = self._fetch_json(action, **params)
        self._write_cache(key, data)
        return data

    # -- public API --------------------------------------------------------

    def vod_categories(self, force=False):
        return self._cached_or_fetch("vod_categories", "get_vod_categories", force=force)

    def all_movies(self, force=False):
        return self._cached_or_fetch("vod_streams_all", "get_vod_streams", force=force)

    def movies_in_category(self, category_id, force=False):
        return self._cached_or_fetch(
            "vod_streams_cat_%s" % category_id, "get_vod_streams", force=force, category_id=category_id
        )

    def series_categories(self, force=False):
        return self._cached_or_fetch("series_categories", "get_series_categories", force=force)

    def all_series(self, force=False):
        return self._cached_or_fetch("series_all", "get_series", force=force)

    def series_in_category(self, category_id, force=False):
        return self._cached_or_fetch(
            "series_cat_%s" % category_id, "get_series", force=force, category_id=category_id
        )

    def series_info(self, series_id, force=False):
        return self._cached_or_fetch(
            "series_info_%s" % series_id, "get_series_info", force=force, series_id=series_id
        )

    def refresh_all(self):
        self.vod_categories(force=True)
        self.all_movies(force=True)
        self.series_categories(force=True)
        self.all_series(force=True)

    def search(self, query, limit=150):
        q = _normalize(query)
        movies = self.all_movies() or []
        series = self.all_series() or []
        results = []
        for m in movies:
            name = m.get("name") or m.get("title") or ""
            if q in _normalize(name):
                results.append(("movie", m))
        for s in series:
            name = s.get("name") or s.get("title") or ""
            if q in _normalize(name):
                results.append(("series", s))
        results.sort(key=lambda item: _normalize(item[1].get("name") or ""))
        return results[:limit]
