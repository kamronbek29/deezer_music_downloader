import requests


class DeezerApi(object):
    @staticmethod
    def _make_request(request_url):
        get_request = requests.get(request_url)
        response_json = get_request.json()
        return response_json

    def get_track(self, track_id):
        get_album_url = 'https://api.deezer.com/track/{}'.format(track_id)
        response = self._make_request(get_album_url)

        if 'error' in response.keys():
            return

        track_dict = {'music_dir': None, 'track_info': response}
        return track_dict

    def get_playlist(self, playlist_id):
        get_playlist_url = 'https://api.deezer.com/playlist/{}'.format(playlist_id)
        response = self._make_request(get_playlist_url)

        if 'error' in response.keys():
            return

        playlist_tracks = response['tracks']['data']

        return playlist_tracks

    def search_track(self, search_query):
        search_track_url = 'https://api.deezer.com/search/track?q={}&limit=100'.format(search_query)
        response = self._make_request(search_track_url)

        if 'error' in response.keys() or len(response['data']) == 0:
            return None

        list_tracks_dict = []
        for track_info in response['data']:
            title = track_info['title']
            artist = track_info['artist']['name']
            track_url = track_info['link']
            duration = int(track_info['duration'])
            artwork_url = track_info['album']['cover_medium']
            track_id = track_info['id']

            track_dict = {'title': title, 'artist': artist, 'track_url': track_url, 'track_id': track_id,
                          'duration': duration, 'artwork_url': artwork_url}
            list_tracks_dict.append(track_dict)

        return list_tracks_dict

    def get_popular_tracks(self, count=100):
        popular_chart_url = 'https://api.deezer.com/editorial/0/charts?limit={}'.format(count)
        popular_chart_response = self._make_request(popular_chart_url)
        popular_tracks = popular_chart_response['tracks']['data']

        return popular_tracks
