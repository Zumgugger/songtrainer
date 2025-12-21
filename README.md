# Song Trainer - Practice Tracker

A modern, colorful web application to track your song practice progress for concerts.

## Overview

Song Trainer helps musicians organize and practice their repertoires efficiently. Manage multiple song collections (repertoires), track practice progress with skill mastery, attach audio and sheet music, and sync your practice data across devices. Perfect for choirs, bands, and solo musicians preparing for performances.

## Features

### Core Features
- 🔐 **User Authentication**: Login/logout with session management and remember-me
- 👥 **Multi-user Support**: Each user has their own repertoires and songs
- 🛡️ **Admin Panel**: User management, skill management, and progress tracking
- 🎵 Track songs with title, artist, priority, and practice goals
- ⭐ Master skills for each song (bassline, backing vocals, etc.)
- 📊 Visual progress bars for practice count and skill mastery
- 📈 Overall progress bar showing total skills mastered across all songs

### Organization & Sorting
- 🎯 **Multi-level Sorting**: Sort by song order, name, priority, last practiced, release date, or skills mastered
- 📊 **Secondary Sort**: When sorting by one criteria, previous sort criteria is maintained as secondary sort (e.g., sort by priority then by name = grouped by priority with alphabetical order within each group)
- 💾 **Save Current Order**: Click 💾 button to make the current visual order the permanent song order in the database
- 🔄 Drag-and-drop reordering (in Song Order view)
- 🚦 Click priority badge to toggle: mid → high → low → mid
- 🔍 Search songs by title
- 👁️ Focus mode to toggle detailed view on/off

### Audio & Charts Management
- 🎧 **Attach Audio Files**: Auto-link from folder or manual file selection (MP3, M4A, AAC, WAV, FLAC, OGG)
- 📄 **Attach Chart/Sheet Music**: Auto-link from folder or manual file selection (PDF, PNG, JPG, GIF, TXT, DOC, DOCX, ODT)
- 📁 **Auto-Upload to Charts Folder**: Charts are automatically copied to local `charts/` folder when attached
- 🔄 **Smart Chart Syncing**: When syncing a repertoire, checks for existing external chart paths and automatically copies them to the local `charts/` folder
- 🔗 **Portable Charts**: Charts stored in local `charts/` folder work on any platform (Windows/WSL, Linux, Ubuntu) and follow the app when deployed

### Repertoire Management
- 📑 **Multiple Repertoires**: Organize songs into different collections (Jutzi Trio, Zumgugger, Joy's Sake, Zeitreise, etc.)
- 🔄 **Sync Folders**: Automatically scan MP3 and sheet music folders to:
  - Create new songs from MP3 filenames
  - Link existing MP3s to songs
  - Link matching sheet music to songs
  - **Copy external charts to local `charts/` folder** for portability
- ↩️ **Undo Last Sync**: Revert the last sync operation, restore original chart paths, and clean up copied files
- 📊 Sync statistics showing songs added, MP3s linked, sheets linked, and charts migrated

### UI/UX
- 🎨 Modern, gamified UI with CSS customization
- 💾 SQLite database for persistent data storage
- 🖼️ Practice tracking interface with visual feedback
- ⚡ Responsive design with keyboard support

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

## Project Structure

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
