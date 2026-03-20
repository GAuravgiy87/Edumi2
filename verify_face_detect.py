import requests
import base64
import os
import django
import json
import cv2
import numpy as np

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

# Create a dark image to test low-light enhancement
dark_img = np.zeros((480, 640, 3), dtype=np.uint8)
# Add some very dim "noise" or a faint shape to simulate a low-light scene
cv2.putText(dark_img, "DARK FACE", (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (20, 20, 20), 1)
_, buffer = cv2.imencode('.jpg', dark_img)
b64 = base64.b64encode(buffer).decode()

client = Client()
user = User.objects.filter(is_superuser=True).first()
client.force_login(user)

response = client.post('/attendance/face/detect/', 
                       data=json.dumps({'frame_b64': b64}),
                       content_type='application/json')

print(f"Status: {response.status_code}")
data = response.json()
print(f"Data: {data}")

if data.get('low_light_enhanced'):
    print("SUCCESS: Low-light enhancement was applied!")
else:
    print("FAILURE: Low-light enhancement was NOT applied (or brightness was > 60).")
