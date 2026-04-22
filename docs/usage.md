# Usage Guide

## Prerequisites

1. Python 3.10+ recommended (3.9 works but shows deprecation warnings)
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in all four values:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_APP_TOKEN=xapp-...
   GEMINI_API_KEY=...
   SLACK_CHANNEL_ID=C...
   ```

## Slack App Setup

If you haven't created the Slack app yet:

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. **Enable Socket Mode** (under *Settings*) → generate an App-Level Token with `connections:write` scope → this is your `SLACK_APP_TOKEN`
3. Under **OAuth & Permissions**, add these Bot Token Scopes:
   - `channels:history`
   - `chat:write`
   - `groups:history`
4. Under **Event Subscriptions** → **Subscribe to Bot Events**, add:
   - `message.channels`
   - `message.groups`
5. **Install to Workspace** → copy the Bot User OAuth Token → this is your `SLACK_BOT_TOKEN`
6. Invite the bot to your dedicated channel: `/invite @<bot-name>`
7. Copy the channel ID (right-click the channel → *View channel details* → bottom of the modal) → this is your `SLACK_CHANNEL_ID`

## Adding Knowledge Documents

1. Place Markdown files in `docs/`. Each top-level heading (`##`) becomes a searchable section.
2. Run the indexer:
   ```bash
   python3 index.py
   ```
   This creates a corresponding `docs/indexes/<filename>.index.md` for each document. Re-run whenever you add or update a document.

## Starting the Bot

```bash
python3 bot.py
```

The bot will print `Bot is running. Listening for messages...` and begin listening. Send any message to your dedicated Slack channel — the bot replies in-thread.

## How It Works

1. A message arrives in the configured channel.
2. The bot calls Gemini with all index files to find relevant `(document, section)` pairs.
3. It reads those sections verbatim from the source `.md` files.
4. It calls Gemini again to generate an answer with a blockquote from the source.
5. The answer is posted as a thread reply.

If no relevant section is found, the bot replies: *"I couldn't find information on this topic in the knowledge base."*

## Document Format

Knowledge documents should use `##` headings for top-level sections. Sub-headings (`###`) are supported and will be included when their parent section is retrieved.

```markdown
## Section Title

Content of the section...

### Sub-section

More detail...

## Another Section

...
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `GEMINI_API_KEY is not set` | Check `.env` exists and has the key |
| `KeyError: SLACK_BOT_TOKEN` | Check `.env` has all four Slack values |
| Bot doesn't respond | Confirm the channel ID matches and the bot is invited to the channel |
| `No index files found` | Run `python3 index.py` first |
| Gemini quota error | Free tier is 20 requests/day — wait until the next day or upgrade |
