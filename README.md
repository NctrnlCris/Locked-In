# Locked-In
## What is Locked-In?
- Locked-In is your friendly productivity companion designed to solve one major problem: getting distracted on your computer        without realizing it. Let's be honest—sometimes you open your laptop to work, and an hour later you're deep in YouTube rabbit holes, scrolling Discord, or juggling too many apps at once.
- This app keeps you accountable. It monitors your screen periodically to see what you’re working on and nudges you with a fun or increasingly aggressive reminder if it detects distractions. It adapts to your workflow by letting you choose a profile (like Student, Developer, Writer) or customize your own that defines which apps are productive for you.
## Key Features
- **Automatic Screenshots:** The app takes screenshots every 15 seconds, keeping a rolling record of your recent activity. It stores only the last 10 screenshots to keep things lightweight.
- **Distraction Detection:** Using a Visual Language Model (VLM), Locked-In can analyze your screenshots and determine if you’re being productive. If it thinks you’re distracted, a pop-up will gently remind you to lock in.
- **Profile-Based Productivity:** Pick an archetype that matches your work style or customize your own. Choosing or customizing a profile helps the VLM accurately assess if what your looking it is truly productive.
- **Locally stored data:** All of your browsing is stored locally on your system's drive, so theres no privacy concerns regarding cloud breaches.
- **Fun & Interactice Pop-Ups:** The reminders aren’t just boring alerts — they start friendly, but if you keep getting distracted, the default emoticon and message gradually become more assertive (and a little angrier 😤). It’s a playful but effective way to keep you accountable and push you to truly lock in.
## Tech Stack
- **The Interface (PyQt6)** Handles the GUI including the dashboard and pop-ups in a clean and responsive desktop app.
- **Screenshot Engine (mss + Python):** Efficiently captures your screen every 15 seconds and manages the storage of recent screenshots.
- **Persistence (JSON):** Keeps track of your profile from subsequent uses and handles VLM output
- **AI Integration (VLM):** A Visual Language Model can analyze screenshots and determine if the user is distracted, enabling fun pop-ups.

