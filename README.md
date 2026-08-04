# Copperia Bot

Copperia Bot is a Python Discord bot developed by **linkoro57**.

## Features

- Sends the server rules once in the rules channel
- Sends a welcome embed when a new member joins
- Updates the voice channel name with the current non-bot member count
- Monitors the anti-scam channel and automatically punishes users who post there
- Provides a ticket system with category selection, claim, and delete actions

## Project Structure

- `main.py`: application entry point
- `src/bot.py`: main bot logic
- `src/config.py`: static channel and server configuration
- `src/storage.py`: persistent JSON state handling

## Requirements

- Python 3.11 or newer recommended
- A Discord bot token
- The target Discord server ID

## Installation

```powershell
cd "C:\Users\user\OneDrive\Documents\Copperia Bot"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Environment Setup

Create a `.env` file based on `.env.example`:

```env
DISCORD_TOKEN=your_discord_bot_token_here
GUILD_ID=your_discord_server_id_here
```

## Run

```powershell
cd "C:\Users\user\OneDrive\Documents\Copperia Bot"
.\.venv\Scripts\activate
python main.py
```

## Required Discord Permissions

The bot should have at least:

- View Channels
- Send Messages
- Embed Links
- Manage Messages
- Manage Channels
- Ban Members
- Read Message History
- Manage Permissions

Enable these privileged intents in the Discord Developer Portal as well:

- `Server Members Intent`
- `Message Content Intent`

## Notes

- The bot stores its persistent state in `data/state.json`
- Welcome messages are sent to the dedicated welcome channel configured in `src/config.py`
- The warning about `PyNaCl` is not blocking unless you plan to add voice features
