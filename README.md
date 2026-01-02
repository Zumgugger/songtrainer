# Song Trainer - Practice Tracker

**[🇩🇪 Deutsche Version / German Version](#deutsche-version)**

A modern, colorful web application to track your song practice progress for concerts and performances.

**Software by zumgugger** | [zumgugger.ch](https://zumgugger.ch)

---

## Summary

Song Trainer is a comprehensive practice management system for musicians, bands, and choirs. Track multiple repertoires, monitor skill mastery, attach audio and sheet music, and synchronize your practice data. Features include multi-user support, drag-and-drop reordering, automatic file syncing, and visual progress tracking with a gamified interface.

## Overview

Song Trainer helps musicians organize and practice their repertoires efficiently. Manage multiple song collections (repertoires), track practice progress with skill mastery, attach audio and sheet music, and sync your practice data across devices. Perfect for choirs, bands, and solo musicians preparing for performances.

## Features

### Authentication & User Management
- 🔐 **User Authentication**: Secure login/logout with session management
- 🔄 **Remember Me**: Optional persistent sessions across browser restarts
- 🔑 **Password Reset**: Self-service password reset functionality
- 👥 **Multi-User Support**: Each user has isolated repertoires and song data
- 🛡️ **Admin Panel**: Comprehensive user management and progress monitoring
- 🔒 **Role-Based Access**: Admin-only features with decorator-based authorization

### Song & Practice Management
- 🎵 **Song CRUD**: Create, read, update, and delete songs with rich metadata
- ⭐ **Skill Mastery System**: Track multiple skills per song (bassline, vocals, chords, etc.)
- 📊 **Practice Tracking**: Increment practice count with date-stamped sessions
- 🎯 **Practice Targets**: Set and track practice goals per song
- 📈 **Progress Visualization**: Visual progress bars for practice count and skill mastery
- 📊 **Overall Progress**: Real-time aggregated progress across all repertoire songs
- 🔄 **Practice Reset**: Reset practice counters while preserving session history
- 🚦 **Priority System**: Three-level priority (High 🔴 / Mid 🟡 / Low 🟢) with click-to-toggle
- 📅 **Release Date Tracking**: Organize songs by release date
- 📝 **Notes System**: Add practice notes and reminders to songs

### Organization & Sorting
- 🎯 **Multi-Criteria Sorting**: Sort by song order, name, priority, last practiced, release date, or skills mastered
- 📊 **Secondary Sort Persistence**: Previous sort criteria maintained as secondary sort for complex organization
- 💾 **Save Current Order**: Persist the current visual order to the database with one click
- 🔄 **Drag-and-Drop Reordering**: Intuitive reordering in Song Order view with live database updates
- 🔍 **Real-Time Search**: Filter songs by title with instant results
- 👁️ **Focus Mode**: Toggle detailed view on/off for distraction-free practice

### Media & File Management
- 🎧 **Audio Attachment**: Support for MP3, M4A, AAC, WAV, FLAC, OGG formats
- 📄 **Chart/Sheet Music**: Support for PDF, PNG, JPG, GIF, TXT, DOC, DOCX, ODT formats
- 📁 **Auto-Upload to Charts Folder**: Automatic copying to local `charts/` directory
- 🔗 **Portable Media Paths**: Relative paths ensure cross-platform compatibility
- 🎵 **MP3 Duration Extraction**: Automatic audio duration detection
- 🎛️ **Audio Player Integration**: In-browser audio playback with controls
- 📂 **File Browser**: Select files from filesystem for manual linking

### Repertoire Management
- 📑 **Multiple Repertoires**: Organize songs into collections (bands, choirs, projects)
- 👤 **User-Scoped Repertoires**: Each user maintains independent repertoire sets
- 🔄 **Folder Synchronization**: Automatic scanning of MP3 and chart folders to:
  - Create new songs from MP3 filenames
  - Link existing MP3s to matching songs
  - Link sheet music to songs
  - Copy external charts to local `charts/` folder for portability
- ↩️ **Undo Last Sync**: Full sync rollback with chart cleanup and path restoration
- 📊 **Sync Statistics**: Detailed reports on songs added, MP3s linked, charts migrated
- 📈 **Time Practiced Since**: Track total practice time from custom start dates
- 📄 **PDF Setlist Generation**: Export repertoire as formatted PDF setlist

### Admin Features
- 👥 **User Management**: Create, edit, delete user accounts
- 📊 **Cross-User Progress Monitoring**: View practice statistics for all users
- 🎯 **Skills Management**: Add, edit, delete custom skills (shared across all songs)
- 🔧 **System Administration**: Database integrity and user activity monitoring

### UI/UX
- 🎨 **Modern Gamified Interface**: Colorful, engaging design with CSS animations
- 📱 **Responsive Design**: Optimized for desktop and tablet use
- ⚡ **Real-Time Updates**: Instant UI feedback without page reloads
- ⌨️ **Keyboard Support**: Efficient navigation and shortcuts
- 🎭 **Visual Feedback**: Progress bars, badges, and status indicators
- 🌈 **Customizable Theming**: Easy CSS variable customization

### Technical Features
- 💾 **SQLite Database**: Reliable persistent storage with full ACID compliance
- 🏗️ **Modular Architecture**: Blueprint-based Flask application with clean separation
- 🔌 **RESTful API**: JSON API endpoints for all operations
- 🔄 **Session Management**: Secure server-side session handling
- 🛡️ **CSRF Protection**: Built-in security for form submissions
- 📁 **Cross-Platform Paths**: Intelligent Windows/WSL/Linux path handling
- 🚀 **Production Ready**: Gunicorn-compatible WSGI application

## Setup Instructions

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize the Database

```bash
python database.py
```

This will create `songs.db` with the following default skills:
- Knowing the song
- Playing the bassline
- Singing backing vocals while playing
- Knowing by heart

### 3. Run the Application

```bash
python app.py
```

The app will be available at: `http://localhost:5000`

### 4. First Login

On first run, a default admin user is created automatically:
- **Email**: `admin@example.com`
- **Password**: `admin123`

**⚠️ Important**: Change the password immediately after first login via the Admin page.

**Custom Admin Credentials**: Set environment variables before first run:
```bash
export ADMIN_EMAIL="your-email@example.com"
export ADMIN_PASSWORD="your-secure-password"
python app.py
```

## Usage

### Main Page (/)
- View all your songs with progress tracking
- **Overall Progress Bar**: See total skills mastered across all songs
- Click **Practice** to increment practice count
- Click **🔄 Reset Practice** to reset practice counter
- Click skill badges (☆/⭐) to toggle mastery (updates overall progress)
- Click priority badge (🔴🟡🟢) to cycle through priorities
- **Sort songs**: Choose from Song Order, Name, Priority, Last Practiced, Release Date, or Skills Mastered
- **Multi-level Sorting**: Secondary sort criteria persists when switching sorts
- **Save current order**: Click 💾 button next to 👁️ to make visual order permanent in database
- **Toggle focus mode**: Click 👁️ to hide/show song details
- **Search** songs by title using the search box
- **Drag-and-drop** to reorder songs (when sorted by Song Order)
- Add/Edit/Delete songs
- **Attach audio**: Click 🎧➕ to upload or link audio files (auto-copied to `uploads/`)
- **Attach charts**: Click 📄➕ to upload or link sheet music/charts (auto-copied to `charts/`)
- **View linked files**: Click 🎧 Open audio or 📄 Open chart links

### Repertoire Management
- Click "Manage Repertoires" to view all song collections
- **Sync Folders**: Link folders containing MP3s and charts to auto-import songs and attach media
- **Undo Last Sync**: Revert the last sync operation and restore original chart paths
- Sync statistics show what was imported and how many charts were migrated

### Admin Page (/admin)
- **User Management**: Create, edit, delete users (admin only)
- **User Progress**: View practice progress for all users
- **Skills Management**: Add custom skills
- Edit or delete existing skills
- Skills are shared across all songs

### Auto-Linking Audio and Charts

Link audio files from a folder:
```bash
python link_audio.py "/path/to/your/mp3 originals"
```

Link chart files from a folder:
```bash
python link_charts.py "/path/to/your/song charts"
```

The scripts intelligently match files to songs by title/artist. For charts, files containing "chord" or "chart" in the name are preferred when multiple matches exist.

### Google Drive Audio Integration

For production deployment without uploading large audio files, you can serve audio from Google Drive:

#### Step 1: Get File IDs from Google Drive

1. Go to [script.google.com](https://script.google.com)
2. Create a new project and paste this script:

```javascript
function listFilesInFolder() {
  var folderId = 'YOUR_FOLDER_ID_HERE';  // Get from Drive folder URL
  var folder = DriveApp.getFolderById(folderId);
  
  var output = [];
  var files = folder.getFiles();
  while (files.hasNext()) {
    var file = files.next();
    if (file.getName().toLowerCase().endsWith('.mp3')) {
      output.push([file.getName(), file.getId()]);
    }
  }
  
  Logger.log('Found ' + output.length + ' MP3 files');
  
  if (output.length > 0) {
    var ss = SpreadsheetApp.create('Drive File IDs');
    var sheet = ss.getActiveSheet();
    sheet.getRange(1, 1, output.length, 2).setValues(output);
    Logger.log('Created spreadsheet: ' + ss.getUrl());
  }
}
```

3. Replace `YOUR_FOLDER_ID_HERE` with your folder ID (from URL: `drive.google.com/drive/folders/FOLDER_ID`)
4. Run the function (select `listFilesInFolder` from dropdown, click ▶️)
5. Grant permissions when prompted
6. Find "Drive File IDs" spreadsheet in your Drive with filename/ID pairs

#### Step 2: Make Files Shareable

1. In Google Drive, select all audio files
2. Right-click → Share → Change to "Anyone with the link can view"

#### Step 3: Import IDs into Songtrainer

1. Open a repertoire in Songtrainer
2. Click "Import Drive IDs"
3. Copy/paste the data from the spreadsheet (tab-separated: `filename.mp3    file_id`)
4. Click Import

#### Step 4: Clear Local Audio Paths

After importing Drive IDs, clear local audio paths so Drive links are used:

```bash
docker exec -it songtrainer python -c "import sqlite3; conn = sqlite3.connect('/app/data/songs.db'); conn.execute(\"UPDATE songs SET audio_path = NULL WHERE drive_file_id IS NOT NULL AND drive_file_id != ''\"); conn.commit(); print('Updated', conn.total_changes, 'rows')"
```

Run this command after each batch import to activate Drive playback for those songs.

## Song Properties

- **Title & Artist**: Basic song info
- **Song Number**: Custom sort order
- **Priority**: 🔴 High / 🟡 Mid / 🟢 Low
- **Practice Target**: Set a goal (e.g., practice 10 times)
- **Release Date**: Track when song was released
- **Skills**: Select which skills to track for each song
- **Notes**: Practice notes or reminders
- **Audio Path**: Linked audio file (MP3, M4A, AAC, WAV, FLAC, OGG)
- **Chart Path**: Linked chart file (PDF, PNG, JPG, GIF, TXT, DOC, DOCX, ODT)

## Data Persistence

All data is stored in `songs.db` (SQLite database):
- **users**: User accounts with authentication
- **remember_tokens**: Remember-me session tokens
- **repertoires**: Song collections (scoped per user)
- **songs**: Song details and practice counts (scoped per user)
- **skills**: Available skills to master
- **song_skills**: Which skills are assigned to each song + mastery status
- **practice_sessions**: History of practice dates
- **sync_history**: Track sync operations for undo functionality

## Cross-Platform Path Support

The app intelligently handles file paths across different platforms:
- **Windows with WSL**: Converts Windows paths (e.g., `e:\Drive\...`) to WSL paths (`/mnt/e/Drive/...`)
- **Linux/Ubuntu**: Uses native Linux paths as-is (e.g., `/home/user/...`)
- **Charts Folder**: Always uses relative `charts/` path for portability

This ensures the app works seamlessly whether running locally on Windows/WSL or deployed on Ubuntu/Linux servers.

## Deployment to Ubuntu Server

1. Copy the entire project folder to your server
2. Install Python 3 and pip
3. Install dependencies: `pip install -r requirements.txt`
4. **Set admin credentials** (optional but recommended):
   ```bash
   export ADMIN_EMAIL="your-email@example.com"
   export ADMIN_PASSWORD="your-secure-password"
   ```
5. Initialize database: `python database.py`
6. Run with: `python app.py` (or use a production server like Gunicorn)
7. Optional: Set up Nginx as a reverse proxy

**⚠️ Production Security**: Always set custom `ADMIN_EMAIL` and `ADMIN_PASSWORD` environment variables before first deployment!

### Running with Gunicorn (Production)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Customization

Edit `static/css/style.css` to customize:
- Colors (change CSS variables in `:root`)
- Layout and spacing
- Fonts and animations
- Gamification elements

## Code Structure

The application follows a modular blueprint-based architecture for maintainability and scalability:

```
Songtrainer/
├── app.py                          # Application factory and initialization
├── database.py                     # Database schema and migrations
├── requirements.txt                # Python dependencies
│
├── blueprints/                     # Modular route handlers
│   ├── __init__.py
│   ├── auth.py                     # Authentication routes (457 lines)
│   │   ├── Login/logout, password reset
│   │   ├── User CRUD operations
│   │   └── Remember-me token management
│   ├── songs.py                    # Song management routes (604 lines)
│   │   ├── Song CRUD operations
│   │   ├── Practice tracking
│   │   ├── Skill toggling
│   │   └── Audio/chart serving
│   ├── repertoires.py              # Repertoire management (843 lines)
│   │   ├── Repertoire CRUD
│   │   ├── Folder synchronization
│   │   ├── Sync undo functionality
│   │   └── PDF setlist generation
│   ├── skills.py                   # Skills management (64 lines)
│   │   └── Skills CRUD operations
│   └── main.py                     # Main routes (16 lines)
│       └── Index and admin pages
│
├── utils/                          # Utility modules
│   ├── __init__.py
│   ├── decorators.py               # @login_required, @admin_required
│   ├── helpers.py                  # MP3 duration, time calculation
│   └── permissions.py              # User scope resolution, authorization
│
├── templates/                      # HTML templates
│   ├── index.html                  # Main song list interface
│   ├── admin.html                  # Admin panel
│   └── login.html                  # Login/password reset
│
├── static/                         # Static assets
│   ├── css/
│   │   └── style.css               # Gamified UI styling
│   └── js/
│       └── app.js                  # Frontend JavaScript (AJAX, drag-drop)
│
├── songs.db                        # SQLite database (created on first run)
├── charts/                         # Local charts folder (portable)
├── uploads/                        # User-uploaded audio files (git-ignored)
├── chats/                          # Chat session storage (git-ignored)
└── Database_backups/               # Database backups (git-ignored)
```

### Blueprint Architecture

**Total Routes**: 42 routes across 5 blueprints
**Total Functions**: 59 core functions

- **auth.py**: All authentication and user management
- **songs.py**: Song CRUD, practice tracking, media management
- **repertoires.py**: Repertoire operations, sync, PDF generation
- **skills.py**: Skills CRUD operations
- **main.py**: Index and admin page rendering

### Database Schema

```
users                   # User accounts
├── id, email, password_hash, is_admin, created_at

remember_tokens         # Persistent sessions
├── id, user_id, token, created_at

repertoires             # Song collections
├── id, name, user_id, mp3_folder, charts_folder, time_practiced_start

songs                   # Song data
├── id, repertoire_id, title, artist, song_number, priority
├── practice_count, practice_target, last_practiced, release_date
├── audio_path, chart_path, notes

skills                  # Available skills
├── id, name

song_skills             # Song-skill relationship
├── id, song_id, skill_id, is_mastered

practice_sessions       # Practice history
├── id, song_id, practiced_at

sync_history            # Sync operations for undo
├── id, repertoire_id, timestamp, action_type, details
```

## Project Structure

## Legacy Structure (Pre-Refactoring)

```
Songtrainer/
├── app.py                       # Flask backend
├── database.py                  # Database setup
├── requirements.txt             # Python dependencies
├── songs.db                     # SQLite database (created on first run)
├── charts/                      # Local charts folder (portable, copied from sync)
├── chats/                       # Local chat session storage (git-ignored)
├── Database_backups/            # Database backups (git-ignored)
├── templates/
│   ├── index.html              # Main song list page
│   ├── admin.html              # Skills management page
│   └── login.html              # Login page
├── static/
│   ├── css/
│   │   └── style.css           # Styling
│   └── js/
│       └── app.js              # Frontend JavaScript
└── uploads/                     # User-uploaded files (git-ignored)
```

## Future Enhancements

- Mobile responsive design improvements
- Export/import song lists
- Auto-untoggle mastery if song is neglected
- Practice history charts and statistics
- Setlist builder
- Video/audio streaming integration
- Real-time collaboration for group practice
- Mobile app companion

Enjoy your practice! 🎸🎤
---

## Deutsche Version

# Song Trainer - Übungs-Tracker

Ein modernes, farbenfrohes Webprogramm zur Verfolgung deines Übungsfortschritts für Konzerte und Auftritte.

**Software von zumgugger** | [zumgugger.ch](https://zumgugger.ch)

---

## Zusammenfassung

Song Trainer ist ein umfassendes Übungsverwaltungssystem für Musiker, Bands und Chöre. Verwalte mehrere Repertoires, überwache die Beherrschung von Fähigkeiten, füge Audio und Noten hinzu und synchronisiere deine Übungsdaten. Funktionen umfassen Multi-User-Support, Drag-and-Drop-Neuordnung, automatische Dateisynchronisation und visuelle Fortschrittsanzeige mit gamifizierter Benutzeroberfläche.

## Übersicht

Song Trainer hilft Musikern, ihre Repertoires effizient zu organisieren und zu üben. Verwalte mehrere Songsammlungen (Repertoires), verfolge den Übungsfortschritt mit Skill-Mastery, füge Audio und Noten hinzu und synchronisiere deine Übungsdaten über Geräte hinweg. Perfekt für Chöre, Bands und Solo-Musiker, die sich auf Auftritte vorbereiten.

## Funktionen

### Authentifizierung & Benutzerverwaltung
- 🔐 **Benutzer-Authentifizierung**: Sicheres Login/Logout mit Session-Management
- 🔄 **Angemeldet bleiben**: Optional dauerhafte Sitzungen über Browser-Neustarts hinweg
- 🔑 **Passwort zurücksetzen**: Self-Service Passwort-Zurücksetzung
- 👥 **Multi-User-Unterstützung**: Jeder Benutzer hat isolierte Repertoires und Songdaten
- 🛡️ **Admin-Panel**: Umfassende Benutzerverwaltung und Fortschrittsüberwachung
- 🔒 **Rollenbasierter Zugriff**: Admin-only Features mit Decorator-basierter Autorisierung

### Song- & Übungsverwaltung
- 🎵 **Song CRUD**: Erstellen, Lesen, Aktualisieren und Löschen von Songs mit reichhaltigen Metadaten
- ⭐ **Skill-Mastery-System**: Verfolge mehrere Fähigkeiten pro Song (Bassline, Vocals, Chords, etc.)
- 📊 **Übungs-Tracking**: Erhöhe den Übungszähler mit datumsstempelten Sessions
- 🎯 **Übungsziele**: Setze und verfolge Übungsziele pro Song
- 📈 **Fortschrittsvisualisierung**: Visuelle Fortschrittsbalken für Übungszähler und Skill-Mastery
- 📊 **Gesamtfortschritt**: Echtzeit-aggregierter Fortschritt über alle Repertoire-Songs
- 🔄 **Übung zurücksetzen**: Setze Übungszähler zurück bei Beibehaltung der Session-Historie
- 🚦 **Prioritätssystem**: Drei Prioritätsstufen (Hoch 🔴 / Mittel 🟡 / Niedrig 🟢) mit Klick-zum-Wechseln
- 📅 **Release-Datum-Tracking**: Organisiere Songs nach Veröffentlichungsdatum
- 📝 **Notizen-System**: Füge Übungsnotizen und Erinnerungen zu Songs hinzu

### Organisation & Sortierung
- 🎯 **Multi-Kriterien-Sortierung**: Sortiere nach Songreihenfolge, Name, Priorität, zuletzt geübt, Veröffentlichungsdatum oder beherrschten Skills
- 📊 **Sekundäre Sort-Persistenz**: Vorherige Sortierkriterien werden als sekundäre Sortierung für komplexe Organisation beibehalten
- 💾 **Aktuelle Reihenfolge speichern**: Speichere die aktuelle visuelle Reihenfolge in der Datenbank mit einem Klick
- 🔄 **Drag-and-Drop-Neuordnung**: Intuitive Neuordnung in der Song-Order-Ansicht mit Live-Datenbankaktualisierung
- 🔍 **Echtzeit-Suche**: Filtere Songs nach Titel mit sofortigen Ergebnissen
- 👁️ **Fokus-Modus**: Schalte detaillierte Ansicht ein/aus für ablenkungsfreies Üben

### Medien- & Dateiverwaltung
- 🎧 **Audio-Anhang**: Unterstützung für MP3, M4A, AAC, WAV, FLAC, OGG Formate
- 📄 **Noten/Akkordblätter**: Unterstützung für PDF, PNG, JPG, GIF, TXT, DOC, DOCX, ODT Formate
- 📁 **Auto-Upload in Charts-Ordner**: Automatisches Kopieren in lokales `charts/` Verzeichnis
- 🔗 **Portable Medienpfade**: Relative Pfade gewährleisten Plattformübergreifende Kompatibilität
- 🎵 **MP3-Dauer-Extraktion**: Automatische Audio-Dauer-Erkennung
- 🎛️ **Audio-Player-Integration**: Im-Browser Audio-Wiedergabe mit Steuerelementen
- 📂 **Dateibrowser**: Wähle Dateien aus dem Dateisystem für manuelles Verknüpfen

### Repertoire-Verwaltung
- 📑 **Mehrere Repertoires**: Organisiere Songs in Sammlungen (Bands, Chöre, Projekte)
- 👤 **Benutzerspezifische Repertoires**: Jeder Benutzer pflegt unabhängige Repertoire-Sets
- 🔄 **Ordner-Synchronisation**: Automatisches Scannen von MP3- und Noten-Ordnern um:
  - Neue Songs aus MP3-Dateinamen zu erstellen
  - Bestehende MP3s mit passenden Songs zu verknüpfen
  - Noten mit Songs zu verknüpfen
  - Externe Noten in lokalen `charts/` Ordner zu kopieren für Portabilität
- ↩️ **Letzte Sync rückgängig machen**: Vollständiges Sync-Rollback mit Chart-Cleanup und Pfad-Wiederherstellung
- 📊 **Sync-Statistiken**: Detaillierte Berichte über hinzugefügte Songs, verknüpfte MP3s, migrierte Charts
- 📈 **Zeit geübt seit**: Verfolge gesamte Übungszeit ab benutzerdefinierten Startdaten
- 📄 **PDF-Setlist-Generierung**: Exportiere Repertoire als formatierte PDF-Setlist

### Admin-Funktionen
- 👥 **Benutzerverwaltung**: Erstelle, bearbeite, lösche Benutzerkonten
- 📊 **Benutzerübergreifende Fortschrittsüberwachung**: Zeige Übungsstatistiken für alle Benutzer an
- 🎯 **Skills-Verwaltung**: Füge hinzu, bearbeite, lösche benutzerdefinierte Skills (geteilt über alle Songs)
- 🔧 **System-Administration**: Datenbank-Integrität und Benutzeraktivitätsüberwachung

### UI/UX
- 🎨 **Moderne gamifizierte Oberfläche**: Farbenfrohes, ansprechendes Design mit CSS-Animationen
- 📱 **Responsive Design**: Optimiert für Desktop und Tablet
- ⚡ **Echtzeit-Updates**: Sofortiges UI-Feedback ohne Seitenneuladungen
- ⌨️ **Tastatur-Unterstützung**: Effiziente Navigation und Shortcuts
- 🎭 **Visuelles Feedback**: Fortschrittsbalken, Badges und Statusanzeigen
- 🌈 **Anpassbares Theming**: Einfache CSS-Variable-Anpassung

### Technische Funktionen
- 💾 **SQLite-Datenbank**: Zuverlässiger persistenter Speicher mit voller ACID-Compliance
- 🏗️ **Modulare Architektur**: Blueprint-basierte Flask-Anwendung mit sauberer Trennung
- 🔌 **RESTful API**: JSON-API-Endpunkte für alle Operationen
- 🔄 **Session-Management**: Sicheres serverseitiges Session-Handling
- 🛡️ **CSRF-Schutz**: Eingebaute Sicherheit für Formularübermittlungen
- 📁 **Plattformübergreifende Pfade**: Intelligente Windows/WSL/Linux Pfadbehandlung
- 🚀 **Produktionsbereit**: Gunicorn-kompatible WSGI-Anwendung

## Setup-Anleitung

### 1. Python-Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 2. Datenbank initialisieren

```bash
python database.py
```

Dies erstellt `songs.db` mit den folgenden Standard-Skills:
- Das Lied kennen
- Die Bassline spielen
- Backing Vocals beim Spielen singen
- Auswendig können

### 3. Anwendung starten

```bash
python app.py
```

Die App ist verfügbar unter: `http://localhost:5000`

### 4. Erster Login

Beim ersten Start wird automatisch ein Standard-Admin-Benutzer erstellt:
- **E-Mail**: `admin@example.com`
- **Passwort**: `admin123`

**⚠️ Wichtig**: Ändere das Passwort sofort nach dem ersten Login über die Admin-Seite.

**Benutzerdefinierte Admin-Anmeldedaten**: Setze Umgebungsvariablen vor dem ersten Start:
```bash
export ADMIN_EMAIL="deine-email@example.com"
export ADMIN_PASSWORD="dein-sicheres-passwort"
python app.py
```

## Verwendung

### Hauptseite (/)
- Zeige alle deine Songs mit Fortschrittsverfolgung an
- **Gesamtfortschrittsbalken**: Siehe gesamte beherrschte Skills über alle Songs
- Klicke **Practice** um den Übungszähler zu erhöhen
- Klicke **🔄 Reset Practice** um den Übungszähler zurückzusetzen
- Klicke Skill-Badges (☆/⭐) um die Beherrschung zu togglen (aktualisiert Gesamtfortschritt)
- Klicke Prioritäts-Badge (🔴🟡🟢) um durch Prioritäten zu wechseln
- **Sortiere Songs**: Wähle aus Songreihenfolge, Name, Priorität, Zuletzt geübt, Veröffentlichungsdatum oder Beherrschte Skills
- **Multi-Level-Sortierung**: Sekundäre Sortierkriterien bleiben beim Wechseln der Sortierung erhalten
- **Aktuelle Reihenfolge speichern**: Klicke 💾 Button neben 👁️ um visuelle Reihenfolge permanent in Datenbank zu speichern
- **Fokus-Modus umschalten**: Klicke 👁️ um Song-Details zu verbergen/zeigen
- **Suche** Songs nach Titel über die Suchbox
- **Drag-and-Drop** um Songs neu zu ordnen (wenn nach Song Order sortiert)
- Hinzufügen/Bearbeiten/Löschen von Songs
- **Audio anhängen**: Klicke 🎧➕ um Audiodateien hochzuladen oder zu verlinken (automatisch kopiert nach `uploads/`)
- **Charts anhängen**: Klicke 📄➕ um Noten/Charts hochzuladen oder zu verlinken (automatisch kopiert nach `charts/`)
- **Verlinkte Dateien ansehen**: Klicke 🎧 Audio öffnen oder 📄 Chart-Links öffnen

### Repertoire-Verwaltung
- Klicke "Manage Repertoires" um alle Song-Sammlungen anzuzeigen
- **Ordner synchronisieren**: Verlinke Ordner mit MP3s und Charts um Songs automatisch zu importieren und Medien anzuhängen
- **Letzte Sync rückgängig machen**: Mache die letzte Sync-Operation rückgängig und stelle Original-Chart-Pfade wieder her
- Sync-Statistiken zeigen was importiert wurde und wie viele Charts migriert wurden

### Admin-Seite (/admin)
- **Benutzerverwaltung**: Erstelle, bearbeite, lösche Benutzer (nur Admin)
- **Benutzer-Fortschritt**: Zeige Übungsfortschritt für alle Benutzer an
- **Skills-Verwaltung**: Füge benutzerdefinierte Skills hinzu
- Bearbeite oder lösche bestehende Skills
- Skills werden über alle Songs geteilt

### Auto-Verknüpfung von Audio und Charts

Audio-Dateien aus einem Ordner verknüpfen:
```bash
python link_audio.py "/pfad/zu/deinen/mp3 originals"
```

Chart-Dateien aus einem Ordner verknüpfen:
```bash
python link_charts.py "/pfad/zu/deinen/song charts"
```

Die Skripte matchen Dateien intelligent mit Songs nach Titel/Künstler. Für Charts werden Dateien mit "chord" oder "chart" im Namen bevorzugt, wenn mehrere Matches existieren.

## Song-Eigenschaften

- **Titel & Künstler**: Basis-Songinformationen
- **Song-Nummer**: Benutzerdefinierte Sortierreihenfolge
- **Priorität**: 🔴 Hoch / 🟡 Mittel / 🟢 Niedrig
- **Übungsziel**: Setze ein Ziel (z.B. 10x üben)
- **Veröffentlichungsdatum**: Verfolge wann der Song veröffentlicht wurde
- **Skills**: Wähle welche Skills für jeden Song verfolgt werden sollen
- **Notizen**: Übungsnotizen oder Erinnerungen
- **Audio-Pfad**: Verlinkte Audiodatei (MP3, M4A, AAC, WAV, FLAC, OGG)
- **Chart-Pfad**: Verlinkte Chart-Datei (PDF, PNG, JPG, GIF, TXT, DOC, DOCX, ODT)

## Datenpersistenz

Alle Daten werden in `songs.db` (SQLite-Datenbank) gespeichert:
- **users**: Benutzerkonten mit Authentifizierung
- **remember_tokens**: Angemeldet-bleiben Session-Tokens
- **repertoires**: Song-Sammlungen (pro Benutzer)
- **songs**: Song-Details und Übungszähler (pro Benutzer)
- **skills**: Verfügbare Skills zum Beherrschen
- **song_skills**: Welche Skills jedem Song zugeordnet sind + Beherrschungs-Status
- **practice_sessions**: Historie der Übungsdaten
- **sync_history**: Verfolge Sync-Operationen für Rückgängig-Funktionalität

## Plattformübergreifende Pfad-Unterstützung

Die App handhabt Dateipfade intelligent über verschiedene Plattformen:
- **Windows mit WSL**: Konvertiert Windows-Pfade (z.B. `e:\Drive\...`) zu WSL-Pfaden (`/mnt/e/Drive/...`)
- **Linux/Ubuntu**: Verwendet native Linux-Pfade wie sie sind (z.B. `/home/user/...`)
- **Charts-Ordner**: Verwendet immer relativen `charts/` Pfad für Portabilität

Dies gewährleistet, dass die App nahtlos funktioniert, ob lokal auf Windows/WSL oder auf Ubuntu/Linux-Servern deployed.

## Deployment auf Ubuntu-Server

1. Kopiere den gesamten Projektordner auf deinen Server
2. Installiere Python 3 und pip
3. Installiere Abhängigkeiten: `pip install -r requirements.txt`
4. **Setze Admin-Anmeldedaten** (optional aber empfohlen):
   ```bash
   export ADMIN_EMAIL="deine-email@example.com"
   export ADMIN_PASSWORD="dein-sicheres-passwort"
   ```
5. Initialisiere Datenbank: `python database.py`
6. Starte mit: `python app.py` (oder verwende einen Produktions-Server wie Gunicorn)
7. Optional: Richte Nginx als Reverse-Proxy ein

**⚠️ Produktions-Sicherheit**: Setze immer benutzerdefinierte `ADMIN_EMAIL` und `ADMIN_PASSWORD` Umgebungsvariablen vor dem ersten Deployment!

### Mit Gunicorn starten (Produktion)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Anpassung

Bearbeite `static/css/style.css` um anzupassen:
- Farben (ändere CSS-Variablen in `:root`)
- Layout und Abstände
- Schriftarten und Animationen
- Gamification-Elemente

## Code-Struktur

Die Anwendung folgt einer modularen Blueprint-basierten Architektur für Wartbarkeit und Skalierbarkeit:

```
Songtrainer/
├── app.py                          # Application Factory und Initialisierung
├── database.py                     # Datenbankschema und Migrationen
├── requirements.txt                # Python-Abhängigkeiten
│
├── blueprints/                     # Modulare Route-Handler
│   ├── __init__.py
│   ├── auth.py                     # Authentifizierungs-Routen (457 Zeilen)
│   │   ├── Login/Logout, Passwort-Reset
│   │   ├── Benutzer CRUD-Operationen
│   │   └── Angemeldet-bleiben Token-Management
│   ├── songs.py                    # Song-Management-Routen (604 Zeilen)
│   │   ├── Song CRUD-Operationen
│   │   ├── Übungs-Tracking
│   │   ├── Skill-Toggling
│   │   └── Audio/Chart-Bereitstellung
│   ├── repertoires.py              # Repertoire-Management (843 Zeilen)
│   │   ├── Repertoire CRUD
│   │   ├── Ordner-Synchronisation
│   │   ├── Sync-Rückgängig-Funktionalität
│   │   └── PDF-Setlist-Generierung
│   ├── skills.py                   # Skills-Management (64 Zeilen)
│   │   └── Skills CRUD-Operationen
│   └── main.py                     # Haupt-Routen (16 Zeilen)
│       └── Index- und Admin-Seiten
│
├── utils/                          # Utility-Module
│   ├── __init__.py
│   ├── decorators.py               # @login_required, @admin_required
│   ├── helpers.py                  # MP3-Dauer, Zeit-Berechnung
│   └── permissions.py              # Benutzer-Scope-Auflösung, Autorisierung
│
├── templates/                      # HTML-Templates
│   ├── index.html                  # Haupt-Song-Liste-Interface
│   ├── admin.html                  # Admin-Panel
│   └── login.html                  # Login/Passwort-Reset
│
├── static/                         # Statische Assets
│   ├── css/
│   │   └── style.css               # Gamifiziertes UI-Styling
│   └── js/
│       └── app.js                  # Frontend-JavaScript (AJAX, Drag-Drop)
│
├── songs.db                        # SQLite-Datenbank (erstellt beim ersten Start)
├── charts/                         # Lokaler Charts-Ordner (portabel)
├── uploads/                        # Benutzer-hochgeladene Audiodateien (git-ignoriert)
├── chats/                          # Chat-Session-Speicher (git-ignoriert)
└── Database_backups/               # Datenbank-Backups (git-ignoriert)
```

### Blueprint-Architektur

**Gesamtzahl Routen**: 42 Routen über 5 Blueprints
**Gesamtzahl Funktionen**: 59 Kernfunktionen

- **auth.py**: Alle Authentifizierungs- und Benutzerverwaltung
- **songs.py**: Song CRUD, Übungs-Tracking, Medien-Management
- **repertoires.py**: Repertoire-Operationen, Sync, PDF-Generierung
- **skills.py**: Skills CRUD-Operationen
- **main.py**: Index- und Admin-Seiten-Rendering

### Datenbankschema

```
users                   # Benutzerkonten
├── id, email, password_hash, is_admin, created_at

remember_tokens         # Persistente Sessions
├── id, user_id, token, created_at

repertoires             # Song-Sammlungen
├── id, name, user_id, mp3_folder, charts_folder, time_practiced_start

songs                   # Song-Daten
├── id, repertoire_id, title, artist, song_number, priority
├── practice_count, practice_target, last_practiced, release_date
├── audio_path, chart_path, notes

skills                  # Verfügbare Skills
├── id, name

song_skills             # Song-Skill-Beziehung
├── id, song_id, skill_id, is_mastered

practice_sessions       # Übungs-Historie
├── id, song_id, practiced_at

sync_history            # Sync-Operationen für Rückgängig-Funktion
├── id, repertoire_id, timestamp, action_type, details
```

## Zukünftige Verbesserungen

- Mobile responsive Design-Verbesserungen
- Export/Import von Song-Listen
- Auto-Untoggle-Beherrschung wenn Song vernachlässigt wird
- Übungshistorie-Charts und Statistiken
- Setlist-Builder
- Video/Audio-Streaming-Integration
- Echtzeit-Kollaboration für Gruppen-Übung
- Mobile App Companion

Viel Spaß beim Üben! 🎸🎤

**Software von zumgugger** | [zumgugger.ch](https://zumgugger.ch)