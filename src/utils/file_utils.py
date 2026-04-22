import io
import base64
import pymupdf
import pyclamd
from PIL import Image
from pathlib import Path
from loguru import logger

from src.config import settings


def scan_file_with_clamav(file_path: str | Path) -> bool:
    """使用 ClamAV 扫描文件是否安全
    
    通过网络连接 ClamAV 杀毒软件扫描上传文件，
    确保文件不包含恶意代码。
    
    Args:
        file_path: 文件路径
        
    Returns:
        True 表示安全，False 表示不安全或出错
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return False

    try:
        cd = pyclamd.ClamdNetworkSocket(host=settings.clam_av_host, port=settings.clam_av_port, timeout=30)

        # 读取文件内容并发送给 ClamAV 扫描
        with open(file_path, "rb") as f:
            file_content = f.read()

        result = cd.scan_stream(file_content)

        # None 表示安全
        return result is None
    except Exception as e:
        logger.error(f"scan_file_with_clamav error:{str(e)}")
        return False


def image_to_base64(file_path: str | Path) -> dict[str, str]:
    """将图片文件转为 base64
    
    读取图片文件并转换为 base64 编码和 MIME 类型。
    
    Args:
        file_path: 图片文件路径
        
    Returns:
        {"base64": "...", "mime_type": "image/..."}
    """
    path = Path(file_path)
    mime_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    mime_type = mime_type_map.get(path.suffix.lower(), "image/png")

    with open(path, "rb") as f:
        return {
            "base64": base64.b64encode(f.read()).decode("utf-8"),
            "mime_type": mime_type
        }


def image_to_data_url(file_path: str | Path) -> str:
    """将图片文件转为 data URL
    
    Args:
        file_path: 图片文件路径
        
    Returns:
        data:image/png;base64,... 格式的字符串
        
    Example:
        >>> image_to_data_url("photo.png")
        'data:image/png;base64,iVBORw0KGgo...'
    """
    result = image_to_base64(file_path)
    return f"data:{result['mime_type']};base64,{result['base64']}"


def pdf_to_single_image_to_base64(pdf_path: str, dpi: int = 180) -> dict[str, str]:
    """将 PDF 转为一张长图的 base64
    
    将多页 PDF 垂直拼接为一张长图，
    然后转换为 base64 编码。
    
    特点：
    - 顺序处理每一页
    - 每次调用独立打开 PDF 文件
    - 返回 base64 字符串
    
    Args:
        pdf_path: PDF 文件路径
        dpi: 图片清晰度，默认 180
        
    Returns:
        {"base64": "...", "mime_type": "image/png"}
    """
    # 打开文档获取页数
    with pymupdf.open(pdf_path) as doc:
        num_pages = len(doc)

    # 顺序处理每一页
    images = []
    with pymupdf.open(pdf_path) as doc:
        for page_num in range(num_pages):
            page = doc[page_num]
            zoom = dpi / 72
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)

    # 计算总尺寸
    total_height = sum(img.height for img in images)
    max_width = max(img.width for img in images)

    # 创建大图并拼接
    result = Image.new("RGB", (max_width, total_height), (255, 255, 255))
    y_offset = 0
    for img in images:
        result.paste(img, (0, y_offset))
        y_offset += img.height

    # 转为 base64
    output = io.BytesIO()
    result.save(output, format="PNG")
    return {
        "base64": base64.b64encode(output.getvalue()).decode("utf-8"),
        "mime_type": "image/png"
    }


def pdf_to_single_image_to_data_url(pdf_path: str, dpi: int = 180) -> str:
    """将 PDF 转为一张长图的 data URL
    
    Args:
        pdf_path: PDF 文件路径
        dpi: 图片清晰度，默认 180
        
    Returns:
        data:image/png;base64,... 格式的字符串
    """
    result = pdf_to_single_image_to_base64(pdf_path, dpi)
    return f"data:{result['mime_type']};base64,{result['base64']}"


def pdf_pages_to_base64(file_path: str, dpi: int = 180) -> list[dict]:
    """将 PDF 每页转为 base64 图片
    
    将 PDF 的每一页分别渲染为图片并转为 base64。
    
    Args:
        file_path: PDF 文件路径
        dpi: 图片清晰度，默认 180
        
    Returns:
        [{"page_num": 1, "base64": "...", "mime_type": "image/png"}, ...]
    """
    results = []
    with pymupdf.open(file_path) as doc:
        for page_num, page in enumerate(doc, start=1):
            # 渲染页面为图片
            zoom = dpi / 72
            mat = pymupdf.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            # 转 PNG 字节
            img_bytes = pix.tobytes("png")
            # 转 Base64
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            results.append({
                "page_num": page_num,
                "base64": img_base64,
                "mime_type": "image/png"
            })
    return results


def pdf_to_base64(file_path: str) -> dict[str, str]:
    """将 PDF 转为 base64
    
    Args:
        file_path: PDF 文件路径
        
    Returns:
        {"base64": "...", "mime_type": "application/pdf"}
    """
    with open(file_path, "rb") as f:
        return {
            "base64": base64.b64encode(f.read()).decode("utf-8"),
            "mime_type": "application/pdf"
        }


def file_to_image_data_url(file_path: str | Path, dpi: int = 180) -> str:
    """根据文件类型转为 data URL
    
    自动判断文件类型并调用对应的转换方法：
    - PDF 文件 -> pdf_to_single_image_to_data_url
    - 图片文件 -> image_to_data_url
    
    Args:
        file_path: 文件路径
        dpi: PDF 转图片的清晰度，默认 180
        
    Returns:
        data URL 格式的图片字符串
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return pdf_to_single_image_to_data_url(str(path), dpi)
    else:
        return image_to_data_url(path)


def get_project_files(project_id: str) -> list[Path]:
    """获取项目目录下的所有文件
    
    Args:
        project_id: 项目 ID（目录名）
        
    Returns:
        文件路径列表，按文件名排序
    """
    project_dir = settings.project_file_base_path / project_id

    if not project_dir.exists():
        return []

    return sorted([f for f in project_dir.iterdir() if f.is_file()])


def get_project_file(project_id: str, file_name: str) -> Path:
    """获取项目目录下的指定文件
    
    Args:
        project_id: 项目 ID（目录名）
        file_name: 文件名称
        
    Returns:
        文件路径
    """
    return settings.project_file_base_path / project_id / file_name


def save_project_file(project_id: str, file_name: str, file_data: bytes) -> Path:
    """保存文件至项目目录
    
    在项目目录下创建文件并写入数据。
    
    Args:
        project_id: 项目 ID（目录名）
        file_name: 文件名称
        file_data: 文件数据（字节）
        
    Returns:
        保存后的文件路径
    """
    project_dir = settings.project_file_base_path / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    file_path = project_dir / file_name
    with open(file_path, "wb") as f:
        f.write(file_data)
    return file_path


def get_file_type(file_path: str | Path) -> str:
    """获取文件类型
    
    根据文件扩展名返回文件类型（小写）。
    
    Args:
        file_path: 文件路径
        
    Returns:
        文件类型，如 "pdf", "jpg", "png" 等
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    return suffix.split(".")[-1]


def unlink_file(file_path: str | Path):
    """删除文件

    删除文件

    Args:
        file_path: 文件路径
    """
    path = Path(file_path)
    path.unlink(missing_ok=True)
