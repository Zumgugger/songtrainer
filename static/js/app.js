// Always use latest song object for editing
function editSongById(songId) {
    const song = songs.find(s => s.id === songId);
    if (song) editSong(song);
}
let songs = [];
let skills = [];
let repertoires = [];
let currentRepertoireId = null;
let currentSort = 'song_number';
let sortReverse = false;
let searchQuery = '';
let currentAttachSongId = null;
let currentAttachChartId = null;

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', () => {
    loadSkills();
    loadRepertoires();
    
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
        if (event.target == repertoireModal) {
            closeRepertoireModal();
        }
    };

    // Enable draggable behavior for song modal
    enableSongModalDrag();
    
    // Repertoire modal controls
    const repertoireModal = document.getElementById('repertoireModal');
    const addRepertoireBtn = document.getElementById('addRepertoireBtn');
    const closeRepertoireBtn = document.getElementById('closeRepertoireModal');
    const cancelRepertoireBtn = document.getElementById('cancelRepertoireBtn');
    
    addRepertoireBtn.onclick = () => openRepertoireModal();
    closeRepertoireBtn.onclick = () => closeRepertoireModal();
    cancelRepertoireBtn.onclick = () => closeRepertoireModal();
    
    // Form submission
    document.getElementById('songForm').addEventListener('submit', handleSongSubmit);
    document.getElementById('repertoireForm').addEventListener('submit', handleRepertoireSubmit);
    
    // Sort buttons
    document.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const newSort = e.target.dataset.sort;
            
            // Toggle reverse if clicking same button
            if (currentSort === newSort) {
                sortReverse = !sortReverse;
            } else {
                sortReverse = false;
                currentSort = newSort;
            }
            
            document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            // Add arrow indicator for reverse
            document.querySelectorAll('.sort-btn').forEach(b => {
                b.textContent = b.textContent.replace(' ↑', '').replace(' ↓', '');
            });
            if (sortReverse) {
                e.target.textContent += ' ↓';
            } else {
                e.target.textContent += ' ↑';
            }
            
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
        populateRepertoireSkillsCheckboxes();
    } catch (error) {
        console.error('Error loading skills:', error);
    }
}

async function loadRepertoires() {
    try {
        const response = await fetch('/api/repertoires');
        repertoires = await response.json();
        renderRepertoireTabs();
        
        // Select first repertoire by default
        if (repertoires.length > 0 && !currentRepertoireId) {
            currentRepertoireId = repertoires[0].id;
        }
        
        loadSongs();
    } catch (error) {
        console.error('Error loading repertoires:', error);
    }
}

async function loadSongs() {
    try {
        const url = currentRepertoireId 
            ? `/api/songs?repertoire_id=${currentRepertoireId}`
            : '/api/songs';
        const response = await fetch(url);
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
            body: JSON.stringify({ 
                ordered_ids: orderedIds,
                repertoire_id: currentRepertoireId
            })
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
        let comparison = 0;
        
        if (currentSort === 'song_number') {
            comparison = a.song_number - b.song_number;
        } else if (currentSort === 'priority') {
            const priorityOrder = { high: 0, mid: 1, low: 2 };
            comparison = priorityOrder[a.priority] - priorityOrder[b.priority];
        } else if (currentSort === 'last_practiced') {
            if (!a.last_practiced) return sortReverse ? -1 : 1;
            if (!b.last_practiced) return sortReverse ? 1 : -1;
            comparison = new Date(a.last_practiced) - new Date(b.last_practiced);
        } else if (currentSort === 'release_date') {
            if (!a.release_date) return sortReverse ? -1 : 1;
            if (!b.release_date) return sortReverse ? 1 : -1;
            comparison = a.release_date.localeCompare(b.release_date);
        }
        
        return sortReverse ? -comparison : comparison;
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
                    ${song.release_date ? `<p class="song-release-date">📅 ${song.release_date}</p>` : ''}
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
    
    // Only count skills from songs in the current repertoire
    const repertoireSongs = currentRepertoireId 
        ? songs.filter(s => s.repertoire_id === currentRepertoireId)
        : songs;
    
    repertoireSongs.forEach(song => {
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
        
        // Show repertoire name in progress text
        const currentRep = currentRepertoireId 
            ? repertoires.find(r => r.id === currentRepertoireId)
            : null;
        const repName = currentRep ? ` (${currentRep.name})` : '';
        progressText.textContent = `${masteredSkills} / ${totalSkills} skills mastered${repName}`;
    }
}

// ==================== MODAL FUNCTIONS ====================

function openModal(song = null) {
    const modal = document.getElementById('songModal');
    const form = document.getElementById('songForm');
    const title = document.getElementById('modalTitle');
    const modalContent = modal.querySelector('.modal-content');
    
    form.reset();
    
    if (song) {
        title.textContent = 'Edit Song';
        document.getElementById('songId').value = song.id;
        document.getElementById('title').value = song.title;
        document.getElementById('artist').value = song.artist;
        document.getElementById('songNumber').value = song.song_number;
        document.getElementById('priority').value = song.priority;
        document.getElementById('practiceTarget').value = song.practice_target;
        document.getElementById('releaseDate').value = song.release_date || '';
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
        
        // Get next song number for current repertoire
        const maxSongNumber = songs.length > 0 
            ? Math.max(...songs.map(s => s.song_number)) 
            : 0;
        document.getElementById('songNumber').value = maxSongNumber + 1;
        
        // Check default skills for current repertoire
        if (currentRepertoireId) {
            const currentRep = repertoires.find(r => r.id === currentRepertoireId);
            if (currentRep) {
                const defaultSkillIds = currentRep.default_skills.map(s => s.id);
                skills.forEach(skill => {
                    const checkbox = document.getElementById(`skill-${skill.id}`);
                    if (checkbox) {
                        checkbox.checked = defaultSkillIds.includes(skill.id);
                    }
                });
            }
        } else {
            // Check all skills by default if no repertoire selected
            skills.forEach(skill => {
                const checkbox = document.getElementById(`skill-${skill.id}`);
                if (checkbox) {
                    checkbox.checked = true;
                }
            });
        }
    }
    
    modal.style.display = 'block';
    // Ensure draggable styling active
    modalContent.classList.add('draggable-modal');
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
        repertoire_id: currentRepertoireId,
        priority: document.getElementById('priority').value,
        practice_target: parseInt(document.getElementById('practiceTarget').value),
        release_date: document.getElementById('releaseDate').value || null,
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
            loadRepertoires(); // Refresh song counts
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

function populateRepertoireSkillsCheckboxes() {
    const container = document.getElementById('repertoireSkillsCheckboxes');
    
    if (skills.length === 0) {
        container.innerHTML = '<p style="color: #7f8c8d;">No skills available.</p>';
        return;
    }
    
    container.innerHTML = skills.map(skill => `
        <label>
            <input type="checkbox" id="rep-skill-${skill.id}" value="${skill.id}">
            ${skill.name}
        </label>
    `).join('');
}

// ==================== DRAGGABLE MODAL ====================
function enableSongModalDrag() {
    const modalContent = document.querySelector('#songModal .modal-content');
    const handle = modalContent ? modalContent.querySelector('.modal-drag-handle') : null;
    if (!modalContent || !handle) return;
    let dragging = false;
    let startX = 0, startY = 0, origLeft = 0, origTop = 0;

    function onMouseMove(e) {
        if (!dragging) return;
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        modalContent.style.left = (origLeft + dx) + 'px';
        modalContent.style.top = (origTop + dy) + 'px';
    }

    function onMouseUp() {
        if (!dragging) return;
        dragging = false;
        modalContent.classList.remove('modal-moving');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }

    handle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        dragging = true;
        const rect = modalContent.getBoundingClientRect();
        startX = e.clientX;
        startY = e.clientY;
        origLeft = rect.left;
        origTop = rect.top;
        // Activate draggable style if not present
        modalContent.classList.add('draggable-modal');
        modalContent.classList.add('modal-moving');
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}

// ==================== REPERTOIRE FUNCTIONS ====================

function renderRepertoireTabs() {
    const tabsContainer = document.getElementById('repertoireTabs');
    
    if (repertoires.length === 0) {
        tabsContainer.innerHTML = '<p style="color: #7f8c8d;">No repertoires. Click "+ Repertoire" to create one.</p>';
        return;
    }
    
    tabsContainer.innerHTML = repertoires.map(rep => `
        <div class="tab ${rep.id === currentRepertoireId ? 'active' : ''}" 
             data-repid="${rep.id}" draggable="true">
            <span class="tab-name" onclick="switchRepertoire(${rep.id})">${rep.name}</span>
            <span class="tab-count" onclick="switchRepertoire(${rep.id})">${rep.song_count}</span>
            <button class="tab-edit-btn" onclick="event.stopPropagation(); editRepertoire(${rep.id})" title="Edit repertoire">✏️</button>
            <span class="drag-hint" style="cursor:grab; font-size:10px; color:#7f8c8d;">⇅</span>
        </div>
    `).join('');

    setupRepertoireDragAndDrop();
}

let draggedRepId = null;

function setupRepertoireDragAndDrop() {
    const tabsContainer = document.getElementById('repertoireTabs');
    const tabs = tabsContainer.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('dragstart', (e) => {
            draggedRepId = parseInt(tab.dataset.repid);
            e.dataTransfer.setData('text/plain', String(draggedRepId));
        });
        tab.addEventListener('dragover', (e) => {
            e.preventDefault();
        });
        tab.addEventListener('drop', (e) => {
            e.preventDefault();
            const targetId = parseInt(tab.dataset.repid);
            const fromId = parseInt(e.dataTransfer.getData('text/plain'));
            if (fromId === targetId) return;
            const fromIndex = repertoires.findIndex(r => r.id === fromId);
            const toIndex = repertoires.findIndex(r => r.id === targetId);
            if (fromIndex === -1 || toIndex === -1) return;
            const [moved] = repertoires.splice(fromIndex, 1);
            repertoires.splice(toIndex, 0, moved);
            persistRepertoireOrder();
        });
    });
}

async function persistRepertoireOrder() {
    renderRepertoireTabs(); // optimistic UI
    try {
        await fetch('/api/repertoires/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order: repertoires.map(r => r.id) })
        });
    } catch (err) {
        console.error('Failed to persist repertoire order', err);
        // reload from server to recover
        loadRepertoires();
    }
}

function switchRepertoire(repertoireId) {
    currentRepertoireId = repertoireId;
    renderRepertoireTabs();
    loadSongs();
}

function openRepertoireModal(repertoire = null) {
    const modal = document.getElementById('repertoireModal');
    const form = document.getElementById('repertoireForm');
    const title = document.getElementById('repertoireModalTitle');
    const deleteBtn = document.getElementById('deleteRepertoireBtn');
    
    form.reset();
    
    if (repertoire) {
        title.textContent = 'Edit Repertoire';
        document.getElementById('repertoireId').value = repertoire.id;
        document.getElementById('repertoireName').value = repertoire.name;
        
        // Check the default skills for this repertoire
        const defaultSkillIds = repertoire.default_skills.map(s => s.id);
        skills.forEach(skill => {
            const checkbox = document.getElementById(`rep-skill-${skill.id}`);
            if (checkbox) {
                checkbox.checked = defaultSkillIds.includes(skill.id);
            }
        });
        
        // Show delete button for existing repertoires
        if (deleteBtn) {
            deleteBtn.style.display = 'inline-block';
            deleteBtn.onclick = deleteRepertoire;
        }
    } else {
        title.textContent = 'Add Repertoire';
        document.getElementById('repertoireId').value = '';
        
        // Check all skills by default for new repertoires
        skills.forEach(skill => {
            const checkbox = document.getElementById(`rep-skill-${skill.id}`);
            if (checkbox) {
                checkbox.checked = true;
            }
        });
        
        // Hide delete button for new repertoires
        if (deleteBtn) {
            deleteBtn.style.display = 'none';
        }
    }
    
    modal.style.display = 'block';
}

function closeRepertoireModal() {
    document.getElementById('repertoireModal').style.display = 'none';
}

async function editRepertoire(repertoireId) {
    const repertoire = repertoires.find(r => r.id === repertoireId);
    if (repertoire) {
        openRepertoireModal(repertoire);
    }
}

async function handleRepertoireSubmit(e) {
    e.preventDefault();
    
    const repertoireId = document.getElementById('repertoireId').value;
    const isEdit = repertoireId !== '';
    
    const selectedSkillIds = skills
        .filter(skill => document.getElementById(`rep-skill-${skill.id}`).checked)
        .map(skill => skill.id);
    
    const data = {
        name: document.getElementById('repertoireName').value,
        skill_ids: selectedSkillIds
    };
    
    try {
        const url = isEdit ? `/api/repertoires/${repertoireId}` : '/api/repertoires';
        const method = isEdit ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            closeRepertoireModal();
            loadRepertoires();
        } else {
            const error = await response.json();
            alert(error.error || 'Error saving repertoire');
        }
    } catch (error) {
        console.error('Error saving repertoire:', error);
        alert('Error saving repertoire');
    }
}

async function deleteRepertoire() {
    const repertoireId = document.getElementById('repertoireId').value;
    if (!repertoireId) return;
    
    const repertoire = repertoires.find(r => r.id === parseInt(repertoireId));
    if (!repertoire) return;
    
    const confirmMsg = `Delete repertoire "${repertoire.name}"?\n\nThis will also delete all ${repertoire.song_count} song(s) in this repertoire.\n\nThis cannot be undone.`;
    
    if (!confirm(confirmMsg)) return;
    
    try {
        const response = await fetch(`/api/repertoires/${repertoireId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            closeRepertoireModal();
            // If we deleted the current repertoire, switch to first available
            if (currentRepertoireId === parseInt(repertoireId)) {
                currentRepertoireId = null;
            }
            loadRepertoires();
        } else {
            const error = await response.json();
            alert(error.error || 'Error deleting repertoire');
        }
    } catch (error) {
        console.error('Error deleting repertoire:', error);
        alert('Error deleting repertoire');
    }
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
