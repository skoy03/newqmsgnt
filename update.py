import os
import requests
import zipfile
import shutil
import json
from git import Repo, GitCommandError
from datetime import datetime, timedelta

# 关键配置：强制指向 runner 工作目录（与仓库根目录一致）
REPO_API = "https://api.github.com/repos/1244453393/QmsgNtClient-NapCatQQ/releases/latest"
TARGET_FILE = "Linux-Docker.zip"
# GitHub Actions 中，GITHUB_WORKSPACE 环境变量自动指向仓库在 runner 上的根目录
REPO_PATH = os.getenv("GITHUB_WORKSPACE", os.getcwd())  # 优先用环境变量，避免路径错误
TEMP_DIR = os.path.join(REPO_PATH, "temp_download")  # 临时目录放在仓库内，便于清理
VERSION_FILE = os.path.join(REPO_PATH, "version.txt")  # 根目录文件
LOG_FILE = os.path.join(REPO_PATH, "update_log.txt")    # 根目录文件


def ensure_write_permission(file_path):
    """确保 GitHub Actions 环境有文件写入权限（关键优化）"""
    # 获取文件所在目录
    dir_path = os.path.dirname(file_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        print(f"创建目录：{dir_path}")
    
    # GitHub Actions 中 runner 权限特殊，强制赋予读写权限
    if os.name != "nt":  # Linux/macOS 环境（GitHub Actions 默认用 Linux）
        os.chmod(dir_path, 0o777)  # 最大权限，避免写入被拒
        print(f"赋予目录 {dir_path} 读写权限")
    
    # 若文件已存在，确保可写
    if os.path.exists(file_path):
        os.chmod(file_path, 0o666)
        print(f"赋予文件 {file_path} 读写权限")


def get_cloud_version():
    """获取云端版本信息，增加错误捕获粒度"""
    try:
        # 增加请求头，避免被 GitHub API 限流
        headers = {"Accept": "application/vnd.github.v3+json"}
        response = requests.get(REPO_API, headers=headers, timeout=15)
        response.raise_for_status()  # 触发 4xx/5xx 错误
        data = response.json()
        
        # 遍历资产找目标文件
        for asset in data["assets"]:
            if asset["name"] == TARGET_FILE:
                return {
                    "tag_name": data["tag_name"],
                    "download_url": asset["browser_download_url"],
                    "published_at": data["published_at"],
                    "release_body": data.get("body", "无更新说明")
                }
        print(f"云端 Release 中未找到 {TARGET_FILE}")
        return None
    except requests.exceptions.Timeout:
        print("获取云端版本超时（15秒）")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"HTTP 错误：{e}（可能是 GitHub API 限流或仓库不存在）")
        return None
    except Exception as e:
        print(f"获取云端版本失败：{str(e)}")
        return None


def write_version_file(version):
    """写入版本文件，确保在仓库根目录"""
    ensure_write_permission(VERSION_FILE)
    try:
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(version.strip())  # 仅写入纯净版本号（如 v1.0.20）
        print(f"✅ 版本文件已生成：{VERSION_FILE}")
        print(f"版本内容：{version.strip()}")
        # 验证文件是否存在且有内容
        if os.path.exists(VERSION_FILE) and os.path.getsize(VERSION_FILE) > 0:
            return True
        else:
            print(f"❌ 版本文件生成失败（空文件或未创建）")
            return False
    except Exception as e:
        print(f"❌ 写入版本文件失败：{str(e)}")
        return False


def write_log_file(cloud_info, result):
    """写入日志文件，确保在仓库根目录"""
    ensure_write_permission(LOG_FILE)
    # 转换 UTC 时间为北京时间（GitHub API 返回 UTC 时间）
    try:
        utc_time = datetime.strptime(cloud_info["published_at"], "%Y-%m-%dT%H:%M:%SZ")
        beijing_time = utc_time + timedelta(hours=8)
        beijing_time_str = beijing_time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        beijing_time_str = "UTC时间解析失败"
        print(f"⚠️  时间解析错误：{str(e)}")
    
    # 日志内容结构化，便于阅读
    log_content = f"""==================== QmsgNtClient 版本更新日志 ====================
更新触发时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}（北京时间）
云端最新版本：{cloud_info.get("tag_name", "未知版本")}
云端发布时间：{beijing_time_str}（北京时间）
更新执行结果：{result}
云端更新说明：
{cloud_info.get("release_body", "无更新说明").strip()}
=================================================================
"""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(log_content)
        print(f"✅ 日志文件已生成：{LOG_FILE}")
        print(f"日志大小：{os.path.getsize(LOG_FILE)} 字节")
        # 验证文件
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
            return True
        else:
            print(f"❌ 日志文件生成失败（空文件或未创建）")
            return False
    except Exception as e:
        print(f"❌ 写入日志文件失败：{str(e)}")
        return False


def download_and_extract(download_url):
    """下载解压文件，临时目录放在仓库内，避免权限问题"""
    # 清理旧临时目录
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
        print(f"已清理旧临时目录：{TEMP_DIR}")
    
    try:
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.chmod(TEMP_DIR, 0o777)  # 赋予临时目录最大权限
        zip_path = os.path.join(TEMP_DIR, TARGET_FILE)
        
        # 分块下载（避免大文件内存溢出）
        print(f"开始下载：{download_url}")
        headers = {"Accept": "application/octet-stream"}  # 二进制文件下载头
        response = requests.get(download_url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB/块
                if chunk:
                    f.write(chunk)
        
        # 验证下载文件
        if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
            raise Exception("下载的压缩包为空或未创建")
        print(f"✅ 下载完成：{zip_path}（大小：{os.path.getsize(zip_path)} 字节）")
        
        # 解压文件
        print(f"开始解压：{zip_path}")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # 获取压缩包根目录（避免文件散落在临时目录）
            root_names = zip_ref.namelist()
            if not root_names:
                raise Exception("压缩包内无文件")
            # 提取根目录（如压缩包内所有文件在 "Linux-Docker/" 下）
            root_dir = os.path.commonprefix(root_names).rstrip("/")
            if not root_dir:
                root_dir = "extracted_files"  # 无根目录时指定默认名
            # 解压到临时目录下的根目录
            zip_ref.extractall(os.path.join(TEMP_DIR, root_dir))
        
        extracted_dir = os.path.join(TEMP_DIR, root_dir)
        if not os.path.exists(extracted_dir):
            raise Exception(f"解压目录未创建：{extracted_dir}")
        print(f"✅ 解压完成：{extracted_dir}")
        return extracted_dir
    except Exception as e:
        print(f"❌ 下载/解压失败：{str(e)}")
        # 清理临时目录
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
        raise  # 抛出异常，终止后续流程


def update_dockerfile(extracted_dir):
    """更新 Dockerfile，保留镜像源替换逻辑"""
    src_docker = os.path.join(extracted_dir, "Dockerfile")
    dst_docker = os.path.join(REPO_PATH, "Dockerfile")
    
    # 检查云端 Dockerfile 是否存在
    if not os.path.exists(src_docker):
        print(f"❌ 解压目录中未找到 Dockerfile：{src_docker}")
        return False
    
    # 读取并修改镜像源（阿里云镜像，加速国内构建）
    try:
        with open(src_docker, "r", encoding="utf-8") as f:
            src_content = f.read()
        # 替换 node 基础镜像
        modified_content = src_content.replace(
            "FROM node:20.12",
            "FROM registry.cn-guangzhou.aliyuncs.com/qmsgnt/node:20.12"
        )
        print("✅ 已替换 Dockerfile 镜像源（阿里云）")
    except Exception as e:
        print(f"❌ 读取/修改 Dockerfile 失败：{str(e)}")
        return False
    
    # 对比本地 Dockerfile，避免无意义更新
    if os.path.exists(dst_docker):
        with open(dst_docker, "r", encoding="utf-8") as f:
            dst_content = f.read()
        if dst_content == modified_content:
            print("✅ 本地 Dockerfile 与云端一致，无需更新")
            return False
    
    # 写入更新后的 Dockerfile
    try:
        with open(dst_docker, "w", encoding="utf-8") as f:
            f.write(modified_content)
        print(f"✅ Dockerfile 已更新：{dst_docker}")
        return True
    except Exception as e:
        print(f"❌ 写入 Dockerfile 失败：{str(e)}")
        return False


def git_commit_push(cloud_tag):
    """GitHub Actions 专用 Git 提交推送逻辑（核心修复）"""
    try:
        # 1. 初始化 Git 仓库（确保在仓库根目录）
        repo = Repo(REPO_PATH)
        print(f"✅ 已加载 Git 仓库：{repo.working_dir}")
        
        # 2. 检查 Git 状态（是否有未跟踪文件）
        if repo.is_dirty(untracked_files=True):
            print("⚠️ Git 仓库存在未跟踪文件，准备添加")
        else:
            print("⚠️ Git 仓库无未跟踪文件，检查目标文件是否存在")
            # 手动检查版本文件和日志文件是否存在
            for file in [VERSION_FILE, LOG_FILE, os.path.join(REPO_PATH, "Dockerfile")]:
                if not os.path.exists(file):
                    print(f"❌ 目标文件不存在：{file}")
                    return False
        
        # 3. 添加关键文件（仅提交需要同步的文件，避免冗余）
        files_to_add = [VERSION_FILE, LOG_FILE, os.path.join(REPO_PATH, "Dockerfile")]
        for file in files_to_add:
            if os.path.exists(file):
                repo.git.add(file)
                print(f"✅ Git 已添加文件：{file}")
            else:
                print(f"⚠️ 跳过不存在的文件：{file}")
        
        # 4. 提交更改（包含版本号，便于追溯）
        commit_msg = f"Auto update to {cloud_tag}"
        repo.index.commit(commit_msg)
        print(f"✅ Git 已提交：{commit_msg}")
        
        # 5. 配置远程仓库（使用 GitHub Actions 内置 Token 认证，关键！）
        # GITHUB_TOKEN 是 GitHub Actions 自动生成的临时令牌，有仓库写入权限
        github_token = os.getenv("GITHUB_TOKEN")
        github_repo = os.getenv("GITHUB_REPOSITORY")  # 格式：用户名/仓库名
        if not github_token or not github_repo:
            raise Exception("GITHUB_TOKEN 或 GITHUB_REPOSITORY 环境变量未设置（GitHub Actions 配置错误）")
        
        # 构建带认证的远程 URL（避免 HTTPS 认证失败）
        remote_url = f"https://x-access-token:{github_token}@github.com/{github_repo}.git"
        origin = repo.remote(name="origin")
        origin.set_url(remote_url)
        print(f"✅ 已配置 Git 远程地址：{origin.url.replace(github_token, '***')}")  # 隐藏令牌
        
        # 6. 推送更改（强制推送 main 分支，避免分支不一致问题）
        # 注意：若仓库默认分支是 main，需改为 origin/main；若是 master，改为 origin/master
        repo.git.push(origin, "HEAD:main", force=True)  # force=True 解决少量分支冲突
        print("✅ Git 推送成功！文件已同步到远程仓库")
        return True
    except GitCommandError as e:
        print(f"❌ Git 命令错误：{str(e)}（可能是权限不足或分支错误）")
        # 打印详细错误日志，便于排查
        print(f"Git 错误详情：{e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Git 提交推送失败：{str(e)}")
        return False


def main():
    print("="*60)
    print(f"QmsgNtClient 版本同步脚本启动（{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}）")
    print(f"仓库根目录：{REPO_PATH}")
    print("="*60)
    
    # 步骤1：获取云端版本信息
    cloud_info = get_cloud_version()
    if not cloud_info:
        # 即使云端信息获取失败，也要生成日志
        cloud_info = {"tag_name": "未知", "published_at": "", "release_body": "未获取到云端信息"}
        write_log_file(cloud_info, "失败：未获取到云端版本信息")
        print("❌ 流程终止：未获取到云端版本信息")
        return
    
    # 步骤2：读取本地版本
    local_version = ""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            local_version = f.read().strip()
    print(f"\n【版本对比】")
    print(f"本地版本：{local_version or '无（首次运行）'}")
    print(f"云端版本：{cloud_info['tag_name']}")
    
    # 步骤3：判断是否需要更新
    if local_version == cloud_info["tag_name"]:
        print("\n✅ 本地版本与云端一致，无需同步")
        # 生成日志（记录检查结果）
        write_log_file(cloud_info, "成功：本地版本与云端一致，无需更新")
        # 若本地无版本文件（首次运行），补全版本文件
        if not local_version:
            write_version_file(cloud_info["tag_name"])
            # 提交版本文件到仓库
            git_commit_push(cloud_info["tag_name"])
        print("✅ 流程结束")
        return
    
    # 步骤4：执行更新流程（下载→解压→更新Dockerfile→写文件→提交）
    try:
        print("\n⚠️ 版本不一致，开始执行更新流程...")
        
        # 4.1 下载并解压云端文件
        extracted_dir = download_and_extract(cloud_info["download_url"])
        
        # 4.2 更新本地 Dockerfile
        docker_updated = update_dockerfile(extracted_dir)
        
        # 4.3 生成版本文件和日志文件（无论 Dockerfile 是否更新，都要生成）
        version_written = write_version_file(cloud_info["tag_name"])
        log_written = write_log_file(cloud_info, "待提交：文件已生成，等待 Git 同步")
        
        # 4.4 提交到 Git 仓库（只有文件生成成功才提交）
        if version_written and log_written:
            git_success = git_commit_push(cloud_info["tag_name"])
            if git_success:
                # 更新日志，标记推送成功
                write_log_file(cloud_info, "成功：Dockerfile+版本+日志已同步到远程仓库")
                print("\n" + "="*60)
                print("✅ 全部流程完成！")
                print(f"1. 版本文件：{VERSION_FILE}（{cloud_info['tag_name']}）")
                print(f"2. 日志文件：{LOG_FILE}（已记录更新详情）")
                print(f"3. Dockerfile：{os.path.join(REPO_PATH, 'Dockerfile')}（已同步云端）")
                print("="*60)
            else:
                write_log_file(cloud_info, "失败：文件已生成，但 Git 推送失败")
                print("❌ 流程终止：Git 推送失败")
        else:
            write_log_file(cloud_info, "失败：版本文件或日志文件生成失败")
            print("❌ 流程终止：版本文件或日志文件生成失败")
    
    except Exception as e:
        # 异常时生成错误日志
        write_log_file(cloud_info, f"失败：更新过程异常 - {str(e)}")
        print(f"\n❌ 流程异常终止：{str(e)}")
    finally:
        # 清理临时目录
        if os.path.exists(TEMP_DIR):
            shutil.rmtree(TEMP_DIR, ignore_errors=True)
            print(f"\n✅ 已清理临时目录：{TEMP_DIR}")


if __name__ == "__main__":
    main()
