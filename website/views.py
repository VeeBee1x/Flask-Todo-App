from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from .models import Todo, User, ActivityLog
from datetime import datetime, timedelta, timezone
from werkzeug.security import check_password_hash, generate_password_hash
from . import db


from datetime import datetime

views = Blueprint('views', __name__)

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

    # Log the creation
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

    


@views.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Check if email is already taken by another user
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

@views.route('/settings')
def settings():
  return render_template("main/settings.html", user=current_user)

@views.route('/task/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Todo.query.get_or_404(task_id)

    if task.user_id != current_user.id:
        flash('You do not have permission to delete this task.', category='error')
        return redirect(url_for('views.home'))

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
    
    if task.user_id != current_user.id:
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
    
    if task.user_id != current_user.id:
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

