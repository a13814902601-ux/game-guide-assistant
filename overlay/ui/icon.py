# -*- coding: utf-8 -*-
"""程序图标：运行时用 QPainter 画，另存 PNG/ICO 给桌面快捷方式。"""
from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


def make_pixmap(size: int = 256) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    rect = QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92)
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.24, size * 0.24)
    grad = QLinearGradient(QPointF(0, 0), QPointF(size, size))
    grad.setColorAt(0.0, QColor("#0ea5a4"))
    grad.setColorAt(0.55, QColor("#0f766e"))
    grad.setColorAt(1.0, QColor("#0b3b3a"))
    p.fillPath(path, grad)
    p.setPen(QPen(QColor(255, 255, 255, 40), max(1, size // 128)))
    p.drawPath(path)

    font = QFont("Microsoft YaHei UI", int(size * 0.44), QFont.Bold)
    p.setFont(font)
    p.setPen(QColor("#eafffb"))
    p.drawText(rect, Qt.AlignCenter, "攻")

    # 右下角小气泡，像对话框
    bubble = QPainterPath()
    bw, bh = size * 0.34, size * 0.22
    bx, by = size * 0.55, size * 0.62
    bubble.addRoundedRect(QRectF(bx, by, bw, bh), size * 0.08, size * 0.08)
    p.fillPath(bubble, QColor("#5eead4"))
    p.setPen(QPen(QColor("#06251f"), max(1, size // 90)))
    for i in range(3):
        cx = bx + bw * (0.25 + i * 0.25)
        p.drawEllipse(QPointF(cx, by + bh * 0.5), size * 0.018, size * 0.018)
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_pixmap(size))
    return icon


def _png_to_ico(png_bytes: bytes, size: int) -> bytes:
    header = struct.pack("<HHH", 0, 1, 1)
    width = 0 if size >= 256 else size
    entry = struct.pack("<BBBBHHII", width, width, 0, 0, 1, 32, len(png_bytes), 22)
    return header + entry + png_bytes


def save_icon_files(directory: Path | str) -> tuple[Path, Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    png_path = directory / "icon.png"
    ico_path = directory / "icon.ico"
    pm = make_pixmap(256)
    pm.save(str(png_path), "PNG")
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice

    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    ico_path.write_bytes(_png_to_ico(bytes(ba), 256))
    return png_path, ico_path
