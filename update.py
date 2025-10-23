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
REPO_PATH = os.getcwd()  # 强制使用当前工作目录（确保是仓库根目录）
TEMP_DIR = "temp_download"
VERSION_FILE = os.path.join(REPO_PATH, "version.txt")  # 绝对路径
LOG_FILE = os.path.join(REPO_PATH, "update_log.txt")    # 绝对路径


def ensure_file_permission(file_path):
    """确保文件/目录有写入权限"""
    dir_path = os.path.dirname(file_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    # 赋予读写权限（针对Linux环境）
    if os.name != "nt":  # 非Windows系统
        os.chmod(dir_path, 0o755)
    # 若文件已存在，确保可写
    if os.path.exists(file_path) and not os.access(file_path, os.W_OK):
        os.chmod(file_path, 0o644)


def get_cloud_version():
    """获取云端版本信息"""
    try:
        response = requests.get(REPO_API, timeout=10)
        response.raise_for_status()
        data = response.json()
        for asset in data["assets"]:
            if asset["name"] == TARGET_FILE:
                return {
                    "tag_name": data["tag_name"],
                    "download_url": asset["browser_download_url"],
                    "published_at": data["published_at"],
                    "release_body": data.get("body", "无更新说明")
                }
        print(f"云端未找到目标文件：{TARGET_FILE}")
        return None
    except Exception as e:
        print(f"获取云端版本失败：{str(e)}")
        return None


def get_local_version():
    """读取本地版本（无文件则返回None）"""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    return None


def write_local_version(cloud_tag):
    """写入版本文件（强制创建）"""
    ensure_file_permission(VERSION_FILE)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(cloud_tag)
    print(f"已生成/更新 {VERSION_FILE}，版本：{cloud_tag}")


def write_update_log(cloud_info, update_result):
    """写入日志文件（强制创建）"""
    ensure_file_permission(LOG_FILE)
    # 转换UTC时间为北京时间
    try:
        utc_time = datetime.strptime(cloud_info["published_at"], "%Y-%m-%dT%H:%M:%SZ")
        beijing_time = (utc_time + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    except:
        beijing_time = "解析失败"
    
    log_content = f"""==================== 版本更新日志 ====================
更新时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}（本地时间）
云端版本：{cloud_info.get("tag_name", "未知")}
云端发布时间：{beijing_time}（UTC+8）
更新结果：{update_result}
云端更新说明：
{cloud_info.get("release_body", "无").strip()}
=====================================================
"""
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(log_content)
    print(f"已生成/更新 {LOG_FILE}")


def download_and_extract(download_url):
    """下载并解压文件"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    try:
        os.makedirs(TEMP_DIR)
        zip_path = os.path.join(TEMP_DIR, TARGET_FILE)
        response = requests.get(download_url, timeout=30, stream=True)
        response.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        print(f"下载完成：{zip_path}")
        
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            root_dirs = {name.split('/')[0] for name in zip_ref.namelist() if '/' in name}
            root_dir = root_dirs.pop() if root_dirs else os.path.splitext(TARGET_FILE)[0]
            zip_ref.extractall(TEMP_DIR)
        extracted_dir = os.path.join(TEMP_DIR, root_dir)
        return extracted_dir if os.path.exists(extracted_dir) else TEMP_DIR
    except Exception as e:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        raise Exception(f"下载/解压失败：{str(e)}")


def update_dockerfile(extracted_dir):
    """更新Dockerfile"""
    src_docker = os.path.join(extracted_dir, "Dockerfile")
    dst_docker = os.path.join(REPO_PATH, "Dockerfile")
    if not os.path.exists(src_docker):
        print("未找到云端Dockerfile")
        return False
    
    with open(src_docker, "r", encoding="utf-8") as f:
        modified_content = f.read().replace(
            "FROM node:20.12",
            "FROM registry.cn-guangzhou.aliyuncs.com/qmsgnt/node:20.12"
        )
    
    if os.path.exists(dst_docker):
        with open(dst_docker, "r", encoding="utf-8") as f:
            if f.read() == modified_content:
                print("Dockerfile无需更新")
                return False
    
    with open(dst_docker, "w", encoding="utf-8") as f:
        f.write(modified_content)
    return True


def git_commit_push(cloud_tag):
    """提交文件到仓库"""
    try:
        repo = Repo(REPO_PATH)
        repo.git.add([VERSION_FILE, LOG_FILE, os.path.join(REPO_PATH, "Dockerfile")])
        repo.index.commit(f"Sync to {cloud_tag}: update version + log + Dockerfile")
        origin = repo.remote("origin")
        origin.set_url(f"https://x-access-token:{os.getenv('GITHUB_TOKEN')}@github.com/{os.getenv('GITHUB_REPOSITORY')}.git")
        origin.push()
        print("Git提交成功")
    except Exception as e:
        raise Exception(f"Git提交失败：{str(e)}")


def main():
    print(f"启动版本同步（{datetime.now()}）")
    cloud_info = get_cloud_version()
    # 即使云端信息获取失败，也生成日志
    if not cloud_info:
        cloud_info = {"tag_name": "未知", "published_at": "", "release_body": ""}
        write_update_log(cloud_info, "获取云端版本失败，未执行更新")
        return
    
    local_tag = get_local_version()
    print(f"本地版本：{local_tag or '无'}，云端版本：{cloud_info['tag_name']}")
    
    # 强制生成日志（无论是否更新）
    if local_tag == cloud_info["tag_name"]:
        write_update_log(cloud_info, "版本一致，未更新")
        # 首次运行且无本地版本时，强制生成version.txt
        if not local_tag:
            write_local_version(cloud_info["tag_name"])
        return
    
    # 执行更新
    try:
        extracted_dir = download_and_extract(cloud_info["download_url"])
        if update_dockerfile(extracted_dir):
            write_local_version(cloud_info["tag_name"])
            write_update_log(cloud_info, "更新成功")
            git_commit_push(cloud_info["tag_name"])
        else:
            write_update_log(cloud_info, "Dockerfile未更新")
    except Exception as e:
        write_update_log(cloud_info, f"更新失败：{str(e)}")
        print(f"错误：{e}")
    finally:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)


if __name__ == "__main__":
    main()
