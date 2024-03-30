import hashlib
import os

import requests
from urllib3.util.retry import Retry
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


SECRET = 'g4el58wc0zvf9na1'
SECRET_2 = 'jo6aey6haid2Teih'

DECRYPTED_URL = 'https://e-cdns-proxy-{0}.dzcdn.net/mobile/1/{1}'
AJAX_URL = 'https://www.deezer.com/ajax/gw-light.php'

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'

HTTP_HEADERS = {
    'User-Agent': USER_AGENT,
    'Content-Language': 'en-US',
    'Cache-Control': 'max-age=0',
    'Accept': '*/*',
    'Accept-Charset': 'utf-8,ISO-8859-1;q=0.7,*;q=0.3',
    'Accept-Language': 'en-US;q=0.6,en;q=0.4',
    'Connection': 'keep-alive',
}

GET_USER_DATA = 'deezer.getUserData'
CHARACTER = b'\xa4'

ARL_TOKEN = 'YOUR ARL TOKEN'


def get_track_download_url(md5_origin, media_version, sng_id, track_quality_id):
    """ Generates the deezer download URL from a given MD5_ORIGIN (MD5 hash), SNG_ID and MEDIA_VERSION. """

    decoded_character = CHARACTER.decode('unicode_escape')
    step1 = decoded_character.join((md5_origin, track_quality_id, sng_id, media_version))

    md5_hashlib = hashlib.md5()
    md5_hashlib.update(bytes([ord(x) for x in step1]))

    step2 = f'{md5_hashlib.hexdigest()}{decoded_character}{step1}{decoded_character}'

    step3 = step2.ljust(80, ' ')
    cipher = Cipher(algorithms.AES(bytes(SECRET_2, 'ascii')), modes.ECB(), default_backend())
    encryptor = cipher.encryptor()

    step4 = encryptor.update(bytes([ord(x) for x in step3])).hex()

    decrypted_ready_url = DECRYPTED_URL.format(md5_origin[0], step4)

    return decrypted_ready_url


def get_blow_fish_key(track_id):
    """ Calculates the Blow fish decrypt key for a given SNG_ID."""
    m = hashlib.md5()
    m.update(bytes([ord(x) for x in track_id]))
    id_md5 = m.hexdigest()
    bf_key = bytes(([(ord(id_md5[i]) ^ ord(id_md5[i + 16]) ^ ord(SECRET[i]))
                    for i in range(16)]))
    return bf_key


def decrypt_chunk(chunk, bf_key):
    """ Decrypt a given encrypted chunk with a blow fish key. """
    cipher = Cipher(algorithms.Blowfish(bf_key), modes.CBC(bytes([i for i in range(8)])), default_backend())
    decryptor = cipher.decryptor()
    dec_chunk = decryptor.update(chunk) + decryptor.finalize()
    return dec_chunk


class DeezerDownloader:
    def __init__(self):
        if len(ARL_TOKEN) != 192:
            print('Your token is wrong. Please pass correct arl token')
            return

        self.session = requests.Session()
        self.session.headers.update(HTTP_HEADERS)
        self._login_by_token(ARL_TOKEN)

        user_data = self._api_call(GET_USER_DATA)
        self.CSRFToken = user_data['checkForm']

    def _api_call(self, api_method, json_req=None):
        api_params = {'api_version': '1.0', 'input': '3', 'method': api_method, 'api_token': 'null'}
        if api_method != GET_USER_DATA:
            api_params['api_token'] = self.CSRFToken

        post_request = self._requests_retry_session().post(url=AJAX_URL, params=api_params, json=json_req)
        response_json = post_request.json()
        request_results = response_json['results']

        return request_results

    def _login_by_token(self, arl_token):
        """ If there is no USER_ID, False is returned. It means that your arl token is wrong """

        cookies = {'arl': arl_token}
        self.session.cookies.update(cookies)

        request_results = self._api_call(GET_USER_DATA)
        user_id = request_results['USER']['USER_ID']

        if not user_id:
            return False
        else:
            return True

    def _requests_retry_session(self, retries=3, backoff_factor=0.3, status_force_list=(500, 502, 504)):
        retry = Retry(total=retries, read=retries, connect=retries, backoff_factor=backoff_factor,
                      status_forcelist=status_force_list, method_whitelist=frozenset(['GET', 'POST']))

        adapter = requests.adapters.HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        return self.session

    def _get_json(self, media_type, media_id, subtype=""):
        """ This function is used to download the ID3 tags """

        request_url = f'https://api.deezer.com/{media_type}/{media_id}/{subtype}?limit=-1'
        session = self._requests_retry_session()
        get_request = session.get(request_url)
        response_json = get_request.json()

        return response_json

    def _continue_download(self, download_url, file_size):
        download_header = {'Range': 'bytes=%d-' % file_size}
        session = self._requests_retry_session()
        get_request = session.get(download_url, headers=download_header, stream=True)

        return get_request

    def _download_track(self, file_directory, url, bf_key):
        """ Download and decrypts a track. Resumes download for tmp files."""

        temporary_file = f'{file_directory}.tmp'
        real_file_name = f'{file_directory}.mp3'

        if os.path.isfile(temporary_file):
            size_on_disk = os.stat(temporary_file).st_size  # size downloaded file
            # reduce size_on_disk to a multiple of 2048 for seamless decryption
            size_on_disk = size_on_disk - (size_on_disk % 2048)
            i = size_on_disk / 2048
            req = self._continue_download(url, size_on_disk)
        else:
            size_on_disk = 0
            i = 0
            req = self._requests_retry_session().get(url, stream=True)
            if req.headers['Content-length'] == '0':
                print("Empty file, skipping...\n", end='')
                return False, None

        # Decrypt content and write to file
        with open(temporary_file, 'ab') as fd:
            fd.seek(size_on_disk)  # jump to end of the file in order to append to it
            # Only every third 2048 byte block is encrypted.
            for chunk in req.iter_content(2048):
                if i % 3 == 0 and len(chunk) >= 2048:
                    chunk = decrypt_chunk(chunk, bf_key)
                fd.write(chunk)
                i += 1

        os.rename(temporary_file, real_file_name)
        return True, real_file_name

    def get_track(self, track_id, track_quality_id):
        """ Calls the necessary functions to download and tag the tracks. """

        print(f'{track_id}: Trying to get track info by track id')
        track_info = self._get_json('track', track_id)
        track_data = self._api_call('deezer.pageTrack', {'SNG_ID': track_id})['DATA']

        title = str(track_info['title']).replace('/', '')
        artist = str(track_info['artist']['name']).replace('/', '')

        file_directory = 'music/{0} - {1}'.format(title, artist)

        md5_origin = track_data['MD5_ORIGIN']
        media_version = track_data['MEDIA_VERSION']
        sng_id = track_data['SNG_ID']

        print(f'{track_id}: Trying to get decrypted download url')
        decrypted_url = get_track_download_url(md5_origin, media_version, sng_id, track_quality_id)

        bf_key = get_blow_fish_key(sng_id)

        print(f'{track_id}: Downloading track')
        is_downloaded, music_directory = self._download_track(file_directory, decrypted_url, bf_key)
        self.session.close()
        if not is_downloaded:
            print(f'{track_id}: Unfortunately, unable to download this track')
            return

        print(f'{track_id}: Track is downloaded. File directory: {music_directory}')
        return music_directory
