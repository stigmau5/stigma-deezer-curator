# STiGMA Deezer Curator

STiGMA Deezer Curator is a small, personal Python tool for **curating Deezer links** and handing them off cleanly to **streamrip**.

It is intentionally boring, explicit, and transparent.

No daemons.  
No background magic.  
No guessing what ran or what failed.

If something happens, you can see it.  
If something breaks, you know where and why.

---

## What problem does this solve?

If you collect Deezer links over time, you’ve probably run into:

- duplicate runs
- guessing which artist or album failed
- messy text files full of mixed content
- re-downloading things you already processed
- “did I already run this?” anxiety

This tool fixes that by introducing **curation with receipts**.

---

## Core ideas

- **Curation first, execution later**
- **Every handoff leaves a trace**
- **Files are the source of truth**
- **If you can’t explain it later, it’s not good enough**

STiGMA Deezer Curator prepares *clean intent*.  
streamrip executes it.

Each tool does one job well.

---

## Features

### ✅ Inbox-based curation
- Paste raw Deezer links (albums or artists) into `data/inbox.txt`
- Artist links are expanded via the Deezer API
- Already processed content is skipped automatically

### ✅ Artist-based output
- Each artist gets their own `.txt` file
- Easy to inspect, verify, and reason about
- No duplicates, no surprises

### ✅ GUI workbench
- Artist list on the left
- Main panel switches between:
  - Artist view (read-only)
  - Inbox view (editable)
- Streamrip queue always visible on the right

### ✅ Streamrip handoff (terminal-based)
- One-click **Send to streamrip**
- Opens your **default terminal** (Tilix, GNOME Terminal, etc.)
- Runs streamrip interactively with full progress and error output
- No background execution, no hidden state

### ✅ Clean execution queues
- Mixed text is allowed while editing
- Before sending, the queue is stripped to **URLs only**
- streamrip only ever sees valid links

### ✅ Immutable shipping history
Every streamrip run is archived automatically:


This gives you:
- a permanent audit trail
- proof of what was sent
- zero “did I already run this?” doubt

---

## What this tool is NOT

- ❌ Not a downloader
- ❌ Not a daemon
- ❌ Not a background service
- ❌ Not a scraper crawler
- ❌ Not an all-in-one music manager

It deliberately stops at the handoff.

---

## Requirements

- Python 3.10+
- Debian / Linux Mint (tested)
- `streamrip` installed in a virtual environment
- Internet connection (for Deezer API lookups)

---

## Project structure


---

## Typical workflow

1. Paste Deezer links into **Inbox**
2. Run curator
3. Inspect artist files if needed
4. Copy desired album links into the streamrip queue
5. Click **Send to streamrip**
6. Watch streamrip do its thing in the terminal
7. Enjoy music, sleep well

---

## Philosophy

This project exists because:

- clarity beats cleverness
- explicit state beats hidden automation
- files beat databases for personal tools
- trust matters more than speed

If you’re looking for maximum automation, this is not for you.

If you want calm, explainable tooling that respects your time and memory — welcome.

---

## License

Personal use.  
Do whatever you want with it.

If it helps you think more clearly, that’s the real win.

## Why this exists

This tool exists because most workflows fail in quiet, annoying ways.

Not catastrophically — just enough to make you doubt:
- *Did I already run this?*
- *Which artist failed?*
- *Did this link ever get processed?*
- *What did I hand off, exactly?*

STiGMA Deezer Curator exists to remove that uncertainty.

It trades automation for **clarity**, and convenience for **trust**.
Every step leaves a trace. Every decision is visible. Nothing runs behind your back.

It’s built for one person solving a real problem — and that’s intentional.
