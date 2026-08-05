"""VoxSlide AI — Main UI Dashboard"""

import json
import os
import sys
import threading
import time
from pathlib import Path

import pyautogui
import customtkinter
from customtkinter import CTkLabel, CTkButton, CTkSlider, CTkTextbox, CTkFrame, CTkEntry
from config import Config
from audio_engine import AudioEngine
from license_manager import LicenseManager, SUPPORT_WHATSAPP
from session_manager import SessionManager

pyautogui.FAILSAFE = False


def _app_base_dir() -> Path:
    """Return the directory that holds bundled assets (dev or frozen)."""
    if getattr(sys, "frozen", False):
        # PyInstaller onefile extracts to _MEIPASS; also check beside the EXE.
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        exe_dir = Path(sys.executable).parent
        for candidate in (meipass, exe_dir):
            if (candidate / "icon.ico").exists():
                return candidate
        return meipass
    return Path(__file__).resolve().parent


def _icon_path() -> Path | None:
    path = _app_base_dir() / "icon.ico"
    return path if path.is_file() else None


class VoxSlideApp(customtkinter.CTk):

    def __init__(self):
        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("blue")
        super().__init__()

        self.title(Config.APP_NAME)
        self.geometry("600x800")
        self.state("zoomed")
        self.resizable(True, True)
        self.minsize(500, 680)
        self.configure(fg_color=Config.COLOR_BG)

        # Override CustomTkinter's default blue window icon.
        # Re-apply shortly after init — CTK may set its own icon during startup.
        self._apply_window_icon()
        self.after(200, self._apply_window_icon)

        self.is_pro = LicenseManager.is_pro()
        if self.is_pro:
            self._load_custom_commands()

        self.is_listening = False
        self.session_start = None
        self.audio_engine = None
        self.license_expanded = False
        self.cooldown_label = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Non-blocking update check after the UI is ready
        self.after(900, self._schedule_update_check)

    def _apply_window_icon(self):
        """Set the Windows title-bar / taskbar icon from icon.ico."""
        icon = _icon_path()
        if icon is None:
            return
        try:
            # iconbitmap is the reliable Windows .ico title-bar API
            self.iconbitmap(default=str(icon))
            self.wm_iconbitmap(str(icon))
        except Exception:
            pass
        try:
            # Keep a PhotoImage reference so Tk does not GC it
            from PIL import Image, ImageTk

            img = Image.open(icon)
            # Prefer a mid-size frame for the title bar
            try:
                img.seek(0)
            except EOFError:
                pass
            photo = ImageTk.PhotoImage(img.convert("RGBA"))
            self.iconphoto(True, photo)
            self._icon_photo = photo
        except Exception:
            pass

    # ── UI BUILD ──────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Header
        header = CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, pady=(30, 4), padx=24, sticky="ew")

        title_row = CTkFrame(header, fg_color="transparent")
        title_row.pack()

        self.mic_badge = CTkLabel(
            title_row, text="🎙️",
            font=("Segoe UI", 18),
            text_color=Config.COLOR_LIME_TEXT,
            fg_color=Config.COLOR_LIME,
            corner_radius=10,
            width=40, height=40,
        )
        self.mic_badge.pack(side="left", padx=(0, 12))

        CTkLabel(
            title_row, text="VoxSlide AI",
            font=("Segoe UI", 26, "bold"), text_color="white"
        ).pack(side="left")

        self.tier_badge = CTkLabel(
            title_row,
            text="Pro" if self.is_pro else "Free Tier",
            font=("Segoe UI Semibold", 11, "bold"),
            text_color=Config.COLOR_LIME_TEXT if self.is_pro else Config.COLOR_GRAY,
            fg_color=Config.COLOR_LIME if self.is_pro else Config.COLOR_SURFACE,
            corner_radius=20,
            padx=10, pady=3,
        )
        self.tier_badge.pack(side="left", padx=(10, 0))

        CTkLabel(
            header, text="Hands-Free Slide Control  •  Powered by AI",
            font=("Segoe UI", 12), text_color=Config.COLOR_GRAY
        ).pack(pady=(6, 0))

        self.cooldown_label = CTkLabel(
            header,
            text="",
            font=("Segoe UI", 11, "bold"),
            text_color=Config.COLOR_ORANGE,
        )
        # Initially hidden; _refresh_cooldown_label() shows it when needed.

        self.pro_status_label = CTkLabel(
            header,
            text="Pro Active — all features unlocked",
            font=("Segoe UI", 11, "bold"),
            text_color=Config.COLOR_LIME,
        )
        if self.is_pro:
            self.pro_status_label.pack(pady=(4, 0))

        # ── Status Badge
        self.status_label = CTkLabel(
            self, text="●  Idle",
            font=("Segoe UI", 14, "bold"),
            text_color=Config.COLOR_CYAN
        )
        self.status_label.grid(row=1, column=0, pady=(10, 0))

        # ── Toggle Button
        # Idle: dark outlined pill. Listening: lime-filled, bold border — the
        # one moment in the app that should feel unmistakably "on".
        self.toggle_btn = CTkButton(
            self,
            text="Start Listening",
            width=280, height=56,
            font=("Segoe UI", 15, "bold"),
            fg_color=Config.COLOR_SURFACE,
            hover_color=Config.COLOR_SURFACE_RAISED,
            text_color="white",
            border_width=1.5,
            border_color=Config.COLOR_BORDER,
            corner_radius=28,
            command=self.toggle_listening
        )
        self.toggle_btn.grid(row=2, column=0, pady=18)

        # ── Sensitivity Slider
        slider_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=14
        )
        slider_frame.grid(row=3, column=0, padx=24, pady=(0, 14), sticky="ew")
        slider_frame.grid_columnconfigure(1, weight=1)

        CTkLabel(
            slider_frame, text="Mic Sensitivity",
            font=("Segoe UI", 13, "bold"), text_color="white"
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 4), sticky="w")

        self.slider = CTkSlider(
            slider_frame,
            from_=50, to=1000,
            width=300,
            progress_color=Config.COLOR_LIME,
            button_color=Config.COLOR_LIME,
            button_hover_color=Config.COLOR_LIME_HOVER,
            fg_color=Config.COLOR_BORDER,
            command=self._on_slider_change
        )
        self.slider.set(Config.ENERGY_THRESHOLD)
        self.slider.grid(row=1, column=0, padx=(16, 8), pady=(0, 14))

        self.slider_value_label = CTkLabel(
            slider_frame,
            text=str(Config.ENERGY_THRESHOLD),
            font=("Segoe UI", 12, "bold"), text_color=Config.COLOR_LIME, width=40
        )
        self.slider_value_label.grid(row=1, column=1, padx=(0, 16), pady=(0, 14))

        # ── Trigger Words Reference (chip style)
        ref_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=14
        )
        ref_frame.grid(row=4, column=0, padx=24, pady=(0, 14), sticky="ew")

        CTkLabel(
            ref_frame, text="Voice Commands",
            font=("Segoe UI", 13, "bold"), text_color="white"
        ).grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        self.next_cmds_row = CTkFrame(ref_frame, fg_color="transparent")
        self.next_cmds_row.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        self.prev_cmds_row = CTkFrame(ref_frame, fg_color="transparent")
        self.prev_cmds_row.grid(row=2, column=0, padx=16, pady=(0, 16), sticky="w")

        self._render_trigger_chips(
            self.next_cmds_row, Config.TRIGGER_NEXT,
            chip_fg=Config.COLOR_LIME, chip_text=Config.COLOR_LIME_TEXT,
            suffix="→  Next slide"
        )
        self._render_trigger_chips(
            self.prev_cmds_row, Config.TRIGGER_PREV,
            chip_fg=Config.COLOR_CORAL, chip_text="white",
            suffix="→  Previous slide"
        )

        # ── Custom Commands (Pro) / Locked (Free)
        self.commands_pro_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=14
        )
        self.commands_pro_frame.grid(row=5, column=0, padx=24, pady=(0, 14), sticky="ew")
        self.commands_pro_frame.grid_columnconfigure(1, weight=1)

        CTkLabel(
            self.commands_pro_frame, text="Custom Commands",
            font=("Segoe UI", 13, "bold"), text_color="white"
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 8), sticky="w")

        CTkLabel(
            self.commands_pro_frame, text="Next Slide Command",
            font=("Segoe UI", 11), text_color=Config.COLOR_GRAY
        ).grid(row=1, column=0, padx=16, pady=(0, 6), sticky="w")

        self.next_cmd_entry = CTkEntry(
            self.commands_pro_frame,
            placeholder_text="next, next slide, forward",
            font=("Segoe UI", 11),
            fg_color=Config.COLOR_BG,
            border_color=Config.COLOR_BORDER,
            corner_radius=8,
        )
        self.next_cmd_entry.grid(row=1, column=1, padx=(0, 16), pady=(0, 6), sticky="ew")
        if self.is_pro:
            self.next_cmd_entry.insert(0, ", ".join(Config.TRIGGER_NEXT))

        CTkLabel(
            self.commands_pro_frame, text="Previous Slide Command",
            font=("Segoe UI", 11), text_color=Config.COLOR_GRAY
        ).grid(row=2, column=0, padx=16, pady=(0, 6), sticky="w")

        self.prev_cmd_entry = CTkEntry(
            self.commands_pro_frame,
            placeholder_text="back, previous, go back",
            font=("Segoe UI", 11),
            fg_color=Config.COLOR_BG,
            border_color=Config.COLOR_BORDER,
            corner_radius=8,
        )
        self.prev_cmd_entry.grid(row=2, column=1, padx=(0, 16), pady=(0, 6), sticky="ew")
        if self.is_pro:
            self.prev_cmd_entry.insert(0, ", ".join(Config.TRIGGER_PREV))

        CTkButton(
            self.commands_pro_frame,
            text="Save Commands",
            font=("Segoe UI", 12, "bold"),
            fg_color=Config.COLOR_LIME,
            hover_color=Config.COLOR_LIME_HOVER,
            text_color=Config.COLOR_LIME_TEXT,
            corner_radius=8,
            height=34,
            command=self._save_custom_commands,
        ).grid(row=3, column=0, columnspan=2, padx=16, pady=(4, 14), sticky="ew")

        self.commands_locked_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=14
        )
        self.commands_locked_frame.grid(row=5, column=0, padx=24, pady=(0, 14), sticky="ew")
        self.commands_locked_frame.grid_columnconfigure(0, weight=1)

        CTkLabel(
            self.commands_locked_frame,
            text="Custom Commands            LOCKED",
            font=("Segoe UI", 12, "bold"), text_color="white"
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 2), sticky="w")

        CTkLabel(
            self.commands_locked_frame,
            text="Upgrade to Pro to customize voice triggers.",
            font=("Segoe UI", 11), text_color=Config.COLOR_GRAY
        ).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")

        self.activate_link = CTkButton(
            self.commands_locked_frame,
            text="Activate Pro",
            font=("Segoe UI", 11, "bold"),
            fg_color=Config.COLOR_LIME,
            hover_color=Config.COLOR_LIME_HOVER,
            text_color=Config.COLOR_LIME_TEXT,
            width=110, height=30,
            corner_radius=8,
            border_width=0,
            command=self._scroll_to_license,
        )
        self.activate_link.grid(row=1, column=1, padx=16, pady=(0, 14), sticky="e")

        if self.is_pro:
            self.commands_locked_frame.grid_remove()
        else:
            self.commands_pro_frame.grid_remove()

        # ── License Activation (free tier only — this is the conversion
        # moment, so it gets a full card, not a buried footnote)
        self.license_section = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=14,
        )
        if not self.is_pro:
            self.license_section.grid(row=6, column=0, padx=24, pady=(0, 14), sticky="ew")
        self.license_section.grid_columnconfigure(0, weight=1)

        self.license_toggle_btn = CTkButton(
            self.license_section,
            text="🔑  Activate License  ▼",
            font=("Segoe UI", 13, "bold"),
            fg_color="transparent",
            hover_color=Config.COLOR_SURFACE_RAISED,
            text_color="white",
            anchor="w",
            height=44,
            corner_radius=14,
            border_width=0,
            command=self._toggle_license_section,
        )
        self.license_toggle_btn.grid(row=0, column=0, padx=6, pady=6, sticky="ew")

        self.license_content = CTkFrame(self.license_section, fg_color="transparent")

        self.license_entry = CTkEntry(
            self.license_content,
            placeholder_text="Paste your license key here",
            font=("Segoe UI", 11),
            fg_color=Config.COLOR_BG,
            border_color=Config.COLOR_BORDER,
            corner_radius=8,
            height=36,
        )
        self.license_entry.pack(fill="x", padx=16, pady=(0, 10))
        self.license_entry.bind("<Return>", lambda _e: self._activate_license())

        self.activate_btn = CTkButton(
            self.license_content,
            text="Activate",
            font=("Segoe UI", 13, "bold"),
            fg_color=Config.COLOR_LIME,
            hover_color=Config.COLOR_LIME_HOVER,
            text_color=Config.COLOR_LIME_TEXT,
            corner_radius=8,
            height=38,
            command=self._activate_license,
        )
        self.activate_btn.pack(fill="x", padx=16, pady=(0, 16))

        # ── Live Log Terminal
        log_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=14
        )
        log_frame.grid(row=7, column=0, padx=24, pady=(0, 14), sticky="ew")

        CTkLabel(
            log_frame, text="Live Log",
            font=("Segoe UI", 13, "bold"), text_color="white"
        ).pack(anchor="w", padx=16, pady=(14, 6))

        self.log_box = CTkTextbox(
            log_frame,
            height=250,
            font=("Consolas", 11),
            fg_color=Config.COLOR_LOG_BG,
            text_color=Config.COLOR_LOG_TEXT,
            border_width=0,
            corner_radius=10,
            state="disabled",
            wrap="word"
        )
        self.log_box.pack(fill="x", padx=12, pady=(0, 14))

        # ── Footer
        footer_text = (
            f"v{Config.VERSION}  •  Pro Tier"
            if self.is_pro
            else f"v{Config.VERSION}  •  Free Tier"
        )
        self.footer_label = CTkLabel(
            self,
            text=footer_text,
            font=("Consolas", 10),
            text_color=Config.COLOR_GRAY
        )
        self.footer_label.grid(row=8, column=0, pady=(0, 20))

        self._log("[System] VoxSlide AI ready. Press Start to begin.")
        if self.is_pro:
            self._log("[Pro] License active — unlimited sessions enabled.")
        self._refresh_cooldown_label()

    # ── LICENSE & COMMANDS ────────────────────────────────────

    @staticmethod
    def _format_trigger_line(icon: str, triggers: list, _color: str) -> str:
        quoted = '  /  '.join(f'"{t}"' for t in triggers)
        return f"{icon}  {quoted}"

    @staticmethod
    def _render_trigger_chips(row_frame, triggers, chip_fg, chip_text, suffix):
        """Fill row_frame with pill-style chips for each trigger word,
        followed by a muted suffix label (e.g. '→  Next slide')."""
        for widget in row_frame.winfo_children():
            widget.destroy()
        # Only show the first couple of chips to avoid overflow; the rest
        # are still active triggers, just not all individually chip'd.
        shown = triggers[:2]
        for word in shown:
            CTkLabel(
                row_frame, text=word,
                font=("Consolas", 11, "bold"),
                text_color=chip_text, fg_color=chip_fg,
                corner_radius=8, padx=8, pady=2,
            ).pack(side="left", padx=(0, 6))
        CTkLabel(
            row_frame, text=suffix,
            font=("Segoe UI", 11), text_color=Config.COLOR_GRAY
        ).pack(side="left")

    def _toggle_license_section(self):
        self.license_expanded = not self.license_expanded
        if self.license_expanded:
            self.license_content.grid(row=1, column=0, sticky="ew")
            self.license_toggle_btn.configure(text="🔑  Activate License  ▲")
        else:
            self.license_content.grid_forget()
            self.license_toggle_btn.configure(text="🔑  Activate License  ▼")

    def _scroll_to_license(self):
        if self.is_pro:
            return
        if not self.license_expanded:
            self._toggle_license_section()
        self.license_section.lift()
        self.license_entry.focus_set()
        self.update_idletasks()

    def _activate_license(self):
        key = self.license_entry.get().strip()
        if not key:
            self._log("[License] Please enter a license key.")
            return
        try:
            status = LicenseManager.activate(key)
        except OSError as e:
            self._log(f"[License] Could not save license: {e}")
            return
        if status == LicenseManager.STATUS_OK:
            self.is_pro = True
            self._load_custom_commands()
            self._apply_pro_ui()
            self._log("[Pro] License activated successfully!")
        elif status == LicenseManager.STATUS_WRONG_DEVICE:
            self._log(
                f"[Error] This key is already activated on another device. "
                f"Contact support on WhatsApp: {SUPPORT_WHATSAPP}"
            )
        else:  # STATUS_INVALID
            self._log("[License] Invalid license key. Please check and try again.")

    def _apply_pro_ui(self):
        self.tier_badge.configure(
            text="Pro",
            text_color=Config.COLOR_LIME_TEXT,
            fg_color=Config.COLOR_LIME,
        )
        self.pro_status_label.configure(text="Pro Active — all features unlocked")
        self.pro_status_label.pack(pady=(4, 0))
        self.footer_label.configure(text=f"v{Config.VERSION}  •  Pro Tier")
        self.license_section.grid_remove()
        self.commands_locked_frame.grid_remove()
        self.commands_pro_frame.grid()
        self.next_cmd_entry.delete(0, "end")
        self.next_cmd_entry.insert(0, ", ".join(Config.TRIGGER_NEXT))
        self.prev_cmd_entry.delete(0, "end")
        self.prev_cmd_entry.insert(0, ", ".join(Config.TRIGGER_PREV))
        self._refresh_trigger_labels()
        self._refresh_cooldown_label()  # hide the countdown for Pro users

    def _load_custom_commands(self):
        if not self.is_pro or not Config.PRO_COMMANDS_FILE.exists():
            return
        try:
            data = json.loads(Config.PRO_COMMANDS_FILE.read_text(encoding="utf-8"))
            if "next" in data and isinstance(data["next"], list):
                Config.TRIGGER_NEXT = [str(w).strip() for w in data["next"] if str(w).strip()]
            if "prev" in data and isinstance(data["prev"], list):
                Config.TRIGGER_PREV = [str(w).strip() for w in data["prev"] if str(w).strip()]
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    def _save_custom_commands(self):
        if not self.is_pro:
            return
        next_cmds = [w.strip() for w in self.next_cmd_entry.get().split(",") if w.strip()]
        prev_cmds = [w.strip() for w in self.prev_cmd_entry.get().split(",") if w.strip()]
        if not next_cmds or not prev_cmds:
            self._log("[Pro] Each command field needs at least one phrase.")
            return
        Config.TRIGGER_NEXT = next_cmds
        Config.TRIGGER_PREV = prev_cmds
        payload = {"next": next_cmds, "prev": prev_cmds}
        try:
            Config.PRO_COMMANDS_FILE.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except OSError as e:
            self._log(f"[Pro] Could not save commands: {e}")
            return
        self._refresh_trigger_labels()
        self._log("[Pro] Custom commands saved successfully")

    def _refresh_trigger_labels(self):
        self._render_trigger_chips(
            self.next_cmds_row, Config.TRIGGER_NEXT,
            chip_fg=Config.COLOR_LIME, chip_text=Config.COLOR_LIME_TEXT,
            suffix="→  Next slide"
        )
        self._render_trigger_chips(
            self.prev_cmds_row, Config.TRIGGER_PREV,
            chip_fg=Config.COLOR_CORAL, chip_text="white",
            suffix="→  Previous slide"
        )

    # ── CONTROLS ──────────────────────────────────────────────

    def toggle_listening(self):
        if not self.is_listening:
            if not self.is_pro and SessionManager.is_in_cooldown():
                remaining = SessionManager.cooldown_remaining()
                mins = remaining // 60
                self._log(
                    f"[System] ⏳ Cooldown active. Next session in {mins} min."
                )
                self._refresh_cooldown_label()
                return
            self.is_listening = True
            self.toggle_btn.configure(
                text="●  Stop Listening",
                fg_color=Config.COLOR_LIME,
                hover_color=Config.COLOR_LIME_HOVER,
                text_color=Config.COLOR_LIME_TEXT,
                border_width=1.5,
                border_color=Config.COLOR_LIME,
            )
            self._set_status("●  Listening...", Config.COLOR_LIME)
            self.session_start = time.time()
            self.audio_engine = AudioEngine(
                on_heard=self._safe_log,
                on_action=self._safe_action
            )
            self.audio_engine.start()
            self._log("[System] Listening started. Adjusting for ambient noise...")
            if not self.is_pro:
                self._check_session_limit()
        else:
            self._stop_listening()

    def _stop_listening(self):
        self.is_listening = False
        self.toggle_btn.configure(
            text="Start Listening",
            fg_color=Config.COLOR_SURFACE,
            hover_color=Config.COLOR_SURFACE_RAISED,
            text_color="white",
            border_width=1.5,
            border_color=Config.COLOR_BORDER,
        )
        self._set_status("●  Idle", Config.COLOR_CYAN)
        if self.audio_engine:
            self.audio_engine.stop()
            self.audio_engine = None
        self._log("[System] Listening stopped.")
        # Free-tier cooldown: stamp session end whenever a free user
        # actually started one (manual stop or timeout).
        if not self.is_pro and self.session_start is not None:
            SessionManager.record_session_end()
            self.session_start = None
            self._log(
                f"[Free] {Config.SESSION_LIMIT_MINUTES} min session complete. "
                f"Next session available in 1 hour. "
                f"Upgrade to Pro for unlimited time."
            )
            self._refresh_cooldown_label()

    def _set_status(self, text: str, color: str):
        self.status_label.configure(text=text, text_color=color)

    def _log(self, message: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")

    def _on_slider_change(self, value):
        self.slider_value_label.configure(text=str(int(value)))
        if self.audio_engine:
            self.audio_engine.set_threshold(int(value))

    # ── CALLBACKS (thread-safe) ────────────────────────────────

    def _safe_log(self, text: str):
        self.after(0, lambda: self._log(f'[Audio] Heard: "{text}"'))

    def _safe_action(self, action: str):
        if action == "NEXT":
            self.after(0, lambda: self._log("[Action] ➡️  Next Slide triggered"))
            self.after(0, lambda: self._set_status("➡️  Next Slide", Config.COLOR_BLUE))
            self.after(0, lambda: pyautogui.press("right"))
            self.after(2000, lambda: self._set_status("● Listening...", Config.COLOR_GREEN) if self.is_listening else None)
        elif action == "PREV":
            self.after(0, lambda: self._log("[Action] ⬅️  Previous Slide triggered"))
            self.after(0, lambda: self._set_status("⬅️  Previous Slide", Config.COLOR_ORANGE))
            self.after(0, lambda: pyautogui.press("left"))
            self.after(2000, lambda: self._set_status("● Listening...", Config.COLOR_GREEN) if self.is_listening else None)
        elif action == "NO_MIC":
            self.after(0, lambda: self._log("[Error] ⚠️ No microphone detected. Please connect one."))
            self.after(0, lambda: self._set_status("⚠️ No Mic Found", Config.COLOR_RED))
            self.after(0, self._stop_listening)

    # ── SESSION TIMER ─────────────────────────────────────────

    def _check_session_limit(self):
        if self.is_pro or not self.is_listening:
            return
        elapsed = time.time() - self.session_start
        if elapsed >= Config.SESSION_LIMIT_MINUTES * 60:
            self._log("[System] ⏱️ Free 10-min session limit reached.")
            self._log("[System] Upgrade to Pro for unlimited sessions + offline mode.")
            self._set_status("⏱️ Session Limit Reached", Config.COLOR_RED)
            self._stop_listening()
        else:
            self.after(10000, self._check_session_limit)

    def _refresh_cooldown_label(self):
        """Show / hide / update the cooldown countdown label.

        Refreshes every 60 seconds while a cooldown is active. Hides
        itself when the cooldown expires or the user upgrades to Pro.
        """
        if self.cooldown_label is None:
            return
        if self.is_pro or not SessionManager.is_in_cooldown():
            self.cooldown_label.pack_forget()
            return
        secs = SessionManager.cooldown_remaining()
        mins = max(1, secs // 60)  # show at least 1 min to avoid "0 min"
        self.cooldown_label.configure(
            text=f"⏳ Next session available in {mins} min"
        )
        self.cooldown_label.pack(pady=(2, 0))
        # Re-check in 60 seconds; this method is a no-op once cooldown ends.
        self.after(60_000, self._refresh_cooldown_label)

    # ── AUTO UPDATE ───────────────────────────────────────────

    def _schedule_update_check(self):
        """Kick off a background GitHub Releases check (never blocks UI)."""
        if Config.SKIP_UPDATE_CHECK:
            return
        if os.environ.get("VOXSLIDE_SKIP_UPDATE", "").strip() in ("1", "true", "yes"):
            return
        owner = (Config.GITHUB_OWNER or "").strip()
        if not owner or owner.startswith("YOUR_"):
            # Repo not configured yet — skip silently until RELEASE.md steps are done
            return
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _update_check_worker(self):
        try:
            from updater import (
                NetworkUnavailableError,
                UpdateError,
                check_for_update,
            )

            info = check_for_update(
                Config.GITHUB_OWNER,
                Config.GITHUB_REPO,
                local_version=Config.VERSION,
                preferred_assets=[Config.UPDATE_ASSET_NAME, "VoxSlideAI_Setup.exe"],
            )
            if info is None:
                return
            self.after(0, lambda: self._show_update_dialog(info))
        except NetworkUnavailableError:
            # Offline / flaky network — launch normally
            pass
        except UpdateError as exc:
            self.after(0, lambda e=exc: self._log(f"[Update] Skipped: {e}"))
        except Exception as exc:
            self.after(0, lambda e=exc: self._log(f"[Update] Check failed: {e}"))

    def _show_update_dialog(self, info):
        if not self.winfo_exists():
            return
        from update_dialog import UpdateDialog

        self._log(
            f"[Update] Version {info.version} available "
            f"(installed v{Config.VERSION})."
        )
        UpdateDialog(self, info, on_finished=self._quit_for_update)

    def _quit_for_update(self):
        """Close the app so the installer can replace files cleanly."""
        if self.audio_engine:
            try:
                self.audio_engine.stop()
            except Exception:
                pass
        try:
            self.destroy()
        except Exception:
            pass
        sys.exit(0)

    # ── CLEANUP ───────────────────────────────────────────────

    def _on_close(self):
        if self.audio_engine:
            self.audio_engine.stop()
        self.destroy()
