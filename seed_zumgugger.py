#!/usr/bin/env python3
"""
Seed Zumgugger repertoire with songs from the Zeitreise project
"""
import os
import re
from database import get_db
from datetime import datetime

# Song list with file paths
SONG_FILES = [
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2019 - für immer uf di - patent ochsner.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1900 - irish rover - (dubliners and pogues).mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1900 - whiskey in the jar - (the dubliners).mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1955 - rock around the clock - bill haley and the comets.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1957 - rock and roll music - chuck berry.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1957 - tutti frutti - little richard.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1957 -jailhouse rock - elvis presley.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1958 - johnny b goode - chuck berry.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1961 - can't help falling in love - elvis presley.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1963 - lucky lips - cliff richards.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1963 - surfin usa - beach boys.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1965 - help - beatles.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1967 - little wing - jimi hendrix.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1967 - the letter - the box tops.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1967 - to love somebody - bee gees.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1968 - born to be wild - steppenwolf.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1968 - hey jude - beatles.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1969 - come together - beatles -2ht.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1970 - let it be - beatles.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1971 - aint no sunshine - bill withers.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1973 - knocking on heaven's door - bob dylan.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1976 - hotel california - eagles.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1977 - don't stop - fleetwood mac.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1977 - dust in the wind - kansas.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1977 - i was made for loving you - kiss.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1977 - rocking all over the world - status quo.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1977 - staying alive - bee gees.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1977 - we will rock you - queen.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1979 - dont bring me down - electric light orchestra.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1979 - hot stuff - donna summer.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1979 - whatever you want - status quo.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1980 - breaking the law - judas priest.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1981 - dont stop believin - journey.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1982 - africa - toto.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1982 - eye of the tiger - survivor -3ht.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1982 - here i go again - whitesnake.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1982 - purple rain - prince.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1983 - i'm still standing - elton john.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1983 - louenesee - span.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1983 - rebell yell - billy idol.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1983 - sharp dressed man - zz top.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1984 - i want to know what love is - foreigner -1HT.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1984 - it's only love - bryan adams.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1984 - runaway - bon jovi.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1984 - streams of whiskey - poguges.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1984 - summer of 69 - bryan adams.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1985 - a pair of brown eyes - pogues.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1985 - alperose - polo hofer.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1985 - dirty old town - pogues.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1985 - rock the night - europe.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1985 - take on me - a-ha.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1985 - walk of life - dire straits.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1986 - livin on a prayer - bon jovi.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1986 - the final countdown - europe -2HT.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1986 - wanted dead or alive - bon jovi.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1986 - you give love a bad name - bon jovi.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1987 - alone - heart.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1987 - paradise city - guns n roses.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1987 - rock you like a hurricane - scorpions.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1988 - summer 68 - polo hofer.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1988 - the look - roxette.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1989 - poison - alice cooper.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1989 - rocking in th free world - neil young.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1990 - more than words - extreme  +1ht.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1990 - still got the blues - gary moore.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1990 - thunderstruck - acdc.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1990 - wind of change - scorpions.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1991 - scharlachrot - patent ochsner.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1991 - show must go on - queen.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1992 - bard's song - blind guardian.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1992 - nothing else matters - metallica.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1992 - tears in heaven - eric clapton.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1994 - basket case - green day.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1994 - i schänke dir mis härz - züri west.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1994 - kiss from a rose - seal.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1994 - sleeping in my car - roxette.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1995 - wonderwall - oasis.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1997 - angles - robbie williams.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1997 - wnuss vo bümpliz - patent ochsner.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1998 - I dont want to miss a thing - aerosmith.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1999 - i want it that way - backstreet boys.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1999 - livin la vida loca - ricky martin.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\1999 - sex bomb - tom jones.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2000 - bye bye bye - nsync.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2000 - devil's dance floor - flogging molly.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2001 - baila - zuchero.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2001 - how you remind me - nickelback -1ht.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2002 - ein kompliment - sportfreunde stiller.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2002 - feel -robbie williams.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2002 - heimweh -plüsch.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2003 - trybguet - patent ochsner.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2004 - fingt z glück eim - züri west.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2006 - hard rock hallelujah - lordi  +2ht.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2008 - dance with somebody - mando diao.mp3.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2009 - marry me - train.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2011 - sleep - allen stone.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2011 - tshirt - grauhouz.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2012 - let her go - passenger.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2012 - tage wie diese - die toten hosen.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2012 - troublemaker - olly murs.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2013 - applaus applaus  - sportfreunde stiller.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2013 - cheating - john newman.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2013 - counting stars -one republic -2ht.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2014 - auf uns - andreas bourani.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2014 - photograph - ed sheeran.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2015 - one call away - charlie puth -1.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2016 -  theres nothing holding me back - shawn mendes.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2016 - chöre - mark forster.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2016 - magnetised - tom odell.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2017 - perfect - ed sheeran.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2017 - shape of you - ed sheeran.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2018 - shallow - lady gaga.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2019 -  senorita - shawn mendes camila caballo.mp3",
    "e:\\Drive\\Music Sync\\Projekte\\Zeitreise\\Lieder mp3\\2019 - blinding lights - the weekend.mp3",
]

def parse_filename(filename):
    """Extract year, title, and artist from filename"""
    # Handle both Windows and Unix paths - extract just the filename
    if '\\' in filename:
        basename = filename.split('\\')[-1]
    else:
        basename = os.path.basename(filename)
    
    # Remove .mp3 extension
    basename = basename.replace('.mp3', '').replace('.mp3', '')  # Handle double extension
    
    # Remove any annotation suffixes like -2ht, +1HT, -1, etc.
    basename = re.sub(r'\s*[-+]\d*[hH]?[tT]?\s*$', '', basename)
    basename = re.sub(r'\s+-\d+\s*$', '', basename)
    
    # Pattern: YEAR - TITLE - ARTIST
    # Split by ' - ' to get parts
    parts = basename.split(' - ')
    
    if len(parts) >= 3:
        year = parts[0].strip()
        title = parts[1].strip()
        artist = ' - '.join(parts[2:]).strip()  # In case artist name contains ' - '
        
        # Clean up parentheses
        title = title.replace('(', '').replace(')', '')
        artist = artist.replace('(', '').replace(')', '')
        
        # Capitalize properly
        title = title.title()
        artist = artist.title()
        
        # Verify year is actually a 4-digit number
        if re.match(r'^\d{4}$', year):
            return year, title, artist
    
    return None, None, None

def main():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Get Zumgugger repertoire ID
        rep = cursor.execute("SELECT id FROM repertoires WHERE name = 'Zumgugger'").fetchone()
        if not rep:
            print("Error: Zumgugger repertoire not found. Please create it first.")
            return
        
        repertoire_id = rep['id']
        
        # Get default skills for this repertoire
        default_skills = cursor.execute('''
            SELECT skill_id FROM repertoire_skills WHERE repertoire_id = ?
        ''', (repertoire_id,)).fetchall()
        default_skill_ids = [row['skill_id'] for row in default_skills]
        
        # Get current max song_number for this repertoire
        max_num = cursor.execute(
            'SELECT COALESCE(MAX(song_number), 0) as max FROM songs WHERE repertoire_id = ?',
            (repertoire_id,)
        ).fetchone()
        current_number = max_num['max']
        
        added = 0
        skipped = 0
        
        for song_file in SONG_FILES:
            year, title, artist = parse_filename(song_file)
            
            if not title or not artist:
                print(f"⚠️  Could not parse: {os.path.basename(song_file)}")
                skipped += 1
                continue
            
            # Check if song already exists (by title + artist)
            existing = cursor.execute(
                'SELECT id FROM songs WHERE LOWER(title) = LOWER(?) AND LOWER(artist) = LOWER(?) AND repertoire_id = ?',
                (title, artist, repertoire_id)
            ).fetchone()
            
            if existing:
                print(f"⏭️  Skipping duplicate: {title} - {artist}")
                skipped += 1
                continue
            
            current_number += 1
            
            # Insert song
            cursor.execute('''
                INSERT INTO songs (title, artist, song_number, repertoire_id, priority, practice_target, 
                                   date_added, release_date, audio_path, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title,
                artist,
                current_number,
                repertoire_id,
                'mid',
                5,
                datetime.now().isoformat(),
                year,
                song_file,  # Store full path for audio
                ''
            ))
            
            song_id = cursor.lastrowid
            
            # Assign default skills
            for skill_id in default_skill_ids:
                cursor.execute('''
                    INSERT INTO song_skills (song_id, skill_id, is_mastered)
                    VALUES (?, ?, 0)
                ''', (song_id, skill_id))
            
            print(f"✅ Added: {title} - {artist} ({year})")
            added += 1
        
        print(f"\n🎵 Summary: {added} songs added, {skipped} skipped")

if __name__ == '__main__':
    main()
