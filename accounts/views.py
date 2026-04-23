from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import models
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .forms import RegisterForm
from .models import UserProfile
from meetings.models import Meeting

def login_view(request):
    if request.user.is_authenticated:
        # Check if admin user
        if request.user.is_superuser:
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
            if user.is_superuser:
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
                request.session['show_welcome'] = True
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
    
    from .services import get_teacher_stats
    context = get_teacher_stats(request.user)
    
    return render(request, 'accounts/teacher_dashboard.html', context)

@login_required
def student_dashboard(request):
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.user_type != 'student':
        return redirect('login')
    
    profile = request.user.userprofile
    
    from .services import get_student_stats, get_profile_completion
    context = get_student_stats(request.user)
    context['profile_completion'] = get_profile_completion(request.user)
    context['profile'] = profile
    
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
        if profile_user.is_superuser:
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
    if profile_user.is_superuser:
        # Admin statistics
        stats['total_users'] = User.objects.count()
        stats['total_meetings'] = Meeting.objects.count()
        stats['live_meetings'] = Meeting.objects.filter(status='live').count()
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
    if not request.user.is_superuser:
        return redirect('login')

    from .services import get_admin_stats
    stats = get_admin_stats()

    # Only load what's needed for the summary cards — no full table dumps
    live_meetings = (
        Meeting.objects
        .filter(status='live', classroom__isnull=True)
        .select_related('teacher')
        .only('id', 'title', 'meeting_code', 'teacher__username')
        .prefetch_related('participants')
        [:10]  # cap at 10 for the dashboard widget
    )
    for m in live_meetings:
        m.active_participants_count = m.participants.filter(is_active=True).count()

    # Recent 10 users only — full list is in user_management
    recent_users = (
        User.objects
        .select_related('userprofile')
        .only('id', 'username', 'email', 'date_joined', 'userprofile__user_type', 'userprofile__avatar_url')
        .order_by('-date_joined')
        [:10]
    )

    context = {
        **stats,
        'live_meetings': live_meetings,
        'recent_users': recent_users,
    }
    return render(request, 'accounts/admin_panel.html', context)

@login_required
def user_management(request):
    if not request.user.is_superuser:
        return redirect('login')

    from django.core.paginator import Paginator
    qs = (
        User.objects
        .select_related('userprofile')
        .only('id', 'username', 'email', 'date_joined', 'is_active',
              'userprofile__user_type', 'userprofile__avatar_url')
        .order_by('-date_joined')
    )
    paginator = Paginator(qs, 25)  # 25 per page
    page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'accounts/user_management.html', {'users': page, 'paginator': paginator})

@login_required
def delete_user(request, user_id):
    # Check if user is admin
    if not request.user.is_superuser:
        return redirect('login')
    
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        if not user.is_superuser:  # Prevent deleting admin users
            user.delete()
    
    return redirect('user_management')



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
    
    conversations = request.user.conversations.all().prefetch_related(
        'participants', 'participants__userprofile', 'messages'
    )
    
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


@login_required
def settings_view(request):
    """Settings page - Under Development"""
    return render(request, 'accounts/settings.html')

def error_404(request, exception):
    return render(request, '404.html', status=404)

def error_500(request):
    return render(request, '500.html', status=500)


@require_POST
def dismiss_welcome(request):
    request.session.pop('show_welcome', None)
    return JsonResponse({'ok': True})


@require_POST
@login_required
def save_emoji_avatar(request):
    import base64, uuid, os
    from django.core.files.base import ContentFile
    data_url = request.POST.get('data_url', '')
    if not data_url.startswith('data:image/png;base64,'):
        return JsonResponse({'ok': False, 'error': 'Invalid data'}, status=400)
    img_data = base64.b64decode(data_url.split(',')[1])
    profile = request.user.userprofile
    filename = f"emoji_{request.user.id}_{uuid.uuid4().hex[:8]}.png"
    profile.profile_picture.save(filename, ContentFile(img_data), save=True)
    profile.avatar_url = ''
    profile.save()
    return JsonResponse({'ok': True, 'url': profile.profile_picture.url})
