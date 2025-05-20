from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User
from . import db
from flask_login import login_user, logout_user

auth = Blueprint('auth', __name__)

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