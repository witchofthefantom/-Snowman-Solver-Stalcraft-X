import tkinter as tk
from tkinter import font
from dataclasses import dataclass
from typing import List
from enum import Enum
import platform
import math

# Константы
ROWS = 5
COLS = 6
TOTAL_GOLD = 4
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600

# Enum для категорий плиток
class Category(Enum):
    GOLD = "gold"
    COMMON = "common"

class HintType(Enum):
    GOLD = "gold"
    COMMON = "common"

@dataclass
class TileData:
    """Данные одной плитки"""
    row: int
    col: int
    opened: bool = False
    value: str = "unknown"  # 'gold' или 'common'
    hint: str = "unknown"   # 'gold' или 'common'

class Tile:
    """Класс плитки для логики решателя"""
    def __init__(self, row: int, col: int):
        self.row = row
        self.col = col
        self.opened = False
        self.category = Category.COMMON
        self.neighbor_hint = HintType.COMMON
    
    def __repr__(self):
        return f"Tile({self.row},{self.col})"

class Grid:
    """Игровая сетка"""
    def __init__(self, rows: int, cols: int, golds: int):
        self.rows = rows
        self.cols = cols
        self.golds = golds
        self.tiles: List[Tile] = []
        self.golds_found = 0
        
        for r in range(rows):
            for c in range(cols):
                self.tiles.append(Tile(r, c))
    
    def init_from_tile_data(self, tile_data: List[List[TileData]]):
        """Инициализация из данных плиток"""
        self.golds_found = 0
        for r in range(self.rows):
            for c in range(self.cols):
                tile = self.get_tile(r, c)
                data = tile_data[r][c]
                tile.opened = data.opened
                
                if data.value == 'gold':
                    tile.category = Category.GOLD
                    if tile.opened:
                        self.golds_found += 1
                else:
                    tile.category = Category.COMMON
                
                tile.neighbor_hint = HintType.GOLD if data.hint == 'gold' else HintType.COMMON
    
    def get_tile(self, r: int, c: int) -> Tile:
        """Получить плитку по координатам"""
        return self.tiles[r * self.cols + c]
    
    def get_neighbors(self, tile: Tile) -> List[Tile]:
        """Получить соседей плитки (верх, низ, лево, право)"""
        neighbors = []
        r, c = tile.row, tile.col
        
        if r > 0:
            neighbors.append(self.get_tile(r-1, c))
        if r < self.rows - 1:
            neighbors.append(self.get_tile(r+1, c))
        if c > 0:
            neighbors.append(self.get_tile(r, c-1))
        if c < self.cols - 1:
            neighbors.append(self.get_tile(r, c+1))
        
        return neighbors

class BruteforceProbabilitySolver:
    """Решатель через перебор вероятностей"""
    
    def __init__(self, grid: Grid):
        self.grid = grid
        
        self.num_tiles = len(grid.tiles)
        self.possible_configurations = self._get_possible_configurations(TOTAL_GOLD, self.num_tiles)
        self.possible_configurations_remaining = len(self.possible_configurations)
        
        self.neighbors_index = []
        for i, tile in enumerate(grid.tiles):
            neighbors = grid.get_neighbors(tile)
            self.neighbors_index.append([self._get_tile_index(nt) for nt in neighbors])
        
        self.configurations_per_gold_tile = [0] * self.num_tiles
        self.configurations_per_gold_hint_tile = [0] * self.num_tiles
        self.remaining_configs_after_open_estimate = [0] * self.num_tiles
    
    def _get_tile_index(self, tile: Tile) -> int:
        """Получить индекс плитки"""
        return tile.col + tile.row * self.grid.cols
    
    def _get_possible_configurations(self, golds: int, num_tiles: int) -> List[int]:
        configurations = []
        for p1 in range(num_tiles):
            for p2 in range(p1 + 1, num_tiles):
                for p3 in range(p2 + 1, num_tiles):
                    for p4 in range(p3 + 1, num_tiles):
                        config = p1 | (p2 << 8) | (p3 << 16) | (p4 << 24)
                        configurations.append(config)
        return configurations
    
    def _is_gold_in_configuration(self, configuration: int, tile_index: int) -> bool:
        return ((configuration & 0xFF) == tile_index or
                ((configuration >> 8) & 0xFF) == tile_index or
                ((configuration >> 16) & 0xFF) == tile_index or
                ((configuration >> 24) & 0xFF) == tile_index)
    
    def _remove_configuration(self, index: int):
        self.possible_configurations[index] = self.possible_configurations[self.possible_configurations_remaining - 1]
        self.possible_configurations_remaining -= 1
    
    def update_possible_configurations(self):
        self.possible_configurations = self._get_possible_configurations(TOTAL_GOLD, self.num_tiles)
        self.possible_configurations_remaining = len(self.possible_configurations)
        
        for tile in self.grid.tiles:
            if tile.opened:
                self._narrow_down_configurations(tile)
    
    def _narrow_down_configurations(self, open_tile: Tile):
        is_gold = open_tile.category == Category.GOLD
        is_gold_hint = open_tile.neighbor_hint == HintType.GOLD
        tile_index = self._get_tile_index(open_tile)
        
        i = 0
        while i < self.possible_configurations_remaining:
            config = self.possible_configurations[i]
            
            if is_gold != self._is_gold_in_configuration(config, tile_index):
                self._remove_configuration(i)
                continue
            
            if is_gold_hint:
                if not self._has_gold_neighbors(tile_index, config):
                    self._remove_configuration(i)
                    continue
            else:
                remove = False
                for neighbor_idx in self.neighbors_index[tile_index]:
                    if self._is_gold_in_configuration(config, neighbor_idx):
                        remove = True
                        break
                if remove:
                    self._remove_configuration(i)
                    continue
            
            i += 1
    
    def _has_gold_neighbors(self, tile_index: int, configuration: int) -> bool:
        for neighbor_idx in self.neighbors_index[tile_index]:
            if self._is_gold_in_configuration(configuration, neighbor_idx):
                return True
        return False
    
    def update_probabilities(self):
        self.configurations_per_gold_tile = [0] * self.num_tiles
        self.configurations_per_gold_hint_tile = [0] * self.num_tiles
        
        for i in range(self.possible_configurations_remaining):
            config = self.possible_configurations[i]
            
            gold_indices = [
                config & 0xFF,
                (config >> 8) & 0xFF,
                (config >> 16) & 0xFF,
                (config >> 24) & 0xFF
            ]
            
            for gi in gold_indices:
                self.configurations_per_gold_tile[gi] += 1
            
            gold_hint_bits = 0
            for gi in gold_indices:
                for neighbor_idx in self.neighbors_index[gi]:
                    gold_hint_bits |= (1 << neighbor_idx)
            
            for tile_idx in range(self.num_tiles):
                if (gold_hint_bits >> tile_idx) & 1:
                    self.configurations_per_gold_hint_tile[tile_idx] += 1
    
    def update_remaining_configs_estimate(self):
        for tile in self.grid.tiles:
            tile_idx = self._get_tile_index(tile)
            self.remaining_configs_after_open_estimate[tile_idx] = self._calc_remaining_configs_estimate(tile)
    
    def _calc_remaining_configs_estimate(self, tile: Tile) -> float:
        tile_idx = self._get_tile_index(tile)
        
        if self.possible_configurations_remaining == 0:
            return 0
        
        gold_prob = self.configurations_per_gold_tile[tile_idx] / self.possible_configurations_remaining
        gold_hint_prob = self.configurations_per_gold_hint_tile[tile_idx] / self.possible_configurations_remaining
        
        weighted_avg = 0.0
        
        for is_gold, is_gold_hint in [(False, False), (False, True), (True, False), (True, True)]:
            prob_scenario = (1.0 - gold_prob if not is_gold else gold_prob) * \
                           (1.0 - gold_hint_prob if not is_gold_hint else gold_hint_prob)
            remaining = self._get_configs_after_open(tile, is_gold, is_gold_hint)
            weighted_avg += remaining * prob_scenario
        
        return weighted_avg
    
    def _get_configs_after_open(self, tile: Tile, is_gold: bool, is_gold_hint: bool) -> int:
        tile_idx = self._get_tile_index(tile)
        remaining = 0
        
        for i in range(self.possible_configurations_remaining):
            config = self.possible_configurations[i]
            
            if is_gold != self._is_gold_in_configuration(config, tile_idx):
                continue
            
            if is_gold_hint:
                if not self._has_gold_neighbors(tile_idx, config):
                    continue
            else:
                skip = False
                for neighbor_idx in self.neighbors_index[tile_idx]:
                    if self._is_gold_in_configuration(config, neighbor_idx):
                        skip = True
                        break
                if skip:
                    continue
            
            remaining += 1
        
        return remaining
    
    def get_tile_priority(self, tile: Tile) -> float:
        tile_idx = self._get_tile_index(tile)
        
        if self.possible_configurations_remaining == 0:
            return 0
        
        gold_prob = self.configurations_per_gold_tile[tile_idx] / self.possible_configurations_remaining
        excluded_share = 1.0 - (self.remaining_configs_after_open_estimate[tile_idx] / 
                               self.possible_configurations_remaining)
        
        return 1.0 - ((1.0 - gold_prob) * (1.0 - excluded_share) ** 2)
    
    def get_next_tile_to_open(self) -> Tile:
        unopened_tiles = [t for t in self.grid.tiles if not t.opened]
        
        if not unopened_tiles:
            return None
        
        unopened_tiles.sort(key=lambda t: self.get_tile_priority(t), reverse=True)
        return unopened_tiles[0]

class SnowmanSolverApp:
    
    def __init__(self, root):
        self.root = root
        self.root.title("Snowman Solver - Решатель головоломки")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg='#0f0f0f')
        self.root.resizable(False, False)
        
        self.emoji_font = self.get_emoji_font()
        
        self.tile_data = self._initialize_tile_data()
        self.current_edit = None
        self.suggested_tile = None
        
        self.colors = {
            'bg': '#0f0f0f',
            'card_bg': '#1e1e1e',
            'text': '#ffffff',
            'text_secondary': '#b0b0b0',
            'accent': '#4a90e2',
            'selection': '#ff6b6b',
            'gold': '#ffd700',
            'success': '#2ecc71',
            'warning': '#e74c3c',
            'tile_closed': '#2d2d2d',
            'tile_opened': '#3a3a3a',
            'border': '#404040',
            'hover': '#4a4a4a',
            'suggestion': '#ff4444'
        }
        
        self.create_widgets()

        self.update_suggestion()

        self.setup_keyboard_shortcuts()
    
    def get_emoji_font(self):
        system = platform.system()
        available_fonts = font.families()
        
        emoji_font_candidates = [
            "Segoe UI Emoji",
            "Segoe UI Symbol",
            "Apple Color Emoji",
            "Noto Color Emoji",
            "Symbola",
            "DejaVu Sans",
            "Arial Unicode MS",
            "Arial"
        ]
        
        for font_name in emoji_font_candidates:
            if font_name in available_fonts:
                return font_name
        
        return "Arial"
    
    def _initialize_tile_data(self) -> List[List[TileData]]:
        data = []
        for r in range(ROWS):
            row = []
            for c in range(COLS):
                row.append(TileData(r, c))
            data.append(row)
        return data
    
    def create_widgets(self):
        self.main_container = tk.Frame(self.root, bg=self.colors['bg'])
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        title_frame = tk.Frame(self.main_container, bg=self.colors['bg'])
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = tk.Label(
            title_frame,
            text="🔍 Snowman Solver - Решатель головоломки",
            font=(self.emoji_font, 22, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['accent']
        )
        title_label.pack()
        

        content_frame = tk.Frame(self.main_container, bg=self.colors['bg'])
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        left_panel = tk.Frame(content_frame, bg=self.colors['bg'])
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        
        board_container = tk.Frame(left_panel, bg=self.colors['bg'])
        board_container.pack(expand=True)
        
        board_frame = tk.Frame(board_container, bg=self.colors['bg'])
        board_frame.pack()
        
        self.tile_buttons = []
        for r in range(ROWS):
            for c in range(COLS):
                btn = tk.Button(
                    board_frame,
                    text="?",
                    font=(self.emoji_font, 16, "bold"),
                    width=3,
                    height=1,
                    bg=self.colors['tile_closed'],
                    fg=self.colors['text'],
                    relief=tk.FLAT,
                    bd=0,
                    cursor="hand2",
                    command=lambda row=r, col=c: self.select_tile(row, col),
                    activebackground=self.colors['hover']
                )
                btn.grid(row=r, column=c, padx=4, pady=4)
                
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.colors['hover']))
                btn.bind("<Leave>", lambda e, b=btn, row=r, col=c: self.update_button_style(b, row, col))
                
                self.tile_buttons.append(btn)

        right_panel = tk.Frame(
            content_frame, 
            bg=self.colors['card_bg'],
            relief=tk.FLAT,
            bd=1,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0))
        
        panel_content = tk.Frame(right_panel, bg=self.colors['card_bg'], padx=15, pady=15)
        panel_content.pack(fill=tk.BOTH, expand=True)
        
        panel_title = tk.Label(
            panel_content,
            text="📝 Информация о плитке",
            font=(self.emoji_font, 14, "bold"),
            bg=self.colors['card_bg'],
            fg=self.colors['text']
        )
        panel_title.pack(pady=(0, 15))
        
        self.panel_coords = tk.Label(
            panel_content,
            text="Плитка не выбрана",
            font=("Arial", 10),
            bg=self.colors['card_bg'],
            fg=self.colors['text_secondary']
        )
        self.panel_coords.pack(pady=(0, 20))
        
        type_label = tk.Label(
            panel_content,
            text="Тип плитки:",
            font=("Arial", 10, "bold"),
            bg=self.colors['card_bg'],
            fg=self.colors['text']
        )
        type_label.pack(anchor=tk.W, pady=(0, 5))
        
        type_frame = tk.Frame(panel_content, bg=self.colors['card_bg'])
        type_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.tile_type_var = tk.StringVar(value="common")
        
        tk.Radiobutton(
            type_frame,
            text=" 🥇 Золотая",
            variable=self.tile_type_var,
            value="gold",
            bg=self.colors['card_bg'],
            fg=self.colors['text'],
            selectcolor=self.colors['selection'],  # КРАСНЫЙ выбор
            activebackground=self.colors['card_bg'],
            activeforeground=self.colors['text'],
            font=(self.emoji_font, 10),
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Radiobutton(
            type_frame,
            text=" □ Обычная",
            variable=self.tile_type_var,
            value="common",
            bg=self.colors['card_bg'],
            fg=self.colors['text'],
            selectcolor=self.colors['selection'],  # КРАСНЫЙ выбор
            activebackground=self.colors['card_bg'],
            activeforeground=self.colors['text'],
            font=("Arial", 10),
            cursor="hand2"
        ).pack(side=tk.LEFT)
        
        hint_label = tk.Label(
            panel_content,
            text="Подсказка о соседях:",
            font=("Arial", 10, "bold"),
            bg=self.colors['card_bg'],
            fg=self.colors['text']
        )
        hint_label.pack(anchor=tk.W, pady=(0, 5))
        
        hint_frame = tk.Frame(panel_content, bg=self.colors['card_bg'])
        hint_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.hint_type_var = tk.StringVar(value="common")
        
        tk.Radiobutton(
            hint_frame,
            text=" Есть золотой сосед",
            variable=self.hint_type_var,
            value="gold",
            bg=self.colors['card_bg'],
            fg=self.colors['text'],
            selectcolor=self.colors['selection'],
            activebackground=self.colors['card_bg'],
            activeforeground=self.colors['text'],
            font=("Arial", 10),
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Radiobutton(
            hint_frame,
            text=" Нет золотых соседей",
            variable=self.hint_type_var,
            value="common",
            bg=self.colors['card_bg'],
            fg=self.colors['text'],
            selectcolor=self.colors['selection'],
            activebackground=self.colors['card_bg'],
            activeforeground=self.colors['text'],
            font=("Arial", 10),
            cursor="hand2"
        ).pack(side=tk.LEFT)
        
        button_frame = tk.Frame(panel_content, bg=self.colors['card_bg'])
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.save_btn = tk.Button(
            button_frame,
            text="💾 Сохранить",
            command=self.save_tile_info,
            bg=self.colors['success'],
            fg='white',
            font=(self.emoji_font, 10, "bold"),
            padx=15,
            pady=8,
            cursor="hand2",
            state=tk.DISABLED,
            relief=tk.FLAT,
            bd=0
        )
        self.save_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        self.clear_btn = tk.Button(
            button_frame,
            text="🗑️ Очистить",
            command=self.clear_current_tile,
            bg=self.colors['warning'],
            fg='white',
            font=(self.emoji_font, 10, "bold"),
            padx=15,
            pady=8,
            cursor="hand2",
            state=tk.DISABLED,
            relief=tk.FLAT,
            bd=0
        )
        self.clear_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        suggestion_frame = tk.Frame(
            self.main_container,
            bg=self.colors['card_bg'],
            relief=tk.FLAT,
            bd=1,
            highlightbackground=self.colors['border'],
            highlightthickness=1
        )
        suggestion_frame.pack(fill=tk.X, pady=(15, 0))
        
        suggestion_content = tk.Frame(suggestion_frame, bg=self.colors['card_bg'], padx=15, pady=10)
        suggestion_content.pack(fill=tk.X)
        
        suggestion_label = tk.Label(
            suggestion_content,
            text="🎯 Следующая подсказка:",
            font=(self.emoji_font, 11, "bold"),
            bg=self.colors['card_bg'],
            fg=self.colors['accent']
        )
        suggestion_label.pack(side=tk.LEFT)
        
        self.suggestion_text = tk.Label(
            suggestion_content,
            text="Выберите плитки для получения подсказок",
            font=("Arial", 10),
            bg=self.colors['card_bg'],
            fg=self.colors['text_secondary']
        )
        self.suggestion_text.pack(side=tk.LEFT, padx=(10, 0))
        
        reset_btn = tk.Button(
            self.main_container,
            text="🔄 Начать заново",
            command=self.reset_game,
            bg=self.colors['accent'],
            fg='white',
            font=(self.emoji_font, 10, "bold"),
            padx=25,
            pady=10,
            cursor="hand2",
            relief=tk.FLAT,
            bd=0
        )
        reset_btn.pack(pady=(15, 0))
    
    def update_button_style(self, button, row, col):
        data = self.tile_data[row][col]
        index = row * COLS + col
        
        if self.suggested_tile and row == self.suggested_tile.row and col == self.suggested_tile.col:
            button.config(bg=self.colors['suggestion'])  # Красный для подсказки
        elif self.current_edit and row == self.current_edit[0] and col == self.current_edit[1]:
            button.config(bg=self.colors['selection'])  # КРАСНЫЙ для выбранной плитки
        elif data.opened:
            if data.value == 'gold':
                button.config(bg=self.colors['gold'])
            else:
                button.config(bg=self.colors['tile_opened'])
        else:
            button.config(bg=self.colors['tile_closed'])
    
    def select_tile(self, row: int, col: int):
        self.current_edit = (row, col)
        self.panel_coords.config(text=f"Строка: {row+1}, Колонка: {col+1}")
        
        data = self.tile_data[row][col]
        if data.opened:
            self.tile_type_var.set(data.value if data.value != 'unknown' else 'common')
            self.hint_type_var.set(data.hint if data.hint != 'unknown' else 'common')
        else:
            self.tile_type_var.set("common")
            self.hint_type_var.set("common")
        
        self.save_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.NORMAL)
        
        self.update_tile_selection(row, col)
    
    def update_tile_selection(self, row: int, col: int):
        for i, btn in enumerate(self.tile_buttons):
            r = i // COLS
            c = i % COLS
            data = self.tile_data[r][c]
            
            if self.suggested_tile and r == self.suggested_tile.row and c == self.suggested_tile.col:
                btn.config(bg=self.colors['suggestion'])
            elif r == row and c == col:
                btn.config(bg=self.colors['selection'])
            elif data.opened:
                if data.value == 'gold':
                    btn.config(bg=self.colors['gold'])
                else:
                    btn.config(bg=self.colors['tile_opened'])
            else:
                btn.config(bg=self.colors['tile_closed'])
    
    def save_tile_info(self):
        if not self.current_edit:
            return
        
        row, col = self.current_edit
        self.tile_data[row][col].opened = True
        self.tile_data[row][col].value = self.tile_type_var.get()
        self.tile_data[row][col].hint = self.hint_type_var.get()
        
        self.update_tile_ui(row, col)
        self.update_suggestion()
    
    def clear_current_tile(self):
        if not self.current_edit:
            return
        
        row, col = self.current_edit
        self.tile_data[row][col] = TileData(row, col)
        
        self.update_tile_ui(row, col)
        self.update_suggestion()
        
        self.tile_type_var.set("common")
        self.hint_type_var.set("common")
    
    def update_tile_ui(self, row: int, col: int):
        index = row * COLS + col
        btn = self.tile_buttons[index]
        data = self.tile_data[row][col]
        
        if data.opened:
            if data.value == 'gold':
                btn.config(text="🥇", bg=self.colors['gold'], fg='#333333')
            else:
                btn.config(text="□", bg=self.colors['tile_opened'], fg=self.colors['text'])
            
            if data.hint == 'gold':
                btn.config(text=f"{btn.cget('text')}✨")
        else:
            btn.config(text="?", bg=self.colors['tile_closed'], fg=self.colors['text'])
        
        if self.current_edit and row == self.current_edit[0] and col == self.current_edit[1]:
            btn.config(bg=self.colors['selection'])
        elif self.suggested_tile and row == self.suggested_tile.row and col == self.suggested_tile.col:
            btn.config(bg=self.colors['suggestion'])
    
    def update_suggestion(self):
        grid = Grid(ROWS, COLS, TOTAL_GOLD)
        grid.init_from_tile_data(self.tile_data)
        
        if grid.golds_found >= TOTAL_GOLD:
            self.suggestion_text.config(text="🎉 Все золотые плитки найдены!")
            self.suggested_tile = None
            self.update_tile_selection(-1, -1)
            return
        
        solver = BruteforceProbabilitySolver(grid)
        solver.update_possible_configurations()
        
        if solver.possible_configurations_remaining == 0:
            self.suggestion_text.config(text="⚠️ Невозможная конфигурация!")
            self.suggested_tile = None
            self.update_tile_selection(-1, -1)
            return
        
        solver.update_probabilities()
        solver.update_remaining_configs_estimate()
        
        next_tile = solver.get_next_tile_to_open()
        self.show_suggestion(next_tile)
    
    def show_suggestion(self, next_tile):
        self.suggested_tile = next_tile
        
        if not next_tile:
            self.suggestion_text.config(text="Подсказки недоступны")
            self.update_tile_selection(-1, -1)
            return
        
        self.suggestion_text.config(
            text=f"Откройте плитку в Строке {next_tile.row+1}, Колонке {next_tile.col+1}"
        )
        
        self.update_tile_selection(-1, -1)
    
    def reset_game(self):
        self.tile_data = self._initialize_tile_data()
        for r in range(ROWS):
            for c in range(COLS):
                self.update_tile_ui(r, c)
        
        self.current_edit = None
        self.suggested_tile = None
        self.panel_coords.config(text="Плитка не выбрана")
        self.tile_type_var.set("common")
        self.hint_type_var.set("common")
        self.save_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.DISABLED)
        self.suggestion_text.config(text="Выберите плитки для получения подсказок")
        self.update_suggestion()
    
    def setup_keyboard_shortcuts(self):
        self.root.bind('<Escape>', lambda e: self.reset_game())
        self.root.bind('<Control-r>', lambda e: self.reset_game())

def main():
    root = tk.Tk()
    app = SnowmanSolverApp(root)
    
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (WINDOW_WIDTH // 2)
    y = (root.winfo_screenheight() // 2) - (WINDOW_HEIGHT // 2)
    root.geometry(f'+{x}+{y}')
    
    root.mainloop()

if __name__ == "__main__":
    main()