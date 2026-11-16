import datetime
import json
import os
import random
import sys
import tkinter as tk
from tkinter import colorchooser, messagebox
import urllib.request

# Джерело реальних адміністративних меж України (ADM1: 24 області + АР Крим)
GEOJSON_URLS = [
    "https://raw.githubusercontent.com/EugeneBorshchev/ukraine_geojson/master/ukraine.geojson",
    "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/ukraine.geojson",
]
LOCAL_GEOJSON = "ukraine_adm1.geojson"

# Підписи українською для ключових регіонів
UK_LABELS = {
    "Volyn": "Волинська",
    "Volynska": "Волинська",
    "Rivne": "Рівненська",
    "Rivnenska": "Рівненська",
    "Lviv": "Львівська",
    "Lvivska": "Львівська",
    "Ternopil": "Тернопільська",
    "Ternopilska": "Тернопільська",
    "Khmelnytskyi": "Хмельницька",
    "Khmelnytska": "Хмельницька",
    "Zhytomyr": "Житомирська",
    "Zhytomyrska": "Житомирська",
    "Vinnytsia": "Вінницька",
    "Vinnytska": "Вінницька",
    "Zakarpattia": "Закарпатська",
    "Zakarpatska": "Закарпатська",
    "Ivano-Frankivsk": "Івано-Франківська",
    "Ivano-Frankivska": "Івано-Франківська",
    "Chernivtsi": "Чернівецька",
    "Chernivetska": "Чернівецька",
    "Kyiv": "Київська",
    "Kyivska": "Київська",
    "Kyiv City": "м. Київ",
    "Kiev City": "м. Київ",
    "Chernihiv": "Чернігівська",
    "Chernihivska": "Чернігівська",
    "Sumy": "Сумська",
    "Sumska": "Сумська",
    "Cherkasy": "Черкаська",
    "Cherkaska": "Черкаська",
    "Kirovohrad": "Кіровоградська",
    "Kirovohradska": "Кіровоградська",
    "Poltava": "Полтавська",
    "Poltavska": "Полтавська",
    "Kharkiv": "Харківська",
    "Kharkivska": "Харківська",
    "Odesa": "Одеська",
    "Odessa": "Одеська",
    "Odeska": "Одеська",
    "Mykolaiv": "Миколаївська",
    "Mykolaivska": "Миколаївська",
    "Kherson": "Херсонська",
    "Khersonska": "Херсонська",
    "Dnipropetrovsk": "Дніпропетровська",
    "Dnipropetrovska": "Дніпропетровська",
    "Zaporizhzhia": "Запорізька",
    "Zaporizhzhia Oblast": "Запорізька",
    "Zaporizka": "Запорізька",
    "Donetsk": "Донецька",
    "Donetska": "Донецька",
    "Luhansk": "Луганська",
    "Luhanska": "Луганська",
    "Crimea": "А. Р. Крим",
    "Autonomous Republic of Crimea": "А. Р. Крим",
}

BG_DARK = "#181b21"
PANEL_DARK = "#1f232c"
CARD_DARK = "#282e3b"
IDLE_COLOR = "#333942"
BORDER_COLOR = "#181b21"
TEXT_MAIN = "#f3f5f8"
TEXT_MUTED = "#9aa3b2"


def load_geojson():
    if os.path.exists(LOCAL_GEOJSON):
        with open(LOCAL_GEOJSON, "r", encoding="utf-8") as f:
            return json.load(f)

    for url in GEOJSON_URLS:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict) and data.get("features"):
                    with open(LOCAL_GEOJSON, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                    return data
        except Exception:
            continue
    return None


def get_region_name(feature):
    props = feature.get("properties") or {}
    for key in ("name_uk", "NAME_UK", "name", "NAME_1", "shapeName", "region"):
        val = props.get(key)
        if val:
            raw = str(val).strip()
            return UK_LABELS.get(raw, raw)
    return "Регіон"


def extract_polygons(geometry):
    if not geometry:
        return []
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "Polygon":
        return [coords[0]] if coords else []
    if gtype == "MultiPolygon":
        polys = []
        for poly in coords:
            if poly and poly[0]:
                polys.append(poly[0])
        return polys
    return []


def polygon_centroid(ring):
    if not ring:
        return (0.0, 0.0)
    area = 0.0
    cx = 0.0
    cy = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area) < 1e-9:
        avg_x = sum(p[0] for p in ring) / n
        avg_y = sum(p[1] for p in ring) / n
        return (avg_x, avg_y)
    return (cx / (3.0 * area), cy / (3.0 * area))


def point_in_polygon(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i][0], poly[i][1]
        x2, y2 = poly[(i + 1) % n][0], poly[(i + 1) % n][1]
        cond = ((y1 > y) != (y2 > y)) and (
            x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1
        )
        if cond:
            inside = not inside
    return inside


class AlarmMapApp:
    def __init__(self, root, geojson):
        self.root = root
        self.root.title("Симулятор мапи тривог України (Python)")
        self.root.configure(bg=BG_DARK)
        self.root.geometry("1220x740")

        self.geojson = geojson
        self.selected_color = "#b33933"
        self.mode = "toggle"  # toggle | paint | erase
        self.is_dragging = False
        self.active_regions = {}  # region_name -> color
        self.region_polys = []

        self._build_ui()
        self._prepare_geometry()
        self._render_map()

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=0)
        self.root.rowconfigure(0, weight=1)

        left = tk.Frame(self.root, bg=BG_DARK)
        left.grid(row=0, column=0, sticky="nsew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(left, bg=BG_DARK, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Плашка в лівому нижньому куті
        self.badge = tk.Frame(
            left,
            bg="#1b2234",
            highlightbackground="#2d3854",
            highlightthickness=1,
            padx=12,
            pady=8,
        )
        self.badge.place(x=16, rely=1.0, y=-68, anchor="nw")
        tk.Label(
            self.badge,
            text="map.ukrainealarm.com",
            bg="#1b2234",
            fg="#ffffff",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w")
        self.clock_lbl = tk.Label(
            self.badge,
            text="",
            bg="#1b2234",
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
        )
        self.clock_lbl.pack(anchor="w")
        self._update_clock()

        # Права панель керування
        sidebar = tk.Frame(self.root, bg=PANEL_DARK, width=320, padx=14, pady=14)
        sidebar.grid(row=0, column=1, sticky="ns")
        sidebar.grid_propagate(False)

        tk.Label(
            sidebar,
            text="Антистрес-мапа тривог",
            bg=PANEL_DARK,
            fg=TEXT_MAIN,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        # Кастомізатор кольору
        color_card = tk.Frame(sidebar, bg=CARD_DARK, padx=10, pady=10)
        color_card.pack(fill="x", pady=(0, 10))
        tk.Label(
            color_card,
            text="Колір тривоги",
            bg=CARD_DARK,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        row_colors = tk.Frame(color_card, bg=CARD_DARK)
        row_colors.pack(fill="x")

        tk.Button(
            row_colors,
            text="Червоний",
            bg="#b33933",
            fg="white",
            relief="flat",
            padx=8,
            pady=5,
            command=lambda: self.set_color("#b33933"),
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))

        tk.Button(
            row_colors,
            text="Жовтий",
            bg="#c49c1a",
            fg="white",
            relief="flat",
            padx=8,
            pady=5,
            command=lambda: self.set_color("#c49c1a"),
        ).pack(side="left", expand=True, fill="x", padx=(4, 4))

        tk.Button(
            row_colors,
            text="Свій...",
            bg=PANEL_DARK,
            fg=TEXT_MAIN,
            relief="flat",
            padx=8,
            pady=5,
            command=self.pick_custom_color,
        ).pack(side="left", padx=(4, 0))

        self.color_preview = tk.Label(
            color_card,
            text="Активний колір: #b33933",
            bg=CARD_DARK,
            fg=TEXT_MAIN,
            font=("Segoe UI", 9),
        )
        self.color_preview.pack(anchor="w", pady=(6, 4))

        tk.Button(
            color_card,
            text="Перефарбувати активні тривоги",
            bg=PANEL_DARK,
            fg=TEXT_MAIN,
            relief="flat",
            pady=5,
            command=self.recolor_active,
        ).pack(fill="x")

        # Режими взаємодії
        mode_card = tk.Frame(sidebar, bg=CARD_DARK, padx=10, pady=10)
        mode_card.pack(fill="x", pady=(0, 10))
        tk.Label(
            mode_card,
            text="Режим взаємодії",
            bg=CARD_DARK,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        mode_btns = tk.Frame(mode_card, bg=CARD_DARK)
        mode_btns.pack(fill="x", pady=(0, 6))
        for label, m in [("Клік", "toggle"), ("Малювати +", "paint"), ("Гумка", "erase")]:
            tk.Button(
                mode_btns,
                text=label,
                bg=PANEL_DARK,
                fg=TEXT_MAIN,
                relief="flat",
                padx=6,
                pady=4,
                command=lambda mode=m: self.set_mode(mode),
            ).pack(side="left", expand=True, fill="x", padx=2)

        act_btns = tk.Frame(mode_card, bg=CARD_DARK)
        act_btns.pack(fill="x")
        tk.Button(
            act_btns,
            text="Випадково",
            bg=PANEL_DARK,
            fg=TEXT_MAIN,
            relief="flat",
            pady=4,
            command=self.random_alerts,
        ).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(
            act_btns,
            text="Відбій усіх",
            bg="#7f2924",
            fg="white",
            relief="flat",
            pady=4,
            command=self.clear_all,
        ).pack(side="left", expand=True, fill="x", padx=(4, 0))

        self.stats_lbl = tk.Label(
            sidebar,
            text="Активних тривог: 0 | Режим: Клік",
            bg=PANEL_DARK,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9),
        )
        self.stats_lbl.pack(anchor="w", pady=(0, 6))

        tk.Label(
            sidebar,
            text="Журнал подій",
            bg=PANEL_DARK,
            fg=TEXT_MUTED,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")

        self.log_box = tk.Listbox(
            sidebar,
            bg=CARD_DARK,
            fg=TEXT_MAIN,
            highlightthickness=0,
            bd=0,
            font=("Segoe UI", 9),
        )
        self.log_box.pack(fill="both", expand=True, pady=(4, 0))

        self.canvas.bind("<Configure>", lambda e: self._render_map())
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

    def _update_clock(self):
        now = datetime.datetime.now()
        self.clock_lbl.config(text=now.strftime("%d.%m.%Y %H:%M"))
        self.root.after(15000, self._update_clock)

    def _prepare_geometry(self):
        self.raw_regions = []
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for feat in self.geojson.get("features", []):
            name = get_region_name(feat)
            polys = extract_polygons(feat.get("geometry"))
            for poly in polys:
                for lon, lat in poly:
                    min_x = min(min_x, lon)
                    max_x = max(max_x, lon)
                    min_y = min(min_y, lat)
                    max_y = max(max_y, lat)
                self.raw_regions.append((name, poly))

        self.bounds = (min_x, min_y, max_x, max_y)

    def _lonlat_to_canvas(self, lon, lat, width, height, pad=36):
        min_x, min_y, max_x, max_y = self.bounds
        span_x = max(max_x - min_x, 1e-6)
        span_y = max(max_y - min_y, 1e-6)
        scale = min((width - 2 * pad) / span_x, (height - 2 * pad) / span_y)
        cx = (width - span_x * scale) / 2.0 + (lon - min_x) * scale
        cy = (height - span_y * scale) / 2.0 + (max_y - lat) * scale
        return cx, cy

    def _render_map(self):
        self.canvas.delete("all")
        self.region_polys.clear()

        width = max(self.canvas.winfo_width(), 600)
        height = max(self.canvas.winfo_height(), 450)
        label_candidates = {}

        for name, lonlat_poly in self.raw_regions:
            canvas_poly = [
                self._lonlat_to_canvas(lon, lat, width, height)
                for lon, lat in lonlat_poly
            ]
            flat_coords = [coord for pt in canvas_poly for coord in pt]
            fill_color = self.active_regions.get(name, IDLE_COLOR)

            poly_id = self.canvas.create_polygon(
                flat_coords,
                fill=fill_color,
                outline=BORDER_COLOR,
                width=1.2,
                tags=("region",),
            )
            self.region_polys.append({
                "name": name,
                "canvas_poly": canvas_poly,
                "canvas_id": poly_id,
            })

            area = abs(sum(
                canvas_poly[i][0] * canvas_poly[(i + 1) % len(canvas_poly)][1]
                - canvas_poly[(i + 1) % len(canvas_poly)][0] * canvas_poly[i][1]
                for i in range(len(canvas_poly))
            ))
            if name not in label_candidates or area > label_candidates[name][0]:
                label_candidates[name] = (area, polygon_centroid(canvas_poly))

        for name, (_, (lx, ly)) in label_candidates.items():
            self.canvas.create_text(
                lx,
                ly,
                text=name,
                fill="#ffffff",
                font=("Segoe UI", 8, "bold"),
                tags=("label",),
            )

    def _find_region_at(self, x, y):
        for item in reversed(self.region_polys):
            if point_in_polygon(x, y, item["canvas_poly"]):
                return item["name"]
        return None

    def _log(self, msg):
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.insert(0, f"[{t}] {msg}")

    def _update_stats(self):
        mode_names = {"toggle": "Клік", "paint": "Малювати +", "erase": "Гумка"}
        self.stats_lbl.config(
            text=f"Активних тривог: {len(self.active_regions)} | Режим: {mode_names[self.mode]}"
        )

    def set_region_alert(self, name, force_state=None):
        currently = name in self.active_regions
        next_state = force_state if force_state is not None else not currently

        if next_state:
            self.active_regions[name] = self.selected_color
            if not currently:
                self._log(f"Тривога: {name}")
        else:
            self.active_regions.pop(name, None)
            if currently:
                self._log(f"Відбій: {name}")

        for item in self.region_polys:
            if item["name"] == name:
                self.canvas.itemconfig(
                    item["canvas_id"],
                    fill=self.active_regions.get(name, IDLE_COLOR),
                )
        self._update_stats()

    def _on_mouse_down(self, event):
        self.is_dragging = True
        name = self._find_region_at(event.x, event.y)
        if not name:
            return
        if self.mode == "toggle":
            self.set_region_alert(name)
        elif self.mode == "paint":
            self.set_region_alert(name, True)
        elif self.mode == "erase":
            self.set_region_alert(name, False)

    def _on_mouse_move(self, event):
        if not self.is_dragging:
            return
        name = self._find_region_at(event.x, event.y)
        if not name:
            return
        if self.mode == "paint":
            self.set_region_alert(name, True)
        elif self.mode == "erase":
            self.set_region_alert(name, False)

    def _on_mouse_up(self, _event):
        self.is_dragging = False

    def set_color(self, color):
        self.selected_color = color
        self.color_preview.config(text=f"Активний колір: {color}")

    def pick_custom_color(self):
        _, hex_color = colorchooser.askcolor(
            color=self.selected_color,
            title="Вибір кольору тривоги",
        )
        if hex_color:
            self.set_color(hex_color)

    def recolor_active(self):
        if not self.active_regions:
            return
        for name in list(self.active_regions.keys()):
            self.active_regions[name] = self.selected_color
        for item in self.region_polys:
            if item["name"] in self.active_regions:
                self.canvas.itemconfig(item["canvas_id"], fill=self.selected_color)
        self._log(f"Перефарбовано регіонів: {len(self.active_regions)}")

    def set_mode(self, mode):
        self.mode = mode
        self._update_stats()

    def random_alerts(self):
        names = list({item["name"] for item in self.region_polys})
        if not names:
            return
        for name in random.sample(names, k=min(len(names), random.randint(2, 5))):
            self.set_region_alert(name, True)

    def clear_all(self):
        for name in list(self.active_regions.keys()):
            self.set_region_alert(name, False)


def main():
    geojson = load_geojson()
    if not geojson:
        messagebox.showerror(
            "Немає геоданих",
            "Не вдалося завантажити межі областей України.\n"
            "Покладіть файл ukraine_adm1.geojson поруч зі скриптом і запустіть знову.",
        )
        sys.exit(1)

    root = tk.Tk()
    AlarmMapApp(root, geojson)
    root.mainloop()


if __name__ == "__main__":
    main()