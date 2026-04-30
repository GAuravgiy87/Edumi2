@echo off
echo Starting LiveKit SFU server...
echo.
echo  API Key:    devkey
echo  API Secret: devsecret
echo  URL:        ws://10.7.11.141:7880
echo.
echo Keep this window open while the meeting is running.
echo.
livekit-bin\livekit-server.exe --config livekit.yaml
