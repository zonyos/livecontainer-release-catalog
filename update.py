"""Refresh the LiveContainer catalogue from the projects' public release metadata."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path


PROJECTS = (
    ("huamidev/GestaltX", "com.huami.gestultx"),
    ("jailbreakdotparty/Erosion", "com.jbdotparty.Erosion"),
)


def latest_entry(repository, bundle_id):
    response = subprocess.check_output([
        "curl", "--fail", "--silent", "--show-error", "--location",
        "--max-time", "30", "--retry", "2",
        f"https://api.github.com/repos/{repository}/releases/latest",
    ])
    release = json.loads(response)
    tag = release["tag_name"]
    if not tag or release["draft"] or release["prerelease"]:
        raise ValueError(f"Expected a published release for {repository}")
    day = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00")).date()
    author, name = repository.split("/")
    return {
        "name": name,
        "bundleIdentifier": bundle_id,
        "developerName": author,
        "subtitle": f"官方版本 {tag} · {day} UTC",
        "localizedDescription": f"版本公告来自 {release['html_url']}",
    }


def main():
    source = {
        "name": "GestaltX 与 Erosion 更新",
        "identifier": "personal.gestaltx.erosion.releases",
        "subtitle": "官方正式版公告",
        "description": "在每个应用的副标题查看官方最新版本及发布日期。",
        "apps": [latest_entry(repo, bundle) for repo, bundle in PROJECTS],
    }
    output = Path(__file__).with_name("source.json")
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


if __name__ == "__main__":
    main()
