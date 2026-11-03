"""Публикация сводки в GitHub Issue через REST API."""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
MAX_BODY = 60_000


class GitHubError(Exception):
    pass


def resolve_repo() -> str | None:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo.strip()
    try:
        out = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", out)
    return m.group(1) if m else None


def resolve_token() -> str | None:
    for key in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(key):
            return os.environ[key].strip()
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=15
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


class Client:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            API + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "overwatch-digest",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise GitHubError(f"{method} {path} → {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubError(f"{method} {path} → {exc.reason}") from exc

    def find_issue(self, title: str) -> dict | None:
        # Ищем по заголовку: метка может быть не создана в репозитории.
        query = urllib.parse.quote(f'repo:{self.repo} in:title "{title}"')
        try:
            data = self._request("GET", f"/search/issues?q={query}&per_page=20")
            for issue in data.get("items", []):
                if not isinstance(issue, dict) or issue.get("pull_request"):
                    continue
                if issue.get("title", "").strip() == title.strip():
                    return issue
        except GitHubError:
            pass

        issues = self._request("GET", f"/repos/{self.repo}/issues?state=all&per_page=100")
        for issue in issues:
            if issue.get("pull_request"):
                continue
            if issue.get("title", "").strip() == title.strip():
                return issue
        return None

    def upsert_issue(self, title: str, body: str, label: str | None) -> tuple[str, str]:
        body = body[:MAX_BODY]
        issue = self.find_issue(title)
        if issue is None:
            payload = {"title": title, "body": body}
            if label:
                payload["labels"] = [label]
            try:
                created = self._request("POST", f"/repos/{self.repo}/issues", payload)
            except GitHubError:
                # Метки может не быть в репозитории — создаём без неё.
                created = self._request(
                    "POST", f"/repos/{self.repo}/issues", {"title": title, "body": body}
                )
            return "created", created.get("html_url", "")

        number = issue["number"]
        if issue.get("state") == "closed":
            self._request("PATCH", f"/repos/{self.repo}/issues/{number}", {"state": "open"})
        if issue.get("body", "") != body:
            updated = self._request("PATCH", f"/repos/{self.repo}/issues/{number}", {"body": body})
            return "updated", updated.get("html_url", issue.get("html_url", ""))
        return "unchanged", issue.get("html_url", "")


def publish(body: str, *, title: str, label: str | None) -> tuple[str, str]:
    repo = resolve_repo()
    token = resolve_token()
    if not repo or not token:
        raise GitHubError(
            "Не найдены репозиторий или токен. Нужны GITHUB_REPOSITORY и GITHUB_TOKEN "
            "(локально достаточно `gh auth login`)."
        )
    return Client(repo, token).upsert_issue(title, body, label)
