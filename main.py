from deezer_downloader import DeezerDownloader
from deezer_api import DeezerApi


def main():
    search_query = 'Miyagi - Control'

    deezer_api = DeezerApi()
    search_result = deezer_api.search_track(search_query)

    track_id = search_result[0]['track_id']

    deezer_downloader = DeezerDownloader()
    music_directory = deezer_downloader.get_track(track_id, '1')
    print(music_directory)


if __name__ == '__main__':
    main()
