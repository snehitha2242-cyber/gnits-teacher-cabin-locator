# GNITS Teacher Cabin Locator

A beginner-friendly Flask + SQLite web app for a college project. Users can sign in as a GNITS student (name + roll number) or visitor (name + email), search buildings and faculty cabins, and open a saved map link. The protected Creator dashboard supports CRUD for faculty and buildings and displays registered users.

## Important assumptions
- This project uses **SQLite** rather than MySQL to make the first local demo easy to run without installing a database server. It is a relational database and demonstrates primary keys, foreign keys, SELECT, INSERT, UPDATE, and DELETE. It can be migrated to MySQL later if your course requires it.
- Student and visitor sign-in is identity capture for a classroom demo, **not verified college authentication**. A name and roll number/email alone do not prove identity. Do not use this login for sensitive data without college-approved authentication.
- The database starts with no real faculty/building records. The Creator must enter verified GNITS information and map links. Do not guess room numbers or publish private phone numbers.
- Map buttons open saved Google Maps or other HTTP(S) URLs; there is no live Maps API or indoor-position tracking.
- Teacher availability is not tracked.

## Requirements
- Python 3.10 or newer
- A web browser
- Internet is only needed once to install Flask (unless already installed)

## Run on Windows
1. Extract the ZIP folder.
2. Open Command Prompt or the VS Code terminal in the extracted `teacher_cabin_locator` folder.
3. Create a virtual environment:
   ```bat
   py -m venv .venv
   ```
4. Activate it:
   ```bat
   .venv\Scripts\activate
   ```
5. Install Flask:
   ```bat
   pip install -r requirements.txt
   ```
6. Start the website:
   ```bat
   python app.py
   ```
7. Open `http://127.0.0.1:5000` in your browser.

On macOS/Linux, use `python3 -m venv .venv`, `source .venv/bin/activate`, and `python3 app.py`.

## Creator login for local demo
- Username: `creator`
- Password: `GNITSdemo123!`

This demo password is stored as a **hash**, not plain text. Before any shared/hosted use, set environment variables `ADMIN_USERNAME`, `ADMIN_PASSWORD`, and `SECRET_KEY` before the first run, and do not use the demo credentials. The initial admin is created when the database is first initialized; changing environment variables after that will not change an existing admin record. Delete the local database file only if you want to reset the entire demo database.

## First-time setup
1. Open the site and choose **Creator / Admin login**.
2. Open **Buildings** and add the verified building names and campus location descriptions. Add a map link only if you have checked it.
3. Open **Faculty records** and add the faculty name, department, designation, building, floor, cabin/room number, and any approved contact information.
4. Sign out and test the user search as a student or visitor.

## Database tables
- `users`: student/visitor login records (roll number or email is unique where supplied).
- `admins`: administrator username, password hash, and role.
- `buildings`: building name, location description, optional map URL, last updated.
- `faculty`: faculty profile and cabin details; `building_id` references `buildings.id`.

## Suggested demonstration
1. Sign in as a visitor or student.
2. Search for a partial faculty name, and try a department filter.
3. Open a faculty result and show its building, floor, room, and map link.
4. Search the building directory.
5. Sign in as Creator and add a demo building, then add a demo faculty record assigned to it.
6. Edit the faculty room number, sign out, and search for that faculty.
7. Return to Creator and delete the demo faculty record, then delete the unused demo building.
8. Explain that the database uses primary keys, a foreign key, and CRUD operations.

## Security and deployment notes
This is a local student-project starter, not a production authentication system. Use HTTPS, a strong secret key, proper college identity verification, CSRF protection, rate limiting, backups, and deployment-specific security settings before hosting publicly. Debug mode is enabled only for local development; turn it off for deployment. Only add approved faculty information.
