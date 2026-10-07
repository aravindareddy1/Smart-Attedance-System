import random
from datetime import datetime, date, timedelta, time, timezone
from app import create_app, db
from app.models import (
    User, Student, ClassRoom, Subject, Timetable, Holiday,
    AttendanceSession, AttendanceRecord, AttendanceAdjustment,
    FaceEncoding, Setting, AuditLog
)
from app.utils import set_setting


def run_seed():
    app = create_app('development')
    with app.app_context():
        print("Starting Smart Attendance System database seed...")
        db.drop_all()
        db.create_all()

        # ==========================================
        # 1. APPLICATION SETTINGS
        # ==========================================
        set_setting('attendance_threshold', '75.0', 'Minimum attendance percentage required')
        set_setting('face_distance_threshold', '0.50', 'Face recognition matching tolerance')
        set_setting('min_session_length', '30', 'Minimum length in minutes')
        set_setting('session_timeout_minutes', '60', 'Auto-expiration period in minutes')
        set_setting('late_threshold_minutes', '10', 'Grace period before marking late')
        print("[OK] Settings initialized.")

        # ==========================================
        # 2. USERS (ADMIN & TEACHERS)
        # ==========================================
        admin = User(
            name="System Administrator",
            email="admin@example.com",
            role="admin",
            is_active=True,
            is_default_password=True
        )
        admin.set_password("Admin@123")
        db.session.add(admin)

        teacher1 = User(
            name="Dr. Sarah Jenkins",
            email="dr.sarah@example.com",
            role="teacher",
            is_active=True,
            is_default_password=False
        )
        teacher1.set_password("Teacher@123")
        db.session.add(teacher1)

        teacher2 = User(
            name="Prof. Robert Davis",
            email="prof.robert@example.com",
            role="teacher",
            is_active=True,
            is_default_password=False
        )
        teacher2.set_password("Teacher@123")
        db.session.add(teacher2)

        db.session.commit()
        print("[OK] Admin and 2 Teachers created.")

        # ==========================================
        # 3. CLASSROOMS
        # ==========================================
        c1 = ClassRoom(
            name="CSE-3A",
            department="Computer Science & Engineering",
            year=3,
            section="A",
            academic_year="2025-2026",
            is_active=True
        )
        c2 = ClassRoom(
            name="CSE-3B",
            department="Computer Science & Engineering",
            year=3,
            section="B",
            academic_year="2025-2026",
            is_active=True
        )
        c3 = ClassRoom(
            name="ECE-2A",
            department="Electronics & Communication",
            year=2,
            section="A",
            academic_year="2025-2026",
            is_active=True
        )
        db.session.add_all([c1, c2, c3])
        db.session.commit()
        print("[OK] 3 Classrooms created.")

        # ==========================================
        # 4. SUBJECTS
        # ==========================================
        subjects = [
            # CSE-3A
            Subject(name="Design & Analysis of Algorithms", code="CS301", class_id=c1.id, teacher_id=teacher1.id),
            Subject(name="Database Management Systems", code="CS302", class_id=c1.id, teacher_id=teacher1.id),
            Subject(name="Computer Networks", code="CS303", class_id=c1.id, teacher_id=teacher2.id),
            # CSE-3B
            Subject(name="Operating Systems", code="CS304", class_id=c2.id, teacher_id=teacher1.id),
            Subject(name="Software Engineering", code="CS305", class_id=c2.id, teacher_id=teacher2.id),
            Subject(name="Web Technologies", code="CS306", class_id=c2.id, teacher_id=teacher2.id),
            # ECE-2A
            Subject(name="Digital Signal Processing", code="EC201", class_id=c3.id, teacher_id=teacher2.id),
            Subject(name="Microprocessors & Microcontrollers", code="EC202", class_id=c3.id, teacher_id=teacher1.id),
            Subject(name="Electromagnetic Theory", code="EC203", class_id=c3.id, teacher_id=teacher2.id),
        ]
        db.session.add_all(subjects)
        db.session.commit()
        print("[OK] 9 Subjects created across classes.")

        # ==========================================
        # 5. STUDENTS & STUDENT LOGINS (30 Students)
        # ==========================================
        student_names = [
            # CSE-3A (12 students)
            ("CS2023001", "Aarav Sharma", "aarav.sharma@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023002", "Aditi Patel", "aditi.patel@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023003", "Ananya Rao", "ananya.rao@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023004", "Arjun Verma", "arjun.verma@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023005", "Bhavya Gupta", "bhavya.gupta@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023006", "Chetan Reddy", "chetan.reddy@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023007", "Divya Nair", "divya.nair@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023008", "Eshaan Joshi", "eshaan.joshi@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023009", "Farhan Khan", "farhan.khan@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023010", "Gayatri Iyer", "gayatri.iyer@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023011", "Harshvardhan Singh", "harsh.singh@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            ("CS2023012", "Ishita Roy", "ishita.roy@example.edu", c1.id, "Computer Science & Engineering", 3, "A"),
            # CSE-3B (10 students)
            ("CS2023013", "Kabir Mehta", "kabir.mehta@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            ("CS2023014", "Kavya Deshmukh", "kavya.deshmukh@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            ("CS2023015", "Manish Kumar", "manish.kumar@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            ("CS2023016", "Neha Bhatia", "neha.bhatia@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            ("CS2023017", "Omkar Kulkarni", "omkar.k@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            ("CS2023018", "Pooja Hegde", "pooja.hegde@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            ("CS2023019", "Rahul Pillai", "rahul.pillai@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            ("CS2023020", "Rhea Sengupta", "rhea.s@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            ("CS2023021", "Siddharth Menon", "sid.menon@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            ("CS2023022", "Tanvi Saxena", "tanvi.saxena@example.edu", c2.id, "Computer Science & Engineering", 3, "B"),
            # ECE-2A (8 students)
            ("EC2024001", "Utkarsh Mishra", "utkarsh.m@example.edu", c3.id, "Electronics & Communication", 2, "A"),
            ("EC2024002", "Vaishnavi Sen", "vaishnavi.sen@example.edu", c3.id, "Electronics & Communication", 2, "A"),
            ("EC2024003", "Varun Chopra", "varun.chopra@example.edu", c3.id, "Electronics & Communication", 2, "A"),
            ("EC2024004", "Yashwant Das", "yashwant.das@example.edu", c3.id, "Electronics & Communication", 2, "A"),
            ("EC2024005", "Zara Sheikh", "zara.sheikh@example.edu", c3.id, "Electronics & Communication", 2, "A"),
            ("EC2024006", "Abhishek Tiwari", "abhishek.t@example.edu", c3.id, "Electronics & Communication", 2, "A"),
            ("EC2024007", "Deepika Padukone", "deepika.p@example.edu", c3.id, "Electronics & Communication", 2, "A"),
            ("EC2024008", "Gaurav Kapoor", "gaurav.k@example.edu", c3.id, "Electronics & Communication", 2, "A")
        ]

        created_students = []
        for idx, (roll_no, name, email, class_id, dept, year, sec) in enumerate(student_names):
            user_stu = User(
                name=name,
                email=email,
                role="student",
                is_active=True,
                is_default_password=False
            )
            user_stu.set_password("Student@123")
            db.session.add(user_stu)
            db.session.flush()

            # Enrolled biometrics for ~75% students
            is_enrolled = (idx % 4 != 0)

            stu = Student(
                roll_no=roll_no,
                name=name,
                email=email,
                phone=f"98765432{idx:02d}",
                department=dept,
                year=year,
                section=sec,
                class_id=class_id,
                user_id=user_stu.id,
                is_active=True,
                face_enrolled=is_enrolled,
                biometric_consent=is_enrolled,
                biometric_consent_date=datetime.now(timezone.utc) if is_enrolled else None
            )
            db.session.add(stu)
            db.session.flush()
            created_students.append(stu)

            if is_enrolled:
                # Add sample face encoding placeholder for testing engine matching
                # 120x120 synthetic byte encoding
                import base64
                mock_face = bytes([random.randint(50, 200) for _ in range(120 * 120)])
                mock_enc = base64.b64encode(mock_face).decode('utf-8')
                enc_rec = FaceEncoding(
                    student_id=stu.id,
                    encoding=mock_enc,
                    quality_score=0.92,
                    engine="OpenCV-LBPH",
                    created_at=datetime.now(timezone.utc)
                )
                db.session.add(enc_rec)

        db.session.commit()
        print(f"[OK] {len(created_students)} Students and login accounts created.")

        # ==========================================
        # 6. TIMETABLE
        # ==========================================
        timetable_slots = [
            # Monday (0)
            Timetable(class_id=c1.id, subject_id=subjects[0].id, teacher_id=teacher1.id, weekday=0, period=1, start_time=time(9, 0), end_time=time(10, 0), room="Room 301"),
            Timetable(class_id=c1.id, subject_id=subjects[1].id, teacher_id=teacher1.id, weekday=0, period=2, start_time=time(10, 0), end_time=time(11, 0), room="Room 301"),
            Timetable(class_id=c2.id, subject_id=subjects[3].id, teacher_id=teacher1.id, weekday=0, period=3, start_time=time(11, 15), end_time=time(12, 15), room="Room 302"),
            Timetable(class_id=c3.id, subject_id=subjects[6].id, teacher_id=teacher2.id, weekday=0, period=4, start_time=time(13, 0), end_time=time(14, 0), room="Lab E1"),
            # Tuesday (1)
            Timetable(class_id=c1.id, subject_id=subjects[2].id, teacher_id=teacher2.id, weekday=1, period=1, start_time=time(9, 0), end_time=time(10, 0), room="Room 301"),
            Timetable(class_id=c2.id, subject_id=subjects[4].id, teacher_id=teacher2.id, weekday=1, period=2, start_time=time(10, 0), end_time=time(11, 0), room="Room 302"),
            Timetable(class_id=c3.id, subject_id=subjects[7].id, teacher_id=teacher1.id, weekday=1, period=3, start_time=time(11, 15), end_time=time(12, 15), room="Lab E2"),
            # Wednesday (2)
            Timetable(class_id=c1.id, subject_id=subjects[0].id, teacher_id=teacher1.id, weekday=2, period=1, start_time=time(9, 0), end_time=time(10, 0), room="Room 301"),
            Timetable(class_id=c2.id, subject_id=subjects[5].id, teacher_id=teacher2.id, weekday=2, period=2, start_time=time(10, 0), end_time=time(11, 0), room="Room 302"),
            Timetable(class_id=c3.id, subject_id=subjects[8].id, teacher_id=teacher2.id, weekday=2, period=4, start_time=time(13, 0), end_time=time(14, 0), room="Room 201"),
            # Thursday (3)
            Timetable(class_id=c1.id, subject_id=subjects[1].id, teacher_id=teacher1.id, weekday=3, period=2, start_time=time(10, 0), end_time=time(11, 0), room="Room 301"),
            Timetable(class_id=c2.id, subject_id=subjects[3].id, teacher_id=teacher1.id, weekday=3, period=3, start_time=time(11, 15), end_time=time(12, 15), room="Room 302"),
            # Friday (4)
            Timetable(class_id=c1.id, subject_id=subjects[2].id, teacher_id=teacher2.id, weekday=4, period=1, start_time=time(9, 0), end_time=time(10, 0), room="Room 301"),
            Timetable(class_id=c3.id, subject_id=subjects[6].id, teacher_id=teacher2.id, weekday=4, period=3, start_time=time(11, 15), end_time=time(12, 15), room="Lab E1"),
        ]
        db.session.add_all(timetable_slots)
        db.session.commit()
        print("[OK] Timetable entries created.")

        # ==========================================
        # 7. HOLIDAYS
        # ==========================================
        today = date.today()
        holidays = [
            Holiday(date=today - timedelta(days=45), name="Republic Day", description="National Holiday", is_active=True),
            Holiday(date=today - timedelta(days=20), name="Spring Festival", description="Institutional Holiday", is_active=True),
            Holiday(date=today + timedelta(days=15), name="Labour Day", description="Public Holiday", is_active=True)
        ]
        db.session.add_all(holidays)
        db.session.commit()
        print("[OK] Holidays created.")

        # ==========================================
        # 8. 60 DAYS OF REALISTIC ATTENDANCE DATA
        # ==========================================
        print("Generating 60 days of realistic attendance sessions and records...")
        
        # Define student attendance tendencies
        # Specifically design low attendance students for shortage tracking:
        # e.g. CS2023005 (Bhavya Gupta), CS2023011 (Harshvardhan), CS2023017 (Omkar), EC2024004 (Yashwant)
        low_attendance_rolls = {"CS2023005", "CS2023011", "CS2023017", "EC2024004"}
        medium_attendance_rolls = {"CS2023002", "CS2023008", "CS2023014", "EC2024002"}

        session_count = 0
        record_count = 0

        # Class student mapping
        class_to_students = {
            c1.id: [s for s in created_students if s.class_id == c1.id],
            c2.id: [s for s in created_students if s.class_id == c2.id],
            c3.id: [s for s in created_students if s.class_id == c3.id],
        }

        # Class subject mapping
        class_to_subjects = {
            c1.id: [s for s in subjects if s.class_id == c1.id],
            c2.id: [s for s in subjects if s.class_id == c2.id],
            c3.id: [s for s in subjects if s.class_id == c3.id],
        }

        holiday_dates = {h.date for h in holidays}

        for day_offset in range(60, 0, -1):
            cur_date = today - timedelta(days=day_offset)
            weekday = cur_date.weekday()

            # Skip weekends (5=Saturday, 6=Sunday) and holidays
            if weekday >= 5 or cur_date in holiday_dates:
                continue

            # Conduct 2 sessions per class on active weekdays
            for cid in [c1.id, c2.id, c3.id]:
                c_subs = class_to_subjects[cid]
                c_stus = class_to_students[cid]

                for p_num, sub in enumerate(c_subs[:2], 1):
                    started_dt = datetime.combine(cur_date, time(9 + p_num, 0)).replace(tzinfo=timezone.utc)
                    ended_dt = started_dt + timedelta(minutes=55)

                    session = AttendanceSession(
                        class_id=cid,
                        subject_id=sub.id,
                        teacher_id=sub.teacher_id,
                        date=cur_date,
                        period=p_num,
                        session_name=f"{sub.code} - Lecture {60 - day_offset}",
                        started_at=started_dt,
                        ended_at=ended_dt,
                        duration_minutes=60,
                        status='ended',
                        created_at=started_dt
                    )
                    db.session.add(session)
                    db.session.flush()
                    session_count += 1

                    for stu in c_stus:
                        # Determine status probability
                        if stu.roll_no in low_attendance_rolls:
                            # Low attendance: ~55% present/late, 40% absent, 5% excused
                            rand_val = random.random()
                            if rand_val < 0.45:
                                status = 'Present'
                                method = 'face' if stu.face_enrolled else 'manual'
                            elif rand_val < 0.55:
                                status = 'Late'
                                method = 'face' if stu.face_enrolled else 'manual'
                            elif rand_val < 0.95:
                                status = 'Absent'
                                method = 'system'
                            else:
                                status = 'Excused'
                                method = 'manual'
                        elif stu.roll_no in medium_attendance_rolls:
                            # Medium attendance: ~76% attendance
                            rand_val = random.random()
                            if rand_val < 0.70:
                                status = 'Present'
                                method = 'face' if stu.face_enrolled else 'manual'
                            elif rand_val < 0.78:
                                status = 'Late'
                                method = 'face' if stu.face_enrolled else 'manual'
                            elif rand_val < 0.95:
                                status = 'Absent'
                                method = 'system'
                            else:
                                status = 'Excused'
                                method = 'manual'
                        else:
                            # High attendance: ~88% - 96%
                            rand_val = random.random()
                            if rand_val < 0.85:
                                status = 'Present'
                                method = 'face' if stu.face_enrolled else 'manual'
                            elif rand_val < 0.92:
                                status = 'Late'
                                method = 'face' if stu.face_enrolled else 'manual'
                            elif rand_val < 0.98:
                                status = 'Absent'
                                method = 'system'
                            else:
                                status = 'Excused'
                                method = 'manual'

                        rec = AttendanceRecord(
                            session_id=session.id,
                            student_id=stu.id,
                            status=status,
                            method=method,
                            confidence=0.88 if method == 'face' else None,
                            note='Regular session marking' if status == 'Present' else ('Late entry' if status == 'Late' else 'Unmarked/Excused'),
                            marked_at=started_dt + timedelta(minutes=random.randint(1, 15)),
                            updated_at=started_dt + timedelta(minutes=15)
                        )
                        db.session.add(rec)
                        record_count += 1

        db.session.commit()
        print(f"[OK] {session_count} Sessions and {record_count} Attendance Records generated.")

        # ==========================================
        # 9. TODAY'S SESSIONS
        # ==========================================
        today_session = AttendanceSession(
            class_id=c1.id,
            subject_id=subjects[0].id,
            teacher_id=teacher1.id,
            date=today,
            period=1,
            session_name="CS301 - Today Morning Session",
            started_at=datetime.now(timezone.utc) - timedelta(minutes=35),
            ended_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            duration_minutes=60,
            status='ended'
        )
        db.session.add(today_session)
        db.session.flush()

        for stu in class_to_students[c1.id]:
            st = 'Present' if stu.roll_no not in low_attendance_rolls else 'Absent'
            r = AttendanceRecord(
                session_id=today_session.id,
                student_id=stu.id,
                status=st,
                method='face' if stu.face_enrolled and st == 'Present' else 'manual',
                confidence=0.91 if st == 'Present' else None,
                note='Today morning roll call'
            )
            db.session.add(r)
        
        db.session.commit()
        print("[OK] Today's sample session and attendance generated.")

        # Create initial audit log
        log_entry = AuditLog(
            user_id=admin.id,
            action="SYSTEM_INIT_SEED",
            entity_type="System",
            details="Initial demo seed data populated with 30 students, 3 classes, 9 subjects, and 60 days of historical attendance.",
            created_at=datetime.now(timezone.utc)
        )
        db.session.add(log_entry)
        db.session.commit()

        print("\n=======================================================")
        print("DATABASE SEEDING COMPLETE!")
        print("=======================================================")
        print("Demo Credentials for Development/Testing:")
        print("1. Administrator : admin@example.com      / Admin@123")
        print("2. Teacher 1     : dr.sarah@example.com    / Teacher@123")
        print("3. Teacher 2     : prof.robert@example.com / Teacher@123")
        print("4. Student       : aarav.sharma@example.edu / Student@123")
        print("=======================================================\n")


if __name__ == '__main__':
    run_seed()
