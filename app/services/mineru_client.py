"""
MinerU API 客户端
用于调用 MinerU 在线服务解析 PDF
"""
import asyncio
import httpx
import zipfile
import tempfile
import shutil
from typing import Optional, Dict, Any
from pathlib import Path

from app.config import settings
from app.utils.logger import log
from app.utils.async_helper import async_retry


class MinerUClient:
    """MinerU API 客户端"""
    
    def __init__(self):
        self.base_url = settings.mineru_api_base
        self.token = settings.mineru_token
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
        self.timeout = settings.mineru_timeout
        self.poll_interval = settings.mineru_poll_interval
        # MinerU API 可选参数默认值
        self.default_is_ocr = settings.mineru_is_ocr
        self.default_enable_formula = settings.mineru_enable_formula
        self.default_enable_table = settings.mineru_enable_table
        self.default_language = settings.mineru_language
    
    async def _get_model_version(self, url: str) -> str:
        """
        根据URL的资源类型返回相应的model_version
        
        通过发送HEAD请求检查Content-Type来判断资源类型，
        对于明确的文件扩展名则直接返回，避免额外请求。
        
        Args:
            url: 资源URL
            
        Returns:
            model_version: "vlm" 或 "MinerU-HTML"
        """
        from urllib.parse import urlparse
        
        # 解析URL获取路径
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        # 明确的非HTML文件扩展名，直接返回vlm
        non_html_extensions = {
            '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp',
            '.txt', '.rtf', '.odt', '.odp', '.ods'
        }
        
        for ext in non_html_extensions:
            if path.endswith(ext):
                log.info(f"URL 扩展名为 {ext}，使用 vlm")
                return "vlm"
        
        # HTML文件扩展名，直接返回MinerU-HTML
        html_extensions = {'.html', '.htm'}
        if any(path.endswith(ext) for ext in html_extensions):
            log.info(f"URL 扩展名为 HTML，使用 MinerU-HTML")
            return "MinerU-HTML"
        
        # 对于没有扩展名或无法识别的扩展名，发送HEAD请求检查Content-Type
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                log.info(f"发送 HEAD 请求检测 URL 内容类型: {url}")
                response = await client.head(url, follow_redirects=True)
                content_type = response.headers.get('content-type', '').lower()
                
                log.info(f"URL Content-Type: {content_type}")
                
                if 'text/html' in content_type or 'application/xhtml' in content_type:
                    log.info(f"检测到 HTML 内容类型，使用 MinerU-HTML")
                    return "MinerU-HTML"
                else:
                    log.info(f"非 HTML 内容类型，使用 vlm")
                    return "vlm"
        except Exception as e:
            log.warning(f"无法检测 URL 的 Content-Type，默认使用 vlm: {e}")
            return "vlm"
    
    @async_retry(max_retries=3, delay=2.0)
    async def submit_task(
        self, 
        url: Optional[str] = None, 
        file_path: Optional[Path] = None,
        is_ocr: Optional[bool] = None,
        enable_formula: Optional[bool] = None,
        enable_table: Optional[bool] = None,
        language: Optional[str] = None
    ) -> str:
        """
        提交解析任务
        
        Args:
            url: 论文 URL（如 arXiv 链接）
            file_path: 本地 PDF 文件路径
            is_ocr: 是否启用 OCR 功能（默认 False）
            enable_formula: 是否启用公式识别（默认 True）
            enable_table: 是否启用表格识别（默认 True）
            language: 指定文档语言（默认 "ch"）
            
        Returns:
            task_id
        """
        if not url and not file_path:
            raise ValueError("必须提供 url 或 file_path 之一")
        
        if url and file_path:
            raise ValueError("url 和 file_path 只能提供其中一个")
        
        endpoint = f"{self.base_url}/extract/task"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if url:
                    # 使用 URL 提交
                    model_version = await self._get_model_version(url)
                    data = {
                        "url": url,
                        "model_version": model_version,
                        # 使用传入的参数，如果未传入则使用默认值
                        "is_ocr": is_ocr if is_ocr is not None else self.default_is_ocr,
                        "enable_formula": enable_formula if enable_formula is not None else self.default_enable_formula,
                        "enable_table": enable_table if enable_table is not None else self.default_enable_table,
                        "language": language if language is not None else self.default_language
                    }
                    
                    log.info(f"提交 MinerU 任务: endpoint={endpoint}, data={data}")
                    response = await client.post(endpoint, headers=self.headers, json=data)
                else:
                    # 使用文件上传
                    log.info(f"提交 MinerU 任务（文件上传）: endpoint={endpoint}, file={file_path.name}")
                    with open(file_path, 'rb') as f:
                        files = {'file': (file_path.name, f, 'application/pdf')}
                        # 文件上传需要不同的 header
                        upload_headers = {"Authorization": f"Bearer {self.token}"}
                        
                        # 构建表单数据，包含 model_version 和可选参数
                        form_data = {
                            "model_version": "vlm",
                            # 使用传入的参数，如果未传入则使用默认值
                            "is_ocr": str(is_ocr if is_ocr is not None else self.default_is_ocr).lower(),
                            "enable_formula": str(enable_formula if enable_formula is not None else self.default_enable_formula).lower(),
                            "enable_table": str(enable_table if enable_table is not None else self.default_enable_table).lower(),
                            "language": language if language is not None else self.default_language
                        }
                        
                        response = await client.post(
                            endpoint,
                            headers=upload_headers,
                            files=files,
                            data=form_data
                        )
                
                response.raise_for_status()
                result = response.json()
                
                log.info(f"MinerU API 响应: status={response.status_code}, code={result.get('code')}")
                
                # 检查响应格式
                if not isinstance(result, dict):
                    raise Exception(f"MinerU API 返回格式错误，期望 dict，实际为 {type(result)}")
                
                # MinerU API 约定：code=0 表示成功，code!=0 表示失败
                if result.get("code") != 0:
                    error_msg = result.get('message') or result.get('msg') or '未知错误'
                    log.error(f"MinerU API 返回错误: code={result.get('code')}, message={error_msg}, full_response={result}")
                    raise Exception(f"MinerU API 错误: {error_msg}")
                
                # 从响应中提取 task_id
                data = result.get("data", {})
                if isinstance(data, dict):
                    task_id = data.get("task_id")
                else:
                    # 如果 data 直接是字符串（旧版 API）
                    task_id = data
                
                if not task_id:
                    raise Exception(f"MinerU API 未返回 task_id, 完整响应: {result}")
                
                log.info(f"MinerU 任务提交成功: task_id={task_id}")
                return task_id
                
        except httpx.HTTPError as e:
            log.error(f"提交 MinerU 任务失败（HTTP 错误）: {e}")
            raise
        except Exception as e:
            log.error(f"提交 MinerU 任务异常: {e}")
            raise
    
    @async_retry(max_retries=2, delay=1.0)
    async def check_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        endpoint = f"{self.base_url}/extract/task/{task_id}"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(endpoint, headers=self.headers)
                response.raise_for_status()
                result = response.json()
                
                # MinerU API 约定：code=0 表示成功
                if result.get("code") != 0:
                    raise Exception(f"MinerU API 错误: {result.get('message') or result.get('msg')}")
                
                data = result.get("data", {})
                
                # MinerU API 实际返回的字段名与预期不同
                # state: pending, done, failed
                # full_zip_url: 结果下载链接
                state = data.get("state")
                
                # 将 MinerU 的状态映射到标准状态
                status_map = {
                    "pending": "pending",
                    "processing": "processing",
                    "done": "completed",
                    "failed": "failed"
                }
                
                status_info = {
                    "status": status_map.get(state, state),
                    "progress": data.get("progress", 0),
                    "result_url": data.get("full_zip_url"),  # MinerU 使用 full_zip_url
                    "error": data.get("err_msg")  # MinerU 使用 err_msg
                }
                
                log.info(f"任务 {task_id} 状态: {state} -> {status_info['status']}")
                return status_info
                
        except httpx.HTTPError as e:
            log.error(f"查询 MinerU 任务状态失败: {e}")
            raise
        except Exception as e:
            log.error(f"查询 MinerU 任务状态异常: {e}")
            raise
    
    async def wait_for_completion(self, task_id: str, paper_id: Optional[str] = None) -> Dict[str, Any]:
        """
        等待任务完成
        
        Args:
            task_id: 任务ID
            paper_id: 论文ID，用于保存图片
            
        Returns:
            任务结果
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.timeout:
                raise TimeoutError(f"MinerU 任务超时 (>{self.timeout}s): {task_id}")
            
            status_info = await self.check_status(task_id)
            status = status_info["status"]
            
            log.info(f"MinerU 任务状态: {task_id} - {status} ({status_info.get('progress', 0)}%)")
            
            if status == "completed":
                result_url = status_info.get("result_url")
                if not result_url:
                    raise Exception("任务完成但未返回结果 URL")
                
                # 下载结果，传入 paper_id 以保存图片
                result_content = await self._download_result(result_url, paper_id=paper_id)
                return result_content
            
            elif status == "failed":
                error = status_info.get("error", "未知错误")
                raise Exception(f"MinerU 任务失败: {error}")
            
            # 继续等待
            await asyncio.sleep(self.poll_interval)
    
    @async_retry(max_retries=3, delay=2.0)
    async def _download_result(self, result_url: str, paper_id: Optional[str] = None) -> Dict[str, Any]:
        """
        下载解析结果（zip文件）并解压提取markdown和图片
        
        Args:
            result_url: 结果 URL（zip文件）
            paper_id: 论文ID，用于保存图片到对应目录
            
        Returns:
            解析结果（Markdown 等）
        """
        try:
            # 下载 zip 文件
            async with httpx.AsyncClient(timeout=60.0) as client:
                log.info(f"开始下载 MinerU 结果: {result_url}")
                response = await client.get(result_url)
                response.raise_for_status()
                
                # 创建临时文件保存 zip
                with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_zip:
                    tmp_zip.write(response.content)
                    tmp_zip_path = tmp_zip.name
                
                log.info(f"zip 文件已下载到: {tmp_zip_path}")
                
                # 创建临时目录用于解压
                with tempfile.TemporaryDirectory() as tmp_dir:
                    # 解压 zip 文件
                    with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                        zip_ref.extractall(tmp_dir)
                        log.info(f"zip 文件已解压到: {tmp_dir}")
                        
                        # 列出解压后的文件
                        extracted_files = list(Path(tmp_dir).rglob('*'))
                        log.info(f"解压后的文件列表: {[str(f) for f in extracted_files]}")
                        
                        # 查找 .md 文件
                        md_files = list(Path(tmp_dir).rglob('*.md'))
                        
                        if not md_files:
                            raise Exception(f"在解压结果中未找到 .md 文件")
                        
                        # 如果有多个 .md 文件，选择最大的一个（通常是主文档）
                        md_file = max(md_files, key=lambda f: f.stat().st_size)
                        log.info(f"找到 markdown 文件: {md_file.name}")
                        
                        # 读取 markdown 内容
                        with open(md_file, 'r', encoding='utf-8') as f:
                            markdown_content = f.read()
                        
                        # 保存图片文件到持久化目录
                        images_saved = 0
                        if paper_id:
                            # 查找所有图片文件
                            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
                            image_files = [
                                f for f in extracted_files 
                                if f.is_file() and f.suffix.lower() in image_extensions
                            ]
                            
                            if image_files:
                                # 创建论文图片目录
                                paper_images_dir = settings.parsed_dir / paper_id / "images"
                                paper_images_dir.mkdir(parents=True, exist_ok=True)
                                
                                for img_file in image_files:
                                    dest_path = paper_images_dir / img_file.name
                                    shutil.copy2(img_file, dest_path)
                                    images_saved += 1
                                
                                log.info(f"已保存 {images_saved} 张图片到: {paper_images_dir}")
                        
                        # 清理临时 zip 文件
                        Path(tmp_zip_path).unlink()
                        
                        return {
                            "content": markdown_content,
                            "format": "markdown",
                            "filename": md_file.name,
                            "images_saved": images_saved
                        }
                    
        except httpx.HTTPError as e:
            log.error(f"下载 MinerU 结果失败: {e}")
            raise
        except zipfile.BadZipFile as e:
            log.error(f"zip 文件解压失败: {e}")
            raise Exception(f"下载的文件不是有效的 zip 文件")
        except Exception as e:
            log.error(f"下载 MinerU 结果异常: {e}")
            raise
    
    async def parse_pdf(
        self, 
        url: Optional[str] = None, 
        file_path: Optional[Path] = None, 
        paper_id: Optional[str] = None,
        is_ocr: Optional[bool] = None,
        enable_formula: Optional[bool] = None,
        enable_table: Optional[bool] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        完整的 PDF 解析流程（提交 -> 等待 -> 获取结果）
        
        Args:
            url: 论文 URL
            file_path: 本地文件路径
            paper_id: 论文ID，用于保存图片到对应目录
            is_ocr: 是否启用 OCR 功能（默认 False）
            enable_formula: 是否启用公式识别（默认 True）
            enable_table: 是否启用表格识别（默认 True）
            language: 指定文档语言（默认 "ch"）
            
        Returns:
            解析结果
        """
        log.info(f"开始解析 PDF: url={url}, file={file_path}, paper_id={paper_id}")
        
        # 提交任务，传递所有可选参数
        task_id = await self.submit_task(
            url=url, 
            file_path=file_path,
            is_ocr=is_ocr,
            enable_formula=enable_formula,
            enable_table=enable_table,
            language=language
        )
        
        # 等待完成，传入 paper_id 以保存图片
        result = await self.wait_for_completion(task_id, paper_id=paper_id)
        
        log.info(f"PDF 解析完成: task_id={task_id}")
        return result


# 全局客户端实例
mineru_client = MinerUClient()

