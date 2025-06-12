import os
import sys

# 内部存储映射关系
# _virtual_to_real_map: 虚拟根路径 -> 实际根路径
# _real_to_virtual_map: 实际根路径 -> 虚拟根路径
_virtual_to_real_map = {}
_real_to_virtual_map = {}

# 存储按长度降序排列的根路径，用于最长前缀匹配
_virtual_roots_sorted = []
_real_roots_sorted = []


def _normalize_path(path):
    """
    规范化路径：
    1. 转换为绝对路径。
    2. 移除冗余分隔符 (//)，解析 '.' 和 '..'.
    3. 移除末尾的分隔符，除非是根路径本身 (如 '/' 或 'C:\')。
    """
    if not path:
        return ""

    # os.path.abspath 会处理相对路径，并根据操作系统加入盘符或根目录
    normalized_path = os.path.abspath(path)

    # os.path.normpath 会移除多余的斜杠，处理 . 和 ..
    normalized_path = os.path.normpath(normalized_path)

    # 确保在 Windows 上，盘符后的斜杠不被移除 (e.g., C: -> C:\)
    # 对于UNIX/Linux，根目录 '/' normpath后依然是 '/'
    if sys.platform.startswith("win") and len(normalized_path) == 2 and normalized_path[1] == ":":
        normalized_path += os.sep

    return normalized_path


def _parse_fs_map_env():
    """
    解析 FS_MAP 环境变量并初始化映射表。
    环境变量格式示例: "/virtual1:/actual/path1;/virtual2:/actual/path2"
    或者 Windows 格式: "C:\virt:D:\actual;E:\another_virt:F:\another_actual"
    """
    global _virtual_to_real_map, _real_to_virtual_map, _virtual_roots_sorted, _real_roots_sorted

    # 清空现有映射，以便重新解析（例如，如果需要重新加载配置）
    _virtual_to_real_map.clear()
    _real_to_virtual_map.clear()
    _virtual_roots_sorted.clear()
    _real_roots_sorted.clear()

    fs_map_str = os.getenv("AGENT_FS_MAP")

    if not fs_map_str:
        # print("Info: FS_MAP environment variable is not set or is empty.")
        fs_map_str = ""  # 确保 fs_map_str 是一个字符串，即使它为空

    # 添加对 AGENT_FS_MAP_TMP_DIR 的默认映射
    tmp_dir = os.getenv("AGENT_FS_MAP_TMP_DIR")
    if tmp_dir:
        # 如果 /tmp 已经在 AGENT_FS_MAP 中定义，则优先使用 AGENT_FS_MAP 中的定义
        # 这里只是在没有显式定义时，添加一个默认值
        # 检查现有映射中是否已经包含 /tmp
        existing_virtual_roots = [p.split(":", 1)[0].strip() for p in fs_map_str.split(";") if ":" in p]
        if "/tmp" not in existing_virtual_roots:
            if fs_map_str:
                fs_map_str += ";"
            fs_map_str += f"/tmp:{tmp_dir}"

    if not fs_map_str:  # 如果经过处理后仍然为空，则直接返回
        return

    # 分割每个映射对
    pairs = fs_map_str.split(";")

    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue

        # 分割虚拟路径和实际路径，只分割第一个 ':'
        parts = pair.split(":", 1)
        if len(parts) == 2:
            virtual_raw = parts[0].strip()
            real_raw = parts[1].strip()

            if not virtual_raw or not real_raw:
                print(f"Warning: Malformed FS_MAP entry (empty path) '{pair}'. Skipping.")
                continue

            virtual_root = _normalize_path(virtual_raw)
            real_root = _normalize_path(real_raw)

            if not virtual_root or not real_root:
                print(f"Warning: Failed to normalize paths for entry '{pair}'. Skipping.")
                continue

            if virtual_root in _virtual_to_real_map:
                print(f"Warning: Duplicate virtual root '{virtual_root}' found. Overwriting existing mapping.")
            if real_root in _real_to_virtual_map:
                print(f"Warning: Duplicate real root '{real_root}' found. Overwriting existing mapping.")

            _virtual_to_real_map[virtual_root] = real_root
            _real_to_virtual_map[real_root] = virtual_root
        else:
            print(f"Warning: Malformed FS_MAP entry (missing colon) '{pair}'. Skipping.")

    # 对所有根路径按长度降序排序，以便实现最长前缀匹配
    _virtual_roots_sorted[:] = sorted(_virtual_to_real_map.keys(), key=len, reverse=True)
    _real_roots_sorted[:] = sorted(_real_to_virtual_map.keys(), key=len, reverse=True)


# 模块加载时自动解析环境变量
_parse_fs_map_env()


def resolve_virtual_path(virtual_path: str) -> str | None:
    """
    将虚拟路径解析为实际路径。

    参数:
        virtual_path (str): 需要解析的虚拟路径。

    返回:
        str | None: 对应的实际路径，如果找不到映射则返回 None。
    """
    if not virtual_path:
        return None

    normalized_virtual_path = _normalize_path(virtual_path)

    for v_root in _virtual_roots_sorted:
        if not os.path.isabs(virtual_path):
            normalized_virtual_path = os.path.join(v_root, virtual_path)
            normalized_virtual_path = _normalize_path(normalized_virtual_path)

        # 检查是否是精确匹配根路径
        if normalized_virtual_path == v_root:
            return _virtual_to_real_map[v_root]

        # 检查是否以虚拟根路径开头，并且后面紧跟着路径分隔符
        # 例如，v_root="/a", normalized_virtual_path="/a/b"
        # 避免 "/a" 匹配到 "/apple"
        if normalized_virtual_path.startswith(v_root + os.sep):
            # 获取虚拟路径中根路径之后的部分
            relative_path = normalized_virtual_path[len(v_root) :]

            # 使用 os.path.join 拼接路径，它会自动处理分隔符
            real_base = _virtual_to_real_map[v_root]

            # 确保相对路径在拼接前移除了开头的 os.sep，因为 join 会自动添加
            # 例如: os.path.join('/real', '/sub/path') -> '/real/sub/path' (Linux)
            # 但如果 real_base 是 C:\ 且 relative_path 是 \sub\path，直接 join 也行
            # _normalize_path 会再处理一次，确保最终结果正确
            return _normalize_path(os.path.join(real_base, relative_path.lstrip(os.sep)))

    return None


def get_virtual_path(real_path: str) -> str | None:
    """
    将实际路径转换为虚拟路径。

    参数:
        real_path (str): 需要转换的实际路径。

    返回:
        str | None: 对应的虚拟路径，如果找不到映射则返回 None。
    """
    if not real_path:
        return None

    normalized_real_path = _normalize_path(real_path)

    for r_root in _real_roots_sorted:
        # 检查是否是精确匹配根路径
        if normalized_real_path == r_root:
            return _real_to_virtual_map[r_root]

        # 检查是否以实际根路径开头，并且后面紧跟着路径分隔符
        if normalized_real_path.startswith(r_root + os.sep):
            # 获取实际路径中根路径之后的部分
            relative_path = normalized_real_path[len(r_root) :]

            # 使用 os.path.join 拼接路径
            virtual_base = _real_to_virtual_map[r_root]

            # 确保相对路径在拼接前移除了开头的 os.sep
            return _normalize_path(os.path.join(virtual_base, relative_path.lstrip(os.sep)))

    return None


def get_map_status():
    """
    返回当前加载的 FS_MAP 状态。
    """
    return {
        "virtual_to_real_map": _virtual_to_real_map,
        "real_to_virtual_map": _real_to_virtual_map,
        "virtual_roots_sorted": _virtual_roots_sorted,
        "real_roots_sorted": _real_roots_sorted,
        "fs_map_env_raw": os.getenv("FS_MAP"),
    }


# 您可以添加一个函数来手动重新加载配置，如果环境变量在程序运行时发生变化
def reload_fs_map():
    """
    重新加载并解析 FS_MAP 环境变量。
    如果 FS_MAP 环境变量在程序运行时发生变化，可以调用此函数更新映射。
    """
    _parse_fs_map_env()
