from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from . import db
from flask_login import login_user, logout_user
from itsdangerous import URLSafeTimedSerializer
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

auth = Blueprint('auth', __name__)

def send_reset_email(user_email, token):
    msg = MIMEMultipart()
    msg['From'] = current_app.config['MAIL_USERNAME']
    msg['To'] = user_email
    msg['Subject'] = 'Password Reset Request'
    
    reset_url = url_for('auth.reset_password_confirm', token=token, _external=True)
    body = f'To reset your password, visit the following link: {reset_url}\n\nIf you did not make this request then simply ignore this email.'
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@auth.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    email = request.form.get('email')
    password = request.form.get('password')

    user = User.query.filter_by(email=email).first()
    if user:
      if check_password_hash(user.password, password):
        flash('Logged in successfully!', category='success')
        login_user(user, remember=True)
        return redirect(url_for('views.home'))
      else:
        flash('Incorrect password, try again.', category='error')
    else:
      flash('Email does not exist.', category='error')

  return render_template("auth/login.html", user=current_user)

@auth.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('views.home'))

@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
  if request.method == 'POST':
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')


    user = User.query.filter_by(email=email).first()
    if user:
      flash('Email already exists.', category='error')
    elif len(email) < 4:
      flash('Email must be greater than 3 characters.', category='error')
    elif len(username) < 2:
      flash('First name must be greater than 1 character.', category='error')
    elif len(password) < 7:
      flash('Password must be at least 7 characters.', category='error')
    else:
      new_user = User(email=email, username=username, password=generate_password_hash(password, method='pbkdf2:sha256'))
      db.session.add(new_user)
      db.session.commit()
      flash('Account created successfully!', category='success')
      return redirect(url_for('views.home'))
    
  return render_template("auth/sign_up.html", user=current_user)

@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            token = serializer.dumps(email, salt='password-reset-salt')
            
            if send_reset_email(email, token):
                flash('Password reset instructions have been sent to your email.', category='success')
            else:
                flash('Error sending reset email. Please try again later.', category='error')
        else:
            flash('Email address not found.', category='error')
            
    return render_template("reset_password.html", user=current_user)

@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_confirm(token):
    if request.method == 'POST':
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        
        if password1 != password2:
            flash('Passwords do not match.', category='error')
            return redirect(url_for('auth.reset_password_confirm', token=token))
            
        if len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
            return redirect(url_for('auth.reset_password_confirm', token=token))
            
        try:
            serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # Token expires in 1 hour
            user = User.query.filter_by(email=email).first()
            
            if user:
                user.password = generate_password_hash(password1, method='sha256')
                db.session.commit()
                flash('Your password has been updated!', category='success')
                return redirect(url_for('auth.login'))
            else:
                flash('Invalid or expired password reset link.', category='error')
                return redirect(url_for('auth.reset_password'))
                
        except Exception as e:
            flash('Invalid or expired password reset link.', category='error')
            return redirect(url_for('auth.reset_password'))
            
    return render_template("reset_password_confirm.html", user=current_user)



      



