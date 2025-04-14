from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import pandas as pd
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.platypus import Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

# Ensure instance folder exists
os.makedirs('instance', exist_ok=True)

# Ensure data directory exists
os.makedirs(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'data'), exist_ok=True)

# Set up the database path
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'data', 'attendance.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this to a secure secret key
app.secret_key = 'your-secret-key-here'  # Add this line to enable session
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    subject = db.relationship('Subject', backref=db.backref('attendances', lazy=True))
    register_no = db.Column(db.String(20), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(10), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('attendances', lazy=True))

class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sheet_id = db.Column(db.Integer, db.ForeignKey('attendance.id'), nullable=False)
    student_id = db.Column(db.String(20), nullable=False)
    student_name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    remarks = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sheet = db.relationship('Attendance', backref=db.backref('records', lazy=True))

# Database initialization and session handling
def init_db():
    with app.app_context():
        db.create_all()
        # Create default admin user if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()

@app.before_request
def before_request():
    if not hasattr(db.session, 'is_active'):
        db.session.is_active = True

@app.teardown_appcontext
def shutdown_session(exception=None):
    if hasattr(db.session, 'is_active'):
        db.session.remove()

# Initialize database
init_db()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        try:
            username = request.form['username']
            password = request.form['password']
            print(f"Login attempt for user: {username}")  # Debug log
            
            user = User.query.filter_by(username=username).first()
            
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                session['user_id'] = user.id
                print(f"User {username} logged in successfully")  # Debug log
                flash('Logged in successfully!')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password')
        except Exception as e:
            print(f"Login error: {str(e)}")  # Debug log
            flash('An error occurred during login')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match!')
            return redirect(url_for('register'))
            
        if User.query.filter_by(username=username).first():
            flash('Username already exists!')
            return redirect(url_for('register'))
            
        new_user = User(
            username=username,
            password_hash=generate_password_hash(password),
            is_admin=False
        )
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('user_id', None)  # Clear user ID from session
    flash('Logged out successfully!')
    return redirect(url_for('login'))

@app.route('/add_subject', methods=['POST'])
@login_required
def add_subject():
    try:
        print("Starting add_subject")  # Debug log
        subject_name = request.form['subject_name']
        print(f"Adding subject: {subject_name}")  # Debug log
        
        # Check if subject exists
        existing_subject = Subject.query.filter_by(name=subject_name).first()
        if existing_subject:
            flash('Subject already exists!')
            return redirect(url_for('root'))
        
        # Create new subject
        print("Creating new subject")  # Debug log
        new_subject = Subject(name=subject_name)
        db.session.add(new_subject)
        print("Committing to database")  # Debug log
        db.session.commit()
        print("Subject added successfully")  # Debug log
        flash('Subject added successfully!')
        return redirect(url_for('root'))
    except Exception as e:
        print(f"Error adding subject: {str(e)}")  # Debug log
        db.session.rollback()
        flash(f'Error adding subject: {str(e)}')
        return redirect(url_for('root'))

@app.route('/edit_attendance/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_attendance(record_id):
    record = Attendance.query.get_or_404(record_id)
    
    if request.method == 'POST':
        record.status = request.form['status']
        db.session.commit()
        flash('Attendance status updated successfully!')
        return redirect(url_for('index', subject_id=record.subject_id))
        
    return render_template('edit_attendance.html', record=record)

@app.route('/')
def root():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get all subjects
    subjects = Subject.query.order_by(Subject.name).all()
    
    # Get recent attendance sheets
    recent_sheets = Attendance.query.join(Subject).order_by(Attendance.date.desc(), Attendance.time.desc()).limit(10).all()
    
    # Get current date and time
    current_datetime = datetime.now()
    today_date = current_datetime.strftime('%Y-%m-%d')
    current_time = current_datetime.strftime('%H:%M')
    
    return render_template('index.html',
                         subjects=subjects,
                         recent_sheets=recent_sheets,
                         today_date=today_date,
                         current_time=current_time)

@app.route('/add_attendance', methods=['POST'])
@login_required
def add_attendance():
    subject_id = request.form['subject_id']
    register_no = request.form['register_no']
    student_name = request.form['student_name']
    status = request.form['status']
    
    try:
        # Create new attendance record
        new_record = AttendanceRecord(
            sheet_id=subject_id,  # Using subject_id as sheet_id for now
            student_id=register_no,
            student_name=student_name,
            status=status.lower(),  # Convert to lowercase for consistency
            remarks=''
        )
        
        db.session.add(new_record)
        db.session.commit()
        
        flash('Attendance record added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding attendance record: {str(e)}', 'error')
    
    return redirect(url_for('index', subject_id=subject_id))

def get_db_connection():
    """Create a connection to the SQLite database."""
    try:
        conn = sqlite3.connect('attendance.db')
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        flash(f'Database connection error: {str(e)}', 'error')
        return None

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Create subjects table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            teacher_id INTEGER,
            FOREIGN KEY (teacher_id) REFERENCES users (id)
        )
    ''')
    
    # Create attendance_sheets table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_sheets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL,
            date DATE NOT NULL,
            time TIME NOT NULL,
            created_by INTEGER NOT NULL,
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            FOREIGN KEY (created_by) REFERENCES users (id)
        )
    ''')
    
    # Create attendance_records table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sheet_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            student_name TEXT NOT NULL,
            status TEXT NOT NULL,
            remarks TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sheet_id) REFERENCES attendance_sheets (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database tables
# create_tables()  # Commented out as db.create_all() is already used

@app.route('/create_sheet', methods=['GET', 'POST'])
@login_required
def create_sheet():
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        date = request.form.get('date')
        time = request.form.get('time')
        
        if not all([subject_id, date, time]):
            flash('All fields are required', 'error')
            return redirect(url_for('root'))
        
        try:
            # Create new attendance sheet
            new_sheet = Attendance(
                subject_id=subject_id,
                register_no='TEMP',  # Temporary value
                student_name='TEMP',  # Temporary value
                date=datetime.strptime(date, '%Y-%m-%d').date(),
                time=datetime.strptime(time, '%H:%M').time(),
                status='TEMP',  # Temporary value
                created_by=current_user.id
            )
            db.session.add(new_sheet)
            db.session.commit()
            
            flash('Attendance sheet created successfully!', 'success')
            return redirect(url_for('view_sheet', sheet_id=new_sheet.id))
        except Exception as e:
            flash(f'Error creating attendance sheet: {str(e)}', 'error')
            return redirect(url_for('root'))
    
    # If GET request, show the create sheet form
    subjects = Subject.query.all()
    today_date = datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now().strftime('%H:%M')
    
    return render_template('create_sheet.html',
                         subjects=subjects,
                         today_date=today_date,
                         current_time=current_time)

@app.route('/view_sheet/<int:sheet_id>')
@login_required
def view_sheet(sheet_id):
    sheet = Attendance.query.get_or_404(sheet_id)
    subject = Subject.query.get_or_404(sheet.subject_id)
    
    # Get attendance records for this sheet
    records = AttendanceRecord.query.filter_by(sheet_id=sheet_id).order_by(AttendanceRecord.timestamp.desc()).all()
    
    # Calculate statistics for this sheet
    total_records = len(records)
    present_count = len([r for r in records if r.status == 'present'])
    absent_count = len([r for r in records if r.status == 'absent'])
    od_count = len([r for r in records if r.status == 'od'])
    
    # Calculate percentages
    present_percentage = (present_count / total_records * 100) if total_records > 0 else 0
    absent_percentage = (absent_count / total_records * 100) if total_records > 0 else 0
    od_percentage = (od_count / total_records * 100) if total_records > 0 else 0
    
    return render_template('view_sheet.html', 
                         sheet=sheet,
                         subject=subject,
                         records=records,
                         total_records=total_records,
                         present_count=present_count,
                         absent_count=absent_count,
                         od_count=od_count,
                         present_percentage=present_percentage,
                         absent_percentage=absent_percentage,
                         od_percentage=od_percentage,
                         today_date=datetime.now().strftime('%Y-%m-%d'),
                         current_time=datetime.now().strftime('%H:%M'))

@app.route('/download_excel')
@login_required
def download_excel():
    try:
        # Get sheet_id from query parameter
        sheet_id = request.args.get('sheet_id')
        
        # Get custom filename from query parameter
        filename = request.args.get('filename', 'attendance_report')
        if not filename.endswith('.xlsx'):
            filename += '.xlsx'

        # Build the query based on whether sheet_id is provided
        query = db.session.query(
            Subject.name.label('subject'),
            Attendance.student_name,
            Attendance.register_no.label('register_number'),
            Attendance.date,
            Attendance.time,
            Attendance.status
        ).join(Subject)
        
        if sheet_id:
            # Filter by specific sheet_id
            query = query.filter(Attendance.id == sheet_id)
        
        # Get the records ordered by date and time
        records = query.order_by(Attendance.date.desc(), Attendance.time.desc()).all()
        
        if not records:
            flash('No attendance records to download', 'warning')
            return redirect(url_for('root'))
        
        # Convert to pandas DataFrame
        data = []
        for record in records:
            data.append({
                'Subject': record.subject,
                'Student Name': record.student_name,
                'Register Number': record.register_number,
                'Date': record.date.strftime('%Y-%m-%d'),
                'Time': record.time.strftime('%H:%M:%S'),
                'Status': record.status
            })
        
        df = pd.DataFrame(data)
            
        # Create Excel file
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Attendance', index=False)
            
            # Get workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets['Attendance']
            
            # Add some formatting
            header_format = workbook.add_format({
                'bold': True,
                'font_color': 'white',
                'bg_color': '#4CAF50',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            
            # Format headers
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
                worksheet.set_column(col_num, col_num, 15)
            
            # Add row formatting
            row_format = workbook.add_format({
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            })
            
            # Apply row formatting
            for row_num in range(1, len(df) + 1):
                worksheet.set_row(row_num, None, row_format)
        
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error generating Excel file: {str(e)}', 'error')
        return redirect(url_for('root'))

@app.route('/download_pdf')
@login_required
def download_pdf():
    try:
        # Get custom filename from query parameter
        filename = request.args.get('filename', 'attendance_report')
        if not filename.endswith('.pdf'):
            filename += '.pdf'

        # Get attendance data using SQLAlchemy
        records = db.session.query(
            Subject.name.label('subject'),
            Attendance.student_name,
            Attendance.register_no.label('register_number'),
            Attendance.date,
            Attendance.time,
            Attendance.status
        ).join(Subject).order_by(Attendance.date.desc(), Attendance.time.desc()).all()
        
        if not records:
            flash('No attendance records to download', 'warning')
            return redirect(url_for('index'))
        
        # Create PDF
        output = BytesIO()
        doc = SimpleDocTemplate(
            output, 
            pagesize=letter,
            title="Attendance Report"
        )
        
        # Create elements list for the PDF
        elements = []
        
        # Add title
        title_style = getSampleStyleSheet()['Title']
        elements.append(Paragraph("Attendance Report", title_style))
        elements.append(Spacer(1, 20))
        
        # Prepare table data
        table_data = [['Subject', 'Student Name', 'Register No.', 'Date', 'Time', 'Status']]
        table_data.extend([
            [record.subject, record.student_name, record.register_number,
             record.date.strftime('%Y-%m-%d'), record.time.strftime('%H:%M:%S'),
             record.status] for record in records
        ])
        
        # Create table
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.green),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        doc.build(elements)
        
        output.seek(0)
        return send_file(
            output,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error generating PDF file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/download_csv')
@login_required
def download_csv():
    try:
        # Get custom filename from query parameter
        filename = request.args.get('filename', 'attendance_report')
        if not filename.endswith('.csv'):
            filename += '.csv'

        # Get attendance data using SQLAlchemy
        records = db.session.query(
            Subject.name.label('subject'),
            Attendance.student_name,
            Attendance.register_no.label('register_number'),
            Attendance.date,
            Attendance.time,
            Attendance.status
        ).join(Subject).order_by(Attendance.date.desc(), Attendance.time.desc()).all()
        
        if not records:
            flash('No attendance records to download', 'warning')
            return redirect(url_for('index'))
        
        # Convert to pandas DataFrame
        data = []
        for record in records:
            data.append({
                'Subject': record.subject,
                'Student Name': record.student_name,
                'Register Number': record.register_number,
                'Date': record.date.strftime('%Y-%m-%d'),
                'Time': record.time.strftime('%H:%M:%S'),
                'Status': record.status
            })
        
        df = pd.DataFrame(data)
        
        # Create CSV in memory
        output = BytesIO()
        df.to_csv(output, index=False, encoding='utf-8')
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error generating CSV file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/mark_attendance/<int:sheet_id>', methods=['POST'])
@login_required
def mark_attendance(sheet_id):
    student_id = request.form.get('student_id')
    student_name = request.form.get('student_name')
    status = request.form.get('status')
    remarks = request.form.get('remarks')
    
    if not all([student_id, student_name, status]):
        flash('Student ID, Name and Status are required', 'error')
        return redirect(url_for('view_sheet', sheet_id=sheet_id))
    
    try:
        # Create new attendance record
        new_record = AttendanceRecord(
            sheet_id=sheet_id,
            student_id=student_id,
            student_name=student_name,
            status=status,
            remarks=remarks
        )
        
        db.session.add(new_record)
        db.session.commit()
        
        flash('Attendance marked successfully!', 'success')
    except Exception as e:
        flash(f'Error marking attendance: {str(e)}', 'error')
    
    return redirect(url_for('view_sheet', sheet_id=sheet_id))

@app.route('/get_record/<int:record_id>')
@login_required
def get_record(record_id):
    record = AttendanceRecord.query.get_or_404(record_id)
    return jsonify({
        'student_id': record.student_id,
        'student_name': record.student_name,
        'status': record.status,
        'remarks': record.remarks
    })

@app.route('/update_record/<int:record_id>', methods=['POST'])
@login_required
def update_record(record_id):
    record = AttendanceRecord.query.get_or_404(record_id)
    record.student_id = request.form['student_id']
    record.student_name = request.form['student_name']
    record.status = request.form['status']
    record.remarks = request.form.get('remarks')
    db.session.commit()
    flash('Attendance record updated successfully!', 'success')
    return redirect(url_for('view_sheet', sheet_id=record.sheet_id))

@app.route('/delete_record/<int:record_id>')
@login_required
def delete_record(record_id):
    record = AttendanceRecord.query.get_or_404(record_id)
    sheet_id = record.sheet_id
    db.session.delete(record)
    db.session.commit()
    flash('Attendance record deleted successfully!', 'success')
    return redirect(url_for('view_sheet', sheet_id=sheet_id))

@app.route('/delete_sheet/<int:sheet_id>')
@login_required
def delete_sheet(sheet_id):
    sheet = Attendance.query.get_or_404(sheet_id)
    # Delete all records associated with this sheet
    AttendanceRecord.query.filter_by(sheet_id=sheet_id).delete()
    db.session.delete(sheet)
    db.session.commit()
    flash('Attendance sheet deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/delete_subject/<int:subject_id>')
@login_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    # Delete all attendance sheets and records associated with this subject
    sheets = Attendance.query.filter_by(subject_id=subject_id).all()
    for sheet in sheets:
        # Delete all records for this sheet
        AttendanceRecord.query.filter_by(sheet_id=sheet.id).delete()
        # Delete the sheet
        db.session.delete(sheet)
    # Delete the subject
    db.session.delete(subject)
    db.session.commit()
    flash('Subject and all associated attendance sheets deleted successfully!', 'success')
    return redirect(url_for('root'))

if __name__ == '__main__':
    app.run(debug=True) 