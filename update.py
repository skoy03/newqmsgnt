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
DOCKER_FILES = ["Dockerfile"]  # 需要保留的Docker相关文件
VERSION_FILE = ".version"

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
    has_update = False
    
    # 检查并更新Dockerfile
    src_dockerfile = os.path.join(extracted_dir, "Dockerfile")
    dst_dockerfile = os.path.join(REPO_PATH, "Dockerfile")
    
    if os.path.exists(src_dockerfile):
        # 读取源文件内容
        with open(src_dockerfile, 'r') as f:
            content = f.read()
        
        # 替换镜像源
        modified_content = content.replace(
            "FROM node:20.12", 
            "FROM registry.cn-guangzhou.aliyuncs.com/qmsgnt/node:20.12"
        )
        
        # 检查是否需要更新
        if os.path.exists(dst_dockerfile):
            with open(dst_dockerfile, 'r') as f:
                if f.read() == modified_content:
                    print("Dockerfile is up to date, no changes needed.")
                    return False
        
        # 写入修改后的内容
        with open(dst_dockerfile, 'w') as f:
            f.write(modified_content)
        
        has_update = True
        print("Dockerfile updated successfully with custom image source.")
    else:
        print("No Dockerfile found in the downloaded package.")
    
    # 清理临时文件
    shutil.rmtree(TEMP_DIR)
    
    return has_update

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

def check_local_version():
    """检查本地版本"""
    version_file = os.path.join(REPO_PATH, ".version")
    if os.path.exists(version_file):
        with open(version_file, "r") as f:
            return f.read().strip()
    return None

def update_local_version(tag_name):
    """更新本地版本记录"""
    version_file = os.path.join(REPO_PATH, ".version")
    with open(version_file, "w") as f:
        f.write(tag_name)

def main():
    release_info = get_latest_release()
    if release_info:
        print(f"Found latest release: {release_info['tag_name']}")
        
        # 检查版本是否一致
        local_version = check_local_version()
        if local_version == release_info['tag_name']:
            print("Local version is up to date, skipping update.")
            return
            
        extracted_dir = download_and_extract(release_info["download_url"])
        has_update = update_repository(extracted_dir, release_info)
        
        if has_update:
            update_local_version(release_info['tag_name'])  # 更新本地版本记录
            git_commit_and_push(release_info)
            print("Update completed successfully!")
        else:
            print("No changes detected, skipping update.")
    else:
        print("Failed to find the latest release.")

if __name__ == "__main__":
    main()