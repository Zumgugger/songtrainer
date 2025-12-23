with open('static/js/app.js', 'r') as f:
    content = f.read()

# Update the renderRepertoireTabs function to add notes button
old_tabs = """    tabsContainer.innerHTML = repertoires.map(rep => `
        <div class="tab ${rep.id === currentRepertoireId ? 'active' : ''}" 
             data-repid="${rep.id}" draggable="true">
            <span class="tab-name" onclick="switchRepertoire(${rep.id})">${rep.name}</span>
            <span class="tab-count" onclick="switchRepertoire(${rep.id})">${rep.song_count}</span>
            <button class="tab-edit-btn" onclick="event.stopPropagation(); editRepertoire(${rep.id})" title="Edit repertoire">✏️</button>
            <span class="drag-hint" style="cursor:grab; font-size:10px; color:#7f8c8d;">⇅</span>
        </div>
    `).join('');"""

new_tabs = """    tabsContainer.innerHTML = repertoires.map(rep => `
        <div class="tab ${rep.id === currentRepertoireId ? 'active' : ''}" 
             data-repid="${rep.id}" draggable="true">
            <div style="display: flex; flex-direction: column; width: 100%;">
                <span class="tab-name" onclick="switchRepertoire(${rep.id})" style="font-weight: bold;">${rep.name}</span>
                <div style="display: flex; gap: 5px; align-items: center; margin-top: 4px;">
                    <span class="tab-count" onclick="switchRepertoire(${rep.id})" style="font-size: 0.85rem; color: #7f8c8d;">${rep.song_count} songs</span>
                    <button class="tab-edit-btn" onclick="event.stopPropagation(); editRepertoire(${rep.id})" title="Edit repertoire" style="padding: 2px 6px; font-size: 0.8rem;">✏️</button>
                    <button class="tab-edit-btn" onclick="event.stopPropagation(); openRepertoireNotesModal(${rep.id})" title="View/edit repertoire notes" style="padding: 2px 6px; font-size: 0.8rem;">📝</button>
                </div>
            </div>
            <span class="drag-hint" style="cursor:grab; font-size:10px; color:#7f8c8d;">⇅</span>
        </div>
    `).join('');"""

content = content.replace(old_tabs, new_tabs)

with open('static/js/app.js', 'w') as f:
    f.write(content)

print("Tab UI updated with notes button!")
