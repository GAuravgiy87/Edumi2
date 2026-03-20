import requests
import base64
import os

# Use a dummy small JPEG for testing
dummy_image_path = "test_capture.jpg" # I might still have this or I can create one
if not os.path.exists(dummy_image_path):
    import cv2
    import numpy as np
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(img, "FACE", (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2)
    cv2.imwrite(dummy_image_path, img)

with open(dummy_image_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

# Need a session with a logged in user.
# For testing, I'll check the views.py logic directly with a mock if needed,
# but let's see if I can run a standalone test.

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

client = Client()
user = User.objects.filter(is_superuser=True).first()
client.force_login(user)

import json
response = client.post('/attendance/face/capture/', 
                       data=json.dumps({'frame_b64': b64}),
                       content_type='application/json')

print(f"Status: {response.status_code}")
print(f"Content: {response.content}")
