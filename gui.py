"""PySide6 GUI for GLB to UE5 import pipeline."""

import os
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from blender_bridge import find_blender, process_glb
from ue5_bridge import import_fbx


class ImportWorker(QObject):
    """Worker that runs the import pipeline in a background thread."""

    status = Signal(str)
    progress = Signal(int)
    finished = Signal(bool, str)  # success, message

    def __init__(self, glb_path, decimate_ratio, ue5_folder, import_materials, complex_collision, merge_meshes, merge_children, source_folder):
        super().__init__()
        self.glb_path = glb_path
        self.decimate_ratio = decimate_ratio
        self.ue5_folder = ue5_folder
        self.import_materials = import_materials
        self.complex_collision = complex_collision
        self.merge_meshes = merge_meshes
        self.merge_children = merge_children
        self.source_folder = source_folder

    @Slot()
    def run(self):
        temp_dir = None
        try:
            # Validate inputs
            if not os.path.isfile(self.glb_path):
                self.finished.emit(False, f"GLB file not found: {self.glb_path}")
                return

            # Check Blender
            self.status.emit("Checking for Blender...")
            self.progress.emit(5)
            blender = find_blender()
            if not blender:
                self.finished.emit(
                    False,
                    "Blender not found. Install Blender or set BLENDER_PATH.",
                )
                return
            self.status.emit(f"Found Blender: {blender}")

            # Determine FBX output location
            stem = Path(self.glb_path).stem
            if self.source_folder:
                os.makedirs(self.source_folder, exist_ok=True)
                fbx_path = os.path.join(self.source_folder, f"{stem}.fbx")
            else:
                temp_dir = tempfile.mkdtemp(prefix="glb_importer_")
                fbx_path = os.path.join(temp_dir, f"{stem}.fbx")

            # Run Blender conversion
            self.status.emit("Processing GLB in Blender (this may take a while)...")
            self.progress.emit(15)
            result = process_glb(self.glb_path, self.decimate_ratio, fbx_path, merge_children=self.merge_children)
            self.status.emit("Blender processing complete")
            self.progress.emit(60)

            # Log Blender output
            if result.stdout:
                for line in result.stdout.strip().split("\n")[-10:]:
                    self.status.emit(f"  [Blender] {line}")

            if not os.path.isfile(fbx_path):
                self.finished.emit(False, "Blender did not produce FBX output")
                return

            fbx_size = os.path.getsize(fbx_path) / (1024 * 1024)
            self.status.emit(f"FBX file created: {fbx_size:.1f} MB")

            # Import into UE5
            self.status.emit("Connecting to UE5 Editor...")
            self.progress.emit(70)
            import_result = import_fbx(fbx_path, self.ue5_folder, import_materials=self.import_materials, complex_collision=self.complex_collision, combine_meshes=self.merge_meshes)
            self.progress.emit(95)

            output = import_result.get("output", [])
            if output:
                lines = output if isinstance(output, list) else [output]
                for line in lines:
                    self.status.emit(f"  [UE5] {str(line).strip()}")

            self.progress.emit(100)
            if self.source_folder:
                self.status.emit(f"FBX saved to: {fbx_path}")
            self.finished.emit(True, f"Successfully imported '{stem}' to {self.ue5_folder}")

        except Exception as e:
            self.finished.emit(False, f"Error: {e}\n{traceback.format_exc()}")
        finally:
            # Clean up temp files (only if not using source folder)
            if temp_dir and os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                except OSError:
                    pass


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GLB to UE5 Importer")
        self.setMinimumWidth(600)
        self._worker_thread = None
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # GLB file picker
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("GLB File:"))
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Drag & drop or browse for .glb file")
        self.file_input.textChanged.connect(self._on_file_changed)
        file_layout.addWidget(self.file_input)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.browse_btn)
        layout.addLayout(file_layout)

        # Blender settings row
        blender_layout = QHBoxLayout()
        blender_layout.addWidget(QLabel("Blender:"))

        blender_layout.addSpacing(10)

        blender_layout.addWidget(QLabel("Decimate Ratio:"))
        self.decimate_spin = QDoubleSpinBox()
        self.decimate_spin.setRange(0.0, 1.0)
        self.decimate_spin.setSingleStep(0.05)
        self.decimate_spin.setValue(1.0)
        self.decimate_spin.setToolTip("1.0 = no reduction, 0.1 = aggressive reduction")
        blender_layout.addWidget(self.decimate_spin)

        blender_layout.addSpacing(20)

        self.merge_children_cb = QCheckBox("Merge Child Meshes")
        self.merge_children_cb.setChecked(True)
        self.merge_children_cb.setToolTip("In Blender, merge child meshes under empty parent objects into single meshes before export")
        blender_layout.addWidget(self.merge_children_cb)

        blender_layout.addStretch()
        layout.addLayout(blender_layout)

        # UE5 settings row
        ue5_layout = QHBoxLayout()
        ue5_layout.addWidget(QLabel("UE5:"))

        ue5_layout.addSpacing(10)

        self.import_materials_cb = QCheckBox("Import Materials")
        self.import_materials_cb.setChecked(True)
        ue5_layout.addWidget(self.import_materials_cb)

        ue5_layout.addSpacing(20)

        self.complex_collision_cb = QCheckBox("Complex as Simple Collision")
        self.complex_collision_cb.setChecked(False)
        self.complex_collision_cb.setToolTip("Use the mesh geometry as collision (instead of simplified collision shapes)")
        ue5_layout.addWidget(self.complex_collision_cb)

        ue5_layout.addSpacing(20)

        self.merge_meshes_cb = QCheckBox("Merge Meshes")
        self.merge_meshes_cb.setChecked(True)
        self.merge_meshes_cb.setToolTip("Combine all meshes into a single static mesh on import")
        ue5_layout.addWidget(self.merge_meshes_cb)

        ue5_layout.addStretch()
        layout.addLayout(ue5_layout)

        # Folder settings row
        folder_layout = QHBoxLayout()

        folder_layout.addWidget(QLabel("UE5 Folder:"))
        self.ue5_folder_input = QLineEdit("/Game/Imports")
        folder_layout.addWidget(self.ue5_folder_input)

        folder_layout.addSpacing(20)

        folder_layout.addWidget(QLabel("FBX Output:"))
        self.source_folder_input = QLineEdit()
        self.source_folder_input.setPlaceholderText("Leave empty for auto temp")
        self.source_folder_input.setToolTip("Local folder to save the FBX file. Leave empty to use a temporary directory that gets cleaned up.")
        folder_layout.addWidget(self.source_folder_input)
        self.source_browse_btn = QPushButton("Browse...")
        self.source_browse_btn.clicked.connect(self._browse_source_folder)
        folder_layout.addWidget(self.source_browse_btn)

        layout.addLayout(folder_layout)

        # Import button
        self.import_btn = QPushButton("Import to UE5")
        self.import_btn.setEnabled(False)
        self.import_btn.setMinimumHeight(40)
        self.import_btn.clicked.connect(self._start_import)
        layout.addWidget(self.import_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status log
        layout.addWidget(QLabel("Log:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(200)
        self.log_output.setContextMenuPolicy(Qt.CustomContextMenu)
        self.log_output.customContextMenuRequested.connect(self._log_context_menu)
        layout.addWidget(self.log_output)

        # Enable drag and drop
        self.setAcceptDrops(True)

        # Restore saved settings
        self._load_settings()

    def _load_settings(self):
        s = QSettings(str(Path(__file__).parent / "settings.ini"), QSettings.IniFormat)
        if s.contains("geometry"):
            self.restoreGeometry(s.value("geometry"))
        self.decimate_spin.setValue(float(s.value("decimate_ratio", 1.0)))
        self.merge_children_cb.setChecked(s.value("merge_children", "true") == "true")
        self.import_materials_cb.setChecked(s.value("import_materials", "true") == "true")
        self.complex_collision_cb.setChecked(s.value("complex_collision", "false") == "true")
        self.merge_meshes_cb.setChecked(s.value("merge_meshes", "true") == "true")
        self.ue5_folder_input.setText(s.value("ue5_folder", "/Game/Imports"))
        self.source_folder_input.setText(s.value("source_folder", ""))

    def _save_settings(self):
        s = QSettings(str(Path(__file__).parent / "settings.ini"), QSettings.IniFormat)
        s.setValue("geometry", self.saveGeometry())
        s.setValue("decimate_ratio", self.decimate_spin.value())
        s.setValue("merge_children", "true" if self.merge_children_cb.isChecked() else "false")
        s.setValue("import_materials", "true" if self.import_materials_cb.isChecked() else "false")
        s.setValue("complex_collision", "true" if self.complex_collision_cb.isChecked() else "false")
        s.setValue("merge_meshes", "true" if self.merge_meshes_cb.isChecked() else "false")
        s.setValue("ue5_folder", self.ue5_folder_input.text())
        s.setValue("source_folder", self.source_folder_input.text())

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".glb"):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".glb"):
                self.file_input.setText(path)
                break

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select GLB File", "", "GLB Files (*.glb);;All Files (*)"
        )
        if path:
            self.file_input.setText(path)

    def _browse_source_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select FBX Output Folder")
        if path:
            self.source_folder_input.setText(path)

    def _on_file_changed(self, text):
        self.import_btn.setEnabled(
            bool(text) and text.lower().endswith(".glb") and os.path.isfile(text)
        )

    def _log_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Clear Log", self.log_output.clear)
        menu.exec(self.log_output.mapToGlobal(pos))

    def _log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def _start_import(self):
        glb_path = self.file_input.text().strip()
        decimate = self.decimate_spin.value()
        ue5_folder = self.ue5_folder_input.text().strip()
        import_materials = self.import_materials_cb.isChecked()
        complex_collision = self.complex_collision_cb.isChecked()
        merge_meshes = self.merge_meshes_cb.isChecked()
        merge_children = self.merge_children_cb.isChecked()
        source_folder = self.source_folder_input.text().strip() or ""

        self._log(f"Starting import: {Path(glb_path).name}")
        self._log(f"  Decimate ratio: {decimate}")
        self._log(f"  Import materials: {import_materials}")
        self._log(f"  Complex as simple collision: {complex_collision}")
        self._log(f"  Merge meshes: {merge_meshes}")
        self._log(f"  Merge child meshes: {merge_children}")
        self._log(f"  UE5 folder: {ue5_folder}")
        if source_folder:
            self._log(f"  Source folder: {source_folder}")

        # Disable controls during import
        self.import_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)

        # Create worker in thread
        self._worker = ImportWorker(glb_path, decimate, ue5_folder, import_materials, complex_collision, merge_meshes, merge_children, source_folder)
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.status.connect(self._log)
        self._worker.progress.connect(self.progress_bar.setValue)
        self._worker.finished.connect(self._on_import_finished)

        self._worker_thread.start()

    def _on_import_finished(self, success, message):
        if success:
            self._log(f"SUCCESS: {message}")
        else:
            self._log(f"FAILED: {message}")

        # Re-enable controls
        self.import_btn.setEnabled(bool(self.file_input.text()))
        self.browse_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        # Clean up thread
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None
            self._worker = None
