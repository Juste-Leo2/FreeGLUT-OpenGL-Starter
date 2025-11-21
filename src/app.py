import os
import re
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QTextEdit, QPlainTextEdit, QPushButton, 
                             QFileDialog, QMessageBox, QSplitter, QLabel)
from PyQt6.QtGui import (QAction, QColor, QFont, QSyntaxHighlighter, QTextCharFormat, 
                         QPainter, QTextFormat, QPalette, QTextCursor)
from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, QObject

from . import config
from . import session_manager
from .file_manager import FileManager
from .build_manager import BuildManager

# --- COMPOSANTS DE L'ÉDITEUR (Syntaxe & Numéros de ligne) ---

class CppHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightingRules = []

        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#CC7832")) # Orange type JetBrains
        keywordFormat.setFontWeight(QFont.Weight.Bold)
        keywords = [
            "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor",
            "bool", "break", "case", "catch", "char", "char16_t", "char32_t", "class",
            "compl", "const", "constexpr", "const_cast", "continue", "decltype", "default",
            "delete", "do", "double", "dynamic_cast", "else", "enum", "explicit", "export",
            "extern", "false", "float", "for", "friend", "goto", "if", "inline", "int",
            "long", "mutable", "namespace", "new", "noexcept", "not", "not_eq", "nullptr",
            "operator", "or", "or_eq", "private", "protected", "public", "register",
            "reinterpret_cast", "return", "short", "signed", "sizeof", "static",
            "static_assert", "static_cast", "struct", "switch", "template", "this",
            "thread_local", "throw", "true", "try", "typedef", "typeid", "typename",
            "union", "unsigned", "using", "virtual", "void", "volatile", "wchar_t",
            "while", "xor", "xor_eq", "include"
        ]
        for pattern in keywords:
            self.highlightingRules.append((re.compile(f"\\b{pattern}\\b"), keywordFormat))

        # Includes <...>
        includeFormat = QTextCharFormat()
        includeFormat.setForeground(QColor("#6A8759")) # Vert
        self.highlightingRules.append((re.compile(r"<.*?>"), includeFormat))
        
        # Strings "..."
        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#6A8759"))
        self.highlightingRules.append((re.compile(r"\".*?\""), stringFormat))

        # Comments //
        singleLineCommentFormat = QTextCharFormat()
        singleLineCommentFormat.setForeground(QColor("#808080"))
        self.highlightingRules.append((re.compile(r"//[^\n]*"), singleLineCommentFormat))

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), format)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        
        # Style de l'éditeur
        font = QFont("Consolas", 12)
        self.setFont(font)
        self.setStyleSheet("background-color: #2B2B2B; color: #A9B7C6; border: none;")
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(' '))
        
        self.highlighter = CppHighlighter(self.document())
        self.updateLineNumberAreaWidth(0)

    def lineNumberAreaWidth(self):
        digits = 1
        max_val = max(1, self.blockCount())
        while max_val >= 10:
            max_val //= 10
            digits += 1
        space = 20 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        
        # --- CORRECTION ICI ---
        # On vérifie si le rectangle de mise à jour couvre tout le viewport
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#313335"))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#606366"))
                painter.drawText(0, top, self.lineNumberArea.width() - 5, self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            blockNumber += 1

# --- APPLICATION PRINCIPALE ---

class MainWindow(QMainWindow):
    # Signal pour mettre à jour l'interface depuis le thread de build
    log_signal = pyqtSignal(str, bool) # message, overwrite

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Éditeur C++ / OpenGL (Qt6)")
        self.resize(1200, 800)
        self._setup_dark_theme()
        self._ensure_directories_exist()

        # Managers
        self.file_manager = FileManager(self)
        self.build_manager = BuildManager(self)
        
        # UI Setup
        self.setup_ui()
        
        # Signaux
        self.log_signal.connect(self._handle_log_signal)
        
        # Démarrage
        self._load_session_or_start_default()

    def _setup_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        self.setPalette(palette)

    def _ensure_directories_exist(self):
        for path in [config.SAVE_DIR, config.BUILD_DIR]:
            if not os.path.exists(path):
                os.makedirs(path)

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        self.btn_new = QPushButton("Nouveau")
        self.btn_import = QPushButton("Importer")
        self.btn_save = QPushButton("Enregistrer")
        self.btn_save_as = QPushButton("Enr. sous")
        self.btn_close_tab = QPushButton("Fermer onglet")
        self.btn_compile = QPushButton("Compiler")
        self.btn_run = QPushButton("Exécuter")
        self.btn_run.setEnabled(False)
        self.btn_compile_run = QPushButton("Comp. & Exéc.")
        
        buttons = [self.btn_new, self.btn_import, self.btn_save, self.btn_save_as, 
                   self.btn_close_tab, self.btn_compile, self.btn_run, self.btn_compile_run]
        
        for btn in buttons:
            btn.setStyleSheet("padding: 5px;")
            toolbar_layout.addWidget(btn)
        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)

        # Splitter (Tabs + Output)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(self.splitter)

        # Tabs
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.file_manager.close_tab_by_index)
        self.splitter.addWidget(self.tab_widget)

        # Output Panel
        self.output_panel = QTextEdit()
        self.output_panel.setReadOnly(True)
        self.output_panel.setStyleSheet("background-color: #1E1E1E; color: #DDDDDD; font-family: Consolas;")
        self.splitter.addWidget(self.output_panel)
        self.splitter.setSizes([600, 150])

        # Connections
        self.btn_new.clicked.connect(self.file_manager.new_file)
        self.btn_import.clicked.connect(self.file_manager.open_file_dialog)
        self.btn_save.clicked.connect(self.file_manager.save_current_file)
        self.btn_save_as.clicked.connect(self.file_manager.save_current_file_as)
        self.btn_close_tab.clicked.connect(self.file_manager.close_current_tab)
        self.btn_compile.clicked.connect(self.build_manager.compile_code)
        self.btn_run.clicked.connect(self.build_manager.run_app)
        self.btn_compile_run.clicked.connect(self.build_manager.compile_and_run_code)

    # --- Interface méthodes (proxies) ---

    def add_editor_tab(self, tab_name, content):
        editor = CodeEditor()
        editor.setPlainText(content)
        editor.textChanged.connect(self.file_manager.on_text_changed_proxy)
        index = self.tab_widget.addTab(editor, tab_name)
        self.tab_widget.setCurrentIndex(index)
        return editor

    def get_current_editor(self):
        return self.tab_widget.currentWidget()

    def get_current_tab_name(self):
        idx = self.tab_widget.currentIndex()
        if idx == -1: return None
        return self.tab_widget.tabText(idx)

    def set_tab_name(self, name, new_name):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == name:
                self.tab_widget.setTabText(i, new_name)
                break

    def delete_tab(self, name):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == name:
                self.tab_widget.removeTab(i)
                break

    def get_all_tab_names(self):
        return [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]

    def set_active_tab(self, name):
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == name:
                self.tab_widget.setCurrentIndex(i)
                break

    def update_run_button_state(self):
        state = os.path.exists(config.OUTPUT_EXECUTABLE)
        self.btn_run.setEnabled(state)

    def closeEvent(self, event):
        if self.on_closing():
            event.accept()
        else:
            event.ignore()

    # --- Gestion Session ---

    def _load_session_or_start_default(self):
        session_data = session_manager.load_session()
        if session_data and session_data.get("open_files"):
            filepaths = session_data.get("open_files", [])
            active_file = session_data.get("active_file")
            active_name = None
            
            for path in filepaths:
                if os.path.exists(path):
                    self.file_manager.open_file(path)

            if active_file:
                for name, info in self.file_manager.open_tabs.items():
                    if info["filepath"] == active_file:
                        active_name = name
                        break
            if active_name:
                self.set_active_tab(active_name)
            
            if self.tab_widget.count() == 0:
                 self._open_start_file()
        else:
            self._open_start_file()
        self.update_run_button_state()

    def _open_start_file(self):
        if not os.path.exists(config.DEFAULT_START_FILE):
            with open(config.DEFAULT_START_FILE, "w", encoding="utf-8") as f: 
                f.write(config.DEFAULT_CPP_CODE)
        self.file_manager.open_file(config.DEFAULT_START_FILE)

    def on_closing(self):
        open_filepaths = self.file_manager.get_open_filepaths_in_order()
        current_info = self.file_manager.get_current_tab_info()
        active_filepath = current_info["filepath"] if current_info else None
        
        session_manager.save_session({"open_files": open_filepaths, "active_file": active_filepath})
        
        if self.file_manager.has_dirty_files():
            reply = QMessageBox.question(self, "Quitter", 
                "Des fichiers ont été modifiés. Voulez-vous vraiment quitter ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            return reply == QMessageBox.StandardButton.Yes
        return True

    # --- Thread-Safe Output Handling ---

    def update_output(self, message):
        self.log_signal.emit(message, True)

    def append_output(self, message):
        self.log_signal.emit(message, False)

    def _handle_log_signal(self, message, overwrite):
        if overwrite:
            self.output_panel.setPlainText(message)
        else:
            self.output_panel.moveCursor(QTextCursor.MoveOperation.End) if hasattr(self, 'QTextCursor') else None
            self.output_panel.insertPlainText(message)
            self.output_panel.verticalScrollBar().setValue(self.output_panel.verticalScrollBar().maximum())

    def show_warning(self, title, message):
        # Attention: à ne pas appeler depuis un thread secondaire
        QMessageBox.warning(self, title, message)