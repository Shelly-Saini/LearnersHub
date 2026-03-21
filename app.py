from flask import Flask
from database import db
from flask_login import LoginManager
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

app.jinja_env.globals.update(enumerate=enumerate)

from models import User, Course, Enrollment, Quiz, Result, Module, Lesson, Review, ForumPost, LectureComment, Message, Announcement
from werkzeug.security import generate_password_hash, check_password_hash
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import urllib.parse

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    if not current_user.is_authenticated:
        return render_template("auth.html")
        
    query = request.args.get('search', '')
    category = request.args.get('category', 'All')
    
    courses_query = Course.query
    if query:
        courses_query = courses_query.filter(Course.title.contains(query) | Course.description.contains(query))
    if category != 'All':
        courses_query = courses_query.filter_by(category=category)
        
    courses = courses_query.all()
    categories = db.session.query(Course.category).distinct().all()
    categories = [c[0] for c in categories]
    
    # Pre-calculate ratings for each course
    for course in courses:
        if course.reviews:
            course.avg_rating = round(sum(r.rating for r in course.reviews) / len(course.reviews), 1)
        else:
            course.avg_rating = 0
            
    return render_template("index.html", courses=courses, categories=categories, current_category=category)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        # ... logic ...
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user_exists = User.query.filter((User.email == email) | (User.username == username)).first()
        if user_exists:
            flash('Email or username already exists.', 'error')
            return redirect(url_for('register'))
        
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='scrypt')
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('home'))
    return render_template("auth.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials.', 'error')
    return render_template("auth.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('home')) # Redirect to root (Gatekeeper)

@app.route("/dashboard")
@login_required
def dashboard():
    enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
    results = Result.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard.html", enrollments=enrollments, results=results)

@app.route("/enroll/<int:course_id>")
@login_required
def enroll(course_id):
    course = Course.query.get_or_404(course_id)
    existing_enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    
    if existing_enrollment:
        flash('You are already enrolled in this course.', 'info')
    else:
        new_enrollment = Enrollment(user_id=current_user.id, course_id=course_id)
        db.session.add(new_enrollment)
        db.session.commit()
        flash(f'Successfully enrolled in {course.title}!', 'success')
    
    return redirect(url_for('dashboard'))

@app.route("/quiz/<int:quiz_id>")
@login_required
def quiz_view(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    return render_template("quiz.html", quiz=quiz)

@app.route("/quiz/<int:quiz_id>/submit", methods=['POST'])
@login_required
def quiz_submit(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    score = 0
    total = len(quiz.questions)
    
    for i, q in enumerate(quiz.questions):
        user_answer = request.form.get(f'q{i}')
        if user_answer == q['answer']:
            score += 1
            
    result = Result(user_id=current_user.id, quiz_id=quiz_id, score=score, total_questions=total)
    
    # Update progress (simple logic: completing one quiz = 100% progress for now)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=quiz.course_id).first()
    if enrollment:
        enrollment.progress = 100
    
    # Add points for quiz completion (score * 10)
    current_user.points += (score * 10)
        
    db.session.add(result)
    db.session.commit()
    
    flash(f'Quiz completed! Your score: {score}/{total}', 'success')
    return redirect(url_for('dashboard'))

@app.route("/course/<int:course_id>")
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    enrolled = False
    if current_user.is_authenticated:
        enrolled = Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first() is not None
    
    avg_rating = 0
    if course.reviews:
        avg_rating = sum(r.rating for r in course.reviews) / len(course.reviews)
    
    return render_template("course_detail.html", course=course, enrolled=enrolled, avg_rating=round(avg_rating, 1))

@app.route("/lesson/<int:lesson_id>")
@login_required
def lesson_view(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=lesson.course_id).first()
    if not enrollment:
        flash('You must enroll in the course to view lessons.', 'error')
        return redirect(url_for('course_detail', course_id=lesson.course_id))
    
    course = Course.query.get(lesson.course_id)
    
    # YouTube ID extraction
    video_id = None
    if lesson.video_url:
        if 'youtu.be' in lesson.video_url:
            video_id = lesson.video_url.split('/')[-1]
        elif 'youtube.com' in lesson.video_url:
            url_data = urllib.parse.urlparse(lesson.video_url)
            query = urllib.parse.parse_qs(url_data.query)
            video_id = query.get('v', [None])[0]
            
    return render_template("lesson.html", lesson=lesson, course=course, video_id=video_id)

@app.route("/course/<int:course_id>/review", methods=['POST'])
@login_required
def add_review(course_id):
    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment')
    
    if not rating or rating < 1 or rating > 5:
        flash('Please provide a rating between 1 and 5.', 'error')
        return redirect(url_for('course_detail', course_id=course_id))
        
    existing_review = Review.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    if existing_review:
        existing_review.rating = rating
        existing_review.comment = comment
        existing_review.date_posted = datetime.utcnow()
    else:
        new_review = Review(user_id=current_user.id, course_id=course_id, rating=rating, comment=comment)
        db.session.add(new_review)
    
    db.session.commit()
    flash('Thank you for your review!', 'success')
    return redirect(url_for('course_detail', course_id=course_id))

@app.route("/leaderboard")
def leaderboard():
    top_users = User.query.order_by(User.points.desc()).limit(10).all()
    return render_template("leaderboard.html", users=top_users)

# --- FORUM & ANNOUNCEMENTS ---
@app.route("/course/<int:course_id>/forum", methods=['POST'])
@login_required
def post_forum(course_id):
    title = request.form.get('title')
    content = request.form.get('content')
    if title and content:
        post = ForumPost(course_id=course_id, user_id=current_user.id, title=title, content=content)
        db.session.add(post)
        db.session.commit()
        flash('Topic posted to forum!', 'success')
    return redirect(url_for('course_detail', course_id=course_id))

@app.route("/course/<int:course_id>/announcement", methods=['POST'])
@login_required
def post_announcement(course_id):
    if current_user.role != 'instructor' and current_user.role != 'admin':
        flash('Only instructors can post announcements.', 'danger')
        return redirect(url_for('course_detail', course_id=course_id))
    
    title = request.form.get('title')
    content = request.form.get('content')
    if title and content:
        ann = Announcement(course_id=course_id, title=title, content=content)
        db.session.add(ann)
        db.session.commit()
        flash('Announcement published!', 'success')
    return redirect(url_for('course_detail', course_id=course_id))

# --- LECTURE COMMENTS ---
@app.route("/lesson/<int:lesson_id>/comment", methods=['POST'])
@login_required
def add_comment(lesson_id):
    content = request.form.get('content')
    if content:
        comment = LectureComment(lesson_id=lesson_id, user_id=current_user.id, content=content)
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for('lesson_view', lesson_id=lesson_id))

# --- MESSAGING ---
@app.route("/messages", methods=['GET', 'POST'])
@login_required
def messages():
    if request.method == 'POST':
        recipient_id = request.form.get('recipient_id')
        content = request.form.get('content')
        if recipient_id and content:
            msg = Message(sender_id=current_user.id, recipient_id=recipient_id, content=content)
            db.session.add(msg)
            db.session.commit()
            flash('Message sent!', 'success')
            return redirect(url_for('messages'))

    sent = Message.query.filter_by(sender_id=current_user.id).all()
    received = Message.query.filter_by(recipient_id=current_user.id).all()
    
    partners_ids = set([m.recipient_id for m in sent] + [m.sender_id for m in received])
    inbox = []
    for p_id in partners_ids:
        partner = User.query.get(p_id)
        last_msg = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.recipient_id == p_id)) |
            ((Message.sender_id == p_id) & (Message.recipient_id == current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        inbox.append({'partner': partner, 'last_msg': last_msg})

    return render_template("messages.html", inbox=inbox)

@app.route("/messages/chat/<int:user_id>")
@login_required
def chat(user_id):
    partner = User.query.get_or_404(user_id)
    msgs = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()
    
    Message.query.filter_by(sender_id=user_id, recipient_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    
    return render_template("chat.html", partner=partner, messages=msgs)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
