"""VoxSlide AI — Main UI Dashboard"""

import json
import time
import pyautogui
import customtkinter
from customtkinter import CTkLabel, CTkButton, CTkSlider, CTkTextbox, CTkFrame, CTkEntry
from config import Config
from audio_engine import AudioEngine
from license_manager import LicenseManager, SUPPORT_WHATSAPP
from session_manager import SessionManager

pyautogui.FAILSAFE = False


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

    # ── UI BUILD ──────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # ── Header
        header = CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, pady=(30, 4), padx=24, sticky="ew")

        title_row = CTkFrame(header, fg_color="transparent")
        title_row.pack()

        CTkLabel(
            title_row, text="🎙️  VoxSlide AI",
            font=("Segoe UI", 28, "bold"), text_color="white"
        ).pack(side="left")

        self.tier_badge = CTkLabel(
            title_row,
            text="⚡ Pro" if self.is_pro else "Free Tier",
            font=("Segoe UI", 11, "bold"),
            text_color=Config.COLOR_GOLD if self.is_pro else Config.COLOR_GRAY,
            fg_color=Config.COLOR_SURFACE,
            corner_radius=6,
            padx=8, pady=2,
        )
        self.tier_badge.pack(side="left", padx=(10, 0))

        CTkLabel(
            header, text="Hands-Free Slide Control  •  Powered by AI",
            font=("Segoe UI", 12), text_color=Config.COLOR_GRAY
        ).pack()

        self.cooldown_label = CTkLabel(
            header,
            text="",
            font=("Segoe UI", 11, "bold"),
            text_color=Config.COLOR_ORANGE,
        )
        # Initially hidden; _refresh_cooldown_label() shows it when needed.

        self.pro_status_label = CTkLabel(
            header,
            text="✅ Pro Active — Unlimited Sessions",
            font=("Segoe UI", 11, "bold"),
            text_color=Config.COLOR_GREEN,
        )
        if self.is_pro:
            self.pro_status_label.pack(pady=(4, 0))

        # ── Status Badge
        self.status_label = CTkLabel(
            self, text="● Idle",
            font=("Segoe UI", 15, "bold"),
            text_color=Config.COLOR_GRAY
        )
        self.status_label.grid(row=1, column=0, pady=(10, 0))

        # ── Toggle Button
        self.toggle_btn = CTkButton(
            self,
            text="▶   Start Listening",
            width=240, height=58,
            font=("Segoe UI", 16, "bold"),
            fg_color=Config.COLOR_BLUE,
            hover_color=Config.COLOR_BLUE_HOVER,
            corner_radius=14,
            command=self.toggle_listening
        )
        self.toggle_btn.grid(row=2, column=0, pady=18)

        # ── Sensitivity Slider
        slider_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=12
        )
        slider_frame.grid(row=3, column=0, padx=24, pady=(0, 14), sticky="ew")
        slider_frame.grid_columnconfigure(1, weight=1)

        CTkLabel(
            slider_frame, text="🎚️  Mic Sensitivity",
            font=("Segoe UI", 13, "bold"), text_color="white"
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 4), sticky="w")

        self.slider = CTkSlider(
            slider_frame,
            from_=50, to=1000,
            width=300,
            command=self._on_slider_change
        )
        self.slider.set(Config.ENERGY_THRESHOLD)
        self.slider.grid(row=1, column=0, padx=(16, 8), pady=(0, 14))

        self.slider_value_label = CTkLabel(
            slider_frame,
            text=str(Config.ENERGY_THRESHOLD),
            font=("Segoe UI", 12), text_color=Config.COLOR_GRAY, width=40
        )
        self.slider_value_label.grid(row=1, column=1, padx=(0, 16), pady=(0, 14))

        # ── Trigger Words Reference
        ref_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=12
        )
        ref_frame.grid(row=4, column=0, padx=24, pady=(0, 14), sticky="ew")

        CTkLabel(
            ref_frame, text="🗣️  Voice Commands",
            font=("Segoe UI", 13, "bold"), text_color="white"
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 6), sticky="w")

        self.next_cmds_label = CTkLabel(
            ref_frame,
            text=self._format_trigger_line("➡️", Config.TRIGGER_NEXT, Config.COLOR_GREEN),
            font=("Segoe UI", 11), text_color=Config.COLOR_GREEN
        )
        self.next_cmds_label.grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

        self.prev_cmds_label = CTkLabel(
            ref_frame,
            text=self._format_trigger_line("⬅️", Config.TRIGGER_PREV, Config.COLOR_ORANGE),
            font=("Segoe UI", 11), text_color=Config.COLOR_ORANGE
        )
        self.prev_cmds_label.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="w")

        # ── Custom Commands (Pro) / Locked (Free)
        self.commands_pro_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=12
        )
        self.commands_pro_frame.grid(row=5, column=0, padx=24, pady=(0, 14), sticky="ew")
        self.commands_pro_frame.grid_columnconfigure(1, weight=1)

        CTkLabel(
            self.commands_pro_frame, text="⚙️  Custom Commands",
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
        )
        self.prev_cmd_entry.grid(row=2, column=1, padx=(0, 16), pady=(0, 6), sticky="ew")
        if self.is_pro:
            self.prev_cmd_entry.insert(0, ", ".join(Config.TRIGGER_PREV))

        CTkButton(
            self.commands_pro_frame,
            text="Save Commands",
            font=("Segoe UI", 12, "bold"),
            fg_color=Config.COLOR_BLUE,
            hover_color=Config.COLOR_BLUE_HOVER,
            command=self._save_custom_commands,
        ).grid(row=3, column=0, columnspan=2, padx=16, pady=(4, 14), sticky="w")

        self.commands_locked_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=12
        )
        self.commands_locked_frame.grid(row=5, column=0, padx=24, pady=(0, 14), sticky="ew")

        locked_row = CTkFrame(self.commands_locked_frame, fg_color="transparent")
        locked_row.pack(padx=16, pady=14)

        CTkLabel(
            locked_row,
            text="🔒 Custom Commands — Pro Only",
            font=("Segoe UI", 12), text_color=Config.COLOR_GRAY
        ).pack(side="left")

        self.activate_link = CTkButton(
            locked_row,
            text="Activate Pro",
            font=("Segoe UI", 11, "bold"),
            fg_color=Config.COLOR_SURFACE,
            hover_color=Config.COLOR_BORDER,
            text_color=Config.COLOR_BLUE,
            width=100, height=26,
            border_width=0,
            command=self._scroll_to_license,
        )
        self.activate_link.pack(side="left", padx=(8, 0))

        if self.is_pro:
            self.commands_locked_frame.grid_remove()
        else:
            self.commands_pro_frame.grid_remove()

        # ── License Activation (free tier — above log so it stays on screen)
        self.license_section = CTkFrame(self, fg_color=Config.COLOR_BG)
        if not self.is_pro:
            self.license_section.grid(row=6, column=0, padx=24, pady=(0, 10), sticky="ew")

        self.license_toggle_btn = CTkButton(
            self.license_section,
            text="🔑 Activate Pro  ▼",
            font=("Segoe UI", 11),
            fg_color=Config.COLOR_BG,
            hover_color=Config.COLOR_SURFACE,
            text_color=Config.COLOR_GRAY,
            anchor="w",
            height=28,
            border_width=0,
            command=self._toggle_license_section,
        )
        self.license_toggle_btn.pack(fill="x")

        self.license_content = CTkFrame(
            self.license_section,
            fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=10,
        )

        license_row = CTkFrame(self.license_content, fg_color=Config.COLOR_BG)
        license_row.pack(fill="x", padx=12, pady=12)

        self.license_entry = CTkEntry(
            license_row,
            placeholder_text="Enter license key (e.g. VOXS-PRO1-2026-A001)",
            font=("Segoe UI", 11),
            width=280,
        )
        self.license_entry.pack(side="left", padx=(0, 8))
        self.license_entry.bind("<Return>", lambda _e: self._activate_license())

        self.activate_btn = CTkButton(
            license_row,
            text="Activate",
            font=("Segoe UI", 11, "bold"),
            fg_color=Config.COLOR_BLUE,
            hover_color=Config.COLOR_BLUE_HOVER,
            width=80,
            command=self._activate_license,
        )
        self.activate_btn.pack(side="left")

        # ── Live Log Terminal
        log_frame = CTkFrame(
            self, fg_color=Config.COLOR_SURFACE,
            border_width=1, border_color=Config.COLOR_BORDER,
            corner_radius=12
        )
        log_frame.grid(row=7, column=0, padx=24, pady=(0, 14), sticky="ew")

        CTkLabel(
            log_frame, text="📋  Live Log",
            font=("Segoe UI", 12, "bold"), text_color="white"
        ).pack(anchor="w", padx=16, pady=(12, 4))

        self.log_box = CTkTextbox(
            log_frame,
            height=250,
            font=("Courier New", 11),
            fg_color=Config.COLOR_LOG_BG,
            text_color=Config.COLOR_LOG_TEXT,
            border_width=0,
            corner_radius=8,
            state="disabled",
            wrap="word"
        )
        self.log_box.pack(fill="x", padx=12, pady=(0, 12))

        # ── Footer
        footer_text = (
            f"VoxSlide AI  v{Config.VERSION}   •   Unlimited Sessions"
            if self.is_pro
            else f"VoxSlide AI  v{Config.VERSION}   •   Free Tier: {Config.SESSION_LIMIT_MINUTES} min sessions"
        )
        self.footer_label = CTkLabel(
            self,
            text=footer_text,
            font=("Segoe UI", 10),
            text_color=Config.COLOR_BORDER
        )
        self.footer_label.grid(row=8, column=0, pady=(0, 16))

        self._log("[System] VoxSlide AI ready. Press Start to begin.")
        if self.is_pro:
            self._log("[Pro] License active — unlimited sessions enabled.")
        self._refresh_cooldown_label()

    # ── LICENSE & COMMANDS ────────────────────────────────────

    @staticmethod
    def _format_trigger_line(icon: str, triggers: list, _color: str) -> str:
        quoted = '  /  '.join(f'"{t}"' for t in triggers)
        return f"{icon}  {quoted}"

    def _toggle_license_section(self):
        self.license_expanded = not self.license_expanded
        if self.license_expanded:
            self.license_content.pack(fill="x", pady=(4, 0))
            self.license_toggle_btn.configure(text="🔑 Activate Pro  ▲")
        else:
            self.license_content.pack_forget()
            self.license_toggle_btn.configure(text="🔑 Activate Pro  ▼")

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
        self.tier_badge.configure(text="⚡ Pro", text_color=Config.COLOR_GOLD)
        self.pro_status_label.pack(pady=(4, 0))
        self.footer_label.configure(
            text=f"VoxSlide AI  v{Config.VERSION}   •   Unlimited Sessions"
        )
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
        self.next_cmds_label.configure(
            text=self._format_trigger_line("➡️", Config.TRIGGER_NEXT, Config.COLOR_GREEN)
        )
        self.prev_cmds_label.configure(
            text=self._format_trigger_line("⬅️", Config.TRIGGER_PREV, Config.COLOR_ORANGE)
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
                text="■   Stop Listening",
                fg_color=Config.COLOR_RED,
                hover_color=Config.COLOR_RED_HOVER
            )
            self._set_status("● Listening...", Config.COLOR_GREEN)
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
            text="▶   Start Listening",
            fg_color=Config.COLOR_BLUE,
            hover_color=Config.COLOR_BLUE_HOVER
        )
        self._set_status("● Idle", Config.COLOR_GRAY)
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

    # ── CLEANUP ───────────────────────────────────────────────

    def _on_close(self):
        if self.audio_engine:
            self.audio_engine.stop()
        self.destroy()
