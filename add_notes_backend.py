import re

with open('app.py', 'r') as f:
    content = f.read()

# Add notes to GET endpoint
old_text = """            rep_dict['song_count'] = song_count['count']
            
            repertoires_list.append(rep_dict)"""

new_text = """            rep_dict['song_count'] = song_count['count']
            # Include notes from the repertoire
            rep_dict['notes'] = rep['notes'] or ''
            
            repertoires_list.append(rep_dict)"""

content = content.replace(old_text, new_text)

# Add notes to PUT endpoint
old_update = """        # Update name
        if 'name' in data:
            try:
                cursor.execute(
                    'UPDATE repertoires SET name = ? WHERE id = ?',
                    (data['name'], repertoire_id)
                )
            except sqlite3.IntegrityError:
                return jsonify({'error': 'Repertoire name already exists'}), 400
        
        # Update folder paths"""

new_update = """        # Update name
        if 'name' in data:
            try:
                cursor.execute(
                    'UPDATE repertoires SET name = ? WHERE id = ?',
                    (data['name'], repertoire_id)
                )
            except sqlite3.IntegrityError:
                return jsonify({'error': 'Repertoire name already exists'}), 400
        
        # Update notes
        if 'notes' in data:
            cursor.execute(
                'UPDATE repertoires SET notes = ? WHERE id = ?',
                (data['notes'] or None, repertoire_id)
            )
        
        # Update folder paths"""

content = content.replace(old_update, new_update)

with open('app.py', 'w') as f:
    f.write(content)

print("Backend updated successfully!")
