"""Refresh the LiveContainer catalogue from the projects' public release metadata."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit


MAX_RELEASES = 5  # 每个项目最多拉取多少个正式版（1 个最新版进 source.json，其余旧版进 history.json）
SOURCE_ICON_URL = (
    "https://raw.githubusercontent.com/LiveContainer/LiveContainer/main/"
    "Resources/Assets.xcassets/AppIcon.appiconset/AppIcon1024.png"
)


def published_releases(repository, limit=MAX_RELEASES):
    response = subprocess.check_output([
        "curl", "--fail", "--silent", "--show-error", "--location",
        "--max-time", "30", "--retry", "2",
        f"https://api.github.com/repos/{repository}/releases?per_page={limit}",
    ])
    releases = [
        release for release in json.loads(response)
        if release.get("tag_name") and not release.get("draft") and not release.get("prerelease")
    ]
    if not releases:
        raise ValueError(f"Expected at least one published release for {repository}")
    return releases


def release_asset(repository, release, preferred_filename):
    packages = [
        asset for asset in release["assets"]
        if asset["name"].casefold().endswith(".ipa") and asset["state"] == "uploaded" and asset["size"] > 0
    ]
    if len(packages) > 1:
        stem = preferred_filename.removesuffix(".ipa").casefold()
        standard = [asset for asset in packages if asset["name"].casefold() == stem + ".ipa"]
        if standard:
            packages = standard
        else:
            tag = release["tag_name"].casefold()
            names = {
                f"{stem}{separator}{version}.ipa"
                for separator in ("-", "_", ".", " ")
                for version in (tag, tag.removeprefix("v"))
            }
            packages = [asset for asset in packages if asset["name"].casefold() in names]
    if len(packages) != 1:
        return None

    asset = packages[0]
    url = urlsplit(asset["browser_download_url"])
    expected_path = f"/{repository}/releases/download/{release['tag_name']}/{asset['name']}"
    if url.scheme != "https" or url.netloc != "github.com" or unquote(url.path) != expected_path:
        return None
    return asset


def catalogue_entries(project):
    repository = project["repository"]
    author, name = repository.split("/")
    bundle = project["bundleIdentifier"]
    icon_url = project.get("iconURL", f"https://github.com/{author}.png")

    configured_url = project.get("downloadURL")
    preferred_filename = name + ".ipa"
    if configured_url:
        latest_prefix = f"https://github.com/{repository}/releases/latest/download/"
        if not configured_url.startswith(latest_prefix):
            raise ValueError(f"Expected an official latest-release link for {name}")
        preferred_filename = unquote(configured_url.removeprefix(latest_prefix))

    entries = []
    versions = []
    for release in published_releases(repository):
        asset = release_asset(repository, release, preferred_filename)
        if not asset:
            continue
        tag = release["tag_name"]
        published = release["published_at"]
        day = datetime.fromisoformat(published.replace("Z", "+00:00")).date()
        version_str = tag.removeprefix("v")
        description = f"版本公告来自 {release['html_url']}"
        download_url = asset["browser_download_url"]
        size = asset["size"]

        is_latest = len(entries) == 0
        entries.append({
            "name": name if is_latest else f"{name} ({tag})",
            "bundleIdentifier": bundle,
            "developerName": author,
            "subtitle": f"{'官方版本' if is_latest else '历史版本'} {tag} · {day} UTC",
            "localizedDescription": description,
            "iconURL": icon_url,
            "version": version_str,
            "versionDate": published,
            "downloadURL": download_url,
            "size": size,
        })
        versions.append({
            "version": version_str,
            "date": published,
            "localizedDescription": description,
            "downloadURL": download_url,
            "size": size,
        })

    if not entries:
        raise ValueError(f"Expected at least one valid IPA release for {repository}")

    entries[0]["versions"] = versions
    return entries[0], entries[1:]


def write_json(path, payload):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main():
    projects = [
        # 官方发布页 https://github.com/huamidev/GestaltX/releases/latest
        {
            "repository": "huamidev/GestaltX",
            "bundleIdentifier": "com.huami.gestultx",
            "iconURL": "https://raw.githubusercontent.com/huamidev/GestaltX/main/GestaltX/Assets.xcassets/AppIcon.appiconset/AppIcon.png",
        },
        # 官方发布页 https://github.com/jailbreakdotparty/Erosion/releases/latest
        {
            "repository": "jailbreakdotparty/Erosion",
            "bundleIdentifier": "com.jbdotparty.Erosion",
            "iconURL": "https://raw.githubusercontent.com/jailbreakdotparty/Erosion/main/PreviewIcon.png",
        },
        # 官方发布页 https://github.com/Kianuni/Erosion-CN/releases/latest
        {
            "repository": "Kianuni/Erosion-CN",
            "bundleIdentifier": "com.jbdotparty.Erosion",
            "iconURL": "https://raw.githubusercontent.com/Kianuni/Erosion-CN/main/PreviewIcon.png",
        },
        # 官方发布页 https://github.com/Lakr233/Asspp/releases/latest
        {
            "repository": "Lakr233/Asspp",
            "bundleIdentifier": "wiki.qaq.Asspp",
            "iconURL": "https://raw.githubusercontent.com/Lakr233/Asspp/main/Asspp/App/Assets.xcassets/AppIcon.appiconset/asspp.png",
        },
    ]

    latest_apps = []
    history_apps = []
    for project in projects:
        latest_entry, older_entries = catalogue_entries(project)
        latest_apps.append(latest_entry)
        history_apps.extend(older_entries)

    joined_names = "、".join(app["name"] for app in latest_apps)

    # 1. 主源：仅包含 4 个项目的最新版
    source = {
        "name": joined_names,
        "identifier": "personal.gestaltx.erosion.releases",
        "subtitle": "最新版",
        "description": "在每个应用的副标题查看官方最新版本及发布日期。",
        "iconURL": SOURCE_ICON_URL,
        "apps": latest_apps,
    }
    write_json(Path(__file__).with_name("source.json"), source)

    # 2. 历史版本源：按应用分组展示旧版本，在 LiveContainer 中可单独折叠收起
    history_source = {
        "name": f"{joined_names} 历史版本",
        "identifier": "personal.gestaltx.erosion.releases.history",
        "subtitle": "历史旧版回退",
        "description": "各项目的历史正式版本归档，供降级回退安装使用。",
        "iconURL": SOURCE_ICON_URL,
        "tintColor": "#8E8E93",
        "apps": history_apps,
    }
    write_json(Path(__file__).with_name("history.json"), history_source)


if __name__ == "__main__":
    main()
