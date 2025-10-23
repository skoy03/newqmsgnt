import os
import requests
import zipfile
import shutil
import json
from git import Repo, GitCommandError
from datetime import datetime, timedelta

# 配置信息
REPO_API = "https://api.github.com/repos/1244453393/QmsgNtClient-NapCatQQ/releases/latest"
TARGET_FILE = "Linux-Docker.zip"
REPO_PATH = os.getenv("GITHUB_WORKSPACE", os.getcwd())  # GitHub Actions 仓库目录
TEMP_DIR = os.path.join(REPO_PATH, "temp_download")
VERSION_FILE = os.path.join(REPO_PATH, "version.txt")
LOG_FILE = os.path.join(REPO_PATH, "update_log.txt")


def utc_to_beijing(utc_time=None):
    """将 UTC 时间转换为北京时间（UTC+8）"""
    if utc_time is None:
        utc_time = datetime.utcnow()
    beijing_time = utc_time + timedelta(hours=8)
    return beijing_time


def ensure_write_permission(file_path):
    """确保文件写入权限（GitHub Actions 环境适配）"""
    dir_path = os.path.dirname(file_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    if os.name != "nt":
        os.chmod(dir_path, 0o777)
    if os.path.exists(file_path):
        os.chmod(file_path, 0o666)


def get_cloud_version():
    """获取云端版本信息，带时间转换"""
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        response = requests.get(REPO_API, headers=headers, timeout=15)
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
        print(f"云端未找到 {TARGET_FILE}")
        return None
    except Exception as e:
        print(f"获取云端版本失败：{str(e)}")
        return None


def write_version_file(version):
    """写入版本文件"""
    ensure_write_permission(VERSION_FILE)
    try:
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(version.strip())
        print(f"✅ 版本文件已生成：版本：{version.strip()}")
        return os.path.exists(VERSION_FILE)
    except Exception as e:
        print(f"❌ 写入版本文件失败：{str(e)}")
        return False


def write_log_file(cloud_info, result):
    """写入日志文件，时间统一为北京时间"""
    ensure_write_permission(LOG_FILE)
    # 转换云端发布时间（UTC 字符串 → 北京时间）
    beijing_publish_time = "解析失败"
    if cloud_info.get("published_at"):
        try:
            utc_publish = datetime.strptime(cloud_info["published_at"], "%Y-%m-%dT%H:%M:%SZ")
            beijing_publish = utc_to_beijing(utc_publish)
            beijing_publish_time = beijing_publish.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"时间解析错误：{str(e)}")
    
    # 当前日志生成时间（北京时间）
    current_bj_time = utc_to_beijing().strftime("%Y-%m-%d %H:%M:%S")
    
    log_content = f"""==================== QmsgNtClient 版本更新日志 ====================
更新触发时间：{current_bj_time}
云端最新版本：{cloud_info.get("tag_name", "未知版本")}
云端发布时间：{beijing_publish_time}
更新执行结果：{result}
云端更新说明：
{cloud_info.get("release_body", "无更新说明").strip()}
=================================================================
"""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(log_content)
        print(f"✅ 日志文件已生成：update_log.txt")
        return os.path.exists(LOG_FILE)
    except Exception as e:
        print(f"❌ 写入日志文件失败：{str(e)}")
        return False


def download_and_extract(download_url):
    """下载并解压文件"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.chmod(TEMP_DIR, 0o777)
        zip_path = os.path.join(TEMP_DIR, TARGET_FILE)
        
        print(f"开始下载：{download_url}")
        response = requests.get(download_url, timeout=30, stream=True)
        response.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        
        if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
            raise Exception("压缩包为空")
        
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(TEMP_DIR)
        
        print(f"✅ 解压完成：temp_download（所有文件已提取到临时目录）")
        return TEMP_DIR
    except Exception as e:
        print(f"❌ 下载/解压失败：{str(e)}")
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        raise


def update_dockerfile(search_dir):
    """更新 Dockerfile（遍历所有子目录查找）"""
    dst_docker = os.path.join(REPO_PATH, "Dockerfile")
    src_docker = None

    for root, dirs, files in os.walk(search_dir):
        if "Dockerfile" in files:
            src_docker = os.path.join(root, "Dockerfile")
            print(f"✅ 找到 Dockerfile：qmsgnt/Dockerfile")
            break
    
    if not src_docker:
        print(f"❌ 在临时目录 {search_dir} 及其所有子目录中，未找到 Dockerfile")
        return False
    
    try:
        with open(src_docker, "r", encoding="utf-8") as f:
            modified_content = f.read().replace(
                "FROM node:20.12",
                "FROM registry.cn-guangzhou.aliyuncs.com/qmsgnt/node:20.12"
            )
    except Exception as e:
        print(f"❌ 读取/修改 Dockerfile 失败：{str(e)}")
        return False
    
    if os.path.exists(dst_docker):
        with open(dst_docker, "r", encoding="utf-8") as f:
            if f.read() == modified_content:
                print("✅ Dockerfile 内容无变化，无需更新")
                return False
    
    with open(dst_docker, "w", encoding="utf-8") as f:
        f.write(modified_content)
    print(f"✅ Dockerfile 已更新到仓库目录：newqmsgnt/Dockerfile")
    return True


def main():
    current_bj_time = utc_to_beijing().strftime("%Y-%m-%d %H:%M:%S")
    print("="*60)
    print(f"QmsgNtClient 版本同步脚本启动（运行时间：{current_bj_time}）")
    print("="*60)
    
    cloud_info = get_cloud_version()
    if not cloud_info:
        cloud_info = {"tag_name": "未知", "published_at": "", "release_body": ""}
        write_log_file(cloud_info, "失败：未获取到云端版本")
        return
    
    local_version = ""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            local_version = f.read().strip()
    
    print(f"\n【版本对比】（{current_bj_time}）")
    print(f"本地版本：{local_version or '无'}")
    print(f"云端版本：{cloud_info['tag_name']}")
    
    if local_version == cloud_info["tag_name"]:
        print("\n✅ 版本一致，无需更新")
        write_log_file(cloud_info, "成功：版本一致")
        if not local_version:
            # 首次无版本文件时，统一提交版本文件和日志
            write_version_file(cloud_info["tag_name"])
            repo = Repo(REPO_PATH)
            repo.git.add([VERSION_FILE, LOG_FILE])
            repo.index.commit(f"初始化版本文件：{cloud_info['tag_name']}")
            origin = repo.remote("origin")
            origin.set_url(f"https://x-access-token:{os.getenv('GITHUB_TOKEN')}@github.com/{os.getenv('GITHUB_REPOSITORY')}.git")
            origin.push(force=True)
        return
    
    try:
        # 1. 下载并解压文件
        temp_dir = download_and_extract(cloud_info["download_url"])
        # 2. 更新 Dockerfile
        docker_updated = update_dockerfile(temp_dir)
        # 3. 生成版本文件
        version_ok = write_version_file(cloud_info["tag_name"])
        
        if not version_ok:
            raise Exception("版本文件生成失败")
        
        # 4. 生成最终状态日志（此时已确认前面步骤成功，直接写成功状态）
        log_result = f"{'更新完成' if docker_updated else '无需更新'}"
        log_ok = write_log_file(cloud_info, log_result)
        if not log_ok:
            raise Exception("日志文件生成失败")
        
        # 5. 统一提交所有文件（版本+Dockerfile+日志）
        repo = Repo(REPO_PATH)
        github_token = os.getenv("GITHUB_TOKEN")
        github_repo = os.getenv("GITHUB_REPOSITORY")
        origin = repo.remote("origin")
        origin.set_url(f"https://x-access-token:{github_token}@github.com/{github_repo}.git")
        
        files_to_add = [
            VERSION_FILE, 
            os.path.join(REPO_PATH, "Dockerfile"),
            LOG_FILE
        ]
        repo.git.add(files_to_add)
        commit_msg = f"自动更新到 {cloud_info['tag_name']} (更新时间: {utc_to_beijing().strftime('%Y-%m-%d %H:%M:%S')})"
        repo.index.commit(commit_msg)
        origin.push(force=True)
        print("✅ Dockerfile更新完成！")
        
        print("\n✅ 更新已完成（执行时间：{}）".format(utc_to_beijing().strftime("%Y-%m-%d %H:%M:%S")))
    except Exception as e:
        # 异常时写入失败日志（不提交，仅本地生成）
        write_log_file(cloud_info, f"失败：{str(e)}")
        print(f"❌ 流程终止：{str(e)}")
    finally:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            print(f"\n✅ 临时目录已清理：temp_download")


if __name__ == "__main__":
    main()
