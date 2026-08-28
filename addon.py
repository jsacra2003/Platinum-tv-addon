import sys
import urllib.parse

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

sys.path.insert(0, __file__.rsplit("/addon.py", 1)[0] + "/resources/lib")
from xtream import XtreamClient  # noqa: E402

ADDON = xbmcaddon.Addon()
ADDON_HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def L(msgid):
    return ADDON.getLocalizedString(msgid)


def build_url(**kwargs):
    return BASE_URL + "?" + urllib.parse.urlencode(kwargs)


def get_client():
    server = ADDON.getSetting("server")
    username = ADDON.getSetting("username")
    password = ADDON.getSetting("password")
    if not server or not username or not password:
        xbmcgui.Dialog().notification(ADDON.getAddonInfo("name"), L(30020), xbmcgui.NOTIFICATION_ERROR)
        ADDON.openSettings()
        return None
    port = ADDON.getSettingInt("port") or 80
    use_https = ADDON.getSettingBool("use_https")
    ttl_hours = ADDON.getSettingInt("cache_ttl_hours") or 6
    cache_dir = xbmcvfs.translatePath(ADDON.getAddonInfo("profile") + "cache/")
    return XtreamClient(server, port, username, password, use_https, cache_dir, ttl_hours)


def actors(cast_csv):
    if not cast_csv:
        return []
    return [xbmc.Actor(name=n.strip()) for n in cast_csv.split(",") if n.strip()]


def genres(genre_csv):
    if not genre_csv:
        return []
    return [g.strip() for g in genre_csv.split(",") if g.strip()]


def apply_common_info(tag, entry, media_type):
    name = entry.get("name") or entry.get("title") or ""
    tag.setTitle(name)
    tag.setMediaType(media_type)
    plot = entry.get("plot") or (entry.get("info") or {}).get("plot")
    if plot:
        tag.setPlot(plot)
    genre_list = genres(entry.get("genre"))
    if genre_list:
        tag.setGenres(genre_list)
    cast_list = actors(entry.get("cast"))
    if cast_list:
        tag.setCast(cast_list)
    director = entry.get("director")
    if director:
        tag.setDirectors([d.strip() for d in director.split(",") if d.strip()])
    rating = entry.get("rating")
    try:
        if rating not in (None, "", "0"):
            tag.setRating(float(rating))
    except (TypeError, ValueError):
        pass
    year = entry.get("year")
    try:
        if year:
            tag.setYear(int(year))
    except (TypeError, ValueError):
        pass
    premiered = entry.get("release_date") or entry.get("releaseDate")
    if premiered:
        tag.setPremiered(premiered)


def poster_for(entry):
    return entry.get("stream_icon") or entry.get("cover") or entry.get("movie_image") or ""


def fanart_for(entry):
    bd = entry.get("backdrop_path")
    if isinstance(bd, list) and bd:
        return bd[0]
    return poster_for(entry)


def split_genres(genre_csv):
    return [g.strip() for g in (genre_csv or "").split(",") if g.strip()]


def all_genre_names(items):
    seen = {}
    for item in items or []:
        for g in split_genres(item.get("genre")):
            seen.setdefault(g.casefold(), g)
    return sorted(seen.values(), key=lambda x: x.casefold())


def items_in_genre(items, genre_name):
    key = genre_name.casefold()
    return [item for item in items or [] if key in {g.casefold() for g in split_genres(item.get("genre"))}]


def recently_added(items, limit):
    def added_ts(item):
        try:
            return int(item.get("added") or 0)
        except (TypeError, ValueError):
            return 0
    return sorted(items or [], key=added_ts, reverse=True)[:limit]


# -- directory renderers -------------------------------------------------


def list_root():
    items = [
        (L(30010), build_url(action="movies"), "DefaultMovies.png"),
        (L(30011), build_url(action="series"), "DefaultTVShows.png"),
        (L(30012), build_url(action="search"), "DefaultAddonsSearch.png"),
        (L(30013), build_url(action="refresh"), "DefaultAddonProgram.png"),
    ]
    for label, url, icon in items:
        li = xbmcgui.ListItem(label=label)
        li.setArt({"icon": icon, "thumb": icon})
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_categories(categories, action):
    for cat in categories or []:
        label = cat.get("category_name", "?")
        url = build_url(action=action, cat_id=cat.get("category_id"))
        li = xbmcgui.ListItem(label=label)
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_genre_folders(genre_names, action):
    for name in genre_names:
        li = xbmcgui.ListItem(label=name)
        li.setArt({"icon": "DefaultGenre.png", "thumb": "DefaultGenre.png"})
        url = build_url(action=action, genre=name)
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)
    xbmcplugin.addSortMethod(ADDON_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_hub(kind):
    # kind is "movies" or "series"
    recent_icon = "DefaultRecentlyAddedMovies.png" if kind == "movies" else "DefaultRecentlyAddedEpisodes.png"
    items = [
        (L(30022), build_url(action="%s_genres" % kind), "DefaultGenre.png"),
        (L(30023), build_url(action="%s_recent" % kind), recent_icon),
        (L(30024), build_url(action="%s_by_category" % kind), "DefaultFolder.png"),
    ]
    for label, url, icon in items:
        li = xbmcgui.ListItem(label=label)
        li.setArt({"icon": icon, "thumb": icon})
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_movies(client, movies, preserve_order=False):
    xbmcplugin.setContent(ADDON_HANDLE, "movies")
    for m in movies or []:
        name = m.get("name") or m.get("title") or "?"
        li = xbmcgui.ListItem(label=name)
        li.setArt({"poster": poster_for(m), "thumb": poster_for(m), "fanart": fanart_for(m)})
        apply_common_info(li.getVideoInfoTag(), m, "movie")
        li.setProperty("IsPlayable", "true")
        url = client.stream_url("movie", m.get("stream_id"), m.get("container_extension") or "mp4")
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=False)
    if preserve_order:
        xbmcplugin.addSortMethod(ADDON_HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    else:
        xbmcplugin.addSortMethod(ADDON_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_series(series_list, preserve_order=False):
    xbmcplugin.setContent(ADDON_HANDLE, "tvshows")
    for s in series_list or []:
        name = s.get("name") or s.get("title") or "?"
        li = xbmcgui.ListItem(label=name)
        li.setArt({"poster": poster_for(s), "thumb": poster_for(s), "fanart": fanart_for(s)})
        apply_common_info(li.getVideoInfoTag(), s, "tvshow")
        url = build_url(action="series_seasons", series_id=s.get("series_id"))
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)
    if preserve_order:
        xbmcplugin.addSortMethod(ADDON_HANDLE, xbmcplugin.SORT_METHOD_UNSORTED)
    else:
        xbmcplugin.addSortMethod(ADDON_HANDLE, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_seasons(series_id):
    client = get_client()
    info = client.series_info(series_id)
    show_info = info.get("info", {}) if info else {}
    show_name = show_info.get("name") or show_info.get("title") or ""
    xbmcplugin.setContent(ADDON_HANDLE, "seasons")
    for season in info.get("seasons", []):
        season_num = season.get("season_number")
        label = season.get("name") or (L(30021) % season_num)
        li = xbmcgui.ListItem(label=label)
        poster = season.get("cover_big") or season.get("cover") or poster_for(show_info)
        li.setArt({"poster": poster, "thumb": poster})
        tag = li.getVideoInfoTag()
        tag.setTitle(label)
        tag.setMediaType("season")
        tag.setTvShowTitle(show_name)
        try:
            tag.setSeason(int(season_num))
        except (TypeError, ValueError):
            pass
        if season.get("overview"):
            tag.setPlot(season["overview"])
        url = build_url(action="series_episodes", series_id=series_id, season=season_num)
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def list_episodes(series_id, season):
    client = get_client()
    info = client.series_info(series_id)
    show_info = info.get("info", {}) if info else {}
    show_name = show_info.get("name") or show_info.get("title") or ""
    episodes = (info.get("episodes") or {}).get(str(season), [])
    xbmcplugin.setContent(ADDON_HANDLE, "episodes")
    for ep in episodes:
        ep_info = ep.get("info") or {}
        title = ep.get("title") or "Episode %s" % ep.get("episode_num")
        li = xbmcgui.ListItem(label=title)
        poster = ep_info.get("movie_image") or poster_for(show_info)
        li.setArt({"thumb": poster, "poster": poster})
        tag = li.getVideoInfoTag()
        tag.setTitle(title)
        tag.setTvShowTitle(show_name)
        tag.setMediaType("episode")
        try:
            tag.setSeason(int(season))
        except (TypeError, ValueError):
            pass
        try:
            tag.setEpisode(int(ep.get("episode_num")))
        except (TypeError, ValueError):
            pass
        if ep_info.get("plot"):
            tag.setPlot(ep_info["plot"])
        if ep_info.get("duration_secs"):
            try:
                tag.setDuration(int(ep_info["duration_secs"]))
            except (TypeError, ValueError):
                pass
        if ep_info.get("rating"):
            try:
                tag.setRating(float(ep_info["rating"]))
            except (TypeError, ValueError):
                pass
        li.setProperty("IsPlayable", "true")
        url = client.stream_url("series", ep.get("id"), ep.get("container_extension") or "mp4")
        xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=False)
    xbmcplugin.addSortMethod(ADDON_HANDLE, xbmcplugin.SORT_METHOD_EPISODE)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def do_search():
    client = get_client()
    if client is None:
        return
    keyboard = xbmcgui.Dialog().input(L(30014), type=xbmcgui.INPUT_ALPHANUM)
    if not keyboard:
        xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
        return
    limit = ADDON.getSettingInt("search_result_limit") or 150
    results = client.search(keyboard, limit=limit)
    if not results:
        xbmcgui.Dialog().notification(ADDON.getAddonInfo("name"), L(30015), xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)
        return
    for kind, entry in results:
        name = entry.get("name") or entry.get("title") or "?"
        if kind == "movie":
            label = L(30016) % name
            li = xbmcgui.ListItem(label=label)
            li.setArt({"poster": poster_for(entry), "thumb": poster_for(entry), "fanart": fanart_for(entry)})
            apply_common_info(li.getVideoInfoTag(), entry, "movie")
            li.setProperty("IsPlayable", "true")
            url = client.stream_url("movie", entry.get("stream_id"), entry.get("container_extension") or "mp4")
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=False)
        else:
            label = L(30017) % name
            li = xbmcgui.ListItem(label=label)
            li.setArt({"poster": poster_for(entry), "thumb": poster_for(entry), "fanart": fanart_for(entry)})
            apply_common_info(li.getVideoInfoTag(), entry, "tvshow")
            url = build_url(action="series_seasons", series_id=entry.get("series_id"))
            xbmcplugin.addDirectoryItem(ADDON_HANDLE, url, li, isFolder=True)
    xbmcplugin.endOfDirectory(ADDON_HANDLE)


def do_refresh():
    client = get_client()
    if client is None:
        return
    xbmcgui.Dialog().notification(ADDON.getAddonInfo("name"), L(30018), xbmcgui.NOTIFICATION_INFO, 3000)
    client.refresh_all()
    xbmcgui.Dialog().notification(ADDON.getAddonInfo("name"), L(30019), xbmcgui.NOTIFICATION_INFO, 3000)
    xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)


def router(paramstring):
    params = dict(urllib.parse.parse_qsl(paramstring))
    action = params.get("action")

    if action is None:
        list_root()
        return

    if action == "movies":
        list_hub("movies")
        return

    if action == "movies_by_category":
        client = get_client()
        if client:
            list_categories(client.vod_categories(), "movies_cat")
        return

    if action == "movies_cat":
        client = get_client()
        if client:
            list_movies(client, client.movies_in_category(params["cat_id"]))
        return

    if action == "movies_genres":
        client = get_client()
        if client:
            list_genre_folders(all_genre_names(client.all_movies()), "movies_genre")
        return

    if action == "movies_genre":
        client = get_client()
        if client:
            list_movies(client, items_in_genre(client.all_movies(), params["genre"]))
        return

    if action == "movies_recent":
        client = get_client()
        if client:
            limit = ADDON.getSettingInt("recently_added_limit") or 60
            list_movies(client, recently_added(client.all_movies(), limit), preserve_order=True)
        return

    if action == "series":
        list_hub("series")
        return

    if action == "series_by_category":
        client = get_client()
        if client:
            list_categories(client.series_categories(), "series_cat")
        return

    if action == "series_cat":
        client = get_client()
        if client:
            list_series(client.series_in_category(params["cat_id"]))
        return

    if action == "series_genres":
        client = get_client()
        if client:
            list_genre_folders(all_genre_names(client.all_series()), "series_genre")
        return

    if action == "series_genre":
        client = get_client()
        if client:
            list_series(items_in_genre(client.all_series(), params["genre"]))
        return

    if action == "series_recent":
        client = get_client()
        if client:
            limit = ADDON.getSettingInt("recently_added_limit") or 60
            list_series(recently_added(client.all_series(), limit), preserve_order=True)
        return

    if action == "series_seasons":
        list_seasons(params["series_id"])
        return

    if action == "series_episodes":
        list_episodes(params["series_id"], params["season"])
        return

    if action == "search":
        do_search()
        return

    if action == "refresh":
        do_refresh()
        return

    xbmc.log("plugin.video.platinumtv: unknown action %s" % action, xbmc.LOGWARNING)
    xbmcplugin.endOfDirectory(ADDON_HANDLE, succeeded=False)


if __name__ == "__main__":
    router(sys.argv[2][1:])
