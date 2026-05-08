import os
import requests
from livekit.api import AccessToken, VideoGrants

KEY = os.environ.get('LIVEKIT_API_KEY', 'devkey')
SECRET = os.environ.get('LIVEKIT_API_SECRET', 'devsecret_must_be_32_characters_long_1234')
meeting = 'TESTROOM'

try:
    token = AccessToken(KEY, SECRET).with_identity('test').with_name('test').with_grants(
        VideoGrants(room_join=True, room=meeting, can_publish=True, can_subscribe=True, can_publish_data=True)
    ).to_jwt()
    url = f'http://localhost:8000/livekit-proxy/rtc?access_token={token}'
    print('Testing URL:', url)
    r = requests.get(url, timeout=10, allow_redirects=False)
    print('Status:', r.status_code)
    print('Headers:', dict(r.headers))
    print('Body:', r.text[:500])
except Exception as e:
    print('Error:', type(e).__name__, e)
