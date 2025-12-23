with open('templates/index.html', 'r') as f:
    content = f.read()

# Add CSS for tab layout
style_block = """    <style>
        .tab {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
    </style>"""

# Insert before the closing </head>
if '</head>' in content and '<style>' not in content:
    content = content.replace('</head>', style_block + '\n    </head>')

with open('templates/index.html', 'w') as f:
    f.write(content)

print("CSS added to index.html!")
