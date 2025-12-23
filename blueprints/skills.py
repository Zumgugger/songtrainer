"""Skills blueprint for CRUD operations on skills."""

from flask import Blueprint, request, jsonify
from database import get_db
from utils.decorators import login_required, admin_required
import sqlite3

skills = Blueprint('skills', __name__)


@skills.route('/api/skills', methods=['GET'])
@login_required
def get_skills():
    """Get all skills"""
    with get_db() as conn:
        cursor = conn.cursor()
        skills_data = cursor.execute('SELECT * FROM skills ORDER BY id').fetchall()

        return jsonify([dict(skill) for skill in skills_data])


@skills.route('/api/skills', methods=['POST'])
@admin_required
def create_skill():
    """Create a new skill"""
    data = request.json or {}

    with get_db() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute('INSERT INTO skills (name) VALUES (?)', (data['name'],))
            skill_id = cursor.lastrowid

            return jsonify({'id': skill_id, 'message': 'Skill created successfully'}), 201
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Skill already exists'}), 400


@skills.route('/api/skills/<int:skill_id>', methods=['PUT'])
@admin_required
def update_skill(skill_id):
    """Update a skill"""
    data = request.json or {}

    with get_db() as conn:
        cursor = conn.cursor()

        try:
            cursor.execute('UPDATE skills SET name = ? WHERE id = ?', (data['name'], skill_id))
            return jsonify({'message': 'Skill updated successfully'})
        except sqlite3.IntegrityError:
            return jsonify({'error': 'Skill name already exists'}), 400


@skills.route('/api/skills/<int:skill_id>', methods=['DELETE'])
@admin_required
def delete_skill(skill_id):
    """Delete a skill"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM skills WHERE id = ?', (skill_id,))

        return jsonify({'message': 'Skill deleted successfully'})
