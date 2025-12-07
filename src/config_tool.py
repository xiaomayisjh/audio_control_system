"""Cue 列表配置工具 - 独立入口

独立启动配置编辑器，用于创建和编辑 Cue 列表配置。

Requirements: 9.1
"""
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.tools.config_editor import ConfigEditor


def main():
    """配置工具入口
    
    独立启动 Cue 列表配置编辑器。
    
    Requirements: 9.1
    """
    print("="*50)
    print("Cue 列表配置编辑器")
    print("="*50)
    
    try:
        app = ConfigEditor()
        print("配置编辑器已启动")
        app.mainloop()
    except Exception as e:
        print(f"启动配置编辑器失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    print("配置编辑器已关闭")


if __name__ == "__main__":
    main()
