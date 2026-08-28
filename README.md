# plugin.video.platinumtv

A Kodi video add-on for **Platinum TV** ([platinum-apk.com](https://platinum-apk.com)), an Xtream Codes IPTV panel. Platinum TV doesn't ship an official Kodi add-on — their VOD movies and series are normally distributed as one flat `m3u_plus` playlist alongside live channels, which means every movie and every episode of every series shows up as its own fake "channel" in Kodi's live TV guide.

This add-on talks to the panel's Xtream JSON API directly instead, so VOD content gets a real Movies / TV Shows library:

- **Movies** — browse by category, with poster, plot, cast, director, genre, year and rating pulled from the panel's TMDB-backed metadata
- **TV Shows** — category → series → season → episode drill-down
- **Search** — keyboard search across your entire VOD + series catalog, accent/case-insensitive
- **Refresh library cache** — force a re-fetch from the panel

Not affiliated with Platinum TV / platinum-apk.com. This just consumes the standard Xtream Codes `player_api.php` API that the panel already exposes to any client.

## Requirements

- Kodi 20 (Nexus) or newer — uses the `InfoTagVideo` API (`ListItem.getVideoInfoTag()`)
- An active Xtream Codes-compatible subscription (server host, port, username, password)

## Install

1. Clone this repo directly into your Kodi `addons` directory, naming the target folder after the add-on id (on LibreELEC: `/storage/.kodi/addons/`):
   ```
   git clone git@github.com:jsacra2003/Platinum-tv-addon.git plugin.video.platinumtv
   ```
   (Or download a zip and extract it into a folder named `plugin.video.platinumtv` there — the folder name has to match the add-on id in `addon.xml`.)
2. In Kodi: **Settings → Add-ons → My add-ons → Video add-ons → Platinum VOD → Configure**, and enter your panel's server, port, username and password.
3. Launch it from **Add-ons → Video add-ons → Platinum VOD** (or add it to Favourites / the home screen for one-tap access).

## Notes on the live TV guide

This add-on only handles VOD/series. If your live channel playlist also mixes in VOD/series entries (common with a raw `get.php?type=m3u_plus` export), you'll want to regenerate it from the panel's `get_live_categories` / `get_live_streams` API instead, so only real live channels reach `pvr.iptvsimple`. That's outside the scope of this repo — it's a one-off script per setup, not something this add-on manages.

## How it works

- `resources/lib/xtream.py` — thin Xtream Codes API client with local JSON caching (`special://profile/addon_data/plugin.video.platinumtv/cache/`, TTL configurable in settings)
- `addon.py` — the plugin's directory routing and Kodi `ListItem`/`InfoTagVideo` rendering

Movie and episode playback resolves directly to the panel's stream URL (`http://host:port/movie/user/pass/id.ext` or `.../series/user/pass/id.ext`) — no intermediate resolving step.
