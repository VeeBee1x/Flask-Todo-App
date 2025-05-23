from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from .models import Todo, User, ActivityLog, SharedTask
from datetime import datetime, timedelta, timezone
from werkzeug.security import check_password_hash, generate_password_hash
from . import db
from sqlalchemy import func

from datetime import datetime

views = Blueprint('views', __name__)

# Startsida 
@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
  tasks = Todo.query.filter_by(user_id=current_user.id).order_by(Todo.due_date).all()
  if request.method == 'POST':
    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    priority = request.form.get('priority')
    completed = request.form.get('completed') == 'on'

    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash('Invalid due date format.', category='error')
    
            return render_template('main/dashboard.html', tasks=tasks)

    new_todo = Todo(title=title, description=description, due_date=due_date, priority=priority, completed=completed, user_id=current_user.id)
    db.session.add(new_todo)
    db.session.commit()

    # Logga skapandet av todon
    activity = ActivityLog(
        user_id=current_user.id,
        type='create',
        description=f'Created task: {new_todo.title}',
        timestamp = datetime.now(timezone.utc)
    )
    db.session.add(activity)
    db.session.commit()

    flash('Todo created successfully!', category='success')
    return redirect(url_for('views.home'))

  return render_template("main/dashboard.html", user=current_user, tasks=tasks)

# Profil
@views.route('/profile')
@login_required
def profile():
    todos = Todo.query.filter_by(user_id=current_user.id).all()
    
    stats = {
        'total_tasks': len(todos),
        'active_tasks': len([todo for todo in todos if not todo.completed]),
        'completed_tasks': len([todo for todo in todos if todo.completed])
    }
    
    recent_activities = ActivityLog.query.filter(
        ActivityLog.user_id == current_user.id,
        ActivityLog.timestamp >= datetime.utcnow() - timedelta(days=7)
    ).order_by(ActivityLog.timestamp.desc()).all()

    return render_template("main/profile.html", 
                         user=current_user,
                         stats=stats,
                         recent_activities=recent_activities)


# Historik
@views.route('/history')
def history():
    recent_activities = ActivityLog.query.filter(
        ActivityLog.user_id == current_user.id,
        ActivityLog.timestamp >= datetime.utcnow() - timedelta(days=7)
    ).order_by(ActivityLog.timestamp.desc()).all()

    return render_template("main/history.html", 
                            user=current_user,
                            recent_activities=recent_activities)


# Uppdatera användarprofil
@views.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')


        username_lower = username.lower()
        username_exists = User.query.filter(func.lower(User.username) == username_lower).first()
        if username_exists and username != current_user.username:
            flash('Username already exists.', category='error')
            return redirect(url_for('views.profile'))

        # Kolla om mailen redan används
        if email != current_user.email:
            user = User.query.filter_by(email=email).first()
            if user:
                flash('Email already exists.', category='error')
                return redirect(url_for('views.profile'))

        # Validate current password if trying to change password
        if new_password:
            if not check_password_hash(current_user.password, current_password):
                flash('Current password is incorrect.', category='error')
                return redirect(url_for('views.profile'))
            
            if new_password != confirm_password:
                flash('New passwords do not match.', category='error')
                return redirect(url_for('views.profile'))
            
            if len(new_password) < 7:
                flash('New password must be at least 7 characters.', category='error')
                return redirect(url_for('views.profile'))

        # Update user information
        current_user.username = username
        current_user.email = email
        if new_password:
            current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        
        db.session.commit()
        flash('Profile updated successfully!', category='success')
        return redirect(url_for('views.profile'))

@views.route('/task/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Todo.query.get_or_404(task_id)

    if task.user_id != current_user.id:
        flash('You do not have permission to delete this task.', category='error')
        return redirect(url_for('views.home'))

    # First, delete any shared task records
    SharedTask.query.filter_by(task_id=task_id).delete()
    
    # Log the deletion before removing the task
    activity = ActivityLog(
        user_id=current_user.id,
        type='delete',
        description=f'Deleted task: {task.title}',
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(activity)

    # Now delete the task
    db.session.delete(task)
    db.session.commit()

    flash('Task deleted successfully.', category='success')
    return redirect(url_for('views.home'))

@views.route('/task/complete/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    task = Todo.query.get_or_404(task_id)
    
    # Check if the user owns the task or has edit permissions
    user_has_permission = task.user_id == current_user.id
    
    if not user_has_permission:
        # Check if task is shared with the user and with edit permissions
        shared_task = SharedTask.query.filter_by(
            task_id=task_id,
            shared_with_id=current_user.id,
            can_edit=True
        ).first()
        
        user_has_permission = shared_task is not None
    
    if not user_has_permission:
        if request.content_type == 'application/json':
            return jsonify({'success': False, 'message': 'You do not have permission to update this task.'}), 403
        flash('You do not have permission to update this task.', category='error')
        return redirect(url_for('views.home'))
    
    task.completed = True
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    # Add activity log
    activity = ActivityLog(
        user_id=current_user.id,
        type='complete',
        description=f'Completed task: {task.title}',
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(activity)
    db.session.commit()

    # Handle AJAX requests
    if request.content_type == 'application/json':
        return jsonify({'success': True, 'message': 'Task marked as complete'})
    
    # Handle form submissions
    flash('Task marked as complete!', category='success')
    return redirect(url_for('views.home'))


@views.route('/task/uncomplete/<int:task_id>', methods=['POST'])
@login_required
def uncomplete_task(task_id):
    task = Todo.query.get_or_404(task_id)
    
    # Check if the user owns the task or has edit permissions
    user_has_permission = task.user_id == current_user.id
    
    if not user_has_permission:
        # Check if task is shared with the user and with edit permissions
        shared_task = SharedTask.query.filter_by(
            task_id=task_id,
            shared_with_id=current_user.id,
            can_edit=True
        ).first()
        
        user_has_permission = shared_task is not None
    
    if not user_has_permission:
        return jsonify({'success': False, 'message': 'You do not have permission to update this task.'}), 403
    
    task.completed = False
    task.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    # Add activity log for uncompleting task
    activity = ActivityLog(
        user_id=current_user.id,
        type='uncomplete',
        description=f'Marked task as not completed: {task.title}',
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(activity)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Task marked as not completed'})

@views.route('/profile/clear-history', methods=['POST'])
@login_required
def clear_history():
    ActivityLog.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('Activity history cleared.', category='success')
    return redirect(url_for('views.profile'))

@views.route('/task/edit/<int:task_id>', methods=['POST'])
@login_required
def edit_task(task_id):
    task = Todo.query.get_or_404(task_id)

    if task.user_id != current_user.id:
        flash('You do not have permission to edit this task.', category='error')
        return redirect(url_for('views.home'))

    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    priority = request.form.get('priority')
    completed = request.form.get('completed') == 'on'

    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash('Invalid due date format.', category='error')
            return redirect(url_for('views.home'))

    task.title = title
    task.description = description
    task.priority = priority
    task.completed = completed
    task.updated_at = datetime.utcnow()

    db.session.commit()

    # Log the edit
    activity = ActivityLog(
        user_id=current_user.id,
        type='edit',
        description=f'Edited task: {task.title}',
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(activity)
    db.session.commit()

    flash('Task updated successfully!', category='success')
    return redirect(url_for('views.home'))


@views.route('/task/share', methods=['POST'])
@login_required
def share_task():
    data = request.json
    task_id = data.get('taskId')
    username = data.get('username')
    can_edit = data.get('canEdit', False)
    
    # Validate data
    if not task_id or not username:
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400
    
    # Ensure task_id is an integer
    try:
        task_id = int(task_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid task ID'}), 400
    
    # Find the task
    task = Todo.query.get(task_id)
    if not task:
        return jsonify({'success': False, 'message': 'Task not found'}), 404
    
    # Verify task ownership
    if task.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'You do not have permission to share this task'}), 403
    
    # Find the user to share with
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404
    
    # Check if task is already shared with this user
    existing_share = SharedTask.query.filter_by(
        task_id=task_id,
        shared_with_id=user.id
    ).first()
    
    if existing_share:
        return jsonify({'success': False, 'message': 'Task already shared with this user'}), 400
    
    # Create the share
    shared_task = SharedTask(
        task_id=task_id,
        shared_by_id=current_user.id,
        shared_with_id=user.id,
        can_edit=can_edit
    )
    
    db.session.add(shared_task)
    
    # Log the activity
    activity = ActivityLog(
        user_id=current_user.id,
        type='share',
        description=f'Shared task "{task.title}" with {user.username}',
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(activity)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Task shared with {user.username}'}), 200

@views.route('/shared-with-me', methods=['GET'])
@login_required
def shared_tasks():
    # Get all tasks shared with the current user
    shared_tasks_data = (
        db.session.query(Todo, SharedTask, User)
        .join(SharedTask, Todo.id == SharedTask.task_id)
        .join(User, User.id == SharedTask.shared_by_id)
        .filter(SharedTask.shared_with_id == current_user.id)
        .all()
    )
    
    # Format the results for display
    tasks = []
    for todo, shared_task, shared_by in shared_tasks_data:
        tasks.append({
            'todo': todo,
            'shared_by': shared_by.username,
            'can_edit': shared_task.can_edit
        })
    
    return render_template("main/shared_tasks.html", shared_tasks=tasks, user=current_user)

@views.route('/task/update-shared/<int:task_id>', methods=['POST'])
@login_required
def update_shared_task(task_id):
    # Find the task
    task = Todo.query.get_or_404(task_id)
    
    # Find the share record
    shared_task = SharedTask.query.filter_by(
        task_id=task_id,
        shared_with_id=current_user.id
    ).first()
    
    # Verify permission
    if not shared_task or not shared_task.can_edit:
        flash('You do not have permission to edit this task.', category='error')
        return redirect(url_for('views.shared_tasks'))
    
    # Update the task (similar to edit_task function)
    title = request.form.get('title')
    description = request.form.get('description')
    due_date_str = request.form.get('due_date')
    priority = request.form.get('priority')
    completed = request.form.get('completed') == 'on'
    
    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            flash('Invalid due date format.', category='error')
            return redirect(url_for('views.shared_tasks'))
    
    task.title = title
    task.description = description
    task.priority = priority
    task.completed = completed
    task.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    # Log the edit
    activity = ActivityLog(
        user_id=current_user.id,
        type='edit_shared',
        description=f'Edited shared task: {task.title}',
        timestamp=datetime.now(timezone.utc)
    )
    db.session.add(activity)
    db.session.commit()
    
    flash('Shared task updated successfully!', category='success')
    return redirect(url_for('views.shared_tasks'))