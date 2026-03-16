# Camera Permission System

## Overview
The camera permission system ensures secure, role-based access control for all cameras in the EduMi platform.

## User Roles & Permissions

### 👑 Admin
- **Can Add Cameras**: ✅ Yes
- **Can Delete Cameras**: ✅ Yes
- **Can View All Cameras**: ✅ Yes
- **Can Grant Permissions**: ✅ Yes
- **Can Revoke Permissions**: ✅ Yes

### 👨‍🏫 Teacher
- **Can Add Cameras**: ❌ No (Admin only)
- **Can Delete Cameras**: ❌ No (Admin only)
- **Can View Cameras**: ✅ Only cameras with explicit permission
- **Can Grant Permissions**: ❌ No (Admin only)
- **Can Revoke Permissions**: ❌ No (Admin only)

### 👨‍🎓 Student
- **Can Add Cameras**: ❌ No
- **Can Delete Cameras**: ❌ No
- **Can View Cameras**: ✅ All active cameras
- **Can Grant Permissions**: ❌ No
- **Can Revoke Permissions**: ❌ No

## How It Works

### 1. Admin Adds Camera
```
Admin Dashboard → Add Camera → Enter Details → Camera Created
```

### 2. Admin Grants Permission to Teacher
```
Admin Dashboard → Camera Card → Permissions Button → Select Teacher → Grant Access
```

### 3. Teacher Accesses Camera
```
Teacher Dashboard → Live Monitor → Only sees authorized cameras
```

### 4. Admin Revokes Permission
```
Admin Dashboard → Camera Card → Permissions Button → Select Teacher → Revoke Access
```

## Permission Management UI

### Admin Dashboard
- Shows all cameras
- Each camera card displays:
  - Camera name and status
  - Number of authorized teachers
  - "Permissions" button
  - "View Feed" button
  - "Delete" button

### Manage Permissions Page
- **Left Column**: Authorized Teachers
  - Shows teachers with access
  - "Revoke" button for each
  
- **Right Column**: Available Teachers
  - Shows teachers without access
  - "Grant Access" button for each

## Database Schema

### Camera Model
```python
class Camera(models.Model):
    name = CharField
    rtsp_url = CharField
    ip_address = CharField
    port = IntegerField
    is_active = BooleanField
    created_at = DateTimeField
```

### CameraPermission Model
```python
class CameraPermission(models.Model):
    camera = ForeignKey(Camera)
    teacher = ForeignKey(User)
    granted_by = ForeignKey(User)
    granted_at = DateTimeField
    
    unique_together = ('camera', 'teacher')
```

## API Endpoints

### Grant Permission
```
POST /cameras/grant-permission/<camera_id>/
Body: teacher_id=<id>
Response: {"success": true, "message": "Access granted"}
```

### Revoke Permission
```
POST /cameras/revoke-permission/<camera_id>/<teacher_id>/
Response: {"success": true, "message": "Access revoked"}
```

### Manage Permissions Page
```
GET /cameras/manage-permissions/<camera_id>/
Returns: HTML page with permission management UI
```

## Security Features

1. **Admin-Only Management**: Only admins can add/delete cameras
2. **Explicit Permissions**: Teachers need explicit permission for each camera
3. **Permission Checks**: All camera views check permissions before allowing access
4. **CSRF Protection**: All permission changes require CSRF token
5. **Audit Trail**: Tracks who granted permission and when
6. **Automatic Cleanup**: Permissions deleted when camera is removed

## Usage Examples

### Example 1: Grant Access to Math Teacher
1. Admin logs in
2. Goes to Admin Dashboard
3. Finds "Classroom A Camera"
4. Clicks "Permissions" button
5. Finds "Mr. Smith (Math Teacher)" in Available Teachers
6. Clicks "Grant Access"
7. Mr. Smith can now view Classroom A Camera

### Example 2: Revoke Access
1. Admin logs in
2. Goes to Admin Dashboard
3. Finds "Classroom A Camera"
4. Clicks "Permissions" button
5. Finds "Mr. Smith" in Authorized Teachers
6. Clicks "Revoke"
7. Mr. Smith can no longer view Classroom A Camera

### Example 3: Teacher Views Cameras
1. Teacher logs in
2. Goes to Live Monitor
3. Sees only cameras they have permission for
4. Cannot see cameras without permission

### Example 4: Student Views Cameras
1. Student logs in
2. Goes to Live Monitor
3. Sees all active cameras
4. No permission restrictions for students

## Benefits

✅ **Security**: Controlled access to sensitive camera feeds
✅ **Flexibility**: Admin can grant/revoke access anytime
✅ **Transparency**: Clear view of who has access to what
✅ **Audit Trail**: Track permission changes
✅ **User-Friendly**: Simple one-click grant/revoke interface
✅ **Scalable**: Works with any number of cameras and teachers
