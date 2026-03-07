from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import models
from .forms import RegisterForm
from .models import UserProfile
from meetings.models import Meeting
from cameras.models import Camera

def login_view(request):
    if request.user.is_authenticated:
        # Check if admin user
        if request.user.username == 'Admin' or request.user.is_superuser:
            return redirect('admin_panel')
        # Check user type
        if hasattr(request.user, 'userprofile'):
            if request.user.userprofile.user_type == 'teacher':
                return redirect('teacher_dashboard')
            elif request.user.userprofile.user_type == 'student':
                return redirect('student_dashboard')
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect based on user type
            if username == 'Admin' or user.is_superuser:
                return redirect('admin_panel')
            if hasattr(user, 'userprofile'):
                if user.userprofile.user_type == 'teacher':
                    return redirect('teacher_dashboard')
                elif user.userprofile.user_type == 'student':
                    return redirect('student_dashboard')
            return redirect('home')
        else:
            return render(request, 'accounts/login.html', {'error': 'Invalid username or password'})
    
    return render(request, 'accounts/login.html')

def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        user_type = request.POST.get('user_type')
        
        if password1 == password2:
            from django.contrib.auth.models import User
            try:
                user = User.objects.create_user(username=username, password=password1)
                UserProfile.objects.create(user=user, user_type=user_type)
                login(request, user)
                if user_type == 'teacher':
                    return redirect('teacher_dashboard')
                elif user_type == 'student':
                    return redirect('student_dashboard')
                return redirect('home')
            except:
                return render(request, 'accounts/register.html', {'error': 'Username already exists'})
        else:
            return render(request, 'accounts/register.html', {'error': 'Passwords do not match'})
    
    return render(request, 'accounts/register.html')

def home(request):
    return render(request, 'accounts/home.html')

@login_required
def teacher_dashboard(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'teacher':
        return redirect('login')
    
    # Get real meeting statistics (exclude classroom meetings)
    total_meetings = Meeting.objects.filter(teacher=request.user, classroom__isnull=True).count()
    live_meetings = Meeting.objects.filter(teacher=request.user, status='live', classroom__isnull=True).count()
    scheduled_meetings = Meeting.objects.filter(teacher=request.user, status='scheduled', classroom__isnull=True).count()
    
    context = {
        'total_meetings': total_meetings,
        'live_meetings': live_meetings,
        'scheduled_meetings': scheduled_meetings,
    }
    
    return render(request, 'accounts/teacher_dashboard.html', context)

@login_required
def student_dashboard(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        return redirect('login')
    
    profile = request.user.userprofile
    
    # Get real meeting statistics (exclude classroom meetings)
    available_meetings = Meeting.objects.filter(status__in=['scheduled', 'live'], classroom__isnull=True).count()
    attended_meetings = request.user.meetingparticipant_set.filter(meeting__classroom__isnull=True).count()
    
    # Calculate profile completion
    completion = 0
    if profile.display_name: completion += 10
    if request.user.first_name: completion += 10
    if request.user.last_name: completion += 10
    if request.user.email: completion += 10
    if profile.bio: completion += 15
    if profile.phone: completion += 10
    if profile.date_of_birth: completion += 10
    if profile.address: completion += 10
    if profile.profile_picture or profile.avatar_url: completion += 15
    
    context = {
        'available_meetings': available_meetings,
        'attended_meetings': attended_meetings,
        'profile_completion': completion,
        'profile': profile,
    }
    
    return render(request, 'accounts/student_dashboard.html', context)

@login_required
def profile_view(request, username=None):
    if username:
        profile_user = get_object_or_404(User, username=username)
    else:
        profile_user = request.user
    
    try:
        profile = profile_user.userprofile
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist (for admin users)
        if profile_user.is_superuser or profile_user.username == 'Admin':
            profile = UserProfile.objects.create(user=profile_user, user_type='teacher')
        else:
            profile = None
    
    # Check if viewing own profile
    is_own_profile = request.user == profile_user
    
    # Handle form submission for own profile
    if is_own_profile and request.method == 'POST':
        try:
            # Create profile if it doesn't exist
            if not profile:
                profile = UserProfile.objects.create(user=request.user, user_type='teacher')
            
            # Update User model (allow empty values)
            request.user.first_name = request.POST.get('first_name', '').strip()
            request.user.last_name = request.POST.get('last_name', '').strip()
            request.user.email = request.POST.get('email', '').strip()
            request.user.save()
            
            # Update UserProfile (allow empty values)
            profile.display_name = request.POST.get('display_name', '').strip()
            profile.bio = request.POST.get('bio', '').strip()
            profile.phone = request.POST.get('phone', '').strip()
            profile.address = request.POST.get('address', '').strip()
            
            # Handle profile picture - check if avatar was selected or file uploaded
            avatar_choice = request.POST.get('avatar_choice', '').strip()
            if request.FILES.get('profile_picture'):
                # File uploaded - save it and clear avatar URL
                profile.profile_picture = request.FILES['profile_picture']
                profile.avatar_url = None
            elif avatar_choice:
                # Avatar selected - save URL and clear uploaded picture
                profile.avatar_url = avatar_choice
                profile.profile_picture = None
            
            # Date of birth (optional)
            dob = request.POST.get('date_of_birth', '').strip()
            if dob:
                profile.date_of_birth = dob
            else:
                profile.date_of_birth = None
            
            # Social links (optional)
            profile.linkedin = request.POST.get('linkedin', '').strip()
            profile.twitter = request.POST.get('twitter', '').strip()
            profile.website = request.POST.get('website', '').strip()
            
            # Type-specific fields (optional)
            if profile.user_type == 'student':
                profile.student_id = request.POST.get('student_id', '').strip()
                profile.grade = request.POST.get('grade', '').strip()
                enrollment = request.POST.get('enrollment_date', '').strip()
                if enrollment:
                    profile.enrollment_date = enrollment
                else:
                    profile.enrollment_date = None
            elif profile.user_type == 'teacher':
                profile.employee_id = request.POST.get('employee_id', '').strip()
                profile.department = request.POST.get('department', '').strip()
                profile.specialization = request.POST.get('specialization', '').strip()
                join = request.POST.get('join_date', '').strip()
                if join:
                    profile.join_date = join
                else:
                    profile.join_date = None
            
            profile.save()
            
            # Add success message
            messages.success(request, 'Profile updated successfully!')
            
            # Redirect to prevent form resubmission
            return redirect('profile_view', username=request.user.username)
        
        except Exception as e:
            # Add error message
            messages.error(request, f'Error updating profile: {str(e)}')
            print(f"Profile save error: {str(e)}")  # Debug print
    
    # Calculate profile completion
    completion = 0
    if is_own_profile and profile:
        if profile.display_name: completion += 10
        if profile_user.first_name: completion += 10
        if profile_user.last_name: completion += 10
        if profile_user.email: completion += 10
        if profile.bio: completion += 15
        if profile.phone: completion += 10
        if profile.date_of_birth: completion += 10
        if profile.address: completion += 10
        if profile.profile_picture or profile.avatar_url: completion += 15
    
    # Get user statistics
    stats = {}
    if profile_user.is_superuser or profile_user.username == 'Admin':
        # Admin statistics
        stats['total_users'] = User.objects.count()
        stats['total_meetings'] = Meeting.objects.count()
        stats['live_meetings'] = Meeting.objects.filter(status='live').count()
        stats['total_cameras'] = Camera.objects.count()
    elif profile and profile.user_type == 'teacher':
        stats['total_meetings'] = Meeting.objects.filter(teacher=profile_user, classroom__isnull=True).count()
        stats['live_meetings'] = Meeting.objects.filter(teacher=profile_user, status='live', classroom__isnull=True).count()
        stats['completed_meetings'] = Meeting.objects.filter(teacher=profile_user, status='ended', classroom__isnull=True).count()
    elif profile and profile.user_type == 'student':
        stats['enrolled_courses'] = 6  # Placeholder
        stats['completed_assignments'] = 15  # Placeholder
        stats['meetings_attended'] = profile_user.meetingparticipant_set.count()
    
    context = {
        'profile_user': profile_user,
        'profile': profile,
        'is_own_profile': is_own_profile,
        'stats': stats,
        'completion': completion,
    }
    
    return render(request, 'accounts/profile.html', context)

@login_required
def edit_profile(request):
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user, user_type='student')
    
    if request.method == 'POST':
        # Update User model
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        
        # Update UserProfile
        profile.display_name = request.POST.get('display_name', '')
        profile.bio = request.POST.get('bio', '')
        profile.phone = request.POST.get('phone', '')
        profile.address = request.POST.get('address', '')
        
        # Handle profile picture upload
        if request.FILES.get('profile_picture'):
            profile.profile_picture = request.FILES['profile_picture']
        
        # Date of birth
        dob = request.POST.get('date_of_birth')
        if dob:
            profile.date_of_birth = dob
        
        # Social links
        profile.linkedin = request.POST.get('linkedin', '')
        profile.twitter = request.POST.get('twitter', '')
        profile.website = request.POST.get('website', '')
        
        # Type-specific fields
        if profile.user_type == 'student':
            profile.student_id = request.POST.get('student_id', '')
            profile.grade = request.POST.get('grade', '')
            enrollment = request.POST.get('enrollment_date')
            if enrollment:
                profile.enrollment_date = enrollment
        elif profile.user_type == 'teacher':
            profile.employee_id = request.POST.get('employee_id', '')
            profile.department = request.POST.get('department', '')
            profile.specialization = request.POST.get('specialization', '')
            join = request.POST.get('join_date')
            if join:
                profile.join_date = join
        
        profile.save()
        
        return redirect('profile_view', username=request.user.username)
    
    return render(request, 'accounts/edit_profile.html', {'profile': profile})

@login_required
def admin_panel(request):
    # Check if user is admin
    if request.user.username != 'Admin' and not request.user.is_superuser:
        return redirect('login')
    
    # Get all statistics (exclude classroom meetings from general counts)
    total_users = User.objects.count()
    total_students = UserProfile.objects.filter(user_type='student').count()
    total_teachers = UserProfile.objects.filter(user_type='teacher').count()
    total_meetings = Meeting.objects.filter(classroom__isnull=True).count()
    live_meetings_count = Meeting.objects.filter(status='live', classroom__isnull=True).count()
    total_cameras = Camera.objects.count()
    
    # Get all detailed lists (exclude classroom meetings)
    all_users = User.objects.all().select_related('userprofile').order_by('-date_joined')
    students = User.objects.filter(userprofile__user_type='student').select_related('userprofile').order_by('-date_joined')
    teachers = User.objects.filter(userprofile__user_type='teacher').select_related('userprofile').order_by('-date_joined')
    all_meetings = Meeting.objects.filter(classroom__isnull=True).select_related('teacher', 'classroom').order_by('-created_at')
    live_meetings = Meeting.objects.filter(status='live', classroom__isnull=True).select_related('teacher', 'classroom').prefetch_related('participants').order_by('-created_at')
    
    # Add active participant count to each live meeting
    for meeting in live_meetings:
        meeting.active_participants_count = meeting.participants.filter(is_active=True).count()
    
    all_cameras = Camera.objects.all().order_by('-created_at')
    recent_users = User.objects.all().select_related('userprofile').order_by('-date_joined')[:10]
    
    context = {
        'total_users': total_users,
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_meetings': total_meetings,
        'live_meetings_count': live_meetings_count,
        'total_cameras': total_cameras,
        
        # Detailed lists
        'all_users': all_users,
        'students': students,
        'teachers': teachers,
        'all_meetings': all_meetings,
        'live_meetings': live_meetings,
        'all_cameras': all_cameras,
        'recent_users': recent_users,
    }
    
    return render(request, 'accounts/admin_panel.html', context)

@login_required
def user_management(request):
    # Check if user is admin
    if request.user.username != 'Admin' and not request.user.is_superuser:
        return redirect('login')
    
    users = User.objects.all().order_by('-date_joined')
    
    return render(request, 'accounts/user_management.html', {'users': users})

@login_required
def delete_user(request, user_id):
    # Check if user is admin
    if request.user.username != 'Admin' and not request.user.is_superuser:
        return redirect('login')
    
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        if user.username != 'Admin':  # Prevent deleting admin
            user.delete()
    
    return redirect('user_management')


@login_required
def architecture_view(request):
    """Display system architecture visualization"""
    # Check if user is admin
    if request.user.username != 'Admin' and not request.user.is_superuser:
        return redirect('login')
    
    # HTML page with both architecture diagrams
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>System Architecture - EduMi</title>
        <meta charset="UTF-8">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                font-family: Arial, sans-serif;
                padding: 20px;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                text-align: center;
                border-radius: 10px;
                margin-bottom: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }
            .header h1 {
                color: white;
                font-size: 2.5em;
                margin-bottom: 5px;
            }
            .header p {
                color: rgba(255,255,255,0.9);
                font-size: 1.1em;
            }
            .back-btn {
                position: fixed;
                top: 20px;
                left: 20px;
                background: rgba(255,255,255,0.2);
                backdrop-filter: blur(10px);
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 25px;
                z-index: 1000;
                transition: all 0.3s;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
            }
            .back-btn:hover {
                background: rgba(255,255,255,0.3);
                transform: translateX(-5px);
            }
            .tabs {
                display: flex;
                gap: 10px;
                margin-bottom: 20px;
                justify-content: center;
            }
            .tab-btn {
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                color: white;
                border: 2px solid rgba(255,255,255,0.2);
                padding: 15px 30px;
                border-radius: 10px;
                cursor: pointer;
                font-size: 1.1em;
                transition: all 0.3s;
            }
            .tab-btn:hover {
                background: rgba(255,255,255,0.2);
                transform: translateY(-2px);
            }
            .tab-btn.active {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-color: #667eea;
            }
            .tab-content {
                display: none;
            }
            .tab-content.active {
                display: block;
            }
            .legend {
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                padding: 15px;
                border-radius: 10px;
                z-index: 1000;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                max-width: 300px;
            }
            .legend h3 {
                color: white;
                margin-bottom: 10px;
                font-size: 1.1em;
            }
            .legend-item {
                display: flex;
                align-items: center;
                margin: 8px 0;
                color: white;
                font-size: 0.9em;
            }
            .legend-dot {
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 10px;
                box-shadow: 0 0 10px currentColor;
            }
            .container {
                max-width: 1850px;
                margin: 0 auto;
                background: rgba(255,255,255,0.05);
                backdrop-filter: blur(10px);
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            }
            .svg-wrapper {
                background: white;
                border-radius: 10px;
                padding: 10px;
                overflow: auto;
                max-height: 85vh;
            }
            svg {
                max-width: 100%;
                height: auto;
                display: block;
            }
            object {
                width: 100%;
                min-height: 2600px;
            }
            .info-box {
                background: rgba(52, 152, 219, 0.2);
                border-left: 4px solid #3498db;
                padding: 15px;
                margin: 20px 0;
                border-radius: 5px;
                color: white;
            }
            .info-box h3 {
                margin-bottom: 10px;
                color: #3498db;
            }
        </style>
    </head>
    <body>
        <a href="/accounts/admin-panel/" class="back-btn">← Back to Admin Panel</a>
        
        <div class="header">
            <h1>🏗️ EduMi Platform - System Architecture</h1>
            <p>Complete Backend Architecture Visualization</p>
        </div>
        
        <div class="tabs">
            <button class="tab-btn active" onclick="showTab('full')">
                🌐 Full System Architecture
            </button>
            <button class="tab-btn" onclick="showTab('backend')">
                ⚙️ Django Backend Flow
            </button>
        </div>
        
        <div id="legend-full" class="legend">
            <h3>🎯 Live Data Flow</h3>
            <div class="legend-item">
                <div class="legend-dot" style="background: #3498db;"></div>
                <span>HTTP Request/Response</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background: #e74c3c;"></div>
                <span>Video Stream (RTSP/MJPEG)</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background: #2ecc71;"></div>
                <span>Database Query/Response</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background: #9b59b6;"></div>
                <span>WebSocket Message</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background: #f39c12;"></div>
                <span>WebRTC P2P (Direct)</span>
            </div>
        </div>
        
        <div id="legend-backend" class="legend" style="display: none;">
            <h3>📋 Request Flow</h3>
            <div class="legend-item">
                <div class="legend-dot" style="background: #3498db;"></div>
                <span>HTTP Request</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background: #e74c3c;"></div>
                <span>Middleware Processing</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background: #f39c12;"></div>
                <span>URL Routing</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background: #2ecc71;"></div>
                <span>View & ORM</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background: #9b59b6;"></div>
                <span>Models & Database</span>
            </div>
        </div>
        
        <div class="container">
            <div id="tab-full" class="tab-content active">
                <div class="info-box">
                    <h3>📡 Watch the packets flow in real-time!</h3>
                    <p>• Blue circles = HTTP requests going to Django server</p>
                    <p>• Red circles = Video streams from cameras to Camera Service</p>
                    <p>• Green circles = Database queries and responses</p>
                    <p>• Purple circles = WebSocket messages for real-time meetings</p>
                    <p>• Orange circles = WebRTC peer-to-peer video (direct between users)</p>
                    <p>• Pulsing boxes = Active components processing data</p>
                </div>
                
                <div class="svg-wrapper">
                    <object data="/static/architecture_diagram.svg" type="image/svg+xml" style="width: 100%; height: auto;">
                        <img src="/static/architecture_diagram.svg" alt="System Architecture Diagram">
                    </object>
                </div>
            </div>
            
            <div id="tab-backend" class="tab-content">
                <div class="info-box">
                    <h3>⚙️ Django Backend Request-Response Cycle</h3>
                    <p>• Shows complete flow from HTTP request to database and back</p>
                    <p>• Middleware stack: Security, Session, CSRF, Authentication</p>
                    <p>• URL routing: How Django matches URLs to views</p>
                    <p>• ORM: Python code to SQL translation</p>
                    <p>• Models & Database: Table structure and relationships</p>
                    <p>• Template rendering: How HTML is generated</p>
                </div>
                
                <div class="svg-wrapper">
                    <object data="/static/backend_architecture.svg" type="image/svg+xml" style="width: 100%; height: auto;">
                        <img src="/static/backend_architecture.svg" alt="Backend Architecture Diagram">
                    </object>
                </div>
            </div>
        </div>
        
        <script>
            function showTab(tabName) {
                // Hide all tabs
                document.querySelectorAll('.tab-content').forEach(tab => {
                    tab.classList.remove('active');
                });
                document.querySelectorAll('.tab-btn').forEach(btn => {
                    btn.classList.remove('active');
                });
                
                // Show selected tab
                document.getElementById('tab-' + tabName).classList.add('active');
                event.target.classList.add('active');
                
                // Show appropriate legend
                if (tabName === 'full') {
                    document.getElementById('legend-full').style.display = 'block';
                    document.getElementById('legend-backend').style.display = 'none';
                } else {
                    document.getElementById('legend-full').style.display = 'none';
                    document.getElementById('legend-backend').style.display = 'block';
                }
            }
        </script>
    </body>
    </html>
    """
    from django.http import HttpResponse
    return HttpResponse(html_content)


@login_required
def directory(request):
    """View all teachers and students directory"""
    teachers = User.objects.filter(userprofile__user_type='teacher').select_related('userprofile').order_by('username')
    students = User.objects.filter(userprofile__user_type='student').select_related('userprofile').order_by('username')
    
    context = {
        'teachers': teachers,
        'students': students,
    }
    
    return render(request, 'accounts/directory.html', context)

@login_required
def search_users(request):
    """Search for teachers and students"""
    query = request.GET.get('q', '').strip()
    user_type = request.GET.get('type', 'all')  # all, teacher, student
    
    results = []
    
    if query:
        # Search in username, first_name, last_name, email
        users = User.objects.filter(
            models.Q(username__icontains=query) |
            models.Q(first_name__icontains=query) |
            models.Q(last_name__icontains=query) |
            models.Q(email__icontains=query) |
            models.Q(userprofile__display_name__icontains=query)
        ).select_related('userprofile').distinct()
        
        # Filter by user type if specified
        if user_type == 'teacher':
            users = users.filter(userprofile__user_type='teacher')
        elif user_type == 'student':
            users = users.filter(userprofile__user_type='student')
        else:
            # Exclude admin users from search
            users = users.filter(userprofile__user_type__in=['teacher', 'student'])
        
        results = users[:20]  # Limit to 20 results
    
    context = {
        'query': query,
        'user_type': user_type,
        'results': results,
    }
    
    return render(request, 'accounts/search_results.html', context)


from .messaging_models import Conversation, Message
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@login_required
def inbox(request):
    """View all conversations with search"""
    search_query = request.GET.get('q', '').strip()
    
    conversations = request.user.conversations.all().prefetch_related('participants', 'messages')
    
    # Add unread count and last message to each conversation
    for conv in conversations:
        conv.other_user = conv.get_other_user(request.user)
        conv.last_msg = conv.get_last_message()
        conv.unread_count = conv.messages.filter(is_read=False).exclude(sender=request.user).count()
    
    # Search for users if query provided
    search_results = []
    if search_query:
        search_results = User.objects.filter(
            models.Q(username__icontains=search_query) |
            models.Q(first_name__icontains=search_query) |
            models.Q(last_name__icontains=search_query) |
            models.Q(email__icontains=search_query) |
            models.Q(userprofile__display_name__icontains=search_query)
        ).exclude(id=request.user.id).select_related('userprofile').distinct()[:10]
    
    context = {
        'conversations': conversations,
        'search_query': search_query,
        'search_results': search_results,
    }
    
    return render(request, 'accounts/inbox.html', context)

@login_required
def conversation_detail(request, conversation_id):
    """View a specific conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Check if user is participant
    if request.user not in conversation.participants.all():
        messages.error(request, 'You do not have access to this conversation')
        return redirect('inbox')
    
    # Mark messages as read
    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    
    other_user = conversation.get_other_user(request.user)
    messages_list = conversation.messages.all().select_related('sender')
    
    context = {
        'conversation': conversation,
        'other_user': other_user,
        'messages': messages_list,
    }
    
    return render(request, 'accounts/conversation.html', context)

@login_required
def start_conversation(request, username):
    """Start a new conversation with a user"""
    other_user = get_object_or_404(User, username=username)
    
    if other_user == request.user:
        messages.error(request, 'You cannot message yourself')
        return redirect('inbox')
    
    # Check if conversation already exists
    existing_conv = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    ).first()
    
    if existing_conv:
        return redirect('conversation_detail', conversation_id=existing_conv.id)
    
    # Create new conversation
    conversation = Conversation.objects.create()
    conversation.participants.add(request.user, other_user)
    
    return redirect('conversation_detail', conversation_id=conversation.id)

@login_required
@require_http_methods(["POST"])
def send_message(request, conversation_id):
    """Send a message in a conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id)
    
    # Check if user is participant
    if request.user not in conversation.participants.all():
        return JsonResponse({'status': 'error', 'message': 'Access denied'}, status=403)
    
    content = request.POST.get('content', '').strip()
    image = request.FILES.get('image')
    file = request.FILES.get('file')
    
    if not content and not image and not file:
        return JsonResponse({'status': 'error', 'message': 'Message cannot be empty'}, status=400)
    
    # Create message
    message = Message.objects.create(
        conversation=conversation,
        sender=request.user,
        content=content,
        image=image,
        file=file
    )
    
    # Update conversation timestamp
    conversation.save()
    
    # Send notification to the other user
    from .notification_utils import notify_new_message
    other_user = conversation.get_other_user(request.user)
    if other_user:
        notify_new_message(request.user, other_user, conversation_id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message_id': message.id,
            'content': message.content,
            'image_url': message.image.url if message.image else None,
            'file_url': message.file.url if message.file else None,
            'sender': message.sender.username,
            'created_at': message.created_at.strftime('%I:%M %p')
        })
    
    return redirect('conversation_detail', conversation_id=conversation_id)
