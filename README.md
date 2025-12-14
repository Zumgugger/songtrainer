# Song Trainer - Practice Tracker

A modern, colorful web application to track your song practice progress for concerts.

## Features

- 🔐 **User Authentication**: Login/logout with session management and remember-me
- 👥 **Multi-user Support**: Each user has their own repertoires and songs
- 🛡️ **Admin Panel**: User management and progress tracking
- 🎵 Track songs with title, artist, priority, and practice goals
- ⭐ Master skills for each song (bassline, backing vocals, etc.)
- 📊 Visual progress bars for practice count and skill mastery
- 📈 Overall progress bar showing total skills mastered across all songs
- 🎯 Sort by: song order, priority, or last practiced
- 🔄 Drag-and-drop reordering (in Song Order view)
- 🚦 Click priority badge to toggle: mid → high → low → mid
- 🎧 Attach audio files (auto-link from folder or manual upload)
- 📄 Attach chart/sheet music files (auto-link from folder or manual upload)
- 🔄 Reset practice counter per song
- 🔍 Search songs by title
- 🎨 Modern, gamified UI with CSS customization
- 💾 SQLite database for persistent data storage

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
- Sort songs by: Song Order, Priority, or Last Practiced
- **Search** songs by title using the search box
- **Drag-and-drop** to reorder songs (when sorted by Song Order)
- Add/Edit/Delete songs
- **Attach audio**: Click 🎧➕ to upload or link audio files
- **Attach charts**: Click 📄➕ to upload or link sheet music/charts
- **View linked files**: Click 🎧 Open audio or 📄 Open chart links

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
- **Skills**: Select which skills to track for each song
- **Notes**: Practice notes or reminders

## Data Persistence

All data is stored in `songs.db` (SQLite database):
- **users**: User accounts with authentication
- **remember_tokens**: Remember-me session tokens
- **repertoires**: Song collections (scoped per user)
- **songs**: Song details and practice counts (scoped per user)
- **skills**: Available skills to master
- **song_skills**: Which skills are assigned to each song + mastery status
- **practice_sessions**: History of practice dates

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
5. Optional: Set up Nginx as a reverse proxy

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
├── app.py                  # Flask backend
├── database.py             # Database setup
├── requirements.txt        # Python dependencies
├── songs.db               # SQLite database (created on first run)
├── templates/
│   ├── index.html         # Main song list page
│   └── admin.html         # Skills management page
└── static/
    ├── css/
    │   └── style.css      # Styling
    └── js/
        └── app.js         # Frontend JavaScript
```

## Future Enhancements

- Mobile responsive design improvements
- Export/import song lists
- Auto-untoggle mastery if song is neglected
- Practice history charts
- Setlist builder
- Audio/video link integration

Enjoy your practice! 🎸🎤
