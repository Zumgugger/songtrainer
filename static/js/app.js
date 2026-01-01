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
let sortHistory = []; // Stack of previous sorts for multi-level sorting
let searchQuery = '';
let currentAttachSongId = null;
let currentAttachChartId = null;
let focusMode = false;
let currentUser = null;

// Reorder lock: prevent re-sorting/filtering after quick actions (e.g., toggling a skill)
let reorderLocked = false;
let lastRenderedSongIds = [];

function lockReordering() {
    reorderLocked = true;
}

function unlockReordering() {
    reorderLocked = false;
    lastRenderedSongIds = [];
}

// Redirect to login on 401 for any fetch
const originalFetch = window.fetch;
window.fetch = async (...args) => {
    const res = await originalFetch(...args);
    if (res.status === 401) {
        window.location = '/login?next=' + encodeURIComponent(window.location.pathname);
        throw new Error('Unauthorized');
    }
    return res;
};

async function loadCurrentUser() {
    try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        currentUser = data.user;
        const emailEl = document.getElementById('userEmail');
        if (emailEl && currentUser) {
            emailEl.textContent = currentUser.email;
        }
        const adminLink = document.getElementById('adminLink');
        if (adminLink) {
            adminLink.style.display = currentUser && currentUser.role === 'admin' ? 'inline-block' : 'none';
        }
    } catch (err) {
        currentUser = null;
    }
}

// ==================== INITIALIZATION ====================

document.addEventListener('DOMContentLoaded', async () => {
    await loadCurrentUser();
    if (!currentUser) return; // loadCurrentUser will redirect on 401

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location = '/login';
        });
    }

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
            // Changing sort explicitly unlocks reordering
            unlockReordering();
            const newSort = e.target.dataset.sort;
            
            // Toggle reverse if clicking same button
            if (currentSort === newSort) {
                sortReverse = !sortReverse;
            } else {
                // Add current sort to history (max 2 levels)
                if (currentSort && currentSort !== newSort) {
                    sortHistory = [{ sort: currentSort, reverse: sortReverse }];
                }
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
        // Changing search explicitly unlocks reordering
        unlockReordering();
        searchQuery = (e.target.value || '').trim().toLowerCase();
        renderSongs();
    });

    // Toggle progress details
    const toggleBtn = document.getElementById('toggleProgressDetails');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            const details = document.getElementById('progressDetails');
            if (details.style.display === 'none') {
                details.style.display = 'block';
                toggleBtn.textContent = 'Show less ▲';
            } else {
                details.style.display = 'none';
                toggleBtn.textContent = 'Show more ▼';
            }
        });
    }

    // Delegated event listener for skill progress clicks in the show more area
    // Attach to document to ensure it works even after HTML updates
    document.addEventListener('click', (e) => {
        const skillDiv = e.target.closest('[data-skill-name]');
        if (skillDiv && skillDiv.closest('#skillsProgressBars')) {
            const skillName = skillDiv.getAttribute('data-skill-name');
            sortBySkill(skillName);
        }
    });

    // Hidden audio file input
    const audioInput = document.getElementById('audioFileInput');
    audioInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file || !currentAttachSongId) return;
        try {
            // Try to get the full file path from the file object
            let filePath = file.path;
            
            // If browser doesn't provide full path, ask user to type it
            if (!filePath) {
                filePath = prompt(`Selected file: ${file.name}\n\nBrowser cannot access full file path.\nPlease enter the complete path to this file:`, '');
                if (!filePath) {
                    e.target.value = '';
                    currentAttachSongId = null;
                    return;
                }
            }
            
            // Convert Windows path to WSL if needed
            filePath = convertWindowsToWSLPath(filePath);
            
            const res = await fetch(`/api/songs/${currentAttachSongId}/audio`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path: filePath })
            });
            if (!res.ok) {
                const msg = await res.json().catch(() => ({}));
                alert(msg.error || 'Failed to link audio');
            } else {
                const result = await res.json();
                console.log('Audio linked:', result);
            }
            await loadSongs();
        } catch (err) {
            console.error('Attach audio failed', err);
            alert('Attach audio failed: ' + err.message);
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
            // Try to get the full file path from the file object
            let filePath = file.path;
            
            // If browser doesn't provide full path, ask user to type it
            if (!filePath) {
                filePath = prompt(`Selected file: ${file.name}\n\nBrowser cannot access full file path.\nPlease enter the complete path to this file:`, '');
                if (!filePath) {
                    e.target.value = '';
                    currentAttachChartId = null;
                    return;
                }
            }
            
            // Convert Windows path to WSL if needed
            filePath = convertWindowsToWSLPath(filePath);
            
            const res = await fetch(`/api/songs/${currentAttachChartId}/chart`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path: filePath })
            });
            if (!res.ok) {
                const msg = await res.json().catch(() => ({}));
                alert(msg.error || 'Failed to link chart');
            } else {
                const result = await res.json();
                console.log('Chart linked:', result);
            }
            await loadSongs();
        } catch (err) {
            console.error('Attach chart failed', err);
            alert('Attach chart failed: ' + err.message);
        } finally {
            e.target.value = '';
            currentAttachChartId = null;
        }
    });

    // Single file pickers to extract folder paths
    const mp3FilePicker = document.getElementById('mp3FilePicker');
    if (mp3FilePicker) {
        mp3FilePicker.addEventListener('change', async (e) => {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                // Try to get full path from file.path property (Electron/VS Code)
                if (file.path) {
                    const fullPath = file.path;
                    const dirPath = fullPath.substring(0, fullPath.lastIndexOf('/')) || fullPath.substring(0, fullPath.lastIndexOf('\\'));
                    const convertedPath = convertWindowsToWSLPath(dirPath);
                    document.getElementById('mp3Folder').value = convertedPath;
                    console.log(`MP3 folder extracted: ${dirPath} → ${convertedPath}`);
                    
                    // Auto-save if editing existing repertoire
                    const repertoireId = document.getElementById('repertoireId')?.value;
                    if (repertoireId) {
                        await saveRepertoireFolderPath('mp3_folder', convertedPath);
                    }
                } else {
                    alert('Cannot extract full path from browser file picker. Please type the full path manually (e.g., E:\\Music\\MP3s)');
                }
            }
            e.target.value = ''; // Reset
        });
    }

    // Auto-convert Windows paths when user manually types them
    const folderInputs = [
        { input: document.getElementById('mp3Folder'), field: 'mp3_folder' },
        { input: document.getElementById('sheetFolder'), field: 'sheet_folder' }
    ];
    
    folderInputs.forEach(({ input, field }) => {
        if (input) {
            input.addEventListener('blur', async (e) => {
                const currentValue = e.target.value.trim();
                if (!currentValue) return;
                
                const converted = convertWindowsToWSLPath(currentValue);
                if (converted !== currentValue) {
                    e.target.value = converted;
                    console.log(`Auto-converted: ${currentValue} → ${converted}`);
                }
                
                // Auto-save if repertoire is open for editing
                const repertoireId = document.getElementById('repertoireId')?.value;
                if (repertoireId) {
                    await saveRepertoireFolderPath(field, converted);
                }
            });
        }
    });
});

// ==================== HELPER FUNCTIONS ====================

function convertWindowsToWSLPath(path) {
    if (!path) return path;
    // Convert Windows path (e.g., "E:\Music\Songs") to WSL path ("/mnt/e/Music/Songs")
    const driveMatch = path.match(/^([A-Z]):\\/i);
    if (driveMatch) {
        const driveLetter = driveMatch[1].toLowerCase();
        const restOfPath = path.substring(3).replace(/\\/g, '/');
        return `/mnt/${driveLetter}/${restOfPath}`;
    }
    return path;
}

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
        // Select first repertoire by default if none selected
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
        // Lock reordering to keep the same song under the cursor for quick repeated clicks
        lockReordering();
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
        // Lock reordering to avoid resort/removal while toggling multiple skills
        lockReordering();
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

function isInArchive() {
    const currentRep = repertoires.find(r => r.id === currentRepertoireId);
    return currentRep && currentRep.name === 'Archive';
}

function createMoveToRepertoireDropdown(songId) {
    const otherRepertoires = repertoires.filter(r => r.id !== currentRepertoireId);
    return `
        <select class="move-repertoire-select" onchange="moveSongToRepertoire(${songId}, this.value); this.selectedIndex = 0;" style="padding: 4px 8px; font-size: 14px;">
            <option value="">Move to...</option>
            ${otherRepertoires.map(rep => `<option value="${rep.id}">${rep.name}</option>`).join('')}
        </select>
    `;
}

async function moveSongToRepertoire(songId, repertoireId) {
    if (!repertoireId) return; // Ignore if no selection
    
    try {
        const response = await fetch(`/api/songs/${songId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repertoire_id: parseInt(repertoireId) })
        });
        
        if (response.ok) {
            await loadRepertoires();
        } else {
            const data = await response.json();
            alert(data.error || 'Failed to move song');
        }
    } catch (error) {
        console.error('Error moving song:', error);
        alert('Failed to move song');
    }
}

async function archiveSong(songId, title) {
    if (!confirm(`Move "${title}" to Archive?`)) return;
    
    try {
        const response = await fetch(`/api/songs/${songId}/archive`, {
            method: 'POST'
        });
        
        if (response.ok) {
            await loadRepertoires();
        } else {
            const data = await response.json();
            alert(data.error || 'Failed to archive song');
        }
    } catch (error) {
        console.error('Error archiving song:', error);
        alert('Failed to archive song');
    }
}

async function deleteSong(songId, title) {
    if (!confirm(`Delete "${title}"? This cannot be undone.`)) return;
    
    try {
        const response = await fetch(`/api/songs/${songId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            await loadRepertoires();
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

async function toggleDifficulty(songId) {
    try {
        const response = await fetch(`/api/songs/${songId}/difficulty/toggle`, {
            method: 'POST'
        });
        
        if (response.ok) {
            loadSongs();
        }
    } catch (error) {
        console.error('Error toggling difficulty:', error);
    }
}

function toggleFocusMode() {
    focusMode = !focusMode;
    const songsList = document.getElementById('songsList');
    const focusBtn = document.getElementById('focusModeToggle');
    
    if (focusMode) {
        songsList.classList.add('focus-mode');
        focusBtn.style.opacity = '0.6';
    } else {
        songsList.classList.remove('focus-mode');
        focusBtn.style.opacity = '1';
    }
}

async function saveCurrentOrder() {
    // Get the current visual order of songs
    const songCards = document.querySelectorAll('.song-card');
    const orderedIds = Array.from(songCards).map(card => parseInt(card.getAttribute('data-id')));
    
    if (orderedIds.length === 0) {
        alert('No songs to save order for.');
        return;
    }
    
    if (!confirm(`Save the current visual order as the permanent song order for ${orderedIds.length} song(s)?`)) {
        return;
    }
    
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
            alert('Song order saved successfully!');
            // Switch to song order view to show the saved order
            currentSort = 'song_number';
            sortReverse = false;
            sortHistory = [];
            document.querySelectorAll('.sort-btn').forEach(b => {
                b.classList.remove('active');
                b.textContent = b.textContent.replace(' ↑', '').replace(' ↓', '');
            });
            document.querySelector('.sort-btn[data-sort="song_number"]').classList.add('active');
            await loadSongs();
        } else {
            const error = await response.json();
            alert('Failed to save order: ' + (error.error || 'Unknown error'));
        }
    } catch (err) {
        console.error('Error saving order:', err);
        alert('Failed to save order: ' + err.message);
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

// Sort by specific skill
function sortBySkill(skillName) {
    // Unlock reordering to allow new sort to take effect
    unlockReordering();
    
    const newSort = 'skill:' + skillName;
    
    // Toggle reverse if clicking same skill
    if (currentSort === newSort) {
        sortReverse = !sortReverse;
    } else {
        // Add current sort to history
        if (currentSort && currentSort !== newSort) {
            sortHistory = [{ sort: currentSort, reverse: sortReverse }];
        }
        sortReverse = false;
        currentSort = newSort;
    }
    
    // Clear active state from sort buttons
    document.querySelectorAll('.sort-btn').forEach(b => {
        b.classList.remove('active');
        b.textContent = b.textContent.replace(' ↑', '').replace(' ↓', '');
    });
    
    renderSongs();
}

// Sort by practice progress
function sortByPracticeProgress() {
    // Unlock reordering to allow new sort to take effect
    unlockReordering();
    
    const newSort = 'practice_progress';
    
    // Toggle reverse if clicking same sort
    if (currentSort === newSort) {
        sortReverse = !sortReverse;
    } else {
        // Add current sort to history
        if (currentSort && currentSort !== newSort) {
            sortHistory = [{ sort: currentSort, reverse: sortReverse }];
        }
        sortReverse = false;
        currentSort = newSort;
    }
    
    // Clear active state from sort buttons
    document.querySelectorAll('.sort-btn').forEach(b => {
        b.classList.remove('active');
        b.textContent = b.textContent.replace(' ↑', '').replace(' ↓', '');
    });
    
    renderSongs();
}

// ==================== RENDERING ====================

function renderSongs() {
    const songsList = document.getElementById('songsList');
    
    if (songs.length === 0) {
        songsList.innerHTML = '<div class="empty-state"><h2>No songs yet!</h2><p>Click "Add Song" to get started.</p></div>';
        return;
    }
    
    // When locked, render the last snapshot to avoid reordering/removal while user does quick actions
    if (reorderLocked && lastRenderedSongIds.length > 0) {
        const stableSongs = lastRenderedSongIds
            .map(id => songs.find(s => s.id === id))
            .filter(Boolean);
        songsList.innerHTML = stableSongs.map(song => createSongCard(song)).join('');
        setupDragAndDrop();
        return;
    }

    // Filter by search query (title only)
    const filtered = songs.filter(s => !searchQuery || (s.title || '').toLowerCase().includes(searchQuery));

    // Helper function to compare two songs by a specific sort criterion
    const compareBy = (a, b, sortType, reverse) => {
        let comparison = 0;
        
        if (sortType === 'song_number') {
            comparison = a.song_number - b.song_number;
        } else if (sortType === 'name') {
            comparison = (a.title || '').localeCompare(b.title || '');
        } else if (sortType === 'priority') {
            const priorityOrder = { high: 0, mid: 1, low: 2 };
            comparison = priorityOrder[a.priority] - priorityOrder[b.priority];
        } else if (sortType === 'difficulty') {
            const difficultyOrder = { easy: 0, normal: 1, hard: 2 };
            const aDiff = a.difficulty || 'normal';
            const bDiff = b.difficulty || 'normal';
            comparison = difficultyOrder[aDiff] - difficultyOrder[bDiff];
        } else if (sortType === 'last_practiced') {
            if (!a.last_practiced) return reverse ? 1 : -1;
            if (!b.last_practiced) return reverse ? -1 : 1;
            comparison = new Date(a.last_practiced) - new Date(b.last_practiced);
        } else if (sortType === 'release_date') {
            if (!a.release_date) return reverse ? -1 : 1;
            if (!b.release_date) return reverse ? 1 : -1;
            comparison = a.release_date.localeCompare(b.release_date);
        } else if (sortType === 'skills_mastered') {
            const aSkills = a.skills.filter(s => s.is_mastered !== null);
            const bSkills = b.skills.filter(s => s.is_mastered !== null);
            const aMastered = aSkills.filter(s => s.is_mastered === 1).length;
            const bMastered = bSkills.filter(s => s.is_mastered === 1).length;
            comparison = aMastered - bMastered;
        } else if (sortType === 'practice_gap') {
            // Sort by gap between practice target and practice count (biggest gap first when descending)
            const aTarget = a.practice_target || 0;
            const aCount = a.practice_count || 0;
            const bTarget = b.practice_target || 0;
            const bCount = b.practice_count || 0;
            const aGap = aTarget - aCount;
            const bGap = bTarget - bCount;
            comparison = aGap - bGap;
        } else if (sortType === 'practice_progress') {
            const aProgress = a.practice_progress || 0;
            const bProgress = b.practice_progress || 0;
            comparison = aProgress - bProgress;
        } else if (sortType.startsWith('skill:')) {
            // Sort by specific skill mastery
            const skillName = sortType.substring(6); // Remove 'skill:' prefix
            const aSkill = a.skills.find(s => s.name === skillName && s.is_mastered !== null);
            const bSkill = b.skills.find(s => s.name === skillName && s.is_mastered !== null);
            
            // Songs with skill assigned and mastered come first, then assigned but not mastered, then not assigned
            const aValue = aSkill ? (aSkill.is_mastered === 1 ? 2 : 1) : 0;
            const bValue = bSkill ? (bSkill.is_mastered === 1 ? 2 : 1) : 0;
            comparison = aValue - bValue;
        }
        
        return reverse ? -comparison : comparison;
    };

    // Sort songs with multi-level sorting
    const sortedSongs = [...filtered].sort((a, b) => {
        // Primary sort
        let comparison = compareBy(a, b, currentSort, sortReverse);
        
        // If equal, use secondary sort from history
        if (comparison === 0 && sortHistory.length > 0) {
            comparison = compareBy(a, b, sortHistory[0].sort, sortHistory[0].reverse);
        }
        
        return comparison;
    });
    
    // Save snapshot for lock mode
    lastRenderedSongIds = sortedSongs.map(s => s.id);
    songsList.innerHTML = sortedSongs.map(song => createSongCard(song)).join('');
    setupDragAndDrop();
}

function createSongCard(song) {
    const priorityIcons = {
        high: '🔴',
        mid: '🟡',
        low: '🟢'
    };
    
    const difficultyIcons = {
        easy: '🪶',
        normal: '🎯',
        hard: '🔥'
    };
    const difficultyValue = song.difficulty || 'normal';
    
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
                            <button class="btn-icon" onclick="increaseTarget(${song.id})" title="+practice rounds" style="margin-left: 8px;">⬆️</button>
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
                        <h3 class="song-title">${song.title}${song.performance_hints ? ' ' + formatPerformanceHints(song.performance_hints) : ''}</h3>
                        <span class="priority-badge" title="Click to change priority (${song.priority})" onclick="togglePriority(${song.id})">${priorityIcons[song.priority]}</span>
                        <span class="difficulty-badge" title="Click to change difficulty (${difficultyValue})" onclick="toggleDifficulty(${song.id})">${difficultyIcons[difficultyValue]}</span>
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
                    ${isInArchive() 
                        ? createMoveToRepertoireDropdown(song.id)
                        : `<button class="btn-icon" onclick="archiveSong(${song.id}, '${song.title.replace(/'/g, "\\'")}')" title="Move to Archive">📦</button>`
                    }
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
    
    // Only enable dragging in song order mode and when not filtering (search active)
    const dragEnabled = currentSort === 'song_number' && (!searchQuery || searchQuery.length === 0);

    if (dragEnabled) {
        cards.forEach(card => {
            card.setAttribute('draggable', 'true');
            
            // Prevent drag on interactive elements
            card.querySelectorAll('button, a, .skill-item').forEach(el => {
                el.setAttribute('draggable', 'false');
                el.addEventListener('mousedown', (e) => e.stopPropagation());
            });
            
            let dragStarted = false;
            
            card.addEventListener('dragstart', (e) => {
                // Only allow drag from drag handle or card background
                if (!e.target.closest('.drag-handle') && 
                    !e.target.classList.contains('song-card') &&
                    !e.target.closest('.song-info')) {
                    e.preventDefault();
                    return;
                }
                card.classList.add('dragging');
                dragStarted = true;
            });
            
            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
                // Only reorder if an actual drag occurred
                if (dragStarted && dragEnabled) {
                    const orderedIds = Array.from(container.querySelectorAll('.song-card'))
                        .map(el => parseInt(el.getAttribute('data-id')));
                    reorderSongsOnServer(orderedIds);
                }
                dragStarted = false;
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
    
    // Update detailed progress (practice and skills breakdown)
    updateProgressDetails();
}

function updateProgressDetails() {
    const repertoireSongs = currentRepertoireId 
        ? songs.filter(s => s.repertoire_id === currentRepertoireId)
        : songs;
    
    // Calculate practice progress
    let totalPracticeTarget = 0;
    let totalPracticeCount = 0;
    
    repertoireSongs.forEach(song => {
        if (song.practice_target > 0) {
            totalPracticeTarget += song.practice_target;
            totalPracticeCount += Math.min(song.practice_count, song.practice_target);
        }
    });
    
    const practicePercentage = totalPracticeTarget > 0 
        ? Math.round((totalPracticeCount / totalPracticeTarget) * 100) 
        : 0;
    
    const practiceBar = document.getElementById('practiceProgressBar');
    const practiceText = document.getElementById('practiceProgressText');
    
    if (practiceBar && practiceText) {
        practiceBar.style.width = practicePercentage + '%';
        practiceBar.textContent = practicePercentage + '%';
        practiceBar.className = 'progress-bar' + (practicePercentage >= 100 ? ' complete' : '');
        practiceText.textContent = `${totalPracticeCount} / ${totalPracticeTarget} songs practiced`;
    }
    
    // Fetch and display daily and all-time practice data
    if (currentRepertoireId) {
        fetch(`/api/repertoires/${currentRepertoireId}/time-practiced`)
            .then(r => r.json())
            .then(data => {
                // Update daily practice bar
                const dailyBar = document.getElementById('dailyProgressBar');
                const dailyText = document.getElementById('dailyTimeText');
                if (dailyBar && data.daily) {
                    const progress = data.daily.progress;
                    dailyBar.style.width = progress + '%';
                    dailyBar.textContent = progress + '%';
                    dailyBar.className = 'progress-bar' + (progress >= 100 ? ' complete' : '');
                }
                if (dailyText && data.daily) {
                    dailyText.textContent = `${data.daily.formatted} / 1h goal`;
                }
                
                // Update all-time practice bar
                const alltimeBar = document.getElementById('alltimeProgressBar');
                const alltimeText = document.getElementById('alltimeTimeText');
                const alltimeHeader = document.getElementById('alltimeHeader');
                if (alltimeBar && data.alltime) {
                    const progress = data.alltime.progress;
                    alltimeBar.style.width = progress + '%';
                    alltimeBar.textContent = progress + '%';
                    alltimeBar.className = 'progress-bar' + (progress >= 100 ? ' complete' : '');
                }
                if (alltimeText && data.alltime) {
                    const targetHours = data.song_count * 5;
                    alltimeText.textContent = `${data.alltime.formatted} / ${targetHours}h goal (5h per song)`;
                }
                if (alltimeHeader && data.alltime && data.alltime.start_date) {
                    alltimeHeader.textContent = `Total time practiced since ${data.alltime.start_date}`;
                }
            })
            .catch(err => console.error('Failed to fetch time practiced:', err));
    }
    
    // Calculate per-skill progress
    const skillsContainer = document.getElementById('skillsProgressBars');
    if (!skillsContainer) return;
    
    // Group by skill
    const skillStats = {};
    
    repertoireSongs.forEach(song => {
        song.skills.forEach(skill => {
            if (skill.is_mastered !== null) { // Only count assigned skills
                if (!skillStats[skill.id]) {
                    skillStats[skill.id] = {
                        name: skill.name,
                        total: 0,
                        mastered: 0
                    };
                }
                skillStats[skill.id].total++;
                if (skill.is_mastered === 1) {
                    skillStats[skill.id].mastered++;
                }
            }
        });
    });
    
    // Render skill progress bars
    const skillsArray = Object.values(skillStats).sort((a, b) => a.name.localeCompare(b.name));
    
    if (skillsArray.length === 0) {
        skillsContainer.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem;">No skills assigned to songs yet.</p>';
        return;
    }
    
    skillsContainer.innerHTML = skillsArray.map(skill => {
        const percentage = Math.round((skill.mastered / skill.total) * 100);
        return `
            <div style="margin-bottom: 15px; cursor: pointer;" data-skill-name="${skill.name}" title="Click to sort by this skill">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span style="font-size: 0.9rem;">${skill.name}</span>
                    <span style="font-size: 0.85rem; color: var(--text-muted);">${skill.mastered} / ${skill.total}</span>
                </div>
                <div class="progress-bar-container" style="height: 18px;">
                    <div class="progress-bar ${percentage >= 100 ? 'complete' : ''}" style="width: ${percentage}%; font-size: 0.8rem;">
                        ${percentage}%
                    </div>
                </div>
            </div>
        `;
    }).join('');
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
        document.getElementById('performanceHints').value = song.performance_hints || '';
        
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
        document.getElementById('practiceTarget').value = 5;
        
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
        performance_hints: document.getElementById('performanceHints').value,
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
            <input type="checkbox" id="rep-skill-${skill.id}" value="${skill.id}" onchange="updateAddSkillsButton()">
            ${skill.name}
        </label>
    `).join('');
    updateAddSkillsButton();
}

function updateAddSkillsButton() {
    const btn = document.getElementById('addSkillsToAllSongsBtn');
    const repertoireId = document.getElementById('repertoireId').value;
    const checkboxes = document.querySelectorAll('#repertoireSkillsCheckboxes input[type="checkbox"]:checked');
    btn.disabled = !repertoireId || checkboxes.length === 0;
}

async function addSkillsToAllSongs() {
    const repertoireId = document.getElementById('repertoireId').value;
    if (!repertoireId) {
        alert('Please save the repertoire first');
        return;
    }
    
    const checkboxes = document.querySelectorAll('#repertoireSkillsCheckboxes input[type="checkbox"]:checked');
    const skillIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    if (skillIds.length === 0) {
        alert('Please select at least one skill');
        return;
    }
    
    const skillNames = skillIds.map(id => skills.find(s => s.id === id)?.name || id).join(', ');
    if (!confirm(`Add skills (${skillNames}) to ALL songs in this repertoire?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/repertoires/${repertoireId}/add-skills-to-songs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ skill_ids: skillIds })
        });
        
        const result = await response.json();
        if (response.ok) {
            alert(`Successfully added skills to ${result.songs_updated} songs (${result.skills_added} skill assignments added)`);
            loadSongs();
        } else {
            alert(`Error: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error adding skills to songs:', error);
        alert('Error adding skills to songs');
    }
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
            <div style="display: flex; gap: 6px; align-items: center;">
                <span class="tab-name" onclick="switchRepertoire(${rep.id})" style="flex: 1;">${rep.name}</span>
                <span class="tab-count" onclick="switchRepertoire(${rep.id})">${rep.song_count}</span>
                <button class="tab-edit-btn" onclick="event.stopPropagation(); editRepertoire(${rep.id})" title="Edit repertoire">✏️</button>
                <button class="tab-notes-btn" onclick="event.stopPropagation(); openRepertoireNotesModal(${rep.id})" title="View/edit repertoire notes" style="padding: 2px 6px; font-size: 0.8rem; background-color: #95a5a6; border: 1px solid #7f8c8d; border-radius: 3px; cursor: pointer; color: white;">📝</button>
                <span class="drag-hint" style="cursor:grab; font-size:10px; color:#7f8c8d;">⇅</span>
            </div>
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
    // Switching repertoire unlocks and refreshes
    unlockReordering();
    currentRepertoireId = repertoireId;
    renderRepertoireTabs();
    loadSongs();
}

function openRepertoireNotesModal(repertoireId) {
    // Find the repertoire
    const repertoire = repertoires.find(r => r.id === repertoireId);
    if (!repertoire) {
        alert('Repertoire not found');
        return;
    }

    // Create modal HTML
    const modalHTML = `
        <div id="notesModal" class="modal" style="display: flex; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center;">
            <div class="modal-content" style="background: white; border-radius: 8px; padding: 20px; max-width: 600px; width: 90%; max-height: 80vh; overflow: auto; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                    <h2 style="margin: 0;">Repertoire Notes: ${repertoire.name}</h2>
                    <button onclick="document.getElementById('notesModal').remove();" style="background: none; border: none; font-size: 1.5rem; cursor: pointer;">✕</button>
                </div>
                <form id="notesForm" style="display: flex; flex-direction: column; gap: 10px;">
                    <textarea id="notesText" placeholder="Add notes about this repertoire (focus areas, learning goals, etc.)" style="width: 100%; min-height: 200px; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: Arial, sans-serif; font-size: 14px;">${repertoire.notes || ''}</textarea>
                    <div style="display: flex; gap: 10px; justify-content: flex-end;">
                        <button type="button" onclick="document.getElementById('notesModal').remove();" style="padding: 8px 16px; background: #95a5a6; color: white; border: none; border-radius: 4px; cursor: pointer;">Cancel</button>
                        <button type="submit" style="padding: 8px 16px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">Save Notes</button>
                    </div>
                </form>
            </div>
        </div>
    `;

    // Insert modal into DOM
    document.body.insertAdjacentHTML('beforeend', modalHTML);

    // Handle form submission
    document.getElementById('notesForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const notes = document.getElementById('notesText').value;

        try {
            const response = await fetch(`/api/repertoires/${repertoireId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes: notes })
            });

            if (response.ok) {
                // Update local repertoires array
                const rep = repertoires.find(r => r.id === repertoireId);
                if (rep) {
                    rep.notes = notes;
                }
                alert('Notes saved!');
                document.getElementById('notesModal').remove();
            } else {
                const error = await response.json();
                alert(`Error saving notes: ${error.error || 'Unknown error'}`);
            }
        } catch (err) {
            console.error('Error saving notes:', err);
            alert('Error saving notes');
        }
    });
}

function openRepertoireModal(repertoire = null) {
    const modal = document.getElementById('repertoireModal');
    const form = document.getElementById('repertoireForm');
    const title = document.getElementById('repertoireModalTitle');
    const syncBtn = document.getElementById('syncRepertoireBtn');
    const undoSyncBtn = document.getElementById('undoSyncBtn');
    const deleteBtn = document.getElementById('deleteRepertoireBtn');
    const copyInfoDiv = document.getElementById('repertoireCopyInfo');
    const copyInfoText = document.getElementById('copyInfoText');
    const shareSection = document.getElementById('shareRepertoireSection');
    
    form.reset();
    
    if (repertoire) {
        title.textContent = 'Edit Repertoire';
        document.getElementById('repertoireId').value = repertoire.id;
        document.getElementById('repertoireName').value = repertoire.name;
        document.getElementById('mp3Folder').value = repertoire.mp3_folder || '';
        document.getElementById('sheetFolder').value = repertoire.sheet_folder || '';
        
        // Show copy info if this repertoire was copied
        if (repertoire.copied_from_user_id && repertoire.copied_date) {
            loadCopyInfo(repertoire.copied_from_user_id, repertoire.copied_date);
            copyInfoDiv.style.display = 'block';
        } else {
            copyInfoDiv.style.display = 'none';
        }
        
        // Check the default skills for this repertoire
        const defaultSkillIds = repertoire.default_skills.map(s => s.id);
        skills.forEach(skill => {
            const checkbox = document.getElementById(`rep-skill-${skill.id}`);
            if (checkbox) {
                checkbox.checked = defaultSkillIds.includes(skill.id);
            }
        });
        
        
        // Show sync button for existing repertoires
        if (syncBtn) {
            syncBtn.style.display = 'inline-block';
            syncBtn.onclick = () => syncRepertoireFolders(repertoire.id);
        }
        
        // Show undo sync button for existing repertoires
        if (undoSyncBtn) {
            undoSyncBtn.style.display = 'inline-block';
            undoSyncBtn.onclick = () => undoLastSync(repertoire.id);
        }
        
        // Show move to archive button for existing repertoires (but not for Archive itself)
        const moveToArchiveBtn = document.getElementById('moveToArchiveBtn');
        if (moveToArchiveBtn && repertoire.name !== 'Archive') {
            moveToArchiveBtn.style.display = 'inline-block';
            moveToArchiveBtn.onclick = () => moveRepertoireToArchive(repertoire.id);
        } else if (moveToArchiveBtn) {
            moveToArchiveBtn.style.display = 'none';
        }
        
        // Show setlist PDF section for existing repertoires
        const setlistSection = document.getElementById('setlistSection');
        if (setlistSection) {
            setlistSection.style.display = 'block';
        }
        
        // Show share section and load users for existing repertoires
        if (shareSection) {
            shareSection.style.display = 'block';
            loadUsersForShare();
        }
    } else {
        title.textContent = 'Add Repertoire';
        document.getElementById('repertoireId').value = '';
        copyInfoDiv.style.display = 'none';
        
        // Check all skills by default for new repertoires
        skills.forEach(skill => {
            const checkbox = document.getElementById(`rep-skill-${skill.id}`);
            if (checkbox) {
                checkbox.checked = true;
            }
        });
        
        // Hide delete and sync buttons for new repertoires
        if (deleteBtn) {
            deleteBtn.style.display = 'none';
        }
        if (syncBtn) {
            syncBtn.style.display = 'none';
        }
        if (undoSyncBtn) {
            undoSyncBtn.style.display = 'none';
        }
        
        // Hide setlist and share sections for new repertoires
        const setlistSection = document.getElementById('setlistSection');
        if (setlistSection) {
            setlistSection.style.display = 'none';
        }
        if (shareSection) {
            shareSection.style.display = 'none';
        }
    }
    
    modal.style.display = 'block';
}

async function loadCopyInfo(userId, copiedDate) {
    try {
        const response = await fetch(`/api/users/${userId}`);
        if (response.ok) {
            const user = await response.json();
            const date = new Date(copiedDate).toLocaleDateString();
            document.getElementById('copyInfoText').textContent = `Copied from ${user.email} on ${date}`;
        }
    } catch (error) {
        console.error('Error loading copy info:', error);
    }
}

async function loadUsersForShare() {
    try {
        const response = await fetch('/api/users');
        if (response.ok) {
            const users = await response.json();
            const select = document.getElementById('shareTargetUser');
            select.innerHTML = '<option value="">Select user...</option>';
            
            // Filter out current user (if currentUser is loaded)
            const otherUsers = currentUser 
                ? users.filter(u => u.id !== currentUser.id)
                : users;
            
            otherUsers.forEach(user => {
                const option = document.createElement('option');
                option.value = user.id;
                option.textContent = `${user.email}${user.role === 'admin' ? ' (Admin)' : ''}`;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading users:', error);
    }
}

async function shareRepertoire() {
    const repertoireId = document.getElementById('repertoireId').value;
    const targetUserId = document.getElementById('shareTargetUser').value;
    
    if (!targetUserId) {
        alert('Please select a user to share with');
        return;
    }
    
    const targetUserText = document.getElementById('shareTargetUser').options[document.getElementById('shareTargetUser').selectedIndex].text;
    
    if (!confirm(`Share this repertoire with ${targetUserText}?\n\nThis will create a copy including all songs and their skills.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/repertoires/${repertoireId}/share`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_user_id: parseInt(targetUserId) })
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(result.message + `\n${result.songs_copied} songs copied.`);
            document.getElementById('shareTargetUser').selectedIndex = 0;
        } else {
            const error = await response.json();
            alert(error.error || 'Error sharing repertoire');
        }
    } catch (error) {
        console.error('Error sharing repertoire:', error);
        alert('Error sharing repertoire');
    }
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
    
    // Get folder paths and convert Windows to WSL format
    const mp3Folder = document.getElementById('mp3Folder').value || null;
    const sheetFolder = document.getElementById('sheetFolder').value || null;
    
    const data = {
        name: document.getElementById('repertoireName').value,
        skill_ids: selectedSkillIds,
        songlist_folder: null,  // No longer used
        mp3_folder: mp3Folder ? convertWindowsToWSLPath(mp3Folder) : null,
        sheet_folder: sheetFolder ? convertWindowsToWSLPath(sheetFolder) : null
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

async function moveRepertoireToArchive(repertoireId) {
    const repertoire = repertoires.find(r => r.id === parseInt(repertoireId));
    if (!repertoire) return;
    
    const confirmMsg = `Move all songs from "${repertoire.name}" to Archive?\n\nThis will move all ${repertoire.song_count} song(s) to your Archive repertoire and delete the "${repertoire.name}" repertoire.\n\nThis cannot be undone.`;
    
    if (!confirm(confirmMsg)) return;
    
    try {
        const response = await fetch(`/api/repertoires/${repertoireId}/archive`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(result.message || 'Repertoire moved to archive');
            closeRepertoireModal();
            // If we archived the current repertoire, switch to first available
            if (currentRepertoireId === parseInt(repertoireId)) {
                currentRepertoireId = null;
            }
            loadRepertoires();
        } else {
            const error = await response.json();
            alert(error.error || 'Error moving repertoire to archive');
        }
    } catch (error) {
        console.error('Error moving repertoire to archive:', error);
        alert('Error moving repertoire to archive');
    }
}

async function syncRepertoireFolders(repertoireId) {
    if (!confirm('Scan linked folders and import missing songs, MP3s, and sheets?')) return;
    
    try {
        const response = await fetch(`/api/repertoires/${repertoireId}/sync`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const stats = await response.json();
            let msg = 'Sync completed:\n\n';
            msg += `Songs added: ${stats.songs_added}\n`;
            msg += `MP3s linked: ${stats.mp3_linked}\n`;
            msg += `Sheets linked: ${stats.sheets_linked}\n`;
            if (stats.debug) {
                msg += `\nDebug Info:\n`;
                msg += `Songs in repertoire: ${stats.debug.songs_in_repertoire}\n`;
                msg += `MP3 files found: ${stats.debug.mp3_files_found}\n`;
                msg += `Sheet files found: ${stats.debug.sheet_files_found}\n`;
            }
            if (stats.errors.length > 0) {
                msg += `\nErrors:\n${stats.errors.join('\n')}`;
            }
            alert(msg);
            closeRepertoireModal();
            loadRepertoires();
            loadSongs();
        } else {
            const error = await response.json();
            alert(error.error || 'Error syncing folders');
        }
    } catch (error) {
        console.error('Error syncing folders:', error);
        alert('Error syncing folders');
    }
}

async function undoLastSync(repertoireId) {
    if (!confirm('Undo the last sync operation? This will:\n- Delete songs that were created\n- Remove audio/chart links that were added')) return;
    
    try {
        const response = await fetch(`/api/repertoires/${repertoireId}/undo-sync`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const stats = await response.json();
            let msg = 'Undo completed:\n\n';
            msg += `Songs deleted: ${stats.songs_deleted}\n`;
            msg += `Audio links removed: ${stats.audio_unlinked}\n`;
            msg += `Chart links removed: ${stats.charts_unlinked}\n`;
            alert(msg);
            closeRepertoireModal();
            loadRepertoires();
            loadSongs();
        } else {
            const error = await response.json();
            alert(error.error || 'Error undoing sync');
        }
    } catch (error) {
        console.error('Error undoing sync:', error);
        alert('Error undoing sync');
    }
}

async function saveRepertoireFolderPath(fieldName, folderPath) {
    const repertoireId = document.getElementById('repertoireId').value;
    if (!repertoireId) return; // Only save for existing repertoires
    
    // Convert Windows path to WSL path if needed
    const convertedPath = convertWindowsToWSLPath(folderPath);
    
    try {
        const data = {};
        data[fieldName] = convertedPath;
        
        const response = await fetch(`/api/repertoires/${repertoireId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            console.log(`Saved ${fieldName}: ${folderPath} → ${convertedPath}`);
            // Update the input field to show converted path
            const inputId = fieldName === 'songlist_folder' ? 'songlistFolder' : 
                           fieldName === 'mp3_folder' ? 'mp3Folder' : 'sheetFolder';
            document.getElementById(inputId).value = convertedPath;
            // Reload repertoires to update state
            await loadRepertoires();
        }
    } catch (error) {
        console.error('Error saving folder path:', error);
    }
}

async function lookupSongMetadata() {
    const title = document.getElementById('title').value.trim();
    if (!title) {
        alert('Please enter a song title first');
        return;
    }
    
    try {
        const response = await fetch('/api/songs/lookup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title })
        });
        
        if (response.ok) {
            const metadata = await response.json();
            if (metadata.found) {
                // Only fill if fields are empty
                if (!document.getElementById('artist').value && metadata.artist) {
                    document.getElementById('artist').value = metadata.artist;
                }
                if (!document.getElementById('releaseDate').value && metadata.release_date) {
                    document.getElementById('releaseDate').value = metadata.release_date;
                }
                alert(`Found: ${metadata.artist} - ${metadata.title}${metadata.release_date ? ' (' + metadata.release_date + ')' : ''}`);
            } else {
                alert('No metadata found for this song');
            }
        } else {
            alert('Lookup failed');
        }
    } catch (error) {
        console.error('Lookup error:', error);
        alert('Lookup failed');
    }
}

// ==================== UTILITIES ====================

function formatDate(isoString) {
    // Parse ISO string as local time (not UTC)
    // Python's datetime.now().isoformat() returns "2025-12-23T14:30:45.123456" without timezone
    // JavaScript's new Date() treats strings without 'Z' or timezone as local time in ISO 8601
    // but for safety, we explicitly parse it as local time
    let date;
    if (isoString.includes('T')) {
        // ISO format with time: extract date and time components
        const parts = isoString.split('T');
        const datePart = parts[0];
        const timePart = parts[1].split('.')[0]; // Remove microseconds if present
        const [year, month, day] = datePart.split('-').map(Number);
        const [hours, minutes, seconds] = timePart.split(':').map(Number);
        date = new Date(year, month - 1, day, hours, minutes, seconds);
    } else {
        // Just a date string
        date = new Date(isoString);
    }
    
    const now = new Date();
    
    // Compare calendar days, not timestamps
    const dateOnly = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const nowOnly = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const diffTime = nowOnly - dateOnly;
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

// Format performance hints with bold text support
function formatPerformanceHints(hints) {
    if (!hints) return '';
    // Replace **text** with <strong>text</strong>
    const formatted = hints.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    return `<span class="performance-hints">(${formatted})</span>`;
}

// Insert bold formatting in performance hints textarea
function insertBoldText() {
    const textarea = document.getElementById('performanceHints');
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = textarea.value.substring(start, end);
    
    if (selectedText) {
        // Wrap selected text in **
        const before = textarea.value.substring(0, start);
        const after = textarea.value.substring(end);
        textarea.value = before + '**' + selectedText + '**' + after;
        // Set cursor after the inserted text
        textarea.selectionStart = textarea.selectionEnd = end + 4;
    } else {
        // Insert ** ** template with cursor in the middle
        const before = textarea.value.substring(0, start);
        const after = textarea.value.substring(end);
        textarea.value = before + '****' + after;
        // Set cursor between the **
        textarea.selectionStart = textarea.selectionEnd = start + 2;
    }
    textarea.focus();
}

// Generate setlist PDF for current repertoire
async function generateSetlistPDF() {
    const repertoireId = document.getElementById('repertoireId').value;
    if (!repertoireId) {
        alert('Please save the repertoire first');
        return;
    }
    
    const minSongNumber = document.getElementById('minSongNumber').value;
    const maxSongNumber = document.getElementById('maxSongNumber').value;
    
    // Get repertoire name for prefilling
    const repertoire = repertoires.find(r => r.id === parseInt(repertoireId));
    const defaultTitle = repertoire ? repertoire.name : '';
    
    // Prompt for custom title
    const customTitle = prompt('Enter setlist title (e.g., add venue or date):', defaultTitle);
    if (customTitle === null) {
        return; // User cancelled
    }
    
    try {
        const response = await fetch(`/api/repertoires/${repertoireId}/setlist-pdf`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                min_song_number: minSongNumber ? parseInt(minSongNumber) : null,
                max_song_number: maxSongNumber ? parseInt(maxSongNumber) : null,
                custom_title: customTitle || defaultTitle
            })
        });
        
        if (response.ok) {
            // Download the PDF
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `setlist_${repertoireId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            const error = await response.json();
            alert(`Error generating PDF: ${error.error || 'Unknown error'}`);
        }
    } catch (error) {
        console.error('Error generating PDF:', error);
        alert('Error generating PDF');
    }
}
