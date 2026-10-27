import os
import re
import sqlite3
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, 'teacher_cabin_locator.db')
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-demo-secret-before-deployment')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.execute('PRAGMA foreign_keys = ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        user_type TEXT NOT NULL CHECK(user_type IN ('student','visitor','admin')),
        roll_number TEXT UNIQUE,
        email TEXT UNIQUE,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'creator'
    );
    CREATE TABLE IF NOT EXISTS buildings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT DEFAULT '',
        campus_location TEXT DEFAULT '',
        map_url TEXT DEFAULT '',
        last_updated TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS faculty (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        department TEXT NOT NULL,
        designation TEXT NOT NULL,
        phone_number TEXT DEFAULT '',
        profession TEXT DEFAULT '',
        building_id INTEGER NOT NULL,
        floor TEXT NOT NULL,
        cabin_number TEXT NOT NULL,
        map_url TEXT DEFAULT '',
        last_updated TEXT NOT NULL,
        FOREIGN KEY(building_id) REFERENCES buildings(id) ON UPDATE CASCADE ON DELETE RESTRICT
    );
    CREATE INDEX IF NOT EXISTS idx_faculty_name ON faculty(full_name);
    CREATE INDEX IF NOT EXISTS idx_faculty_department ON faculty(department);
    ''')
    # Demo account only; change credentials before using beyond a classroom demonstration.
    admin_username = os.environ.get('ADMIN_USERNAME', 'creator')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'GNITSdemo123!')
    existing = db.execute('SELECT id FROM admins WHERE username = ?', (admin_username,)).fetchone()
    if not existing:
        db.execute('INSERT INTO admins (username, password_hash, role) VALUES (?, ?, ?)',
                   (admin_username, generate_password_hash(admin_password), 'creator'))
    db.commit()
    db.close()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin_id'):
            flash('Please sign in with the Creator/Admin account first.', 'warning')
            return redirect(url_for('admin_login'))
        return view(*args, **kwargs)
    return wrapped


def clean(value):
    return (value or '').strip()


def valid_map_url(value):
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def now_text():
    return datetime.now().strftime('%Y-%m-%d %H:%M')


@app.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    return render_template('login.html')


@app.post('/login/student')
def student_login():
    name = clean(request.form.get('name'))
    roll = clean(request.form.get('roll_number')).upper()
    if not name or not roll:
        flash('Enter both your name and roll number.', 'danger')
        return redirect(url_for('index'))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE user_type='student' AND roll_number=?", (roll,)).fetchone()
    if user:
        db.execute('UPDATE users SET name=? WHERE id=?', (name, user['id']))
        user_id = user['id']
    else:
        cur = db.execute('INSERT INTO users(name,user_type,roll_number,created_at) VALUES(?,?,?,?)',
                          (name, 'student', roll, now_text()))
        user_id = cur.lastrowid
    db.commit()
    session.clear()
    session['user_id'] = user_id
    session['user_name'] = name
    session['user_type'] = 'student'
    return redirect(url_for('dashboard'))


@app.post('/login/visitor')
def visitor_login():
    name = clean(request.form.get('name'))
    email = clean(request.form.get('email')).lower()
    if not name or not email or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        flash('Enter your name and a valid email address.', 'danger')
        return redirect(url_for('index'))
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE user_type='visitor' AND email=?", (email,)).fetchone()
    if user:
        db.execute('UPDATE users SET name=? WHERE id=?', (name, user['id']))
        user_id = user['id']
    else:
        cur = db.execute('INSERT INTO users(name,user_type,email,created_at) VALUES(?,?,?,?)',
                          (name, 'visitor', email, now_text()))
        user_id = cur.lastrowid
    db.commit()
    session.clear()
    session['user_id'] = user_id
    session['user_name'] = name
    session['user_type'] = 'visitor'
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('index'))
    db = get_db()
    buildings = db.execute('SELECT * FROM buildings ORDER BY name').fetchall()
    departments = db.execute('SELECT DISTINCT department FROM faculty ORDER BY department').fetchall()
    return render_template('dashboard.html', buildings=buildings, departments=departments)


@app.route('/search/faculty')
def search_faculty():
    if not session.get('user_id'):
        return redirect(url_for('index'))
    q = clean(request.args.get('q'))
    department = clean(request.args.get('department'))
    designation = clean(request.args.get('designation'))
    sql = '''SELECT f.*, b.name AS building_name, b.campus_location, b.map_url AS building_map_url
             FROM faculty f JOIN buildings b ON f.building_id=b.id WHERE 1=1'''
    params = []
    if q:
        sql += ' AND (f.full_name LIKE ? OR f.department LIKE ? OR f.designation LIKE ?)'
        pattern = f'%{q}%'
        params.extend([pattern, pattern, pattern])
    if department:
        sql += ' AND f.department = ?'
        params.append(department)
    if designation:
        sql += ' AND f.designation = ?'
        params.append(designation)
    sql += ' ORDER BY f.full_name COLLATE NOCASE'
    results = get_db().execute(sql, params).fetchall()
    departments = get_db().execute('SELECT DISTINCT department FROM faculty ORDER BY department').fetchall()
    designations = get_db().execute('SELECT DISTINCT designation FROM faculty ORDER BY designation').fetchall()
    return render_template('faculty_results.html', results=results, q=q, department=department,
                           designation=designation, departments=departments, designations=designations)


@app.route('/faculty/<int:faculty_id>')
def faculty_detail(faculty_id):
    if not session.get('user_id'):
        return redirect(url_for('index'))
    faculty = get_db().execute('''SELECT f.*, b.name AS building_name, b.campus_location,
        b.map_url AS building_map_url FROM faculty f JOIN buildings b ON f.building_id=b.id WHERE f.id=?''',
        (faculty_id,)).fetchone()
    if not faculty:
        abort(404)
    return render_template('faculty_detail.html', faculty=faculty)


@app.route('/search/buildings')
def search_buildings():
    if not session.get('user_id'):
        return redirect(url_for('index'))
    q = clean(request.args.get('q'))
    if q:
        buildings = get_db().execute('SELECT * FROM buildings WHERE name LIKE ? OR campus_location LIKE ? OR description LIKE ? ORDER BY name',
                                     (f'%{q}%', f'%{q}%', f'%{q}%')).fetchall()
    else:
        buildings = get_db().execute('SELECT * FROM buildings ORDER BY name').fetchall()
    return render_template('building_results.html', buildings=buildings, q=q)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been signed out.', 'success')
    return redirect(url_for('index'))


@app.route('/creator/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = clean(request.form.get('username'))
        password = request.form.get('password') or ''
        admin = get_db().execute('SELECT * FROM admins WHERE username=?', (username,)).fetchone()
        if admin and check_password_hash(admin['password_hash'], password):
            session.clear()
            session['admin_id'] = admin['id']
            session['admin_username'] = admin['username']
            flash('Welcome to the Creator Dashboard.', 'success')
            return redirect(url_for('admin_dashboard'))
        flash('Incorrect username or password.', 'danger')
    return render_template('admin_login.html')


@app.route('/creator')
@admin_required
def admin_dashboard():
    db = get_db()
    stats = {
        'faculty': db.execute('SELECT COUNT(*) FROM faculty').fetchone()[0],
        'buildings': db.execute('SELECT COUNT(*) FROM buildings').fetchone()[0],
        'users': db.execute("SELECT COUNT(*) FROM users WHERE user_type != 'admin'").fetchone()[0],
    }
    faculty = db.execute('''SELECT f.*, b.name AS building_name FROM faculty f JOIN buildings b ON b.id=f.building_id ORDER BY f.full_name''').fetchall()
    buildings = db.execute('SELECT * FROM buildings ORDER BY name').fetchall()
    users = db.execute('SELECT * FROM users ORDER BY created_at DESC LIMIT 100').fetchall()
    return render_template('admin_dashboard.html', stats=stats, faculty=faculty, buildings=buildings, users=users)


@app.route('/creator/buildings/add', methods=['POST'])
@admin_required
def add_building():
    name = clean(request.form.get('name'))
    description = clean(request.form.get('description'))
    location = clean(request.form.get('campus_location'))
    map_url = clean(request.form.get('map_url'))
    if not name or not location:
        flash('Building name and campus location are required.', 'danger')
    elif not valid_map_url(map_url):
        flash('Map link must start with http:// or https://.', 'danger')
    else:
        try:
            get_db().execute('INSERT INTO buildings(name,description,campus_location,map_url,last_updated) VALUES(?,?,?,?,?)',
                             (name, description, location, map_url, now_text()))
            get_db().commit()
            flash('Building added successfully.', 'success')
        except sqlite3.IntegrityError:
            flash('A building with that name already exists.', 'danger')
    return redirect(url_for('admin_dashboard') + '#buildings')


@app.route('/creator/buildings/<int:building_id>/edit', methods=['POST'])
@admin_required
def edit_building(building_id):
    name = clean(request.form.get('name'))
    description = clean(request.form.get('description'))
    location = clean(request.form.get('campus_location'))
    map_url = clean(request.form.get('map_url'))
    if not name or not location or not valid_map_url(map_url):
        flash('Enter a building name, location, and a valid optional map URL.', 'danger')
    else:
        try:
            cur = get_db().execute('UPDATE buildings SET name=?,description=?,campus_location=?,map_url=?,last_updated=? WHERE id=?',
                                   (name, description, location, map_url, now_text(), building_id))
            get_db().commit()
            flash('Building updated.' if cur.rowcount else 'Building not found.', 'success' if cur.rowcount else 'danger')
        except sqlite3.IntegrityError:
            flash('Another building already uses that name.', 'danger')
    return redirect(url_for('admin_dashboard') + '#buildings')


@app.route('/creator/buildings/<int:building_id>/delete', methods=['POST'])
@admin_required
def delete_building(building_id):
    try:
        cur = get_db().execute('DELETE FROM buildings WHERE id=?', (building_id,))
        get_db().commit()
        flash('Building deleted.' if cur.rowcount else 'Building not found.', 'success' if cur.rowcount else 'danger')
    except sqlite3.IntegrityError:
        flash('This building is assigned to faculty. Reassign or delete those faculty records first.', 'danger')
    return redirect(url_for('admin_dashboard') + '#buildings')


def faculty_form_values():
    return {
        'full_name': clean(request.form.get('full_name')),
        'department': clean(request.form.get('department')),
        'designation': clean(request.form.get('designation')),
        'phone_number': clean(request.form.get('phone_number')),
        'profession': clean(request.form.get('profession')),
        'building_id': clean(request.form.get('building_id')),
        'floor': clean(request.form.get('floor')),
        'cabin_number': clean(request.form.get('cabin_number')),
        'map_url': clean(request.form.get('map_url')),
    }


def validate_faculty(data):
    required = ['full_name', 'department', 'designation', 'building_id', 'floor', 'cabin_number']
    if any(not data[k] for k in required):
        return 'Fill in all required faculty fields.'
    if not data['building_id'].isdigit():
        return 'Choose a valid building.'
    if not valid_map_url(data['map_url']):
        return 'Map link must start with http:// or https://.'
    exists = get_db().execute('SELECT id FROM buildings WHERE id=?', (int(data['building_id']),)).fetchone()
    if not exists:
        return 'Choose a building that exists.'
    return None


@app.route('/creator/faculty/add', methods=['POST'])
@admin_required
def add_faculty():
    data = faculty_form_values()
    error = validate_faculty(data)
    if error:
        flash(error, 'danger')
    else:
        get_db().execute('''INSERT INTO faculty(full_name,department,designation,phone_number,profession,building_id,floor,cabin_number,map_url,last_updated)
            VALUES(?,?,?,?,?,?,?,?,?,?)''', (data['full_name'], data['department'], data['designation'], data['phone_number'],
            data['profession'], int(data['building_id']), data['floor'], data['cabin_number'], data['map_url'], now_text()))
        get_db().commit()
        flash('Faculty record added.', 'success')
    return redirect(url_for('admin_dashboard') + '#faculty')


@app.route('/creator/faculty/<int:faculty_id>/edit', methods=['POST'])
@admin_required
def edit_faculty(faculty_id):
    data = faculty_form_values()
    error = validate_faculty(data)
    if error:
        flash(error, 'danger')
    else:
        cur = get_db().execute('''UPDATE faculty SET full_name=?,department=?,designation=?,phone_number=?,profession=?,building_id=?,floor=?,cabin_number=?,map_url=?,last_updated=? WHERE id=?''',
            (data['full_name'], data['department'], data['designation'], data['phone_number'], data['profession'], int(data['building_id']),
             data['floor'], data['cabin_number'], data['map_url'], now_text(), faculty_id))
        get_db().commit()
        flash('Faculty record updated.' if cur.rowcount else 'Faculty record not found.', 'success' if cur.rowcount else 'danger')
    return redirect(url_for('admin_dashboard') + '#faculty')


@app.route('/creator/faculty/<int:faculty_id>/delete', methods=['POST'])
@admin_required
def delete_faculty(faculty_id):
    cur = get_db().execute('DELETE FROM faculty WHERE id=?', (faculty_id,))
    get_db().commit()
    flash('Faculty record deleted.' if cur.rowcount else 'Faculty record not found.', 'success' if cur.rowcount else 'danger')
    return redirect(url_for('admin_dashboard') + '#faculty')


@app.errorhandler(404)
def not_found(_error):
    return render_template('404.html'), 404


init_db()

if __name__ == '__main__':
    app.run(debug=True)
