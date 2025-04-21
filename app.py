# app.py
from flask import Flask, render_template, request, redirect, flash, send_from_directory
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import os
import time
import sqlite3
import boto3
from models import db
from routes import bp as sections_bp
from home_routes import bp as home_bp
from kiosk_routes import bp as kiosks_bp
from floorplan_routes import bp as floorplan_bp

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = 'your_secret_key'
# Set absolute path for uploads folder
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mkv'}  # Added mkv

# Ensure upload directory exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# SQLAlchemy configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# S3 configuration
app.config['S3_BUCKET'] = os.environ.get('S3_BUCKET')
app.config['S3_KEY'] = os.environ.get('S3_KEY')
app.config['S3_SECRET'] = os.environ.get('S3_SECRET')
app.config['S3_LOCATION'] = os.environ.get('S3_LOCATION')

# Initialize S3 client
app.s3 = boto3.client(
    's3',
    aws_access_key_id=app.config['S3_KEY'],
    aws_secret_access_key=app.config['S3_SECRET']
)

# Initialize SQLAlchemy
db.init_app(app)

# Register blueprints with URL prefix
app.register_blueprint(sections_bp, url_prefix='')
app.register_blueprint(kiosks_bp, url_prefix='')
app.register_blueprint(home_bp, url_prefix='')
app.register_blueprint(floorplan_bp, url_prefix='')

# If you're using MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'floorplan_db'

# Initialize MySQL
mysql = MySQL(app)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

# Create SQLite DB connection (as an alternative to MySQL)
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_sqlite_db():
    # Create tables for existing functionality
    conn = get_db_connection()
    conn.execute('''
    CREATE TABLE IF NOT EXISTS floor_plans_and_elevations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dimension TEXT NOT NULL,
        facing TEXT NOT NULL,
        type_of_use TEXT NOT NULL,
        floors INTEGER NOT NULL,
        floor_plan TEXT,
        elevation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

    # Create tables for new functionality using SQLAlchemy
    with app.app_context():
        db.create_all()

# Initialize SQLite DB
init_sqlite_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_file_locally(file, filename):
    """
    Save file to local storage instead of S3
    """
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    return file_path

@app.route('/')
def index():
    return redirect('/upload_floor_plan_and_elevation')

@app.route('/upload_floor_plan_and_elevation', methods=['GET', 'POST'])
def upload_floor_plan_and_elevation():
    if request.method == 'POST':
        dimension = request.form['site_dimension']
        facing = request.form['facing']
        type_of_use = request.form['type']
        floors = request.form['floors']
                
            # SQLite implementation
        conn = get_db_connection()
        
        # Insert the form data into the floor_plans_and_elevations table
        insert_query = "INSERT INTO floor_plans_and_elevations (dimension, facing, type_of_use, floors) VALUES (?, ?, ?, ?)"
        cursor = conn.execute(insert_query, (dimension, facing, type_of_use, floors))
        last_row_id = cursor.lastrowid
        
        # Handle floor plan upload
        floor_plan = request.files['floor_plan']
        if floor_plan and allowed_file(floor_plan.filename):
            floor_plan_filename = 'fp_' + str(last_row_id) + '_' + str(int(time.time())) + '_' + secure_filename(floor_plan.filename)
            floor_plan_filename = save_file_locally(floor_plan, floor_plan_filename)
        else:
            flash('Invalid floor plan file', 'danger')
            conn.close()
            return redirect(request.url)
        
        # Handle elevation image upload
        elevation = request.files['elevation']
        if elevation and allowed_file(elevation.filename):
            elevation_filename = 'el_' + str(last_row_id) + '_' + str(int(time.time())) + '_' + secure_filename(elevation.filename)
            elevation_filename = save_file_locally(elevation, elevation_filename)
        else:
            flash('Invalid elevation image file', 'danger')
            conn.close()
            return redirect(request.url)
        
        # Update the record with file paths
        update_query = "UPDATE floor_plans_and_elevations SET floor_plan = ?, elevation = ? WHERE id = ?"
        conn.execute(update_query, (floor_plan_filename, elevation_filename, last_row_id))
        
        conn.commit()
        conn.close()
        
        flash('Floor plan and elevation uploaded successfully', 'success')
        return redirect('/upload_floor_plan_and_elevation')
    
    return render_template('upload_floor_plan_and_elevation.html')

@app.route('/view_records')
def view_records():

    conn = get_db_connection()
    records = conn.execute("SELECT * FROM floor_plans_and_elevations").fetchall()
    conn.close()

    return render_template('view_records.html', records=records)



@app.route("/check_floor_plan_and_elevation", methods=['GET'])
def check_floor_plan_and_elevation():

    if 'view' in request.args:
        view = request.args['view']
    else:
        view = ''

    if 'site_dimension' in request.args:
        dimension = request.args['site_dimension']   
    else:
        dimension = ''
    if 'facing' in request.args:
        facing = request.args['facing']
    else:
        facing = ''
    if 'floors' in request.args:
        floors = request.args['floors']
    else:
        floors = ''
    if 'use_type' in request.args:
        type_of_use = request.args['use_type']
    else:
        type_of_use = ''   

    if view == 'featured':
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM floor_plans_and_elevations")
        res = cur.fetchall()
        print(res)
        for row in res:
            print("ID:", row['id'])
            print("Dimension:", row['dimension'])
            print("Facing:", row['facing'])
            print("Type of Use:", row['type_of_use'])
            print("Floors:", row['floors'])
            print("Floor Plan:", row['floor_plan'])
            print("Elevation:", row['elevation'])
            print("Created At:", row['created_at'])
        conn.close()
        return render_template('check_floor_plan_and_elevation.html', floor_plans_and_elevations=res, view_floor_plans=True, no_floor_plans_and_elevations=False)

    if dimension != '' or facing != '' or floors != '' or type_of_use != '':
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM floor_plans_and_elevations WHERE dimension = ? OR facing = ? OR floors = ? OR type_of_use = ?", (dimension, facing, floors, type_of_use))
        res = cur.fetchall()
        conn.close()
        no_floor_plans_and_elevations = True
        if len(res) > 0:
            no_floor_plans_and_elevations = False

        return render_template('check_floor_plan_and_elevation.html', floor_plans_and_elevations=res, view_floor_plans=True, no_floor_plans_and_elevations=no_floor_plans_and_elevations)
    else:
        return render_template('check_floor_plan_and_elevation.html', view_floor_plans=False)

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
