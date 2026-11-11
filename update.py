"""Refresh the LiveContainer catalogue from the projects' public release metadata."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit


PROJECTS = (
    {
        # 官方发布页 https://github.com/huamidev/GestaltX/releases/latest
        "repository": "huamidev/GestaltX",
        "bundleIdentifier": "com.huami.gestultx",
    },
    {
        # 官方发布页 https://github.com/jailbreakdotparty/Erosion/releases/latest
        "repository": "jailbreakdotparty/Erosion",
        "bundleIdentifier": "com.jbdotparty.Erosion",
    },
    {
        # 官方发布页 https://github.com/Lakr233/Asspp/releases/latest
        "repository": "Lakr233/Asspp",
        "bundleIdentifier": "wiki.qaq.Asspp",
    },
)

# 这两个项目沿用现有的版本公告模式。
VERSION_ONLY_REPOSITORIES = {"huamidev/GestaltX", "jailbreakdotparty/Erosion"}


def latest_release(repository):
    response = subprocess.check_output([
        "curl", "--fail", "--silent", "--show-error", "--location",
        "--max-time", "30", "--retry", "2",
        f"https://api.github.com/repos/{repository}/releases/latest",
    ])
    release = json.loads(response)
    tag = release["tag_name"]
    if not tag or release["draft"] or release["prerelease"]:
        raise ValueError(f"Expected a published release for {repository}")
    return release


def release_asset(repository, release):
    packages = [
        asset for asset in release["assets"]
        if asset["name"].casefold().endswith(".ipa") and asset["state"] == "uploaded" and asset["size"] > 0
    ]
    if len(packages) > 1:
        preferred_name = repository.split("/")[1].casefold() + ".ipa"
        packages = [asset for asset in packages if asset["name"].casefold() == preferred_name]
    if len(packages) != 1:
        return None

    asset = packages[0]
    url = urlsplit(asset["browser_download_url"])
    expected_path = f"/{repository}/releases/download/{release['tag_name']}/{asset['name']}"
    if url.scheme != "https" or url.netloc != "github.com" or unquote(url.path) != expected_path:
        return None
    return asset


def catalogue_entry(project, release):
    author, name = project["repository"].split("/")
    tag = release["tag_name"]
    published = release["published_at"]
    day = datetime.fromisoformat(published.replace("Z", "+00:00")).date()
    bundle = project["bundleIdentifier"]
    entry = {
        "name": name,
        "bundleIdentifier": bundle,
        "developerName": author,
        "subtitle": f"官方版本 {tag} · {day} UTC",
        "localizedDescription": f"版本公告来自 {release['html_url']}",
        "version": tag.removeprefix("v"),
        "versionDate": published,
        "downloadURL": "XXXX",
    }
    if project["repository"] not in VERSION_ONLY_REPOSITORIES:
        asset = release_asset(project["repository"], release)
        if asset:
            entry.update(downloadURL=asset["browser_download_url"], size=asset["size"])
    entry["subtitle"] = f"downloadURL: {entry['downloadURL']} · {entry['subtitle']}"
    return entry


def main():
    output = Path(__file__).with_name("source.json")
    apps = []
    for project in PROJECTS:
        release = latest_release(project["repository"])
        apps.append(catalogue_entry(project, release))
    names = [app["name"] for app in apps]
    title = "、".join(names[:-1]) + " 与 " + names[-1] if len(names) > 1 else "".join(names)
    source = {
        "name": f"{title} 更新".strip(),
        "identifier": "personal.gestaltx.erosion.releases",
        "subtitle": "官方正式版公告",
        "description": "在每个应用的副标题查看官方最新版本及发布日期。",
        "apps": apps,
    }
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


if __name__ == "__main__":
    main()
