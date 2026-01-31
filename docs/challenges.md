# Repertoire Challenges - Feature Proposal

## Overview
Challenges are motivational goals that users can add to their repertoires to stay engaged and track their practice progress. Unlike skills (which are specific techniques to master), challenges are time-bound or quantity-based goals that encourage consistent practice.

---

## Challenge Categories

### 1. **Streak Challenges**
- **Daily Practice Streak** - Practice songs from this repertoire X days in a row
- **Weekly Consistency** - Practice at least 3/5/7 days per week for X weeks
- **Morning Practice Streak** - Practice before noon for X consecutive days

### 2. **Time-Based Challenges**
- **Practice Marathon** - Accumulate X hours of practice on this repertoire
- **30-Day Challenge** - Practice every day for 30 days
- **Speed Run** - Master all songs in the repertoire within X weeks
- **Weekly Time Goal** - Hit X minutes of practice per week

### 3. **Song Mastery Challenges**
- **Complete the Set** - Master all songs in the repertoire
- **Song of the Week** - Focus on one song until mastered, then move to next
- **No Song Left Behind** - Practice every song at least once per week
- **Perfect 10** - Get 10 songs to 100% mastery

### 4. **Performance Challenges**
- **Stage Ready** - Prepare X songs for live performance
- **Full Setlist** - Be able to play through the entire repertoire without stopping
- **Memorization Challenge** - Memorize X songs completely (no charts needed)
- **Tempo Master** - Play all songs at full tempo

### 5. **Progress Challenges**
- **Level Up** - Improve average repertoire mastery by X%
- **Skill Collector** - Master X skills across all songs in repertoire
- **Weakness Crusher** - Improve your lowest-rated song by 50%
- **Balanced Practice** - Keep all songs within 20% mastery of each other

### 6. **Fun/Social Challenges**
- **Jam Session Ready** - Learn 5 songs others can play along with
- **Genre Explorer** - Add and learn songs from 3 different styles
- **Throwback Week** - Only practice songs you haven't touched in 30+ days
- **Random Roulette** - Practice a randomly selected song each day for a week

---

## Suggested Data Model

```
Challenge:
- id: Integer (Primary Key)
- name: String (e.g., "30-Day Streak")
- description: String (Detailed explanation)
- type: Enum (streak, time, mastery, performance, progress)
- target_value: Integer (e.g., 30 for 30 days, 10 for 10 hours)
- target_unit: String (days, hours, songs, percent)
- repertoire_id: Foreign Key → Repertoire
- user_id: Foreign Key → User
- start_date: DateTime
- end_date: DateTime (optional, for time-limited challenges)
- current_progress: Integer
- status: Enum (active, completed, failed, paused)
- created_at: DateTime
- completed_at: DateTime (nullable)
```

---

## UI/UX Ideas

### In Edit Repertoire View
- "Add Challenge" button below existing skills section
- Challenge picker modal with categories
- Option to create custom challenges
- Show active challenges with progress bars

### Challenge Display
- Progress indicator (e.g., "Day 12/30" or "7.5/10 hours")
- Visual streak calendar for streak-based challenges
- Celebration animation on completion
- Badge/trophy system for completed challenges

### Notifications/Reminders
- Daily reminder if streak is at risk
- Congratulations on milestone progress (50%, 75%, etc.)
- Weekly summary of challenge progress

---

## MVP Recommendation

For initial implementation, start with these 3 challenge types:

1. **Daily Streak** - Simple and highly motivating
2. **Practice Time Goal** - Easy to track with existing practice logging
3. **Song Mastery Count** - Ties into existing mastery tracking

---

## Questions to Consider

1. Should challenges be pre-defined templates or fully customizable?
2. What happens when a streak breaks? Grace period? Restart option?
3. Should completed challenges give rewards (badges, points)?
4. Can multiple challenges be active on the same repertoire?
5. Should there be "community challenges" that all users can join?

---

## Next Steps

1. Review and select which challenge types to implement first
2. Design database schema for challenges
3. Create API endpoints for challenge CRUD operations
4. Build UI components in edit repertoire view
5. Implement progress tracking logic
6. Add notifications/reminders system
