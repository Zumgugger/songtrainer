from database import get_db, init_db
from datetime import datetime

RAW_SONGS = [
    "Ain’t No Sunshine – Bill Withers",
    "All My Loving – Beatles",
    "All Of Me – Frank Sinatra",
    "Alpenflug – Mani Matter (Version Züri West & S. Eicher)",
    "Alperose – Polo Hofer",
    "Another One Bites The Dust – Queen",
    "Beat It – Michael Jackson",
    "Black Magic Woman – Santana",
    "Black Or White – Michael Jackson",
    "California Dreamin' – The Mamas And The Papas",
    "Champs-Elysées – Joe Dassin",
    "Cocaine – Eric Clapton",
    "Country Roads – John Denver",
    "Crazy Little Thing Called Love – Queen",
    "Don’t Worry Be Happy – Bobby McFerrin",
    "D’Rosmarie Und I – Rumpelstilz",
    "Echo – Züri West",
    "Es Het Einisch Eine Gseit – Ruedi Krebs",
    "Eye Of The Tiger – Survivor",
    "Fingt ds Glück Eim? – Züri West",
    "Für Immer Uf Di – Patent Ochsner",
    "Giggerig – Polo Hofer",
    "Güggu – Züri West",
    "Hemmige – Mani Matter (Version Stephan Eicher)",
    "Hey Jude – Beatles",
    "Highway To Hell – AC/DC",
    "Hotel California – Eagles",
    "House Of The Rising Sun – Animals",
    "I Got A Woman – Ray Charles",
    "I Ha Di Gärn Gha – Züri West",
    "I'm Walking – Fats Domino",
    "Johnny B. Goode – Chuck Berry",
    "Kiosk – Rumpelstilz",
    "Kiss – Prince",
    "Knocking On Heaven's Door – Bob Dylan",
    "Lay Down Sally – Eric Clapton",
    "Let It Be – Beatles",
    "Little Wing – Jimi Hendrix",
    "Long Train Running – Doobie Brothers",
    "Louenesee – Span",
    "Mack The Knife – Kurt Weill",
    "Master Blaster – Stevie Wonder",
    "Members Only – Philipp Fankhauser",
    "Mercy, Mercy, Mercy – Cannonball Adderley",
    "Money For Nothing – Dire Straits",
    "Mustang Sally – The Commitments",
    "No Woman No Cry – Bob Marley",
    "Oye Como Va – Santana",
    "Play That Funky Music – Wild Cherry",
    "Prinz – Züri West",
    "Proud Mary – Creedence Clearwater Revival (Turner-Version)",
    "Rote Wy – Rumpelstilz",
    "Scharlachrot – Patent Ochsner",
    "Smoke On The Water – Deep Purple",
    "Stets I Truure – Rumpelstilz",
    "Sultans Of Swing – Dire Straits",
    "Summertime – George Gershwin",
    "Sweet Home Chicago – Blues Brothers",
    "Teddybär – Rumpelstilz",
    "The Blues Is Alright – Gary Moore",
    "Three Little Birds – Bob Marley",
    "The Look – Roxette",
    "Trybguet – Patent Ochsner",
    "Uf Däm Länge Wäg – Rumpelstilz",
    "Unchain My Heart – Ray Charles (Joe Cocker)",
    "Waitin’ On A Sunny Day – Bruce Springsteen",
    "What A Wonderful World – Louis Armstrong",
    "Wyssebühl – (Artist not specified)",
    "W. Nuss Vo Bümpliz – Patent Ochsner",
    "(You Look) Wonderful Tonight – Eric Clapton",
    "You Shook Me All Night Long – AC/DC",
]

SEPARATOR = " – "  # en dash with spaces

DEFAULT_PRIORITY = "mid"
DEFAULT_TARGET = 5  # gives progress bar something to show


def parse_line(line: str):
    if SEPARATOR in line:
        title, artist = line.split(SEPARATOR, 1)
    else:
        # fallback if dash variant differs
        parts = line.split(" - ", 1)
        if len(parts) == 2:
            title, artist = parts
        else:
            title, artist = line, "Unknown"
    title = title.strip()
    artist = artist.strip()
    if artist == "(Artist not specified)":
        artist = "Unknown"
    return title, artist


def seed():
    init_db()
    with get_db() as conn:
        cur = conn.cursor()
        # Get all skills to assign them to each song by default
        skills = cur.execute("SELECT id, name FROM skills ORDER BY id").fetchall()

        # Determine next song_number start
        last_number = cur.execute("SELECT MAX(song_number) as maxnum FROM songs").fetchone()[
            "maxnum"
        ]
        next_number = (last_number or 0) + 1

        added = 0
        for idx, line in enumerate(RAW_SONGS, start=next_number):
            title, artist = parse_line(line)

            # Skip if already exists (by title+artist)
            existing = cur.execute(
                "SELECT id FROM songs WHERE title = ? AND artist = ?",
                (title, artist),
            ).fetchone()
            if existing:
                continue

            cur.execute(
                """
                INSERT INTO songs (title, artist, song_number, priority, practice_target, date_added, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    artist,
                    idx,
                    DEFAULT_PRIORITY,
                    DEFAULT_TARGET,
                    datetime.now().isoformat(),
                    "",
                ),
            )
            song_id = cur.lastrowid

            # Assign all available skills as trackable (unmastered)
            for sk in skills:
                cur.execute(
                    "INSERT OR IGNORE INTO song_skills (song_id, skill_id, is_mastered) VALUES (?, ?, 0)",
                    (song_id, sk["id"]),
                )
            added += 1

        print(f"Seeding complete. Added {added} new songs.")


if __name__ == "__main__":
    seed()
