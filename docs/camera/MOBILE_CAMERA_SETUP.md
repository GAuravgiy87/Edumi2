# Mobile Camera Setup Guide

## Overview
EduMi supports using your smartphone as a camera using popular mobile camera apps. This is a cost-effective alternative to dedicated RTSP cameras.

## Supported Apps

### 📱 IP Webcam (Android)
- **Platform**: Android
- **Download**: Google Play Store
- **Default Port**: 8080
- **Stream Path**: /video
- **Cost**: Free (with ads) or Pro version

### 📱 DroidCam (iPhone & Android)
- **Platform**: iOS and Android
- **Download**: App Store / Google Play Store
- **Default Port**: 4747
- **Stream Path**: /mjpegfeed
- **Cost**: Free (with limitations) or Pro version

## Setup Instructions

### Step 1: Install Mobile Camera App

**For Android (IP Webcam):**
1. Open Google Play Store
2. Search for "IP Webcam"
3. Install the app by Pavel Khlebovich
4. Open the app

**For iPhone (DroidCam):**
1. Open App Store
2. Search for "DroidCam"
3. Install the app by Dev47Apps
4. Open the app

### Step 2: Configure Your Phone

**For IP Webcam:**
1. Scroll down in the app
2. Tap "Start server"
3. Note the IP address shown (e.g., 192.168.1.100:8080)
4. Keep the app running in foreground

**For DroidCam:**
1. Tap "Start"
2. Note the WiFi IP and Port (e.g., 192.168.1.100:4747)
3. Keep the app running

### Step 3: Add Camera in EduMi

1. Log in as Admin
2. Go to Admin Dashboard
3. Click "Mobile Cameras" button
4. Click "Add Mobile Camera"
5. Fill in the form:
   - **Name**: Give your camera a name (e.g., "My Phone Camera")
   - **Camera Type**: Select IP Webcam or DroidCam
   - **IP Address**: Enter the IP from your phone (e.g., 192.168.1.100)
   - **Port**: Auto-filled based on camera type
   - **Stream Path**: Auto-filled based on camera type
   - **Username/Password**: Leave empty unless you set authentication in the app
6. Click "Add Mobile Camera"

### Step 4: Test Connection

1. Find your camera in the Mobile Camera Dashboard
2. Click "Test" button
3. If successful, status will change to "Active"
4. If failed, check:
   - Phone and server are on same WiFi network
   - IP address is correct
   - Port is correct
   - Camera app is still running

### Step 5: Grant Permissions (Optional)

1. Click "Permissions" button on the camera card
2. Select teachers to grant access
3. Click "Grant Access"
4. Teachers can now view this camera

## Network Requirements

### Same WiFi Network
- Your phone and the EduMi server MUST be on the same WiFi network
- Cannot work across different networks or over the internet (without port forwarding)

### Firewall
- Ensure your firewall allows connections on the camera port
- Default ports: 8080 (IP Webcam), 4747 (DroidCam)

### Static IP (Recommended)
- Consider setting a static IP for your phone in router settings
- This prevents the IP from changing when phone reconnects to WiFi

## Troubleshooting

### Camera Not Connecting

**Problem**: "Cannot access camera" error

**Solutions**:
1. Verify phone and server are on same WiFi
2. Check IP address is correct
3. Ensure camera app is running
4. Try restarting the camera app
5. Check firewall settings
6. Try pinging the phone IP from server

### Stream Not Loading

**Problem**: Camera shows as active but stream doesn't load

**Solutions**:
1. Refresh the page
2. Check if camera app is still running
3. Restart the camera app
4. Clear browser cache
5. Try a different browser

### Poor Quality/Lag

**Problem**: Video is laggy or low quality

**Solutions**:
1. Move phone closer to WiFi router
2. Reduce resolution in camera app settings
3. Close other apps on phone
4. Ensure good WiFi signal strength
5. Reduce frame rate in camera app

### IP Address Changed

**Problem**: Camera stops working after phone reconnects

**Solutions**:
1. Check new IP address in camera app
2. Update IP address in EduMi
3. Set static IP in router settings (recommended)

## Best Practices

### Phone Placement
- Mount phone securely
- Ensure stable position
- Good lighting for better quality
- Avoid direct sunlight on camera lens

### Power Management
- Keep phone plugged in for continuous use
- Disable battery optimization for camera app
- Enable "Stay awake while charging" in developer options

### Network Optimization
- Use 5GHz WiFi if available (better bandwidth)
- Position phone close to WiFi router
- Minimize WiFi interference

### App Settings

**IP Webcam Recommended Settings:**
- Video Resolution: 640x480 or 1280x720
- Quality: 80%
- FPS Limit: 15-30
- Enable: "Keep screen on"

**DroidCam Recommended Settings:**
- Video Quality: Medium or High
- FPS: 15-30
- Enable: "Keep screen on"

## Security Considerations

### Authentication
- Enable username/password in camera app if available
- Enter credentials when adding camera in EduMi

### Network Security
- Use WPA2/WPA3 encrypted WiFi
- Don't expose camera to public networks
- Change default passwords

### Privacy
- Be aware of what the camera can see
- Inform people they're being recorded
- Follow local privacy laws

## Comparison: Mobile vs RTSP Cameras

| Feature | Mobile Camera | RTSP Camera |
|---------|--------------|-------------|
| Cost | Free (use existing phone) | $50-$500+ |
| Setup | Very Easy | Moderate |
| Quality | Good (720p-1080p) | Excellent (1080p-4K) |
| Reliability | Moderate | High |
| Power | Needs charging | PoE/DC power |
| Portability | High | Low |
| Best For | Temporary, testing, budget | Permanent installations |

## Use Cases

### Good For:
- ✅ Temporary monitoring
- ✅ Testing the system
- ✅ Budget-constrained setups
- ✅ Portable monitoring needs
- ✅ Quick deployment

### Not Ideal For:
- ❌ 24/7 monitoring
- ❌ Critical security applications
- ❌ Outdoor installations
- ❌ High-reliability requirements

## Advanced Configuration

### Custom Stream Paths
If using a different mobile camera app:
1. Check app documentation for stream URL
2. Extract IP, port, and path
3. Select "Other Mobile Camera" type
4. Enter custom values

### Authentication
If your camera app requires authentication:
1. Set username/password in camera app
2. Enter same credentials when adding camera in EduMi
3. Credentials are stored securely

### Multiple Cameras
You can add multiple mobile cameras:
1. Each phone needs unique IP address
2. Can use different ports on same phone
3. Each camera has independent permissions

## Support

### Getting Help
- Check camera app documentation
- Verify network connectivity
- Test with camera app's web interface first
- Contact EduMi admin for permission issues

### Reporting Issues
When reporting issues, include:
- Camera app name and version
- Phone model and OS version
- IP address and port
- Error messages
- Network configuration

## Conclusion

Mobile cameras provide a flexible, cost-effective solution for video monitoring in EduMi. While not as robust as dedicated RTSP cameras, they're perfect for testing, temporary setups, or budget-conscious deployments.
