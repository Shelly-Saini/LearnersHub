from app import app
from database import db
from models import User, Course, Module, Lesson, Quiz, Result, Enrollment, Review, ForumPost, LectureComment, Announcement, Message
from werkzeug.security import generate_password_hash

def seed_data():
    with app.app_context():
        # Clear existing data
        db.drop_all()
        db.create_all()

        # Create Instructor
        instructor = User(
            username='prof_smith',
            email='smith@example.com',
            password=generate_password_hash('pass123', method='scrypt'),
            role='instructor'
        )
        db.session.add(instructor)
        
        # Create Student
        mike = User(
            username='mike_coder',
            email='mike@example.com',
            password=generate_password_hash('pass123', method='scrypt'),
            role='student',
            points=250
        )
        db.session.add(mike)
        
        db.session.commit()

        # Helper to add module + lesson
        def add_module_lesson(course, m_title, l_title, l_content, v_url):
            m = Module(title=m_title, order=1, course_id=course.id)
            db.session.add(m)
            db.session.commit()
            l = Lesson(course_id=course.id, module_id=m.id, title=l_title, content=l_content, video_url=v_url, order=1)
            db.session.add(l)
            db.session.commit()
            return m, l

        # Course Definitions with Thumbnails and OFFICIAL BRAND YouTube Videos
        courses_data = [
            ("Python for Enthusiasts", "Programming", "Intermediate", "cover-code.png", "https://www.youtube.com/watch?v=_uQrJ0TkZlc"),
            ("Full-Stack Web Masterclass", "Web Development", "Advanced", "cover-code.png", "https://www.youtube.com/watch?v=nu_pCVPKzTk"),
            ("Data Science & AI Intro", "Data Science", "Beginner", "cover-general.png", "https://www.youtube.com/watch?v=ua-CiDNNj30"),
            ("Master the UI/UX Design", "Design", "Beginner", "cover-design.png", "https://www.youtube.com/watch?v=68w2VwalD5w"),
            ("DevOps Essentials (Docker)", "Infrastructure", "Intermediate", "cover-cloud.png", "https://www.youtube.com/watch?v=Gjnup-PuquQ"),
            ("ML with Scikit-Learn", "Data Science", "Intermediate", "cover-general.png", "https://www.youtube.com/watch?v=E5Rqz9Bju80"),
            ("Advanced React Patterns", "Web Development", "Advanced", "cover-code.png", "https://www.youtube.com/watch?v=hEGg09GVUAs"),
            ("Cybersecurity Fundamentals", "Security", "Beginner", "cover-security.png", "https://www.youtube.com/watch?v=sdpxddDzXfE"),
            ("Mobile App Dev with Flutter", "Mobile", "Intermediate", "cover-design.png", "https://www.youtube.com/watch?v=x0uinJ5dXas"),
            ("Ethical Hacking Workshop", "Security", "Advanced", "cover-security.png", "https://www.youtube.com/watch?v=7yLBV87uUVM"),
            ("JavaScript Pro", "Programming", "Intermediate", "cover-code.png", "https://www.youtube.com/watch?v=PkZNo7MFNFg"),
            ("Cloud Computing with AWS", "Infrastructure", "Intermediate", "cover-cloud.png", "https://www.youtube.com/watch?v=3hLmDS179YE")
        ]

        created_courses = []
        for title, cat, diff, thumb, video in courses_data:
            c = Course(
                title=title, 
                category=cat, 
                difficulty=diff, 
                thumbnail=thumb,
                description=f"In-depth guide to {title}. This premium course provides actionable insights and hands-on projects to master {cat}.",
                instructor_id=instructor.id
            )
            db.session.add(c)
            db.session.commit()
            add_module_lesson(c, "Core Curriculum", f"Foundations of {title}", f"This lesson introduces the core principles of {title}. We explore real-world use cases and industry standards in {cat}.", video)
            created_courses.append(c)

        # Mike enrolls in a few courses for verification
        for i in [7, 10, 11]: # Cyber, JS, AWS
            db.session.add(Enrollment(user_id=mike.id, course_id=created_courses[i].id))

        db.session.commit()
        print("Database re-seeded with OFFICIAL brand-verified educational videos!")

if __name__ == "__main__":
    seed_data()
