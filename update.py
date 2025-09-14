import os
import requests
import zipfile
import shutil
import json
from git import Repo
from datetime import datetime

# 配置信息
REPO_API = "https://api.github.com/repos/1244453393/QmsgNtClient-NapCatQQ/releases/latest"
TARGET_FILE = "Linux-Docker.zip"
REPO_PATH = "."  # 当前仓库路径
TEMP_DIR = "temp_download"
DOCKER_FILES = ["Dockerfile", "docker-compose.yml"]  # 需要保留的Docker相关文件
CHANGELOG_FILE = "CHANGELOG.md"  # 更新日志文件

def get_latest_release():
    """获取最新发布的下载链接和版本信息"""
    response = requests.get(REPO_API)
    if response.status_code == 200:
        data = response.json()
        for asset in data["assets"]:
            if asset["name"] == TARGET_FILE:
                return {
                    "download_url": asset["browser_download_url"],
                    "tag_name": data["tag_name"],
                    "release_body": data["body"],
                    "published_at": data["published_at"]
                }
    return None

def download_and_extract(url):
    """下载并解压文件"""
    try:
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)
        
        # 下载文件
        print(f"Downloading {url}...")
        response = requests.get(url)
        response.raise_for_status()  # 检查HTTP错误
        
        zip_path = os.path.join(TEMP_DIR, TARGET_FILE)
        with open(zip_path, "wb") as f:
            f.write(response.content)
        
        # 解压文件
        print(f"Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # 获取zip文件中的根目录名
            root_dir = os.path.commonprefix(zip_ref.namelist()).rstrip('/')
            if not root_dir:  # 如果zip文件没有根目录
                root_dir = os.path.splitext(TARGET_FILE)[0]
            zip_ref.extractall(TEMP_DIR)
        
        extracted_dir = os.path.join(TEMP_DIR, root_dir)
        if not os.path.exists(extracted_dir):
            raise FileNotFoundError(f"Extracted directory not found: {extracted_dir}")
            
        return extracted_dir
        
    except Exception as e:
        # 清理临时文件
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        raise e

def update_repository(extracted_dir, release_info):
    """更新仓库文件"""
    # 检查是否有实际更新
    has_update = False
    
    # 删除旧文件（保留Docker相关文件和更新日志）
    for item in os.listdir(REPO_PATH):
        if item not in DOCKER_FILES + [".git", TEMP_DIR, CHANGELOG_FILE]:
            item_path = os.path.join(REPO_PATH, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
                has_update = True
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
                has_update = True
    
    # 复制新文件
    for item in os.listdir(extracted_dir):
        src = os.path.join(extracted_dir, item)
        dst = os.path.join(REPO_PATH, item)
        
        # 检查文件是否已存在且内容相同
        if os.path.exists(dst):
            if os.path.isfile(src) and os.path.isfile(dst):
                with open(src, 'rb') as f1, open(dst, 'rb') as f2:
                    if f1.read() == f2.read():
                        continue
        
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            has_update = True
        elif os.path.isdir(src):
            shutil.copytree(src, dst)
            has_update = True
    
    # 更新日志
    if has_update:
        update_changelog(release_info)
    
    # 清理临时文件
    shutil.rmtree(TEMP_DIR)
    
    return has_update

def update_changelog(release_info):
    """更新变更日志"""
    changelog_path = os.path.join(REPO_PATH, CHANGELOG_FILE)
    current_date = datetime.now().strftime("%Y-%m-%d")
    entry = f"## {release_info['tag_name']} ({current_date})\n\n{release_info['release_body']}\n\n"
    
    if os.path.exists(changelog_path):
        with open(changelog_path, 'r+') as f:
            content = f.read()
            f.seek(0, 0)
            f.write(entry + content)
    else:
        with open(changelog_path, 'w') as f:
            f.write(entry)

def git_commit_and_push(release_info):
    """提交更改到Git仓库"""
    repo = Repo(REPO_PATH)
    repo.git.add("--all")
    repo.index.commit(f"Auto update to {release_info['tag_name']}")
    
    # 确保使用正确的远程URL和认证
    origin = repo.remote(name="origin")
    origin.set_url(f"https://x-access-token:{os.getenv('GITHUB_TOKEN')}@github.com/{os.getenv('GITHUB_REPOSITORY')}.git")
    
    try:
        origin.push()
    except Exception as e:
        print(f"Push failed: {str(e)}")
        raise

def main():
    release_info = get_latest_release()
    if release_info:
        print(f"Found latest release: {release_info['tag_name']}")
        extracted_dir = download_and_extract(release_info["download_url"])
        has_update = update_repository(extracted_dir, release_info)
        
        if has_update:
            git_commit_and_push(release_info)
            print("Update completed successfully!")
        else:
            print("No changes detected, skipping update.")
    else:
        print("Failed to find the latest release.")

if __name__ == "__main__":
    main()