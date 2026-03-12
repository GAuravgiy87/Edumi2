#!/usr/bin/env python
"""
Setup admin user for EduMi platform
Creates a superuser with default credentials
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_project.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserProfile

def create_admin():
    """Create admin superuser"""
    username = 'EdumiAdmin'
    email = 'admin@edumi.com'
    password = 'Gaurav@0000'
    
    # Remove old admin users if they exist
    old_admins = ['Admin', 'admin']
    for old_username in old_admins:
        if User.objects.filter(username=old_username).exists():
            old_user = User.objects.get(username=old_username)
            old_user.delete()
            print(f'🗑️  Removed old admin user: {old_username}')
    
    # Check if new admin already exists
    if User.objects.filter(username=username).exists():
        admin = User.objects.get(username=username)
        # Update password in case it changed
        admin.set_password(password)
        admin.email = email
        admin.is_superuser = True
        admin.is_staff = True
        admin.save()
        print(f'✅ Admin user "{username}" updated!')
        print(f'✓ Username: {username}')
        print(f'✓ Email: {admin.email}')
        print(f'✓ Password: Updated')
        return
    
    # Create new superuser
    admin = User.objects.create_superuser(
        username=username,
        email=email,
        password=password,
        first_name='Edumi',
        last_name='Admin'
    )
    
    # Create or update profile
    profile, created = UserProfile.objects.get_or_create(user=admin)
    profile.user_type = 'teacher'  # Admin has teacher privileges
    profile.display_name = 'Edumi Administrator'
    profile.bio = 'System Administrator'
    profile.save()
    
    print('✅ Admin user created successfully!')
    print(f'✓ Username: {username}')
    print(f'✓ Password: {password}')
    print(f'✓ Email: {email}')
    print(f'✓ Superuser: Yes')
    print(f'✓ Staff: Yes')
    print(f'\n🔗 Login at: http://localhost:8000/')
    print(f'🔗 Django Admin: http://localhost:8000/admin/')
    print(f'🔗 App Admin Panel: http://localhost:8000/accounts/admin-panel/')

if __name__ == '__main__':
    print('=' * 60)
    print('EduMi Admin Setup')
    print('=' * 60)
    print('\nSetting up admin user...\n')
    create_admin()
    print('\n' + '=' * 60)
    print('Setup Complete!')
    print('=' * 60)
