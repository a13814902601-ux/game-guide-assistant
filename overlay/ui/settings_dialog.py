# -*- coding: utf-8 -*-
"""设置窗口：显示 / 模型 / 知识库 / 关于。"""
from __future__ import annotations

import copy
import os

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..core import kb_bridge, llm_client
from ..core.config import Config
from . import theme


class FuncWorker(QThread):
    ok = Signal(object)
    fail = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.ok.emit(self.fn())
        except Exception as exc:
            self.fail.emit(str(exc))


class SettingsDialog(QDialog):
    def __init__(self, config: Config, main, hotkey_manager=None):
        super().__init__(main)
        self.config = config
        self.main = main
        self.hotkey_manager = hotkey_manager
        self.temp = Config(copy.deepcopy(config.data), config.path)
        self._workers: list[FuncWorker] = []
        self._current_id: str | None = None
        self._loading = False
        self._selected_game = config.last_game

        self.setWindowTitle("攻略助手 · 设置")
        self.setWindowIcon(main.windowIcon())
        self.setModal(True)
        self.resize(700, 580)
        self.setMinimumSize(640, 520)
        self.setStyleSheet(theme.BASE_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)
        title = QLabel("设置")
        title.setObjectName("Title")
        root.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_display_tab(), "显示")
        self.tabs.addTab(self._build_model_tab(), "模型")
        self.tabs.addTab(self._build_kb_tab(), "知识库")
        self.tabs.addTab(self._build_about_tab(), "关于")
        root.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox()
        self.cancel_btn = buttons.addButton("取消", QDialogButtonBox.RejectRole)
        self.save_btn = buttons.addButton("保存并关闭", QDialogButtonBox.AcceptRole)
        self.save_btn.setObjectName("Primary")
        self.cancel_btn.setObjectName("Secondary")
        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._on_save)
        root.addWidget(buttons)

        self._load_provider_list()
        if self.temp.providers:
            first_id = self.temp.providers[0]["id"]
            self._select_provider(first_id)
            self._load_provider(first_id)

    # ---------- 显示 ----------
    def _build_display_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        section = QLabel("窗口")
        section.setObjectName("Section")
        layout.addWidget(section)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("透明度"))
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(25, 100)
        self.opacity_slider.setValue(int(float(self.temp.window.get("opacity", 0.95)) * 100))
        self.opacity_value = QLabel(f"{self.opacity_slider.value()}%")
        self.opacity_value.setFixedWidth(42)
        self.opacity_slider.valueChanged.connect(self._preview_opacity)
        opacity_row.addWidget(self.opacity_slider, 1)
        opacity_row.addWidget(self.opacity_value)
        layout.addLayout(opacity_row)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("字号"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(11, 22)
        self.font_slider.setValue(int(self.temp.window.get("font_size", 14)))
        self.font_value = QLabel(f"{self.font_slider.value()} px")
        self.font_value.setFixedWidth(52)
        self.font_slider.valueChanged.connect(self._preview_font)
        font_row.addWidget(self.font_slider, 1)
        font_row.addWidget(self.font_value)
        layout.addLayout(font_row)

        self.topmost_check = QCheckBox("窗口始终置顶（盖在游戏上面）")
        self.topmost_check.setChecked(bool(self.temp.window.get("always_on_top", True)))
        self.topmost_check.toggled.connect(self._preview_topmost)
        layout.addWidget(self.topmost_check)

        hint = QLabel("透明度作用于整个窗口；游戏里建议 85%–95%，太低会影响读字。")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        section2 = QLabel("快捷键")
        section2.setObjectName("Section")
        layout.addWidget(section2)
        hot_row = QHBoxLayout()
        hot_row.addWidget(QLabel("显示/隐藏"))
        self.hotkey_edit = QKeySequenceEditCompat()
        self.hotkey_edit.setKeySequence(QKeySequence(self.temp.hotkey))
        hot_row.addWidget(self.hotkey_edit, 1)
        layout.addLayout(hot_row)
        hot_hint = QLabel(
            "点一下输入框，按下想用的组合键。默认 F8；单个字母/数字必须带 Ctrl / Alt / Shift / Win。\n"
            "如果提示被占用，换一个组合（例如 Ctrl+Shift+G）。"
        )
        hot_hint.setObjectName("Hint")
        hot_hint.setWordWrap(True)
        layout.addWidget(hot_hint)

        section3 = QLabel("位置与大小")
        section3.setObjectName("Section")
        layout.addWidget(section3)
        reset_row = QHBoxLayout()
        reset_btn = QPushButton("重置位置和大小")
        reset_btn.setObjectName("Secondary")
        reset_btn.clicked.connect(self.main.reset_geometry)
        reset_row.addWidget(reset_btn)
        reset_row.addStretch(1)
        layout.addLayout(reset_row)
        pos_hint = QLabel("拖动标题栏移动；拖窗口四边或右下角缩放。关闭窗口会缩到托盘，不会退出。")
        pos_hint.setObjectName("Hint")
        pos_hint.setWordWrap(True)
        layout.addWidget(pos_hint)
        layout.addStretch(1)
        return page

    def _preview_opacity(self, value: int):
        self.opacity_value.setText(f"{value}%")
        self.main.setWindowOpacity(max(0.25, value / 100.0))

    def _preview_font(self, value: int):
        self.font_value.setText(f"{value} px")
        self.main.chat.set_font_size(value)

    def _preview_topmost(self, checked: bool):
        self.main._apply_topmost(bool(checked))

    # ---------- 模型 ----------
    def _build_model_tab(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(6)
        left.addWidget(QLabel("提供商"))
        self.provider_list = QListWidget()
        self.provider_list.setMinimumWidth(170)
        self.provider_list.currentItemChanged.connect(self._on_provider_selected)
        left.addWidget(self.provider_list, 1)
        add_btn = QPushButton("＋ 新增")
        add_btn.setObjectName("Secondary")
        add_btn.clicked.connect(self._add_provider)
        del_btn = QPushButton("删除")
        del_btn.setObjectName("Danger")
        del_btn.clicked.connect(self._delete_provider)
        left.addWidget(add_btn)
        left.addWidget(del_btn)
        layout.addLayout(left, 0)

        right_box = QWidget()
        right = QVBoxLayout(right_box)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(8)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setVerticalSpacing(7)
        self.name_edit = QLineEdit()
        self.base_edit = QLineEdit()
        self.base_edit.setPlaceholderText("https://api.deepseek.com/v1")
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        key_row = QHBoxLayout()
        key_row.setContentsMargins(0, 0, 0, 0)
        key_row.setSpacing(4)
        key_row.addWidget(self.key_edit, 1)
        self.eye_btn = QToolButton()
        self.eye_btn.setText("👁")
        self.eye_btn.setCheckable(True)
        self.eye_btn.setToolTip("显示/隐藏密钥")
        self.eye_btn.setCursor(Qt.PointingHandCursor)
        self.eye_btn.toggled.connect(
            lambda on: self.key_edit.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        )
        key_row.addWidget(self.eye_btn)
        key_wrap = QWidget()
        key_wrap.setLayout(key_row)

        model_row = QHBoxLayout()
        model_row.setContentsMargins(0, 0, 0, 0)
        model_row.setSpacing(5)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        model_row.addWidget(self.model_combo, 1)
        self.fetch_btn = QPushButton("拉取清单")
        self.fetch_btn.setObjectName("Secondary")
        self.fetch_btn.clicked.connect(self._fetch_models)
        model_row.addWidget(self.fetch_btn)
        model_wrap = QWidget()
        model_wrap.setLayout(model_row)

        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(256, 65536)
        self.max_tokens.setSingleStep(256)
        self.max_tokens.setValue(int(self.temp.active_provider.get("max_tokens", 4096)))
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.1)
        self.temperature.setValue(float(self.temp.active_provider.get("temperature", 0.3)))

        form.addRow("名称", self.name_edit)
        form.addRow("接口地址", self.base_edit)
        form.addRow("API Key", key_wrap)
        form.addRow("模型", model_wrap)
        form.addRow("最大输出", self.max_tokens)
        form.addRow("温度", self.temperature)
        right.addLayout(form)

        action_row = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.setObjectName("Secondary")
        self.test_btn.clicked.connect(self._test_connection)
        save_provider = QPushButton("保存此提供商")
        save_provider.setObjectName("Primary")
        save_provider.clicked.connect(lambda: self._save_provider(show_status=True))
        active_btn = QPushButton("设为当前")
        active_btn.setObjectName("Secondary")
        active_btn.clicked.connect(self._set_active_provider)
        action_row.addWidget(self.test_btn)
        action_row.addWidget(save_provider)
        action_row.addWidget(active_btn)
        action_row.addStretch(1)
        right.addLayout(action_row)

        self.model_status = QLabel("")
        self.model_status.setObjectName("Hint")
        self.model_status.setWordWrap(True)
        right.addWidget(self.model_status)
        note = QLabel(
            "支持 OpenAI 兼容接口（地址一般以 /v1 结尾）。\n"
            "示例：DeepSeek https://api.deepseek.com/v1、OpenAI https://api.openai.com/v1、"
            "本机反代 http://127.0.0.1:8788/v1。\n"
            "密钥只保存在本机配置里，不会写进项目或发到别处。"
        )
        note.setObjectName("Hint")
        note.setWordWrap(True)
        right.addWidget(note)
        right.addStretch(1)
        layout.addWidget(right_box, 1)
        return page

    def _load_provider_list(self, select_id: str | None = None):
        self._loading = True
        current = select_id or self._current_id
        self.provider_list.clear()
        active_id = self.temp.data.get("active_provider")
        for provider in self.temp.providers:
            label = ("● " if provider.get("id") == active_id else "   ") + str(provider.get("name", "未命名"))
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, provider.get("id"))
            self.provider_list.addItem(item)
        target = current or (self.temp.providers[0]["id"] if self.temp.providers else None)
        if target:
            for i in range(self.provider_list.count()):
                item = self.provider_list.item(i)
                if item.data(Qt.UserRole) == target:
                    self.provider_list.setCurrentItem(item)
                    break
        self._loading = False

    def _select_provider(self, provider_id: str):
        for i in range(self.provider_list.count()):
            item = self.provider_list.item(i)
            if item.data(Qt.UserRole) == provider_id:
                self.provider_list.setCurrentItem(item)
                return

    def _on_provider_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None):
        if self._loading or current is None:
            return
        # 先取 id：保存上一个提供商时可能刷新列表，current 指针会失效
        current_id = current.data(Qt.UserRole)
        if previous is not None and self._current_id:
            self._save_provider(show_status=False, provider_id=self._current_id)
        self._load_provider(current_id)

    def _provider(self, provider_id: str) -> dict | None:
        for provider in self.temp.providers:
            if provider.get("id") == provider_id:
                return provider
        return None

    def _load_provider(self, provider_id: str):
        provider = self._provider(provider_id)
        if provider is None:
            return
        self._current_id = provider_id
        self._loading = True
        self.name_edit.setText(str(provider.get("name", "")))
        self.base_edit.setText(str(provider.get("base_url", "")))
        self.key_edit.setText(str(provider.get("api_key", "")))
        self.model_combo.clear()
        models = [str(m) for m in provider.get("models", []) if str(m)]
        current_model = str(provider.get("model", ""))
        if current_model and current_model not in models:
            models.insert(0, current_model)
        self.model_combo.addItems(models)
        self.model_combo.setCurrentText(current_model)
        self.max_tokens.setValue(int(provider.get("max_tokens", 4096)))
        self.temperature.setValue(float(provider.get("temperature", 0.3)))
        self.model_status.setText("")
        self._loading = False

    def _collect_provider(self) -> dict:
        base = self._provider(self._current_id) if self._current_id else {}
        data = dict(base or {})
        data["id"] = self._current_id or data.get("id") or f"custom-{os.urandom(3).hex()}"
        data["name"] = self.name_edit.text().strip() or "未命名提供商"
        data["base_url"] = self.base_edit.text().strip()
        data["api_key"] = self.key_edit.text().strip()
        data["model"] = self.model_combo.currentText().strip()
        data["models"] = [self.model_combo.itemText(i) for i in range(self.model_combo.count())]
        data["max_tokens"] = int(self.max_tokens.value())
        data["temperature"] = float(self.temperature.value())
        return data

    def _save_provider(self, show_status: bool = True, provider_id: str | None = None) -> bool:
        pid = provider_id or self._current_id
        if not pid:
            return False
        # 切换列表项时字段里还是「上一个提供商」的内容，按传进来的 id 保存
        provider = self._collect_provider()
        provider["id"] = pid
        if not provider.get("name"):
            provider["name"] = "未命名提供商"
        self.temp.upsert_provider(provider)
        if pid == self._current_id:
            self._current_id = provider["id"]
        self._update_item_label(pid)
        if show_status:
            self.model_status.setText("✅ 已保存此提供商")
        return True

    def _update_item_label(self, provider_id: str):
        provider = self._provider(provider_id)
        if not provider:
            return
        active_id = self.temp.data.get("active_provider")
        label = ("● " if provider_id == active_id else "   ") + str(provider.get("name", "未命名"))
        for i in range(self.provider_list.count()):
            item = self.provider_list.item(i)
            if item.data(Qt.UserRole) == provider_id:
                item.setText(label)
                return

    def _add_provider(self):
        if self._current_id:
            self._save_provider(show_status=False)
        provider = {
            "id": f"custom-{os.urandom(3).hex()}",
            "name": "新提供商",
            "base_url": "https://",
            "api_key": "",
            "model": "",
            "models": [],
            "max_tokens": 4096,
            "temperature": 0.3,
        }
        self.temp.upsert_provider(provider)
        self._load_provider_list(select_id=provider["id"])
        self._select_provider(provider["id"])
        self._load_provider(provider["id"])

    def _delete_provider(self):
        if not self._current_id:
            return
        if len(self.temp.providers) <= 1:
            QMessageBox.information(self, "不能删除", "至少要保留一个提供商。")
            return
        provider = self._provider(self._current_id)
        name = provider.get("name", "") if provider else ""
        if QMessageBox.question(self, "删除提供商", f"确定删除「{name}」？") != QMessageBox.Yes:
            return
        self.temp.remove_provider(self._current_id)
        self._current_id = None
        self._load_provider_list()
        if self.temp.providers:
            first_id = self.temp.providers[0]["id"]
            self._select_provider(first_id)
            self._load_provider(first_id)

    def _set_active_provider(self):
        if not self._current_id:
            return
        self._save_provider(show_status=False)
        self.temp.set_active_provider(self._current_id)
        self._load_provider_list(select_id=self._current_id)
        self.model_status.setText("✅ 已设为当前使用的提供商（点「保存并关闭」生效）")

    def _run_worker(self, fn, on_ok, on_fail, button: QPushButton | None = None):
        if button is not None:
            button.setEnabled(False)
        worker = FuncWorker(fn)
        self._workers.append(worker)

        def cleanup():
            if button is not None:
                button.setEnabled(True)
            if worker in self._workers:
                self._workers.remove(worker)
            worker.deleteLater()

        worker.ok.connect(on_ok)
        worker.fail.connect(on_fail)
        worker.finished.connect(cleanup)
        worker.start()

    def _fetch_models(self):
        self._save_provider(show_status=False)
        provider = self._collect_provider()
        if not provider.get("base_url"):
            QMessageBox.warning(self, "缺少接口地址", "先填 Base URL，例如 https://api.deepseek.com/v1")
            return
        self.model_status.setText("正在拉取模型清单…")

        def ok(models):
            current = self.model_combo.currentText().strip()
            self.model_combo.clear()
            self.model_combo.addItems(models)
            if current:
                self.model_combo.setCurrentText(current if current in models else models[0])
            self.model_status.setText(f"✅ 拉到 {len(models)} 个模型，选一个后点「保存此提供商」")

        def fail(message):
            self.model_status.setText("❌ 拉取失败：" + message.replace("\n", " ")[:200])
            QMessageBox.warning(self, "拉取模型清单失败", message)

        self._run_worker(lambda: llm_client.fetch_models(provider), ok, fail, self.fetch_btn)

    def _test_connection(self):
        self._save_provider(show_status=False)
        provider = self._collect_provider()
        if not provider.get("base_url") or not provider.get("model"):
            QMessageBox.warning(self, "配置不完整", "先填接口地址并选择模型。")
            return
        self.model_status.setText("正在测试连接…")

        def ok(result):
            text = (result.text or "").strip() or "（模型只返回了思考内容）"
            self.model_status.setText("✅ 连接成功：" + text[:80])
            QMessageBox.information(self, "连接成功", f"模型回复：{text[:200]}")

        def fail(message):
            self.model_status.setText("❌ 连接失败：" + message.replace("\n", " ")[:200])
            QMessageBox.warning(self, "连接失败", message)

        self._run_worker(
            lambda: llm_client.chat_once(
                provider, [{"role": "user", "content": "只回复四个字：连接成功"}], max_tokens=512
            ),
            ok,
            fail,
            self.test_btn,
        )

    # ---------- 知识库 ----------
    def _build_kb_tab(self) -> QWidget:
        self._kb_root_changed = False
        self._kb_root_value = self.temp.kb_root
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        section = QLabel("攻略库目录（外挂，归 MCP）")
        section.setObjectName("Section")
        layout.addWidget(section)
        path_row = QHBoxLayout()
        self.kb_path_edit = QLineEdit()
        self.kb_path_edit.setReadOnly(True)
        self.kb_path_edit.setPlaceholderText("还没有找到 output 目录")
        choose_btn = QPushButton("选择目录…")
        choose_btn.setObjectName("Secondary")
        choose_btn.clicked.connect(self._choose_kb_dir)
        auto_btn = QPushButton("自动检测")
        auto_btn.setObjectName("Secondary")
        auto_btn.clicked.connect(self._auto_kb_dir)
        path_row.addWidget(self.kb_path_edit, 1)
        path_row.addWidget(choose_btn)
        path_row.addWidget(auto_btn)
        layout.addLayout(path_row)

        section2 = QLabel("当前回答使用的游戏")
        section2.setObjectName("Section")
        layout.addWidget(section2)
        self.game_combo = QComboBox()
        self.game_combo.currentIndexChanged.connect(self._update_kb_info)
        layout.addWidget(self.game_combo)
        self.kb_info = QLabel("")
        self.kb_info.setObjectName("Hint")
        self.kb_info.setWordWrap(True)
        layout.addWidget(self.kb_info)
        row = QHBoxLayout()
        refresh_btn = QPushButton("重新读取")
        refresh_btn.setObjectName("Secondary")
        refresh_btn.clicked.connect(self._reload_games)
        open_btn = QPushButton("打开知识库文件夹")
        open_btn.setObjectName("Secondary")
        open_btn.clicked.connect(self._open_kb_folder)
        row.addWidget(refresh_btn)
        row.addWidget(open_btn)
        row.addStretch(1)
        layout.addLayout(row)
        note = QLabel(
            "exe 不内置攻略库，只读取外部 output 目录（MCP 服务器用同一份）。\n"
            "推荐把 output 放在 exe 旁边；也可以在项目根目录、%APPDATA%\\GameGuideAssistant\\output，"
            "或用环境变量 GGA_OUTPUT_DIR 指定。\n"
            "output/<游戏>/data 是结构化条目，guides 是可选全文；公开版只有 data。"
        )
        note.setObjectName("Hint")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)
        self._reload_games()
        return page

    def _choose_kb_dir(self):
        start = self.kb_path_edit.text().strip() or str(kb_bridge.current_output_root())
        folder = QFileDialog.getExistingDirectory(self, "选择攻略库 output 目录", start)
        if not folder:
            return
        root = kb_bridge.normalize_kb_root(folder)
        if root is None or not any(root.glob("*/_index.json")):
            QMessageBox.warning(
                self,
                "不像是知识库目录",
                "这个目录下没有找到 <游戏>/_index.json。\n请选择包含 deepspace-pawnshop 等游戏子目录的 output 目录。",
            )
            return
        kb_bridge.set_output_root(root)
        self.temp.kb_root = str(root)
        self._kb_root_changed = True
        self._kb_root_value = str(root)
        self.kb_path_edit.setText(str(root))
        self._reload_games()

    def _auto_kb_dir(self):
        root = kb_bridge.auto_output_root()
        if root is None:
            QMessageBox.warning(
                self,
                "没有找到知识库",
                "把 output 目录放到 exe 旁边，或用「选择目录…」手动指定。",
            )
            return
        kb_bridge.set_output_root(root)
        self.temp.kb_root = ""
        self._kb_root_changed = True
        self._kb_root_value = ""
        self.kb_path_edit.setText(str(root))
        self._reload_games()

    def _reload_games(self):
        if hasattr(self, "kb_path_edit"):
            self.kb_path_edit.setText(str(kb_bridge.current_output_root()))
        self.game_combo.blockSignals(True)
        self.game_combo.clear()
        games = kb_bridge.games()
        selected_index = 0
        for i, game in enumerate(games):
            slug = game.get("game", "")
            guides = sum((game.get("guides") or {}).values())
            label = f"{game.get('name_zh') or slug}（{slug}）· 数据 {game.get('data_total', '?')} 条 / 全文 {guides} 篇"
            self.game_combo.addItem(label, slug)
            if slug == self._selected_game:
                selected_index = i
        if games:
            self.game_combo.setCurrentIndex(selected_index)
            self._selected_game = games[selected_index].get("game", self._selected_game)
        else:
            self.game_combo.addItem("（未找到攻略库）", "")
        self.game_combo.blockSignals(False)
        self._update_kb_info()

    def _update_kb_info(self, *_):
        slug = self.game_combo.currentData()
        if not slug:
            self.kb_info.setText(
                f"当前路径：{kb_bridge.current_output_root()}\n"
                "没有找到 <游戏>/_index.json。请选择正确的 output 目录。"
            )
            return
        self._selected_game = slug
        for game in kb_bridge.games():
            if game.get("game") == slug:
                cats = game.get("data_categories") or {}
                cat_text = "、".join(f"{k} {v}" for k, v in cats.items())
                guides = sum((game.get("guides") or {}).values())
                self.kb_info.setText(
                    f"结构化数据 {game.get('data_total', '?')} 条（{cat_text}）；攻略全文 {guides} 篇。\n"
                    f"目录：{kb_bridge.current_output_root() / slug}"
                )
                return

    def _open_kb_folder(self):
        slug = self.game_combo.currentData()
        folder = kb_bridge.current_output_root() / (slug or "")
        if slug and folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        elif kb_bridge.current_output_root().is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(kb_bridge.current_output_root())))
        else:
            QMessageBox.warning(self, "目录不存在", str(folder))

    # ---------- 关于 ----------
    def _build_about_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        text = QLabel(
            "<b>攻略助手悬浮窗 v1.0.0</b><br><br>"
            "查询链路：<code>game-guide-qa</code> 技能规则 + 本地知识库查询核心"
            "（与 MCP 服务器 <code>game-guide-kb</code> 同一套 <code>kb/query.py</code>）。<br><br>"
            "<b>攻略库</b>：exe 不内置数据，外挂 <code>output</code> 目录；"
            "MCP 服务器和悬浮窗共用同一份，可在「知识库」页切换。<br><br>"
            "<b>数据流向</b>：问题先在本地知识库检索，只把命中的攻略片段发给所配置的 LLM；"
            "不读游戏存档，不上传整个知识库。<br><br>"
            "<b>密钥位置</b>：本机 <code>%APPDATA%\\GameGuideAssistant\\overlay-config.json</code>，"
            "不写进 git / outbox。<br><br>"
            "<b>使用限制</b>：独占全屏（DirectX exclusive fullscreen）游戏通常盖不住，"
            "请把游戏改成「无边框窗口 / 窗口化」。<br><br>"
            "<b>默认快捷键</b>：F8 显示/隐藏；Escape 隐藏；关闭按钮缩到托盘。"
        )
        text.setTextFormat(Qt.RichText)
        text.setWordWrap(True)
        layout.addWidget(text)
        open_cfg = QPushButton("打开配置文件夹")
        open_cfg.setObjectName("Secondary")
        open_cfg.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config.path.parent)))
        )
        layout.addWidget(open_cfg, 0, Qt.AlignLeft)
        layout.addStretch(1)
        return page

    # ---------- 保存 / 取消 ----------
    def _on_save(self):
        if self._current_id:
            self._save_provider(show_status=False)
        if not self.temp.providers:
            QMessageBox.warning(self, "没有提供商", "至少保留一个模型提供商。")
            return
        active = self.temp.active_provider
        if not active.get("base_url") or not active.get("model"):
            QMessageBox.warning(
                self, "当前提供商配置不完整", "当前使用的提供商需要填 Base URL 并选择模型。"
            )
            return

        spec = self.hotkey_edit.keySequence().toString().strip()
        if not spec:
            QMessageBox.warning(self, "快捷键为空", "点快捷键输入框，按下一个组合键。")
            return
        if self.hotkey_manager is not None and (
            spec != self.config.hotkey or not getattr(self.hotkey_manager, "current", "")
        ):
            ok, error = self.hotkey_manager.register(spec)
            if not ok:
                QMessageBox.critical(
                    self,
                    "快捷键注册失败",
                    f"{error}\n\n换一个组合再试（例如 Ctrl+Shift+G）。",
                )
                return

        self.temp.hotkey = spec
        self.temp.update_window(
            opacity=self.opacity_slider.value() / 100.0,
            font_size=self.font_slider.value(),
            always_on_top=self.topmost_check.isChecked(),
        )
        if self._selected_game:
            self.temp.last_game = self._selected_game
        if getattr(self, "_kb_root_changed", False):
            self.temp.kb_root = self._kb_root_value
        self.config.data = copy.deepcopy(self.temp.data)
        try:
            self.config.save()
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", f"写配置文件失败：{exc}")
            return
        self.accept()

    def reject(self):
        # 取消时把实时预览还原成原配置
        self.main.apply_config()
        super().reject()


class QKeySequenceEditCompat(QWidget):
    """QKeySequenceEdit 的轻封装：限制只录一段，并给出占位提示。"""

    def __init__(self):
        super().__init__()
        from PySide6.QtWidgets import QKeySequenceEdit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QKeySequenceEdit()
        self.edit.setMaximumSequenceLength(1)
        self.edit.setToolTip("点这里，然后按下想用的快捷键组合")
        layout.addWidget(self.edit)

    def setKeySequence(self, seq: QKeySequence):
        self.edit.setKeySequence(seq)

    def keySequence(self) -> QKeySequence:
        return self.edit.keySequence()
