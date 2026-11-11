"""Refresh the LiveContainer catalogue from the projects' public release metadata."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path


# GestaltX 和 Erosion 的版本公告使用以下下载字段占位示例：
# "downloadURL": "XXXX"
PROJECTS = (
    ("huamidev/GestaltX", "com.huami.gestultx"),
    ("jailbreakdotparty/Erosion", "com.jbdotparty.Erosion"),
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


def catalogue_entry(repository, bundle_id, release):
    tag = release["tag_name"]
    day = datetime.fromisoformat(release["published_at"].replace("Z", "+00:00")).date()
    author, name = repository.split("/")
    return {
        "name": name,
        "bundleIdentifier": bundle_id,
        "developerName": author,
        "subtitle": f"官方版本 {tag} · {day} UTC",
        "localizedDescription": f"版本公告来自 {release['html_url']}",
    }


def asspp_entry(previous_apps):
    repository = "Lakr233/Asspp"
    bundle_id = "wiki.qaq.Asspp"
    release = latest_release(repository)
    packages = [
        asset for asset in release["assets"]
        if asset["name"].lower().endswith(".ipa") and asset["state"] == "uploaded" and asset["size"] > 0
    ]
    if not packages:
        for app in previous_apps:
            if app["bundleIdentifier"] == bundle_id and app.get("downloadURL"):
                return app
        raise ValueError("Asspp has no published IPA or previous downloadable entry")
    if len(packages) > 1:
        packages = [asset for asset in packages if asset["name"].lower() == "asspp.ipa"]
        if len(packages) != 1:
            raise ValueError("Cannot identify the standard Asspp IPA among the release assets")
    asset = packages[0]
    entry = catalogue_entry(repository, bundle_id, release)
    entry.update(
        version=release["tag_name"].removeprefix("v"),
        versionDate=release["published_at"],
        downloadURL=asset["browser_download_url"],
        size=asset["size"],
    )
    return entry


def main():
    output = Path(__file__).with_name("source.json")
    previous_apps = json.loads(output.read_text(encoding="utf-8"))["apps"] if output.exists() else []
    apps = [catalogue_entry(repo, bundle, latest_release(repo)) for repo, bundle in PROJECTS]
    apps.append(asspp_entry(previous_apps))
    source = {
        "name": "GestaltX、Erosion 与 Asspp 更新",
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
