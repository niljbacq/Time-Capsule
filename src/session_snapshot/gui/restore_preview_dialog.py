"""Restore preview dialog: shows the plan before any application launches.

Read-only. The Restore button is present but disabled until 7.4b-2 wires the
actual restore, per the spec rule against decorative controls.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from session_snapshot.gui import styles
from session_snapshot.models.adapter_types import ActionKind
from session_snapshot.report.models import RestorePreview

ACTION_ORDER = (
    (ActionKind.LAUNCH, "Will launch"),
    (ActionKind.RECONNECT, "Will reconnect"),
    (ActionKind.REUSE, "Already running"),
    (ActionKind.SKIP, "Will be skipped"),
)


class RestorePreviewDialog(QDialog):
    """Grouped restore plan viewer. Restore button disabled until 7.4b-2."""

    def __init__(self, preview, parent=None):
        super().__init__(parent)
        self._preview = preview
        self.setWindowTitle(f"Restore preview — {preview.session_name}")
        self.setMinimumSize(520, 420)
        self._build()
        self._populate()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self.title_label = QLabel("", self)
        self.title_label.setObjectName(styles.PAGE_TITLE)
        layout.addWidget(self.title_label)

        self.warnings_label = QLabel("", self)
        self.warnings_label.setObjectName(styles.STATUS_WARNING)
        self.warnings_label.setWordWrap(True)
        layout.addWidget(self.warnings_label)

        self.groups_label = QLabel("", self)
        self.groups_label.setObjectName(styles.MUTED)
        self.groups_label.setWordWrap(True)
        layout.addWidget(self.groups_label)

        layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel, parent=self)
        self.restore_button = QPushButton("Restore", self)
        self.restore_button.setObjectName(styles.PRIMARY_BUTTON)
        self.restore_button.setEnabled(False)
        self.restore_button.setToolTip(
            "GUI restore is coming next round. Use 'sessionctl restore <id>' for now."
        )
        buttons.addButton(self.restore_button, QDialogButtonBox.ActionRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self):
        p = self._preview
        self.title_label.setText(f"Preview: {p.session_name}")

        if p.warnings:
            self.warnings_label.setText("\n".join(f"\u2022 {w}" for w in p.warnings))
            self.warnings_label.setVisible(True)
        else:
            self.warnings_label.setText("")
            self.warnings_label.setVisible(False)

        lines = []
        from session_snapshot.models.adapter_types import ActionKind

        ACTION_ORDER = (
            (ActionKind.LAUNCH, "Will launch"),
            (ActionKind.RECONNECT, "Will reconnect"),
            (ActionKind.REUSE, "Already running"),
            (ActionKind.SKIP, "Will be skipped"),
        )

        for action, title in ACTION_ORDER:
            apps = [a for a in self._preview.apps if a.action == action]
            if not apps:
                continue
            lines.append(f"{title} ({len(apps)})")
            for app in apps:
                line = f"  \u2022 {app.instance_id} [{app.adapter_id}]: {app.message}"
                if app.missing_dependencies:
                    line += f" (missing: {', '.join(app.missing_dependencies)})"
                if app.unavailable_paths:
                    line += f" (unavailable: {', '.join(app.unavailable_paths)})"
                lines.append(line)
            lines.append("")

        if not self._preview.apps:
            lines.append("This session has no applications.")
        self.groups_label.setText("\n".join(lines).rstrip())

    def groups_text(self):
        return self.groups_label.text()

    def warnings_text(self):
        return self.warnings_label.text()
