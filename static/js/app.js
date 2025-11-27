// Always use latest song object for editing
function editSongById(songId) {
    const song = songs.find(s => s.id === songId);
    if (song) editSong(song);
}
let songs = [];
let skills = [];
let currentSort = 'song_number';
let searchQuery = '';
let currentAttachSongId = null;
let currentAttachChartId = null;

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', () => {
    loadSkills();
    loadSongs();
    
    // Modal controls
    const modal = document.getElementById('songModal');
    const addBtn = document.getElementById('addSongBtn');
    const closeBtn = document.querySelector('.close');
    const cancelBtn = document.getElementById('cancelBtn');
    
    addBtn.onclick = () => openModal();
    closeBtn.onclick = () => closeModal();
    cancelBtn.onclick = () => closeModal();
    
    window.onclick = (event) => {
        if (event.target == modal) {
            closeModal();
        }
    };
    
    // Form submission
    document.getElementById('songForm').addEventListener('submit', handleSongSubmit);
    
    // Sort buttons
    document.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentSort = e.target.dataset.sort;
            renderSongs();
        });
    });

    // Search box
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        searchQuery = (e.target.value || '').trim().toLowerCase();
        renderSongs();
    });

    // Hidden audio file input
    const audioInput = document.getElementById('audioFileInput');
    audioInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file || !currentAttachSongId) return;
        try {
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch(`/api/songs/${currentAttachSongId}/audio`, {
                method: 'POST',
                body: formData
            });
            if (!res.ok) {
                const msg = await res.json().catch(() => ({}));
                alert(msg.error || 'Failed to upload audio');
            }
            await loadSongs();
        } catch (err) {
            console.error('Attach audio failed', err);
            alert('Attach audio failed');
        } finally {
            e.target.value = '';
            currentAttachSongId = null;
        }
    });

    // Hidden chart file input
    const chartInput = document.getElementById('chartFileInput');
    chartInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file || !currentAttachChartId) return;
        try {
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch(`/api/songs/${currentAttachChartId}/chart`, {
                method: 'POST',
                body: formData
            });
            if (!res.ok) {
                const msg = await res.json().catch(() => ({}));
                alert(msg.error || 'Failed to upload chart');
            }
            await loadSongs();
        } catch (err) {
            console.error('Attach chart failed', err);
            alert('Attach chart failed');
        } finally {
            e.target.value = '';
            currentAttachChartId = null;
        }
    });
});

// ==================== API CALLS ====================

async function loadSkills() {
    try {
        const response = await fetch('/api/skills');
        skills = await response.json();
        populateSkillsCheckboxes();
    } catch (error) {
        console.error('Error loading skills:', error);
    }
}

async function loadSongs() {
    try {
        const response = await fetch('/api/songs');
        songs = await response.json();
        renderSongs();
        updateOverallProgress();
    } catch (error) {
        console.error('Error loading songs:', error);
    }
}

async function practiceSong(songId) {
    try {
        const response = await fetch(`/api/songs/${songId}/practice`, {
            method: 'POST'
        });
        
        if (response.ok) {
            loadSongs();
        }
    } catch (error) {
        console.error('Error recording practice:', error);
    }
}

async function toggleSkill(songId, skillId) {
    try {
        const response = await fetch(`/api/songs/${songId}/skills/${skillId}/toggle`, {
            method: 'POST'
        });
        
        if (response.ok) {
            loadSongs();
        }
    } catch (error) {
        console.error('Error toggling skill:', error);
    }
}

async function deleteSong(songId, title) {
    if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;
    
    try {
        const response = await fetch(`/api/songs/${songId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadSongs();
        }
    } catch (error) {
        console.error('Error deleting song:', error);
    }
}

async function increaseTarget(songId) {
    try {
        const response = await fetch(`/api/songs/${songId}/target/increase`, {
            method: 'POST'
        });
        
        if (response.ok) {
            loadSongs();
        }
    } catch (error) {
        console.error('Error increasing target:', error);
    }
}

async function togglePriority(songId) {
    try {
        const response = await fetch(`/api/songs/${songId}/priority/toggle`, {
            method: 'POST'
        });
        
        if (response.ok) {
            loadSongs();
        }
    } catch (error) {
        console.error('Error toggling priority:', error);
    }
}

async function reorderSongsOnServer(orderedIds) {
    try {
        const response = await fetch('/api/songs/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ordered_ids: orderedIds })
        });
        if (response.ok) {
            // Reload list to reflect canonical numbering 1..N
            await loadSongs();
        } else {
            console.error('Failed to reorder songs');
        }
    } catch (err) {
        console.error('Error reordering songs:', err);
    }
}

// ==================== RENDERING ====================

function renderSongs() {
    const songsList = document.getElementById('songsList');
    
    if (songs.length === 0) {
        songsList.innerHTML = '<div class="empty-state"><h2>No songs yet!</h2><p>Click "Add Song" to get started.</p></div>';
        return;
    }
    
    // Filter by search query (title only)
    const filtered = songs.filter(s => !searchQuery || (s.title || '').toLowerCase().includes(searchQuery));

    // Sort songs
    const sortedSongs = [...filtered].sort((a, b) => {
        if (currentSort === 'song_number') {
            return a.song_number - b.song_number;
        } else if (currentSort === 'priority') {
            const priorityOrder = { high: 0, mid: 1, low: 2 };
            return priorityOrder[a.priority] - priorityOrder[b.priority];
        } else if (currentSort === 'last_practiced') {
            if (!a.last_practiced) return 1;
            if (!b.last_practiced) return -1;
            return new Date(a.last_practiced) - new Date(b.last_practiced);
        }
        return 0;
    });
    
    songsList.innerHTML = sortedSongs.map(song => createSongCard(song)).join('');
    setupDragAndDrop();
}

function createSongCard(song) {
    const priorityIcons = {
        high: '🔴',
        mid: '🟡',
        low: '🟢'
    };
    
    const lastPracticed = song.last_practiced 
        ? `Last practiced: ${formatDate(song.last_practiced)}`
        : 'Never practiced';
    
    const lastPracticedClass = song.last_practiced ? '' : 'never';
    
    // Get only skills that are assigned to this song
    const assignedSkills = song.skills.filter(skill => skill.is_mastered !== null);
    
    const skillsHTML = assignedSkills.length > 0 ? `
        <div class="skills-section">
            <h4>Skills (${assignedSkills.filter(s => s.is_mastered).length}/${assignedSkills.length} mastered):</h4>
            <div class="skills-grid">
                ${assignedSkills.map(skill => `
                    <div class="skill-item ${skill.is_mastered ? 'mastered' : ''}" 
                         onclick="toggleSkill(${song.id}, ${skill.id})">
                        <span class="skill-star">${skill.is_mastered ? '⭐' : '☆'}</span>
                        <span class="skill-name">${skill.name}</span>
                    </div>
                `).join('')}
            </div>
        </div>
    ` : '';
    
    const audioHTML = song.audio_path ? `
        <div class="song-audio">
            <a class="audio-link" href="/media/${song.id}" title="Open linked audio">
                🎧 Open audio
            </a>
        </div>
    ` : '';

    const chartHTML = song.chart_path ? `
        <div class="song-audio">
            <a class="audio-link" href="/chart/${song.id}" target="_blank" title="Open linked chart">
                📄 Open chart
            </a>
        </div>
    ` : '';

    const notesHTML = song.notes ? `
        <div class="song-notes">
            📝 ${song.notes}
        </div>
    ` : '';
    
    const hasTarget = (song.practice_target || 0) > 0;

    const practiceSection = hasTarget ? `
            <div class="practice-section">
                <div class="practice-button">
                    <button class="btn btn-success" onclick="practiceSong(${song.id})">
                        ✅ Practice
                    </button>
                </div>
                
                <div class="practice-progress">
                    <div class="progress-label">
                        <span>Practice Progress</span>
                        <span>
                            <strong>${song.practice_count}</strong> / ${song.practice_target}
                            <button class="btn-icon" onclick="increaseTarget(${song.id})" title="Add more practice rounds (resets progress bar)" style="margin-left: 8px;">⬆️</button>
                        </span>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar ${song.practice_progress >= 100 ? 'complete' : ''}" 
                             style="width: ${Math.min(song.practice_progress, 100)}%">
                            ${song.practice_progress >= 100 ? '🎉 Complete!' : Math.round(song.practice_progress) + '%'}
                        </div>
                    </div>
                </div>
            </div>
        ` : `
            <div class="practice-section">
                <div class="practice-button">
                    <button class="btn btn-success" onclick="practiceSong(${song.id})">
                        ✅ Practice
                    </button>
                </div>
                <div class="practice-progress">
                    <div class="progress-label">
                        <span>Practice Count</span>
                        <span><strong>${song.practice_count}</strong></span>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar" style="width: 0%">
                            Set a target to track
                        </div>
                    </div>
                </div>
            </div>
        `;

    return `
        <div class="song-card priority-${song.priority}" data-id="${song.id}">
            <div class="song-header">
                <div class="song-info">
                    <div class="song-title-row">
                        <div class="song-number" title="Order">${song.song_number}</div>
                        <h3 class="song-title">${song.title}</h3>
                        <span class="priority-badge" title="Click to change priority (${song.priority})" onclick="togglePriority(${song.id})">${priorityIcons[song.priority]}</span>
                        <span class="drag-handle" title="Drag to reorder">⠿</span>
                    </div>
                    <p class="song-artist">${song.artist}</p>
                    <p class="last-practiced ${lastPracticedClass}">${lastPracticed}</p>
                </div>
                <div class="song-actions">
                    <button class="btn-icon attach-btn" onclick="attachAudio(${song.id})" title="Attach audio">🎧➕</button>
                    ${song.audio_path ? `<button class="btn-icon" onclick="removeAudio(${song.id})" title="Remove audio link">🗑️🎧</button>` : ''}
                    <button class="btn-icon attach-btn" onclick="attachChart(${song.id})" title="Attach chart">📄➕</button>
                    ${song.chart_path ? `<button class="btn-icon" onclick="removeChart(${song.id})" title="Remove chart link">🗑️📄</button>` : ''}
                    <button class="btn-icon" onclick='editSongById(${song.id})' title="Edit">✏️</button>
                    <button class="btn-icon" onclick="deleteSong(${song.id}, '${song.title.replace(/'/g, "\\'")}');" title="Delete">🗑️</button>
                </div>
            </div>
            
            ${skillsHTML}
            ${audioHTML}
            ${chartHTML}
            
            ${practiceSection}
            
            ${notesHTML}
        </div>
    `;
}

// ==================== DRAG & DROP ====================

function setupDragAndDrop() {
    const container = document.getElementById('songsList');
    const cards = container.querySelectorAll('.song-card');
    
    // Only enable dragging in song order mode
    if (currentSort === 'song_number') {
        cards.forEach(card => {
            card.setAttribute('draggable', 'true');
            
            // Prevent drag on interactive elements
            card.querySelectorAll('button, a, .skill-item').forEach(el => {
                el.setAttribute('draggable', 'false');
                el.addEventListener('mousedown', (e) => e.stopPropagation());
            });
            
            card.addEventListener('dragstart', (e) => {
                // Only allow drag from drag handle or card background
                if (!e.target.closest('.drag-handle') && 
                    !e.target.classList.contains('song-card') &&
                    !e.target.closest('.song-info')) {
                    e.preventDefault();
                    return;
                }
                card.classList.add('dragging');
            });
            
            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
                // After drop, collect order and send to server
                const orderedIds = Array.from(container.querySelectorAll('.song-card'))
                    .map(el => parseInt(el.getAttribute('data-id')));
                reorderSongsOnServer(orderedIds);
            });
        });

        container.addEventListener('dragover', (e) => {
            e.preventDefault();
            const afterElement = getDragAfterElement(container, e.clientY);
            const dragging = document.querySelector('.dragging');
            if (!dragging) return;
            if (afterElement == null) {
                container.appendChild(dragging);
            } else {
                container.insertBefore(dragging, afterElement);
            }
        });
    } else {
        // Disable dragging in other sort modes
        cards.forEach(card => {
            card.removeAttribute('draggable');
        });
    }
}

function getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.song-card:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

// ==================== AUDIO ATTACH/REMOVE ====================

function attachAudio(songId) {
    currentAttachSongId = songId;
    const input = document.getElementById('audioFileInput');
    input.click();
}

async function removeAudio(songId) {
    if (!confirm('Remove audio link for this song?')) return;
    try {
        const res = await fetch(`/api/songs/${songId}/audio`, { method: 'DELETE' });
        if (!res.ok) {
            alert('Failed to remove audio link');
            return;
        }
        await loadSongs();
    } catch (err) {
        console.error('Remove audio failed', err);
        alert('Remove audio failed');
    }
}

function attachChart(songId) {
    currentAttachChartId = songId;
    const input = document.getElementById('chartFileInput');
    input.click();
}

async function removeChart(songId) {
    if (!confirm('Remove chart link for this song?')) return;
    try {
        const res = await fetch(`/api/songs/${songId}/chart`, { method: 'DELETE' });
        if (!res.ok) {
            alert('Failed to remove chart link');
            return;
        }
        await loadSongs();
    } catch (err) {
        console.error('Remove chart failed', err);
        alert('Remove chart failed');
    }
}

// ==================== OVERALL PROGRESS ====================

function updateOverallProgress() {
    let totalSkills = 0;
    let masteredSkills = 0;
    
    songs.forEach(song => {
        const assignedSkills = song.skills.filter(s => s.is_mastered !== null);
        totalSkills += assignedSkills.length;
        masteredSkills += assignedSkills.filter(s => s.is_mastered === 1).length;
    });
    
    const percentage = totalSkills > 0 ? Math.round((masteredSkills / totalSkills) * 100) : 0;
    
    const progressBar = document.getElementById('overallProgressBar');
    const progressText = document.getElementById('overallProgressText');
    
    if (progressBar && progressText) {
        progressBar.style.width = percentage + '%';
        progressBar.textContent = percentage + '%';
        progressBar.className = 'progress-bar' + (percentage >= 100 ? ' complete' : '');
        progressText.textContent = `${masteredSkills} / ${totalSkills} skills mastered`;
    }
}

// ==================== MODAL FUNCTIONS ====================

function openModal(song = null) {
    const modal = document.getElementById('songModal');
    const form = document.getElementById('songForm');
    const title = document.getElementById('modalTitle');
    
    form.reset();
    
    if (song) {
        title.textContent = 'Edit Song';
        document.getElementById('songId').value = song.id;
        document.getElementById('title').value = song.title;
        document.getElementById('artist').value = song.artist;
        document.getElementById('songNumber').value = song.song_number;
        document.getElementById('priority').value = song.priority;
        document.getElementById('practiceTarget').value = song.practice_target;
        document.getElementById('notes').value = song.notes || '';
        
        // Check the skills that are assigned to this song
        const assignedSkillIds = song.skills
            .filter(s => s.is_mastered !== null)
            .map(s => s.id);
        
        skills.forEach(skill => {
            const checkbox = document.getElementById(`skill-${skill.id}`);
            if (checkbox) {
                checkbox.checked = assignedSkillIds.includes(skill.id);
            }
        });
    } else {
        title.textContent = 'Add Song';
        document.getElementById('songId').value = '';
        
        // Get next song number
        const maxSongNumber = songs.length > 0 
            ? Math.max(...songs.map(s => s.song_number)) 
            : 0;
        document.getElementById('songNumber').value = maxSongNumber + 1;
        
        // Check all skills by default for new songs
        skills.forEach(skill => {
            const checkbox = document.getElementById(`skill-${skill.id}`);
            if (checkbox) {
                checkbox.checked = true;
            }
        });
    }
    
    modal.style.display = 'block';
}

function closeModal() {
    document.getElementById('songModal').style.display = 'none';
}

function editSong(song) {
    openModal(song);
}

async function handleSongSubmit(e) {
    e.preventDefault();
    
    const songId = document.getElementById('songId').value;
    const isEdit = songId !== '';
    
    const selectedSkillIds = skills
        .filter(skill => document.getElementById(`skill-${skill.id}`).checked)
        .map(skill => skill.id);
    
    const data = {
        title: document.getElementById('title').value,
        artist: document.getElementById('artist').value,
        song_number: parseInt(document.getElementById('songNumber').value),
        priority: document.getElementById('priority').value,
        practice_target: parseInt(document.getElementById('practiceTarget').value),
        notes: document.getElementById('notes').value,
        skill_ids: selectedSkillIds
    };
    
    try {
        const url = isEdit ? `/api/songs/${songId}` : '/api/songs';
        const method = isEdit ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            closeModal();
            loadSongs();
        } else {
            alert('Error saving song');
        }
    } catch (error) {
        console.error('Error saving song:', error);
        alert('Error saving song');
    }
}

function populateSkillsCheckboxes() {
    const container = document.getElementById('skillsCheckboxes');
    
    if (skills.length === 0) {
        container.innerHTML = '<p style="color: #7f8c8d;">No skills available. Go to Admin to add skills.</p>';
        return;
    }
    
    container.innerHTML = skills.map(skill => `
        <label>
            <input type="checkbox" id="skill-${skill.id}" value="${skill.id}">
            ${skill.name}
        </label>
    `).join('');
}

// ==================== UTILITIES ====================

function formatDate(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
        return 'Today';
    } else if (diffDays === 1) {
        return 'Yesterday';
    } else if (diffDays < 7) {
        return `${diffDays} days ago`;
    } else {
        return date.toLocaleDateString();
    }
}
