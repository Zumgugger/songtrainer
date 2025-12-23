with open('static/js/app.js', 'r') as f:
    content = f.read()

# Find the switchRepertoire function and add notes modal function after it
old_switch = """function switchRepertoire(repertoireId) {
    currentRepertoireId = repertoireId;
    renderRepertoireTabs();
    loadSongs();
}"""

new_switch = """function switchRepertoire(repertoireId) {
    currentRepertoireId = repertoireId;
    renderRepertoireTabs();
    loadSongs();
}

// ==================== REPERTOIRE NOTES ====================

function openRepertoireNotesModal(repertoireId) {
    const repertoire = repertoires.find(r => r.id === repertoireId);
    if (!repertoire) return;
    
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.id = 'repertoireNotesModal';
    modal.style.display = 'block';
    
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 600px;">
            <span class="close" onclick="this.closest('.modal').remove()">&times;</span>
            <h2>Notes for "${repertoire.name}"</h2>
            <form id="repertoireNotesForm" style="display: flex; flex-direction: column; gap: 15px;">
                <textarea id="repertoireNotesText" rows="10" style="padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace;">${repertoire.notes || ''}</textarea>
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary">Save Notes</button>
                    <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">Close</button>
                </div>
            </form>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    const form = modal.querySelector('#repertoireNotesForm');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const notes = document.getElementById('repertoireNotesText').value;
        
        try {
            const response = await fetch(`/api/repertoires/${repertoireId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ notes })
            });
            
            if (response.ok) {
                // Update local repertoire object
                const rep = repertoires.find(r => r.id === repertoireId);
                if (rep) rep.notes = notes;
                modal.remove();
            } else {
                alert('Error saving notes');
            }
        } catch (error) {
            console.error('Error saving notes:', error);
            alert('Error saving notes');
        }
    });
    
    // Close modal on background click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}"""

content = content.replace(old_switch, new_switch)

with open('static/js/app.js', 'w') as f:
    f.write(content)

print("Frontend notes modal added!")
