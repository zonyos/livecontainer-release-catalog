"""Refresh the LiveContainer catalogue from the projects' public release metadata."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path


# downloadURL 为官方最新版附件地址，XXXX 表示只展示发布信息。
PROJECTS = (
    {
        # 官方发布页 https://github.com/huamidev/GestaltX/releases/latest
        "repository": "huamidev/GestaltX",
        "bundleIdentifier": "com.huami.gestultx",
        "downloadURL": "XXXX",
    },
    {
        # 官方发布页 https://github.com/jailbreakdotparty/Erosion/releases/latest
        "repository": "jailbreakdotparty/Erosion",
        "bundleIdentifier": "com.jbdotparty.Erosion",
        "downloadURL": "XXXX",
    },
    {
        # 官方发布页 https://github.com/Lakr233/Asspp/releases/latest
        "repository": "Lakr233/Asspp",
        "bundleIdentifier": "wiki.qaq.Asspp",
        "downloadURL": "https://github.com/Lakr233/Asspp/releases/latest/download/Asspp.ipa",
        "publishIPA": True,
    },
)


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


def release_asset(project, release, releases_url):
    configured_url = project["downloadURL"]
    latest_prefix = releases_url + "latest/download/"
    if not configured_url.startswith(latest_prefix):
        raise ValueError(f"Expected a latest-release asset URL for {project['repository']}")
    preferred_name = configured_url.removeprefix(latest_prefix).casefold()
    packages = [
        asset for asset in release["assets"]
        if asset["name"].casefold().endswith(".ipa") and asset["state"] == "uploaded" and asset["size"] > 0
    ]
    if not packages:
        return None
    if len(packages) > 1:
        packages = [asset for asset in packages if asset["name"].casefold() == preferred_name]
        if len(packages) != 1:
            raise ValueError(f"Ambiguous IPA for {project['repository']}")

    asset = packages[0]
    if not asset["browser_download_url"].startswith(releases_url + "download/"):
        raise ValueError(f"Unverified download origin for {project['repository']}")
    return asset


def catalogue_entry(project, release, previous_apps):
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
    }
    if not project.get("publishIPA", False) or project["downloadURL"] == "XXXX":
        return entry

    releases_url = f"https://github.com/{project['repository']}/releases/"
    asset = release_asset(project, release, releases_url)
    if asset:
        entry.update(downloadURL=asset["browser_download_url"], size=asset["size"])
    else:
        previous = previous_apps.get(bundle, {})
        if previous.get("downloadURL", "").startswith(releases_url + "download/"):
            return previous
        raise ValueError(f"No published IPA or previous downloadable entry for {name}")
    return entry


def main():
    output = Path(__file__).with_name("source.json")
    previous_entries = json.loads(output.read_text(encoding="utf-8"))["apps"] if output.exists() else []
    previous_apps = {app["bundleIdentifier"]: app for app in previous_entries}
    apps = []
    for project in PROJECTS:
        release = latest_release(project["repository"])
        apps.append(catalogue_entry(project, release, previous_apps))
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
