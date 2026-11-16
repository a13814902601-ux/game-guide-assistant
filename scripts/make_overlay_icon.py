# -*- coding: utf-8 -*-
"""生成悬浮窗图标（PNG + ICO），给桌面快捷方式用。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from overlay.ui.icon import save_icon_files  # noqa: E402


def main() -> int:
    app = QApplication([sys.argv[0]])
    png, ico = save_icon_files(ROOT / "overlay" / "assets")
    print(f"已生成：{png}\n已生成：{ico}")
    app.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
