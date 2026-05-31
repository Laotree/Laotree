#!/usr/bin/env python3
"""Fetch the last 30 days of public GitHub activity and update README.md."""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ.get("GITHUB_USERNAME", "Laotree")
README_PATH = os.environ.get("README_PATH", "README.md")
START_MARKER = "<!-- ACTIVITY_START -->"
END_MARKER = "<!-- ACTIVITY_END -->"


def api_get(path, params=None):
    url = f"https://api.github.com{path}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = Request(
        url,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(req) as r:
            return json.loads(r.read())
    except HTTPError as e:
        print(f"API error {e.code} on {path}")
        return {}


def main():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)

    raw_events = api_get(f"/users/{USERNAME}/events/public", {"per_page": "100"})
    if not isinstance(raw_events, list):
        raw_events = []

    recent = [
        e for e in raw_events
        if datetime.fromisoformat(e["created_at"].replace("Z", "+00:00")) > cutoff
    ]

    push_events = [e for e in recent if e["type"] == "PushEvent"]
    pr_merged_events = [
        e for e in recent
        if e["type"] == "PullRequestEvent"
        and e["payload"].get("pull_request", {}).get("merged")
    ]
    release_events = [e for e in recent if e["type"] == "ReleaseEvent"]

    total_commits = sum(len(e["payload"].get("commits", [])) for e in push_events)
    active_repos = sorted({e["repo"]["name"] for e in push_events})

    month = now.strftime("%B %Y")
    lines = [f"## Recent Activity — {month}", ""]

    stats = []
    if total_commits:
        stats.append(f"**{total_commits}** commit{'s' if total_commits != 1 else ''}")
    if pr_merged_events:
        n = len(pr_merged_events)
        stats.append(f"**{n}** PR{'s' if n != 1 else ''} merged")
    if release_events:
        n = len(release_events)
        stats.append(f"**{n}** release{'s' if n != 1 else ''} published")
    if stats:
        lines.append("  ·  ".join(stats))
        lines.append("")

    if active_repos:
        lines.append("### Recently pushed")
        lines.append("")
        lines.append("| Repository | Description | Language |")
        lines.append("|---|---|---|")
        for repo_full in active_repos[:8]:
            repo = api_get(f"/repos/{repo_full}")
            if isinstance(repo, dict) and repo.get("name"):
                name = repo["name"]
                url = repo.get("html_url", f"https://github.com/{repo_full}")
                desc = (repo.get("description") or "").replace("|", "\\|")
                lang = repo.get("language") or ""
                lines.append(f"| [{name}]({url}) | {desc} | {lang} |")
        lines.append("")

    if pr_merged_events:
        lines.append("### Merged pull requests")
        lines.append("")
        for e in pr_merged_events[:5]:
            pr = e["payload"]["pull_request"]
            title = pr.get("title", "").replace("|", "\\|")
            url = pr.get("html_url", "")
            repo_name = e["repo"]["name"].split("/")[-1]
            lines.append(f"- [{repo_name}: {title}]({url})")
        lines.append("")

    if release_events:
        lines.append("### Releases")
        lines.append("")
        for e in release_events[:5]:
            release = e["payload"]["release"]
            repo_name = e["repo"]["name"].split("/")[-1]
            tag = release.get("tag_name", "")
            url = release.get("html_url", "")
            lines.append(f"- [{repo_name} {tag}]({url})")
        lines.append("")

    lines.append(
        f"*Auto-generated on {now.strftime('%Y-%m-%d')} "
        f"· [workflow](/.github/workflows/monthly-summary.yml)*"
    )
    lines.append("")
    lines.append("![Activity](https://llp-chart.laotree.workers.dev/chart/2f183a4e64493af3.svg)")

    summary = "\n".join(lines)

    with open(README_PATH) as f:
        content = f.read()

    pattern = re.compile(
        f"{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}",
        re.DOTALL,
    )
    if not pattern.search(content):
        print("Error: activity markers not found in README")
        raise SystemExit(1)

    replacement = f"{START_MARKER}\n\n{summary}\n\n{END_MARKER}"
    new_content = pattern.sub(replacement, content)

    with open(README_PATH, "w") as f:
        f.write(new_content)

    print(f"Updated README with {month} activity summary")


if __name__ == "__main__":
    main()
