from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from .models import Todo, User
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from . import db


from datetime import datetime, timedelta, timezone

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
    flash('Todo created successfully!', category='success')
    return redirect(url_for('views.home'))

  return render_template("main/dashboard.html", user=current_user, tasks=tasks)

@views.route('/profile')
@login_required
def profile():
    # Get user's todos
    todos = Todo.query.filter_by(user_id=current_user.id).all()
    
    # Calculate statistics
    stats = {
        'total_tasks': len(todos),
        'active_tasks': len([todo for todo in todos if not todo.completed]),
        'completed_tasks': len([todo for todo in todos if todo.completed])
    }
    
    # Get recent activities (last 7 days)
    recent_activities = []
    for todo in todos:
        if todo.created_at >= datetime.now(timezone.utc) - timedelta(days=7):
            recent_activities.append({
                'type': 'create',
                'description': f'Created task: {todo.title}',
                'created_at': todo.created_at
            })
        if todo.completed and todo.updated_at >= datetime.now() - timedelta(days=7):
            recent_activities.append({
                'type': 'complete',
                'description': f'Completed task: {todo.title}',
                'created_at': todo.updated_at
            })
    
    # Sort activities by date
    recent_activities.sort(key=lambda x: x['created_at'], reverse=True)
    
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

    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully.', category='success')
    return redirect(url_for('views.home'))