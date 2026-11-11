"""Refresh the LiveContainer catalogue from the projects' public release metadata."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit


MAX_RELEASES = 10  # 每个项目最多保留多少个历史正式版


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


def version_entry(repository, release, preferred_filename, version_only):
    tag = release["tag_name"]
    published = release["published_at"]
    item = {
        "version": tag.removeprefix("v"),
        "date": published,
        "localizedDescription": f"版本公告来自 {release['html_url']}",
        "downloadURL": "XXXX",
    }
    if not version_only:
        asset = release_asset(repository, release, preferred_filename)
        if asset:
            item.update(downloadURL=asset["browser_download_url"], size=asset["size"])
    return item


def catalogue_entry(project):
    releases = published_releases(project["repository"])
    latest = releases[0]
    author, name = project["repository"].split("/")
    tag = latest["tag_name"]
    published = latest["published_at"]
    day = datetime.fromisoformat(published.replace("Z", "+00:00")).date()
    bundle = project["bundleIdentifier"]

    configured_url = project.get("downloadURL")
    version_only = configured_url == "XXXX"
    preferred_filename = name + ".ipa"
    if configured_url and not version_only:
        latest_prefix = f"https://github.com/{project['repository']}/releases/latest/download/"
        if not configured_url.startswith(latest_prefix):
            raise ValueError(f"Expected an official latest-release link for {name}")
        preferred_filename = unquote(configured_url.removeprefix(latest_prefix))

    versions = [
        version_entry(project["repository"], rel, preferred_filename, version_only)
        for rel in releases
    ]
    # 过滤掉找不到有效 IPA 的旧版本（除非是仅公告模式）
    if not version_only:
        versions = [v for v in versions if v["downloadURL"] != "XXXX"] or versions[:1]

    top = versions[0]
    entry = {
        "name": name,
        "bundleIdentifier": bundle,
        "developerName": author,
        "subtitle": f"官方版本 {tag} · {day} UTC",
        "localizedDescription": top["localizedDescription"],
        "iconURL": project.get("iconURL", f"https://github.com/{author}.png"),
        "version": top["version"],
        "versionDate": top["date"],
        "downloadURL": top["downloadURL"],
        "versions": versions,
    }
    if "size" in top:
        entry["size"] = top["size"]
    entry["subtitle"] = f"downloadURL: {entry['downloadURL']} · {entry['subtitle']}"
    return entry


def main():
    output = Path(__file__).with_name("source.json")
    apps = [
        # 官方发布页 https://github.com/huamidev/GestaltX/releases/latest
        catalogue_entry({
            "repository": "huamidev/GestaltX",
            "bundleIdentifier": "com.huami.gestultx",
#            "downloadURL": "XXXX",
        }),
        # 官方发布页 https://github.com/jailbreakdotparty/Erosion/releases/latest
        catalogue_entry({
            "repository": "jailbreakdotparty/Erosion",
            "bundleIdentifier": "com.jbdotparty.Erosion",
 #           "downloadURL": "XXXX",
        }),
        # 官方发布页 https://github.com/Kianuni/Erosion-CN/releases/latest
        catalogue_entry({
            "repository": "Kianuni/Erosion-CN",
            "bundleIdentifier": "com.jbdotparty.Erosion.cn",
        }),
        # 官方发布页 https://github.com/Lakr233/Asspp/releases/latest
        catalogue_entry({
            "repository": "Lakr233/Asspp",
            "bundleIdentifier": "wiki.qaq.Asspp",
            "downloadURL": "https://github.com/Lakr233/Asspp/releases/latest/download/Asspp.ipa",
        }),
        # 新增 App：复制下面四行，去掉行首的「# 」，保留缩进和末尾逗号，替换两个示例值。
        # catalogue_entry({
        #     "repository": "abc/def",
        #     "bundleIdentifier": "com.example.def",
        # }),
        # 默认省略 downloadURL。只有一个 IPA 时直接选用；有多个时先找「仓库名.ipa」，
        # 再按当前 tag 找带版本号的文件。例如 abc/def 在 v1.0.6 可以匹配 def_1.0.6.ipa。
        # 上面的 Asspp 显式指定了 Asspp.ipa，恰好与默认首选同名，所以这行可以省略。
        # 若 tag 为 v4.2.3，Asspp.ipa 和 Asspp_4.2.3.ipa 同时存在时优先选前者。
        # 可选：若有多个 IPA，想选与仓库名不同的附件，可添加 downloadURL 并填写该附件的官方最新版地址。
        # 如果只想显示版本，可添加 "downloadURL": "XXXX"。
    ]
    source = {
        "name": "、".join(app["name"] for app in apps),
        "identifier": "personal.gestaltx.erosion.releases",
        "subtitle": "最新版",
        "description": "在每个应用的副标题查看官方最新版本及发布日期。",
        "iconURL": apps[0]["iconURL"],
        "apps": apps,
    }
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, output)


if __name__ == "__main__":
    main()
