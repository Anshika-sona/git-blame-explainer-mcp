# Git Blame Explainer MCP

An MCP (Model Context Protocol) server that explains **why** any line of code exists — by tracing its git history and fetching the original Pull Request from GitHub.

## What it does

Instead of manually running `git blame` and searching through commits, just ask Claude Desktop in plain English:

> "Explain line 42 of auth.py in this repo"

Claude will automatically:
1. Run `git blame` to find which commit last changed that line
2. Fetch the full commit message
3. Find the original GitHub Pull Request
4. Return a plain English explanation of why that line exists

## Demo

![Demo screenshot](https://github.com/Anshika-sona/git-blame-explainer-mcp/blob/main/Screenshot%202026-03-29%20154707.png)

## Tools

| Tool | What it does |
|------|-------------|
| `explain_line` | Runs git blame and returns commit details for any line |
| `get_commit_context` | Finds the GitHub PR linked to a commit |
| `full_blame_report` | Combines both into one complete explanation |

## Setup

**1. Clone the repo**
```
git clone https://github.com/YourUsername/git-blame-explainer-mcp.git
cd git-blame-explainer-mcp
```

**2. Install dependencies**
```
pip install mcp requests python-dotenv
```

**3. Get a GitHub token**
- Go to github.com → Settings → Developer settings → Personal access tokens
- Create a token with `repo` scope

**4. Add your token to Claude Desktop config**
```json
{
  "mcpServers": {
    "git-blame-explainer": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": {
        "GITHUB_TOKEN": "your_token_here"
      }
    }
  }
}
```

**5. Restart Claude Desktop** and look for the tool in the + menu

## Tech stack

- Python
- MCP (Model Context Protocol) by Anthropic
- GitHub REST API
- asyncio for non-blocking git commands

## Built by

Anshika — SDE fresher learning AI agent development
```
