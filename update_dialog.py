"""Modern CustomTkinter update dialog for VoxSlide AI."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Optional

import customtkinter
from customtkinter import CTkButton, CTkFrame, CTkLabel, CTkProgressBar, CTkTextbox

from config import Config
from updater import (
    CorruptDownloadError,
    DownloadError,
    NetworkUnavailableError,
    UpdateCancelled,
    UpdateInfo,
    download_update,
    launch_installer,
)


class UpdateDialog(customtkinter.CTkToplevel):
    """Modal dialog: show release notes, download with progress, launch installer."""

    def __init__(
        self,
        master,
        info: UpdateInfo,
        *,
        on_finished: Optional[Callable[[], None]] = None,
    ):
        super().__init__(master)
        self.info = info
        self.on_finished = on_finished
        self._cancel = threading.Event()
        self._downloading = False
        self._installer_path: Optional[Path] = None

        self.title("Update Available")
        self.geometry("480x520")
        self.resizable(False, False)
        self.configure(fg_color=Config.COLOR_BG)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_later)

        # Center over parent when possible
        self.after(10, self._center_on_parent)

        root = CTkFrame(self, fg_color=Config.COLOR_BG)
        root.pack(fill="both", expand=True, padx=24, pady=24)

        CTkLabel(
            root,
            text="Update available",
            font=("Segoe UI", 22, "bold"),
            text_color="white",
        ).pack(anchor="w")

        CTkLabel(
            root,
            text=(
                f"VoxSlide AI {info.version} is ready to install.\n"
                f"You are currently on v{Config.VERSION}."
            ),
            font=("Segoe UI", 13),
            text_color=Config.COLOR_GRAY,
            justify="left",
        ).pack(anchor="w", pady=(8, 16))

        CTkLabel(
            root,
            text="What's new",
            font=("Segoe UI", 13, "bold"),
            text_color="white",
        ).pack(anchor="w")

        notes = CTkTextbox(
            root,
            height=180,
            font=("Segoe UI", 12),
            fg_color=Config.COLOR_SURFACE,
            text_color="#E8EEF7",
            border_width=1,
            border_color=Config.COLOR_BORDER,
            corner_radius=10,
            wrap="word",
        )
        notes.pack(fill="x", pady=(6, 16))
        notes.insert("1.0", info.release_notes.strip() or "Bug fixes and improvements.")
        notes.configure(state="disabled")

        self.status_label = CTkLabel(
            root,
            text="",
            font=("Segoe UI", 12),
            text_color=Config.COLOR_CYAN,
            wraplength=420,
            justify="left",
        )
        self.status_label.pack(anchor="w", pady=(0, 6))

        self.progress = CTkProgressBar(
            root,
            height=10,
            progress_color=Config.COLOR_LIME,
            fg_color=Config.COLOR_SURFACE,
            corner_radius=6,
        )
        self.progress.pack(fill="x", pady=(0, 4))
        self.progress.set(0)
        self.progress.pack_forget()

        self.pct_label = CTkLabel(
            root,
            text="",
            font=("Consolas", 11),
            text_color=Config.COLOR_GRAY,
        )
        self.pct_label.pack(anchor="e")
        self.pct_label.pack_forget()

        btn_row = CTkFrame(root, fg_color="transparent")
        btn_row.pack(fill="x", pady=(18, 0))

        self.later_btn = CTkButton(
            btn_row,
            text="Later",
            width=120,
            height=40,
            corner_radius=10,
            fg_color=Config.COLOR_SURFACE,
            hover_color=Config.COLOR_SURFACE_RAISED,
            border_width=1,
            border_color=Config.COLOR_BORDER,
            text_color="white",
            font=("Segoe UI", 13),
            command=self._on_later,
        )
        self.later_btn.pack(side="left")

        self.update_btn = CTkButton(
            btn_row,
            text="Update now",
            width=160,
            height=40,
            corner_radius=10,
            fg_color=Config.COLOR_LIME,
            hover_color=Config.COLOR_LIME_HOVER,
            text_color=Config.COLOR_LIME_TEXT,
            font=("Segoe UI", 13, "bold"),
            command=self._on_update,
        )
        self.update_btn.pack(side="right")

        self.cancel_btn = CTkButton(
            btn_row,
            text="Cancel download",
            width=160,
            height=40,
            corner_radius=10,
            fg_color=Config.COLOR_CORAL,
            hover_color=Config.COLOR_CORAL_HOVER,
            text_color="white",
            font=("Segoe UI", 13),
            command=self._on_cancel_download,
        )
        # Shown only while downloading

    def _center_on_parent(self):
        try:
            self.update_idletasks()
            parent = self.master
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + max(0, (pw - w) // 2)
            y = py + max(0, (ph - h) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _on_later(self):
        if self._downloading:
            self._cancel.set()
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    def _on_cancel_download(self):
        self._cancel.set()
        self.status_label.configure(
            text="Cancelling download…",
            text_color=Config.COLOR_GRAY,
        )

    def _on_update(self):
        if self._downloading:
            return
        self._downloading = True
        self._cancel.clear()
        self.update_btn.configure(state="disabled")
        self.later_btn.configure(state="disabled")
        self.later_btn.pack_forget()
        self.update_btn.pack_forget()
        self.cancel_btn.pack(side="right")
        self.progress.pack(fill="x", pady=(0, 4))
        self.pct_label.pack(anchor="e")
        self.progress.set(0)
        self.status_label.configure(
            text="Downloading update…",
            text_color=Config.COLOR_CYAN,
        )
        threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        try:
            path = download_update(
                self.info,
                progress_callback=self._on_progress,
                cancel_event=self._cancel,
            )
            self._installer_path = path
            self.after(0, self._on_download_success)
        except UpdateCancelled:
            self.after(0, self._on_download_cancelled)
        except NetworkUnavailableError as exc:
            self.after(0, lambda: self._on_download_failed(f"No internet connection.\n{exc}"))
        except CorruptDownloadError as exc:
            self.after(0, lambda: self._on_download_failed(str(exc)))
        except DownloadError as exc:
            self.after(0, lambda: self._on_download_failed(f"Download failed.\n{exc}"))
        except Exception as exc:
            self.after(0, lambda: self._on_download_failed(f"Unexpected error.\n{exc}"))

    def _on_progress(self, received: int, total: int):
        def ui():
            if total > 0:
                frac = min(1.0, received / total)
                self.progress.set(frac)
                mb_r = received / (1024 * 1024)
                mb_t = total / (1024 * 1024)
                self.pct_label.configure(text=f"{mb_r:.1f} / {mb_t:.1f} MB  ({frac * 100:.0f}%)")
            else:
                mb_r = received / (1024 * 1024)
                self.pct_label.configure(text=f"{mb_r:.1f} MB")

        self.after(0, ui)

    def _reset_buttons(self):
        self._downloading = False
        self.cancel_btn.pack_forget()
        self.later_btn.configure(state="normal")
        self.update_btn.configure(state="normal", text="Retry update")
        self.later_btn.pack(side="left")
        self.update_btn.pack(side="right")

    def _on_download_cancelled(self):
        self.progress.pack_forget()
        self.pct_label.pack_forget()
        self.status_label.configure(
            text="Download cancelled. You can update later.",
            text_color=Config.COLOR_GRAY,
        )
        self._reset_buttons()

    def _on_download_failed(self, message: str):
        self.progress.pack_forget()
        self.pct_label.pack_forget()
        self.status_label.configure(text=message, text_color=Config.COLOR_CORAL)
        self._reset_buttons()

    def _on_download_success(self):
        self.progress.set(1)
        self.status_label.configure(
            text="Download complete. Starting installer…",
            text_color=Config.COLOR_LIME,
        )
        self.cancel_btn.configure(state="disabled")
        self.after(400, self._launch_and_quit)

    def _launch_and_quit(self):
        path = self._installer_path
        if path is None:
            self._on_download_failed("Installer path missing.")
            return
        try:
            launch_installer(path)
        except Exception as exc:
            self._on_download_failed(f"Could not start installer.\n{exc}")
            return

        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        if self.on_finished:
            self.on_finished()
