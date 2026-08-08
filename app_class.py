class App(ctk.CTk):
    SECTIONS = {
        "icons": "🖥️ الأيقونات",
        "look": "🎨 المظهر",
        "arrange": "📐 الترتيب",
        "layouts": "💾 التخطيطات",
        "display": "🖥️ الدقة",
        "settings": "⚙️ الإعدادات",
    }

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.title("Desktop Icon Studio")
        self.geometry("1280x850")
        self.minsize(1080, 760)

        try:
            self.ctl = DesktopController()
        except RuntimeError as exc:
            messagebox.showerror("خطأ", str(exc))
            self.destroy()
            return

        base = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.store = LayoutStore(os.path.join(base, "layouts.json"))
        self.settings = SettingsStore(os.path.join(base, "settings.json"))

        self.icons = []
        self.selection = set()
        self.drag_index = None
        self.hidden = False
        self._size_busy = False
        self._res = self.ctl.work_area()
        self.area = self._res

        # --- tk variables ---
        self.search_var = tk.StringVar()
        self.var_x = tk.IntVar(value=0)
        self.var_y = tk.IntVar(value=0)
        self.var_step = tk.IntVar(value=10)
        self.var_size = tk.IntVar(value=48)
        self.var_sx = tk.IntVar(value=DEFAULT_SPACING)
        self.var_sy = tk.IntVar(value=DEFAULT_SPACING)
        self.var_lname = tk.StringVar(value="تخطيطي")
        self._auto_save_res = tk.BooleanVar(value=True)
        self.theme_var = tk.StringVar(value="Dark")
        self.status = tk.StringVar(value="جاهز")

        self.nav_buttons = {}
        self.section_frames = {}
        self.icon_rows = []

        self._build_ui()
        self._apply_saved_theme()

        # --- tray + hotkeys ---
        self.tray_q = queue.Queue()
        icon_path = os.path.join(base, "icon.ico")
        self.tray = TrayManager(self.tray_q, icon_path=icon_path)
        self.tray.start()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_tray_queue)
        self.after(2000, self._check_resolution)
        self.after(300, self.refresh_icons)

    # ==================================================================
    #  Window / theme
    # ==================================================================
    def _set_title_bar_dark(self, dark=True):
        """تفعيل الوضع الداكن لشريط عنوان النافذة في ويندوز 10/11."""
        try:
            hwnd = wintypes.HWND(self.winfo_id())
            value = ctypes.c_int(1 if dark else 0)
            dwm = ctypes.windll.dwmapi
            for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
                try:
                    dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(value),
                                              ctypes.sizeof(value))
                    break
                except OSError:
                    continue
        except Exception:
            pass

    def _apply_theme(self, theme_name="dark"):
        mode = theme_name.capitalize() if theme_name in ("dark", "light") else "System"
        ctk.set_appearance_mode(mode)
        self._set_title_bar_dark(dark=(theme_name != "light"))

    def _apply_saved_theme(self):
        stored = self.settings.get("theme", "dark")
        self.theme_var.set(stored.capitalize())
        self._apply_theme(stored)

    # ==================================================================
    #  UI builders
    # ==================================================================
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- sidebar ---
        sidebar = ctk.CTkFrame(self, width=230, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(1, weight=1)
        sidebar.grid_propagate(False)

        ctk.CTkLabel(
            sidebar,
            text="Desktop Icon\nStudio",
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, pady=(24, 16), padx=20)

        nav_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)

        for key, label in self.SECTIONS.items():
            btn = ctk.CTkButton(
                nav_frame,
                text=label,
                anchor="w",
                height=42,
                font=ctk.CTkFont("Segoe UI", 14),
                fg_color="transparent",
                hover_color=("gray70", "gray35"),
                command=lambda k=key: self._show_section(k),
            )
            btn.pack(fill="x", pady=4)
            self.nav_buttons[key] = btn

        ctk.CTkLabel(
            sidebar,
            textvariable=self.status,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 11),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=12)

        # --- main area ---
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # header
        header = ctk.CTkFrame(main, height=70, corner_radius=0, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        header.grid_columnconfigure(0, weight=1)

        self.header_title = ctk.CTkLabel(
            header,
            text="🖥️ الأيقونات",
            font=ctk.CTkFont("Segoe UI", 24, "bold"),
        )
        self.header_title.grid(row=0, column=0, sticky="w")

        search = ctk.CTkEntry(
            header,
            placeholder_text="بحث…",
            width=260,
            textvariable=self.search_var,
            font=ctk.CTkFont("Segoe UI", 13),
        )
        search.grid(row=0, column=1, sticky="e")
        self.search_var.trace_add("write", lambda *a: self._filter_icons())

        # content container
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        self._build_icons_section(content)
        self._build_look_section(content)
        self._build_arrange_section(content)
        self._build_layouts_section(content)
        self._build_display_section(content)
        self._build_settings_section(content)

        self._show_section("icons")

    def _show_section(self, key):
        for k, frame in self.section_frames.items():
            if k == key:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=("gray75", "gray30"))
            else:
                btn.configure(fg_color="transparent")
        self.header_title.configure(text=self.SECTIONS[key])

    def _build_icons_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["icons"] = frame
        frame.grid_columnconfigure(0, weight=6)
        frame.grid_columnconfigure(1, weight=4)
        frame.grid_rowconfigure(0, weight=1)

        # mini-map card
        map_card = ctk.CTkFrame(frame)
        map_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        map_card.grid_rowconfigure(0, weight=1)
        map_card.grid_columnconfigure(0, weight=1)

        wx, wy, ww, wh = self.area
        self.map_w = 500
        self.map_h = max(240, int(self.map_w * wh / max(1, ww)))
        self.canvas = tk.Canvas(
            map_card,
            bg="#1e1e2e",
            highlightthickness=0,
            width=self.map_w,
            height=self.map_h,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.canvas.bind("<Button-1>", self._map_press)
        self.canvas.bind("<B1-Motion>", self._map_drag)
        self.canvas.bind("<ButtonRelease-1>", self._map_release)

        # right column
        right = ctk.CTkFrame(frame)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        list_card = ctk.CTkFrame(right)
        list_card.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 0))
        list_card.grid_rowconfigure(0, weight=1)
        list_card.grid_columnconfigure(0, weight=1)

        self.icon_list_frame = ctk.CTkScrollableFrame(
            list_card,
            label_text="قائمة الأيقونات",
            fg_color="transparent",
        )
        self.icon_list_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.icon_list_frame.grid_columnconfigure(0, weight=1)

        # action buttons
        ctrl = ctk.CTkFrame(right, fg_color="transparent")
        ctrl.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        ctrl.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.btn_hide = ctk.CTkButton(
            ctrl,
            text="🙈 إخفاء",
            command=self._toggle_hide,
        )
        self.btn_hide.grid(row=0, column=0, padx=4, sticky="ew")
        ctk.CTkButton(
            ctrl,
            text="🧲 محاذاة للشبكة",
            command=self._snap,
        ).grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(
            ctrl,
            text="🔄 تحديث",
            command=self.refresh_icons,
        ).grid(row=0, column=2, padx=4, sticky="ew")
        ctk.CTkButton(
            ctrl,
            text="❌ إلغاء التحديد",
            command=self._clear_selection,
        ).grid(row=0, column=3, padx=4, sticky="ew")

        # direct coordinate move
        coord = ctk.CTkFrame(right, fg_color="transparent")
        coord.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 6))
        ctk.CTkLabel(coord, text="X:").grid(row=0, column=0, padx=(0, 4))
        ctk.CTkEntry(coord, width=70, textvariable=self.var_x).grid(row=0, column=1, padx=4)
        ctk.CTkLabel(coord, text="Y:").grid(row=0, column=2, padx=(0, 4))
        ctk.CTkEntry(coord, width=70, textvariable=self.var_y).grid(row=0, column=3, padx=4)
        ctk.CTkButton(coord, text="📍 نقل", width=70, command=self._move_to_xy).grid(row=0, column=4, padx=(8, 0))

        # nudge controls
        move = ctk.CTkFrame(right, fg_color="transparent")
        move.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkLabel(move, text="خطوة:").grid(row=0, column=0, padx=(0, 4))
        ctk.CTkEntry(move, width=60, textvariable=self.var_step).grid(row=0, column=1, padx=4)
        ctk.CTkButton(move, text="⬆", width=36, command=lambda: self._nudge(0, -1)).grid(
            row=0, column=2, padx=4)
        ctk.CTkButton(move, text="⬅", width=36, command=lambda: self._nudge(-1, 0)).grid(
            row=0, column=3, padx=4)
        ctk.CTkButton(move, text="➡", width=36, command=lambda: self._nudge(1, 0)).grid(
            row=0, column=4, padx=4)
        ctk.CTkButton(move, text="⬇", width=36, command=lambda: self._nudge(0, 1)).grid(
            row=0, column=5, padx=4)

    def _build_look_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["look"] = frame
        frame.grid_columnconfigure(0, weight=1)

        # icon size
        size_card = ctk.CTkFrame(frame)
        size_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        size_card.grid_columnconfigure(0, weight=1)

        cur = self.ctl.get_icon_size()
        self.var_size.set(cur or 48)
        self.lbl_size = ctk.CTkLabel(
            size_card,
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
            text=f"حجم الأيقونات: {cur if cur else 'غير معروف'} بكسل",
        )
        self.lbl_size.grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        ctk.CTkSlider(
            size_card,
            from_=16,
            to=256,
            number_of_steps=240,
            variable=self.var_size,
            command=lambda v: self.lbl_size.configure(
                text=f"حجم الأيقونات: {int(float(v))} بكسل"),
        ).grid(row=1, column=0, sticky="ew", padx=15, pady=5)

        row = ctk.CTkFrame(size_card, fg_color="transparent")
        row.grid(row=2, column=0, sticky="w", padx=15, pady=(5, 15))
        ctk.CTkButton(
            row,
            text="−",
            width=40,
            command=lambda: self._size_step(False),
        ).grid(row=0, column=0, padx=4)
        ctk.CTkButton(
            row,
            text="+",
            width=40,
            command=lambda: self._size_step(True),
        ).grid(row=0, column=1, padx=4)
        self.btn_size = ctk.CTkButton(
            row,
            text="✔ تطبيق الحجم",
            command=self._apply_size,
        )
        self.btn_size.grid(row=0, column=2, padx=(20, 4))

        # spacing
        spacing_card = ctk.CTkFrame(frame)
        spacing_card.grid(row=1, column=0, sticky="ew")
        spacing_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            spacing_card,
            text="المسافات بين الأيقونات",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        try:
            cx, cy = self.ctl.get_spacing()
        except OSError:
            cx, cy = DEFAULT_SPACING, DEFAULT_SPACING
        self.var_sx.set(cx or DEFAULT_SPACING)
        self.var_sy.set(cy or DEFAULT_SPACING)

        ctk.CTkLabel(spacing_card, text="أفقي:").grid(
            row=1, column=0, sticky="w", padx=15)
        ctk.CTkSlider(
            spacing_card,
            from_=32,
            to=400,
            number_of_steps=368,
            variable=self.var_sx,
        ).grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 10))

        ctk.CTkLabel(spacing_card, text="رأسي:").grid(
            row=3, column=0, sticky="w", padx=15)
        ctk.CTkSlider(
            spacing_card,
            from_=32,
            to=400,
            number_of_steps=368,
            variable=self.var_sy,
        ).grid(row=4, column=0, sticky="ew", padx=15, pady=(0, 10))

        row2 = ctk.CTkFrame(spacing_card, fg_color="transparent")
        row2.grid(row=5, column=0, sticky="w", padx=15, pady=(5, 15))
        ctk.CTkButton(row2, text="✔ تطبيق المسافات", command=self._apply_spacing).grid(
            row=0, column=0, padx=4)
        ctk.CTkButton(row2, text="↩ إعادة الافتراضي", command=self._reset_spacing).grid(
            row=0, column=1, padx=4)

    def _build_arrange_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["arrange"] = frame
        frame.grid_columnconfigure((0, 1), weight=1)
        frame.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)

        buttons = [
            ("🔳 شبكة", self._arrange_grid),
            ("⭕ دائرة", self._arrange_circle),
            ("〰 موجة", self._arrange_wave),
            ("🌀 حلزون", self._arrange_spiral),
            ("📂 حسب النوع", self._arrange_by_type),
            ("⬆ صف علوي", lambda: self._arrange_edge("top")),
            ("⬇ صف سفلي", lambda: self._arrange_edge("bottom")),
            ("◀ عمود أيسر", lambda: self._arrange_edge("left")),
            ("▶ عمود أيمن", lambda: self._arrange_edge("right")),
            ("🎯 توسيط", self._arrange_center),
            ("🧲 محاذاة للشبكة", self._snap),
        ]
        for idx, (text, cmd) in enumerate(buttons):
            r, c = divmod(idx, 2)
            ctk.CTkButton(
                frame,
                text=text,
                command=cmd,
                height=70,
                font=ctk.CTkFont("Segoe UI", 14),
            ).grid(row=r, column=c, sticky="nsew", padx=8, pady=8)

    def _build_layouts_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["layouts"] = frame
        frame.grid_columnconfigure(0, weight=1)

        # save
        save_card = ctk.CTkFrame(frame)
        save_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        save_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(save_card, text="اسم التخطيط:").grid(
            row=0, column=0, padx=15, pady=15)
        ctk.CTkEntry(save_card, textvariable=self.var_lname).grid(
            row=0, column=1, sticky="ew", padx=10, pady=15)
        ctk.CTkButton(save_card, text="💾 حفظ", command=self._save_layout).grid(
            row=0, column=2, padx=15, pady=15)

        # restore/delete
        restore_card = ctk.CTkFrame(frame)
        restore_card.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        restore_card.grid_columnconfigure(0, weight=1)

        self.cmb = ctk.CTkOptionMenu(restore_card, values=[])
        self.cmb.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        ctk.CTkButton(restore_card, text="📂 استعادة", command=self._restore_layout).grid(
            row=0, column=1, padx=(0, 10), pady=15)
        ctk.CTkButton(restore_card, text="🗑 حذف", command=self._delete_layout).grid(
            row=0, column=2, padx=(0, 15), pady=15)

        # import/export
        io_card = ctk.CTkFrame(frame)
        io_card.grid(row=2, column=0, sticky="ew")
        ctk.CTkButton(io_card, text="⬇ تصدير JSON", command=self._export_layouts).grid(
            row=0, column=0, padx=15, pady=15)
        ctk.CTkButton(io_card, text="⬆ استيراد JSON", command=self._import_layouts).grid(
            row=0, column=1, padx=(0, 15), pady=15)

        self._reload_layout_list()

    def _build_display_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["display"] = frame
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkSwitch(
            frame,
            text="✅ حفظ/استعادة تلقائية عند تغيّر الدقة",
            variable=self._auto_save_res,
        ).grid(row=0, column=0, sticky="w", padx=15, pady=15)

        self._res_lbl = ctk.CTkLabel(
            frame,
            text=self._res_key(self._res),
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
        )
        self._res_lbl.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 10))

        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 15))
        ctk.CTkButton(
            row,
            text="💾 حفظ تخطيط هذه الدقة",
            command=lambda: self._save_resolution_layout(self.ctl.work_area()),
        ).grid(row=0, column=0, padx=4)
        ctk.CTkButton(
            row,
            text="📂 استعادة تخطيط هذه الدقة",
            command=lambda: self._try_restore_resolution_layout(self.ctl.work_area()),
        ).grid(row=0, column=1, padx=4)

    def _build_settings_section(self, parent):
        frame = ctk.CTkFrame(parent)
        self.section_frames["settings"] = frame
        frame.grid_columnconfigure(0, weight=1)

        # theme
        theme_card = ctk.CTkFrame(frame)
        theme_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        theme_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            theme_card,
            text="المظهر",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        self.theme_cmb = ctk.CTkOptionMenu(
            theme_card,
            values=["Dark", "Light", "System"],
            variable=self.theme_var,
            command=self._on_theme_change,
        )
        self.theme_cmb.grid(row=1, column=0, sticky="w", padx=15, pady=(5, 15))

        # hotkeys
        hotkeys_card = ctk.CTkFrame(frame)
        hotkeys_card.grid(row=1, column=0, sticky="ew")
        hotkeys_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hotkeys_card,
            text="اختصارات الكيبورد",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 5))

        hotkeys_text = (
            "Ctrl+Alt+S    فتح البرنامج\n"
            "Ctrl+Alt+H    إخفاء/إظهار النافذة\n"
            "Ctrl+Alt+R    استعادة تخطيط الدقة\n"
            "Ctrl+Alt+W    ترتيب موجة\n"
            "Ctrl+Alt+P    ترتيب حلزون"
        )
        ctk.CTkLabel(
            hotkeys_card,
            text=hotkeys_text,
            justify="right",
            anchor="e",
            font=ctk.CTkFont("Consolas", 14),
        ).grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 15))

    def _on_theme_change(self, choice):
        key = choice.lower()
        self.settings.set("theme", key)
        self._apply_theme(key)
        self._set_status(f"✅ تم تطبيق المظهر: {choice}")

    # ==================================================================
    #  Icon list helpers
    # ==================================================================
    def _rebuild_icon_list(self):
        for row in self.icon_rows:
            row["frame"].destroy()
        self.icon_rows = []
        self.selection = set()

        for ic in self.icons:
            idx = ic["i"]
            card = ctk.CTkFrame(self.icon_list_frame, fg_color="transparent", corner_radius=6)
            card.grid_columnconfigure(1, weight=1)

            var = tk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(card, text="", variable=var, width=20)
            chk.configure(command=lambda i=idx, v=var: self._row_toggle(i, v.get()))
            chk.grid(row=0, column=0, padx=5)

            name_lbl = ctk.CTkLabel(card, text=ic["name"], anchor="w")
            name_lbl.grid(row=0, column=1, sticky="w", padx=5)
            name_lbl.bind("<Button-1>", lambda e, i=idx: self._select(i, only=True))

            coords_lbl = ctk.CTkLabel(
                card,
                text=f"({ic['x']}, {ic['y']})",
                anchor="e",
                width=80,
            )
            coords_lbl.grid(row=0, column=2, padx=5)
            coords_lbl.bind("<Button-1>", lambda e, i=idx: self._select(i, only=True))

            card.grid(row=len(self.icon_rows), column=0, sticky="ew", pady=2)
            self.icon_rows.append({
                "index": idx,
                "frame": card,
                "name_lbl": name_lbl,
                "coords_lbl": coords_lbl,
                "var": var,
                "name": ic["name"].lower(),
            })
        self._filter_icons()

    def _filter_icons(self):
        term = self.search_var.get().lower().strip()
        for row in self.icon_rows:
            if not term or term in row["name"]:
                row["frame"].grid()
            else:
                row["frame"].grid_remove()

    def _select(self, idx, only=False):
        if only:
            self.selection = {idx}
        else:
            self.selection.add(idx)
        self._update_selection_vars()
        self._update_row_visuals()
        self._on_select()
        self._draw_map()

    def _row_toggle(self, idx, selected):
        if selected:
            self.selection.add(idx)
        else:
            self.selection.discard(idx)
        self._update_selection_vars()
        self._update_row_visuals()
        self._on_select()
        self._draw_map()

    def _clear_selection(self):
        self.selection.clear()
        self._update_selection_vars()
        self._update_row_visuals()
        self._on_select()
        self._draw_map()

    def _update_selection_vars(self):
        for row in self.icon_rows:
            val = row["index"] in self.selection
            if row["var"].get() != val:
                row["var"].set(val)

    def _update_row_visuals(self):
        for row in self.icon_rows:
            if row["index"] in self.selection:
                row["frame"].configure(fg_color=("gray85", "gray25"))
            else:
                row["frame"].configure(fg_color="transparent")

    # ==================================================================
    #  Core backend (kept/reimplemented)
    # ==================================================================
    def _set_status(self, msg):
        self.status.set(msg)
        self.update_idletasks()

    def _res_key(self, area):
        return f"auto_{area[2]}x{area[3]}"

    def refresh_icons(self):
        try:
            self._set_status("⏳ جارٍ قراءة الأيقونات…")
            self.icons = self.ctl.list_icons()
        except OSError as exc:
            messagebox.showerror("خطأ", str(exc))
            self._set_status("تعذّرت قراءة الأيقونات")
            return
        self._rebuild_icon_list()
        self._draw_map()
        cur = self.ctl.get_icon_size()
        self.lbl_size.configure(
            text=f"حجم الأيقونات: {cur if cur else 'غير معروف'} بكسل")
        self._res_lbl.configure(text=self._res_key(self.ctl.work_area()))
        self._set_status(f"✅ {len(self.icons)} أيقونة")

    def _draw_map(self):
        c = self.canvas
        c.delete("all")
        wx, wy, ww, wh = self.area
        sx = self.map_w / max(1, ww)
        sy = self.map_h / max(1, wh)
        self._scale = (sx, sy)
        for ic in self.icons:
            x = (ic["x"] - wx) * sx
            y = (ic["y"] - wy) * sy
            selected = ic["i"] in self.selection
            color = "#f9a825" if selected else "#4fc3f7"
            c.create_rectangle(x, y, x + 10, y + 10, fill=color,
                               outline="", tags=f"ic{ic['i']}")

    def _selected_index(self):
        if not self.selection:
            return None
        return min(self.selection)

    def _on_select(self, _evt=None):
        i = self._selected_index()
        if i is None or i >= len(self.icons):
            return
        ic = self.icons[i]
        self.var_x.set(ic["x"])
        self.var_y.set(ic["y"])

    def _move_icon(self, i, x, y):
        self.ctl.set_position(i, x, y)
        if i < len(self.icons):
            self.icons[i]["x"], self.icons[i]["y"] = x, y
            for row in self.icon_rows:
                if row["index"] == i:
                    row["coords_lbl"].configure(text=f"({x}, {y})")
                    break
        self._draw_map()

    def _move_to_xy(self):
        if not self.selection:
            messagebox.showinfo("تنبيه", "اختر أيقونة من القائمة أولًا.")
            return
        x, y = self.var_x.get(), self.var_y.get()
        base = self.icons[min(self.selection)]
        dx, dy = x - base["x"], y - base["y"]
        for idx in self.selection:
            ic = self.icons[idx]
            self._move_icon(idx, ic["x"] + dx, ic["y"] + dy)
        self.ctl.refresh_view()
        self._set_status(f"📍 نُقلت الأيقونات إلى ({x}, {y})")

    def _nudge(self, dx, dy):
        if not self.selection:
            messagebox.showinfo("تنبيه", "اختر أيقونة من القائمة أولًا.")
            return
        step = self.var_step.get()
        for i in list(self.selection):
            ic = self.icons[i]
            self._move_icon(i, ic["x"] + dx * step, ic["y"] + dy * step)
        self.ctl.refresh_view()

    def _map_to_desktop(self, mx, my):
        sx, sy = self._scale
        wx, wy = self.area[0], self.area[1]
        return int(mx / sx + wx), int(my / sy + wy)

    def _icon_at(self, mx, my):
        sx, sy = self._scale
        wx, wy = self.area[0], self.area[1]
        for ic in self.icons:
            x = (ic["x"] - wx) * sx
            y = (ic["y"] - wy) * sy
            if x - 6 <= mx <= x + 16 and y - 6 <= my <= y + 16:
                return ic["i"]
        return None

    def _map_press(self, evt):
        i = self._icon_at(evt.x, evt.y)
        if i is not None:
            self._select(i, only=True)
            self.drag_index = i
        else:
            if self.selection:
                x, y = self._map_to_desktop(evt.x, evt.y)
                base = self.icons[min(self.selection)]
                dx, dy = x - base["x"], y - base["y"]
                for idx in self.selection:
                    ic = self.icons[idx]
                    self._move_icon(idx, ic["x"] + dx, ic["y"] + dy)
                self.ctl.refresh_view()

    def _map_drag(self, evt):
        if self.drag_index is not None and self.selection:
            x, y = self._map_to_desktop(evt.x, evt.y)
            base = self.icons[self.drag_index]
            dx, dy = x - base["x"], y - base["y"]
            for idx in self.selection:
                ic = self.icons[idx]
                self._move_icon(idx, ic["x"] + dx, ic["y"] + dy)

    def _map_release(self, _evt):
        if self.drag_index is not None:
            self.drag_index = None
            self.ctl.refresh_view()

    def _apply_size(self):
        if self._size_busy:
            return
        target = self.var_size.get()
        self._size_busy = True
        self.btn_size.configure(state="disabled")

        def worker():
            err = None
            try:
                final = self.ctl.set_icon_size(target)
                self.after(0, lambda: self.lbl_size.configure(
                    text=f"حجم الأيقونات: {final if final else 'غير معروف'} بكسل"))
            except RuntimeError as exc:
                err = str(exc)
            finally:
                def done():
                    self._size_busy = False
                    self.btn_size.configure(state="normal")
                    if err:
                        messagebox.showwarning("تعذّر الضبط الدقيق", err)
                    self._set_status("✅ تم ضبط حجم الأيقونات")
                self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _size_step(self, bigger):
        try:
            self.ctl.nudge_icon_size(bigger)
            cur = self.ctl.get_icon_size()
            self.lbl_size.configure(
                text=f"حجم الأيقونات: {cur if cur else 'غير معروف'} بكسل")
            self.var_size.set(cur or self.var_size.get())
        except OSError as exc:
            messagebox.showerror("خطأ", str(exc))

    def _apply_spacing(self):
        try:
            self.ctl.set_spacing(self.var_sx.get(), self.var_sy.get())
            self._set_status(
                f"✅ المسافات: {self.var_sx.get()}×{self.var_sy.get()} بكسل")
        except OSError as exc:
            messagebox.showerror("خطأ", str(exc))

    def _reset_spacing(self):
        self.var_sx.set(DEFAULT_SPACING)
        self.var_sy.set(DEFAULT_SPACING)
        self._apply_spacing()

    def _gap(self):
        return max(40, self.var_sx.get()), max(40, self.var_sy.get())

    def _place(self, positions):
        for ic, (x, y) in zip(self.icons, positions):
            self.ctl.set_position(ic["i"], x, y)
            ic["x"], ic["y"] = x, y
        self.ctl.refresh_view()
        self.refresh_icons()

    def _arrange_grid(self):
        if not self.icons:
            return
        gx, gy = self._gap()
        wx, wy, ww, wh = self.area
        cols = max(1, ww // gx)
        icons = sorted(self.icons, key=lambda c: c["name"].lower())
        pos = []
        for n, _ in enumerate(icons):
            r, cidx = divmod(n, cols)
            pos.append((wx + cidx * gx, wy + r * gy))
        self.icons = icons
        self._place(pos)
        self._set_status("🔳 تم الترتيب في شبكة")

    def _arrange_circle(self):
        n = len(self.icons)
        if not n:
            return
        wx, wy, ww, wh = self.area
        cx, cy = wx + ww // 2, wy + wh // 2
        r = max(120, min(ww, wh) // 2 - 90)
        pos = [(int(cx + r * math.cos(2 * math.pi * k / n - math.pi / 2)) - 30,
                int(cy + r * math.sin(2 * math.pi * k / n - math.pi / 2)) - 30)
               for k in range(n)]
        self._place(pos)
        self._set_status("⭕ تم الترتيب في دائرة")

    def _arrange_wave(self):
        n = len(self.icons)
        if not n:
            return
        wx, wy, ww, wh = self.area
        margin = max(60, ww // 12)
        usable = max(1, ww - 2 * margin)
        step = usable / max(1, n - 1)
        amplitude = max(80, wh // 4)
        cy = wy + wh // 2
        icons = sorted(self.icons, key=lambda c: c["name"].lower())
        pos = []
        for k, _ in enumerate(icons):
            x = wx + margin + int(k * step)
            y = int(cy + amplitude * math.sin(2 * math.pi * k / max(1, n - 1)))
            pos.append((x, y))
        self.icons = icons
        self._place(pos)
        self._set_status("〰 تم الترتيب في موجة")

    def _arrange_spiral(self):
        n = len(self.icons)
        if not n:
            return
        wx, wy, ww, wh = self.area
        cx, cy = wx + ww // 2, wy + wh // 2
        max_r = min(ww, wh) // 2 - 80
        a = max(8, max_r / (2 * math.pi * max(1, math.sqrt(n))))
        icons = sorted(self.icons, key=lambda c: c["name"].lower())
        pos = []
        for k, _ in enumerate(icons):
            t = math.sqrt(k + 1)
            r = a * t
            angle = t * 2 * math.pi
            x = int(cx + r * math.cos(angle))
            y = int(cy + r * math.sin(angle))
            pos.append((x, y))
        self.icons = icons
        self._place(pos)
        self._set_status("🌀 تم الترتيب في حلزون")

    def _arrange_by_type(self):
        if not self.icons:
            return
        desktop = os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
        name_to_ext = {}
        if os.path.isdir(desktop):
            for name in os.listdir(desktop):
                base, ext = os.path.splitext(name)
                ext = ext.lower() if ext else "📄 ملف"
                name_to_ext[base.lower()] = ext

        groups = {}
        for ic in self.icons:
            ext = name_to_ext.get(ic["name"].lower().rstrip(), "🖥️ أيقونة نظام")
            groups.setdefault(ext, []).append(ic)

        gx, gy = self._gap()
        wx, wy, ww, wh = self.area
        col_width = gx * 2
        col_x = wx + gx
        row_y = wy + gy
        max_col_h = 0
        ordered = []
        pos = []
        for ext in sorted(groups.keys()):
            gicons = sorted(groups[ext], key=lambda c: c["name"].lower())
            if col_x + col_width > wx + ww - gx:
                col_x = wx + gx
                row_y += max_col_h + gy
                max_col_h = 0
            for idx, ic in enumerate(gicons):
                ordered.append(ic)
                pos.append((col_x, row_y + idx * gy))
            max_col_h = max(max_col_h, len(gicons) * gy)
            col_x += col_width
        self.icons = ordered
        self._place(pos)
        self._set_status("📂 تم الترتيب حسب نوع الملف")

    def _arrange_edge(self, edge):
        n = len(self.icons)
        if not n:
            return
        gx, gy = self._gap()
        wx, wy, ww, wh = self.area
        pos = []
        if edge == "top":
            pos = [(wx + k * gx, wy) for k in range(n)]
        elif edge == "bottom":
            y = wy + wh - gy
            pos = [(wx + k * gx, y) for k in range(n)]
        elif edge == "left":
            pos = [(wx, wy + k * gy) for k in range(n)]
        else:
            x = wx + ww - gx
            pos = [(x, wy + k * gy) for k in range(n)]
        self._place(pos)
        self._set_status("✅ تم الترتيب على الحافة")

    def _arrange_center(self):
        n = len(self.icons)
        if not n:
            return
        gx, gy = self._gap()
        wx, wy, ww, wh = self.area
        total = n * gx
        x0 = wx + max(0, (ww - total) // 2)
        y0 = wy + wh // 2 - gy // 2
        pos = [(x0 + k * gx, y0) for k in range(n)]
        self._place(pos)
        self._set_status("🎯 تم التوسيط")

    def _snap(self):
        self.ctl.snap_to_grid()
        self._set_status("🧲 تمت المحاذاة للشبكة")
        self.after(400, self.refresh_icons)

    def _toggle_hide(self):
        self.hidden = not self.hidden
        self.ctl.set_visible(not self.hidden)
        self.btn_hide.configure(
            text="👁 إظهار الأيقونات" if self.hidden else "🙈 إخفاء الأيقونات")
        self._set_status("🙈 الأيقونات مخفية" if self.hidden else "👁 الأيقونات ظاهرة")

    # ---------------- Layouts ----------------
    def _reload_layout_list(self):
        names = sorted(self.store.data.keys())
        self.cmb.configure(values=names)
        if names:
            if self.cmb.get() not in names:
                self.cmb.set(names[0])
        else:
            self.cmb.set("")

    def _save_layout(self):
        name = self.var_lname.get().strip()
        if not name:
            messagebox.showinfo("تنبيه", "اكتب اسمًا للتخطيط أولًا.")
            return
        if not self.icons:
            self.refresh_icons()
        try:
            spacing = self.ctl.get_spacing()
        except OSError:
            spacing = (DEFAULT_SPACING, DEFAULT_SPACING)
        self.store.put(name, self.icons, self.area, spacing)
        self._reload_layout_list()
        self.cmb.set(name)
        self._set_status(f"💾 حُفظ التخطيط «{name}»")

    def _restore_layout(self):
        name = self.cmb.get()
        lay = self.store.data.get(name)
        if not lay:
            messagebox.showinfo("تنبيه", "اختر تخطيطًا محفوظًا أولًا.")
            return
        self._apply_layout(lay)
        self._set_status(f"📂 استُعيد التخطيط «{name}»")

    def _apply_layout(self, lay):
        saved_area = lay.get("work_area") or self.area
        sx = self.area[2] / max(1, saved_area[2])
        sy = self.area[3] / max(1, saved_area[3])
        by_name = {ic["name"]: ic for ic in self.icons}
        moved = 0
        for iname, (x, y) in lay.get("icons", {}).items():
            ic = by_name.get(iname)
            if ic:
                nx = int(self.area[0] + (x - saved_area[0]) * sx)
                ny = int(self.area[1] + (y - saved_area[1]) * sy)
                self.ctl.set_position(ic["i"], nx, ny)
                moved += 1
        self.ctl.refresh_view()
        self.refresh_icons()

    def _delete_layout(self):
        name = self.cmb.get()
        if name and name in self.store.data:
            if messagebox.askyesno("تأكيد", f"حذف التخطيط «{name}»؟"):
                self.store.delete(name)
                self.cmb.set("")
                self._reload_layout_list()
                self._set_status(f"🗑 حُذف «{name}»")

    def _export_layouts(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="desktop_layouts.json",
            title="تصدير التخطيطات")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.store.data, f, ensure_ascii=False, indent=2)
                self._set_status(f"⬇ تم التصدير إلى {path}")
            except OSError as exc:
                messagebox.showerror("خطأ", str(exc))

    def _import_layouts(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")], title="استيراد تخطيطات")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.store.data.update(data)
                    self.store.save()
                    self._reload_layout_list()
                    self._set_status("⬆ تم الاستيراد")
            except (OSError, json.JSONDecodeError) as exc:
                messagebox.showerror("خطأ", str(exc))

    # ---------------- Resolution ----------------
    def _save_resolution_layout(self, area):
        if not self.icons:
            self.refresh_icons()
        key = self._res_key(area)
        try:
            spacing = self.ctl.get_spacing()
        except OSError:
            spacing = (DEFAULT_SPACING, DEFAULT_SPACING)
        self.store.put(key, self.icons, area, spacing)
        self._reload_layout_list()
        self.cmb.set(key)
        self._set_status(f"💾 حُفظ تخطيط الدقة {key}")

    def _try_restore_resolution_layout(self, area):
        key = self._res_key(area)
        lay = self.store.data.get(key)
        if lay:
            self._apply_layout(lay)
            self._set_status(f"📂 استُعيد تخطيط الدقة {key}")
        else:
            self._set_status(f"ℹ لا يوجد تخطيط محفوظ للدقة {key}")

    def _check_resolution(self):
        try:
            new_area = self.ctl.work_area()
        except OSError:
            self.after(2000, self._check_resolution)
            return
        if (new_area[2], new_area[3]) != (self._res[2], self._res[3]):
            old_area = self._res
            self._res = new_area
            self.area = new_area
            if self._auto_save_res.get():
                self._save_resolution_layout(old_area)
            self._try_restore_resolution_layout(new_area)
            self._res_lbl.configure(text=self._res_key(new_area))
        self.after(2000, self._check_resolution)

    # ---------------- Tray integration ----------------
    def _poll_tray_queue(self):
        while True:
            try:
                cmd = self.tray_q.get_nowait()
            except queue.Empty:
                break
            if cmd == "SHOW_WINDOW":
                self.deiconify()
                self.lift()
                self.focus_force()
            elif cmd == "TOGGLE_WINDOW":
                if self.state() == "withdrawn":
                    self.deiconify()
                    self.lift()
                else:
                    self.withdraw()
            elif cmd == "SAVE_RES":
                self._save_resolution_layout(self.ctl.work_area())
            elif cmd == "RESTORE_RES":
                self._try_restore_resolution_layout(self.ctl.work_area())
            elif cmd == "ARRANGE_WAVE":
                self._arrange_wave()
            elif cmd == "ARRANGE_SPIRAL":
                self._arrange_spiral()
            elif cmd == "ARRANGE_TYPE":
                self._arrange_by_type()
            elif cmd == "EXIT":
                self._exit_app()
        self.after(100, self._poll_tray_queue)

    def _on_close(self):
        self.withdraw()
        self._set_status("البرنامج يعمل بجانب الساعة — اضغط Ctrl+Alt+S لفتحه")

    def _exit_app(self):
        self.tray.stop()
        try:
            self.tray.join(timeout=2.0)
        except Exception:
            pass
        self.destroy()
