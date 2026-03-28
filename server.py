# ─────────────────────────────────────────────
# server.py  —  Git Blame Explainer MCP Server
# ─────────────────────────────────────────────

# These lines import libraries — code written by other people that we reuse
from mcp.server.fastmcp import FastMCP  # Anthropic's MCP library
import subprocess   # lets us run terminal commands (like git) from Python
import requests     # lets us make internet API calls (to GitHub)
import os           # lets us read environment variables (our secret token)
from dotenv import load_dotenv
load_dotenv()

# Create the MCP server and give it a name
# This name shows up in Claude Desktop so you know which server is connected
mcp = FastMCP("Git Blame Explainer")

# Read your GitHub token from the .env environment variable
# We never write the token directly in code — that's a security risk
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


# @mcp.tool() tells the MCP library:
# "this function is a tool that Claude is allowed to call"
@mcp.tool()
def explain_line(file_path: str, line_number: int, repo_path: str = ".") -> str:
    """
    Explain why a specific line of code exists.
    Finds which commit last changed this line and returns the commit message.

    file_path  : path to the file, e.g. 'src/auth/middleware.py'
    line_number: the line number you want to understand, e.g. 42
    repo_path  : full path to the git repo folder on your computer
    """

    # subprocess.run() runs a terminal command from inside Python
    # This runs:  git blame -L 42,42 --porcelain src/auth/middleware.py
    # -L 42,42    means: only look at line 42
    # --porcelain means: give detailed machine-readable output
    blame_result = subprocess.run(
        ["git", "blame", "-L", f"{line_number},{line_number}", "--porcelain", file_path],
        cwd=repo_path,        # run git inside this repo folder
        capture_output=True,  # capture the output so we can read it in Python
        text=True             # return output as a string not raw bytes
    )

    # If git returned an error, tell the user clearly
    if blame_result.returncode != 0:
        return f"Git error: {blame_result.stderr.strip()}"

    output_lines = blame_result.stdout.splitlines()

    if not output_lines:
        return "No git blame output returned. Is this a git repository?"

    # The first line of git blame --porcelain output looks like:
    # a3f8c91d2b4e5f6a  3  42  1
    # The first part before the space is the commit hash — unique ID for that commit
    commit_hash = output_lines[0].split()[0]

    # Now fetch the full commit message for that hash
    # git log -1 means: show only 1 commit
    # --pretty=format: controls exactly what info we get back
    log_result = subprocess.run(
        [
            "git", "log", "-1",
            "--pretty=format:Author: %an%nDate: %ad%nCommit: %H%nMessage: %s%n%nFull description:%n%b",
            commit_hash
        ],
        cwd=repo_path,
        capture_output=True,
        text=True
    )

    if log_result.returncode != 0:
        return f"Could not fetch commit details: {log_result.stderr.strip()}"

    return (
        f"Line {line_number} of '{file_path}' was last changed in:\n\n"
        f"{log_result.stdout.strip()}"
    )
# ── TOOL 2: get_commit_context ────────────────────────────────────────────
@mcp.tool()
def get_commit_context(commit_hash: str, github_repo: str) -> str:
    """
    Given a commit hash and GitHub repo name, finds the Pull Request
    that introduced this commit and returns its full description.

    commit_hash : the short or full hash, e.g. 'a3f8c91'
    github_repo : in format 'owner/reponame', e.g. 'django/django'
    """

    # Every GitHub API call needs these headers
    # Authorization proves you are you using your token
    # Accept tells GitHub which version of their API response format we want
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # We search GitHub for any Pull Request mentioning this commit hash
    # The GitHub Search API is like Google but specifically for GitHub data
    search_url = (
        f"https://api.github.com/search/issues"
        f"?q={commit_hash}+repo:{github_repo}+type:pr"
    )

    # requests.get() makes an HTTP call to that URL
    # exactly like your browser visiting a webpage, but in Python code
    response = requests.get(search_url, headers=headers)

    # Status code 200 means success
    # 403 means your token is wrong or expired
    # 422 means the request was badly formed
    if response.status_code != 200:
        return (
            f"GitHub API error {response.status_code}.\n"
            f"If 403: your token may be invalid or expired.\n"
            f"Details: {response.text[:300]}"
        )

    # Parse the JSON response into a Python dictionary
    data = response.json()

    # 'items' is the list of matching PRs GitHub found
    if not data.get("items"):
        return (
            f"No Pull Request found mentioning commit {commit_hash[:8]}.\n"
            f"This can happen if the commit was pushed directly without a PR."
        )

    # Take the first result — most relevant match
    pr          = data["items"][0]
    pr_number   = pr["number"]
    pr_title    = pr["title"]
    pr_body     = pr.get("body") or "No description was written for this PR."
    pr_author   = pr["user"]["login"]
    pr_date     = pr["created_at"][:10]

    # Fetch the top 3 comments on this PR for extra context
    comments_url = (
        f"https://api.github.com/repos/{github_repo}"
        f"/issues/{pr_number}/comments"
    )
    comments_response = requests.get(comments_url, headers=headers)

    comments_text = ""
    if comments_response.status_code == 200:
        comments = comments_response.json()[:3]
        for i, comment in enumerate(comments, start=1):
            author = comment["user"]["login"]
            body   = comment["body"][:400]
            comments_text += f"\n--- Comment {i} by {author} ---\n{body}\n"

    return (
        f"PR #{pr_number}: {pr_title}\n"
        f"Author: {pr_author}  |  Date: {pr_date}\n\n"
        f"=== PR Description ===\n{pr_body[:800]}\n\n"
        f"=== Top Comments ==={comments_text if comments_text else ' None'}"
    )

# ── TOOL 3: full_blame_report ─────────────────────────────────────────────
@mcp.tool()
def full_blame_report(
    file_path: str,
    line_number: int,
    github_repo: str,
    repo_path: str = "."
) -> str:
    """
    The complete story of one line of code.
    Combines git history + GitHub PR context into one single answer.
    This is the main tool to use for any 'why does this line exist?' question.

    file_path   : path to the file inside the repo, e.g. 'src/auth.py'
    line_number : the line number to investigate
    github_repo : GitHub repo in format 'owner/reponame'
    repo_path   : full path to the repo folder on your computer
    """

    # Step 1 — call Tool 1 to get the git blame info
    # This runs git blame and git log and returns commit details
    blame_info = explain_line(file_path, line_number, repo_path)

    # Step 2 — extract the commit hash from what Tool 1 returned
    # Our explain_line function returns a line that says "Commit: a3f8c91d..."
    # We loop through the lines to find it and grab just the hash part
    commit_hash = None
    for line in blame_info.split("\n"):
        if line.startswith("Commit:"):
            commit_hash = line.replace("Commit:", "").strip()[:8]
            break

    # If we couldn't find the hash, return what we have and explain why
    if not commit_hash:
        return (
            f"Could not extract commit hash from blame output.\n\n"
            f"Blame info we got:\n{blame_info}"
        )

    # Step 3 — call Tool 2 with that commit hash to get the GitHub PR context
    # This hits the GitHub API and returns the PR title, description, comments
    pr_info = get_commit_context(commit_hash, github_repo)

    # Step 4 — combine both results into one clean report
    return (
        f"{'='*50}\n"
        f"FULL STORY: Line {line_number} of {file_path}\n"
        f"{'='*50}\n\n"
        f"=== GIT HISTORY ===\n{blame_info}\n\n"
        f"=== GITHUB PR CONTEXT ===\n{pr_info}"
    )

# This block runs your server when you type: python server.py
if __name__ == "__main__":
    mcp.run()
