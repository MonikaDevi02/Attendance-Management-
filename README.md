# Attendance Management System

A simple web-based attendance management system that allows you to track student attendance with subject details, date, and time.

## Features

- Manual entry of subject name, student name, and register number
- Automatic date and time capture
- Status tracking (Present/Absent/OD)
- Responsive design for mobile and desktop
- SQLite database for data storage

## Requirements

- Python 3.7 or higher
- Flask
- Flask-SQLAlchemy

## Installation

1. Clone this repository or download the files
2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. Make sure you're in the project directory
2. Run the Flask application:
   ```bash
   python app.py
   ```
3. Open your web browser and navigate to `http://localhost:5000`

## Usage

1. Fill in the attendance form with:
   - Subject Name
   - Register Number
   - Student Name
   - Status (Present/Absent/OD)
2. Click "Add Attendance" to save the record
3. View all attendance records in the table below the form

## Database

The application uses SQLite as its database. The database file (`attendance.db`) will be created automatically when you first run the application. 