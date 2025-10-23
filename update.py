import os
import requests
import zipfile
import shutil
import json
from git import Repo
from datetime import datetime

# 配置信息（更新版本文件和日志文件路径）
REPO_API = "https://api.github.com/repos/1244453393/QmsgNtClient-NapCatQQ/releases/latest"
TARGET_FILE = "Linux-Docker.zip"
REPO_PATH = "."
TEMP_DIR = "temp_download"
VERSION_FILE = "version.txt"  # 改为可查看的txt文件，直接存储版本号
LOG_FILE = "update_log.txt"   # 新增版本更新日志文件


def get_cloud_version():
    """获取云端最新版本信息（版本号、下载链接、发布时间）"""
    try:
        response = requests.get(REPO_API, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        for asset in data["assets"]:
            if asset["name"] == TARGET_FILE:
                return {
                    "tag_name": data["tag_name"],
                    "download_url": asset["browser_download_url"],
                    "published_at": data["published_at"],  # 云端发布时间（UTC格式）
                    "release_body": data.get("body", "无更新说明")  # 云端更新说明
                }
        print(f"云端未找到目标文件：{TARGET_FILE}")
        return None
    except Exception as e:
        print(f"获取云端版本失败：{str(e)}")
        return None


def get_local_version():
    """读取本地version.txt文件中的版本号（无文件/空文件视为无版本）"""
    version_path = os.path.join(REPO_PATH, VERSION_FILE)
    if os.path.exists(version_path):
        with open(version_path, "r", encoding="utf-8") as f:
            local_tag = f.read().strip()
        return local_tag if local_tag else None
    print(f"本地{VERSION_FILE}文件不存在，视为首次运行")
    return None


def write_local_version(cloud_tag):
    """将最新版本号写入version.txt文件（覆盖写入，确保内容纯净）"""
    version_path = os.path.join(REPO_PATH, VERSION_FILE)
    try:
        with open(version_path, "w", encoding="utf-8") as f:
            f.write(cloud_tag)  # 仅写入版本号（如v1.0.20），便于直接查看
        print(f"本地版本已写入{VERSION_FILE}，当前版本：{cloud_tag}")
    except Exception as e:
        raise Exception(f"写入{VERSION_FILE}失败：{str(e)}")


def write_update_log(cloud_info, update_result):
    """写入版本更新日志（每次更新覆盖旧日志，保留最新记录）"""
    log_path = os.path.join(REPO_PATH, LOG_FILE)
    # 转换UTC时间为北京时间（+8小时）
    utc_time = datetime.strptime(cloud_info["published_at"], "%Y-%m-%dT%H:%M:%SZ")
    beijing_time = utc_time.strftime("%Y-%m-%d %H:%M:%S") + "（UTC+8）"
    
    # 日志内容（结构化，便于阅读）
    log_content = f"""==================== 版本更新日志 ====================
更新时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}（本地时间）
云端版本：{cloud_info["tag_name"]}
云端发布时间：{beijing_time}
更新结果：{update_result}
云端更新说明：
{cloud_info["release_body"].strip() if cloud_info["release_body"].strip() else "无"}
=====================================================
"""
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_content)
        print(f"更新日志已覆盖写入{LOG_FILE}")
    except Exception as e:
        raise Exception(f"写入{LOG_FILE}失败：{str(e)}")


def download_and_extract(download_url):
    """下载并解压云端文件（优化分块下载与临时目录清理）"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    
    try:
        os.makedirs(TEMP_DIR)
        zip_path = os.path.join(TEMP_DIR, TARGET_FILE)
        
        # 分块下载（避免大文件占用过多内存）
        print(f"开始下载：{download_url}")
        response = requests.get(download_url, timeout=30, stream=True)
        response.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB/块
                if chunk:
                    f.write(chunk)
        print(f"下载完成，文件保存至：{zip_path}")
        
        # 解压并获取根目录
        print(f"开始解压：{zip_path}")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            root_dirs = {name.split('/')[0] for name in zip_ref.namelist() if '/' in name}
            root_dir = root_dirs.pop() if root_dirs else os.path.splitext(TARGET_FILE)[0]
            zip_ref.extractall(TEMP_DIR)
        
        extracted_dir = os.path.join(TEMP_DIR, root_dir)
        if not os.path.exists(extracted_dir):
            raise FileNotFoundError(f"解压目录不存在：{extracted_dir}")
        print(f"解压完成，解压目录：{extracted_dir}")
        return extracted_dir
    
    except Exception as e:
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        raise Exception(f"下载/解压失败：{str(e)}")


def update_dockerfile(extracted_dir):
    """更新本地Dockerfile（保留镜像源替换逻辑）"""
    src_docker = os.path.join(extracted_dir, "Dockerfile")
    dst_docker = os.path.join(REPO_PATH, "Dockerfile")
    
    if not os.path.exists(src_docker):
        print("解压目录中未找到Dockerfile，无需更新")
        return False
    
    # 读取并修改云端Dockerfile（替换为阿里云镜像）
    with open(src_docker, "r", encoding="utf-8") as f:
        src_content = f.read()
    modified_content = src_content.replace(
        "FROM node:20.12",
        "FROM registry.cn-guangzhou.aliyuncs.com/qmsgnt/node:20.12"
    )
    
    # 对比本地文件，避免无意义更新
    if os.path.exists(dst_docker):
        with open(dst_docker, "r", encoding="utf-8") as f:
            dst_content = f.read()
        if dst_content == modified_content:
            print("本地Dockerfile与云端版本一致，无需更新")
            return False
    
    # 写入更新后的内容
    with open(dst_docker, "w", encoding="utf-8") as f:
        f.write(modified_content)
    print("Dockerfile已更新（含镜像源优化）")
    return True


def git_commit_push(cloud_tag):
    """提交版本文件、日志文件和Dockerfile到Git仓库"""
    try:
        repo = Repo(REPO_PATH)
        # 仅提交关键文件（避免无关文件干扰）
        commit_files = [
            os.path.join(REPO_PATH, VERSION_FILE),
            os.path.join(REPO_PATH, LOG_FILE),
            os.path.join(REPO_PATH, "Dockerfile")
        ]
        repo.git.add(commit_files)
        
        # 提交信息（包含版本号，便于追溯）
        commit_msg = f"Auto update: sync to {cloud_tag} (update Dockerfile + version + log)"
        repo.index.commit(commit_msg)
        
        # 配置远程仓库并推送
        origin = repo.remote("origin")
        origin.set_url(f"https://x-access-token:{os.getenv('GITHUB_TOKEN')}@github.com/{os.getenv('GITHUB_REPOSITORY')}.git")
        origin.push()
        print(f"Git提交成功，commit信息：{commit_msg}")
    except Exception as e:
        raise Exception(f"Git提交推送失败：{str(e)}")


def main():
    print("="*60)
    print(f"版本同步检查启动（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    print("="*60)
    
    # 1. 获取云端与本地版本
    cloud_info = get_cloud_version()
    if not cloud_info:
        print("云端版本获取失败，终止流程")
        return
    cloud_tag = cloud_info["tag_name"]
    local_tag = get_local_version()
    
    # 2. 版本对比
    print(f"\n【版本对比】")
    print(f"本地版本：{local_tag if local_tag else '无'}")
    print(f"云端版本：{cloud_tag}")
    
    if local_tag == cloud_tag:
        print("\n本地版本与云端一致，无需更新")
        # 即使无需更新，也更新日志（记录检查结果）
        write_update_log(cloud_info, "本地版本与云端一致，未执行更新")
        print(f"更新日志已覆盖写入{LOG_FILE}（记录检查结果）")
        return
    print("\n版本不一致，启动更新流程...")
    
    # 3. 执行更新流程
    try:
        # 下载解压 → 更新Dockerfile → 写入版本文件 → 写入日志 → Git提交
        extracted_dir = download_and_extract(cloud_info["download_url"])
        docker_updated = update_dockerfile(extracted_dir)
        
        if docker_updated:
            write_local_version(cloud_tag)
            write_update_log(cloud_info, "更新成功（Dockerfile+版本文件已同步）")
            git_commit_push(cloud_tag)
            
            print("\n" + "="*60)
            print("更新流程全部完成！")
            print(f"1. {VERSION_FILE}：已更新为{cloud_tag}")
            print(f"2. {LOG_FILE}：已覆盖写入最新更新日志")
            print(f"3. Dockerfile：已同步云端最新版本")
            print("="*60)
        else:
            # Dockerfile未更新时，仅记录日志
            write_update_log(cloud_info, "Dockerfile无需更新，未执行版本同步")
            print(f"\nDockerfile未更新，仅写入检查日志至{LOG_FILE}")
        
        # 清理临时目录
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
            print(f"\n临时目录{TEMP_DIR}已清理")
    
    except Exception as e:
        # 异常时清理临时目录+记录错误日志
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR)
        write_update_log(cloud_info, f"更新失败：{str(e)}")
        print(f"\n更新失败：{str(e)}")
        print(f"错误信息已记录至{LOG_FILE}")


if __name__ == "__main__":
    main()
