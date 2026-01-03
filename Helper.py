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
WINDOW_WIDTH = 850
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
        
        # Инициализация плиток
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
        
        # Подготовка данных для быстрого доступа
        self.num_tiles = len(grid.tiles)
        self.possible_configurations = self._get_possible_configurations(TOTAL_GOLD, self.num_tiles)
        self.possible_configurations_remaining = len(self.possible_configurations)
        
        # Индексы соседей для каждой плитки
        self.neighbors_index = []
        for i, tile in enumerate(grid.tiles):
            neighbors = grid.get_neighbors(tile)
            self.neighbors_index.append([self._get_tile_index(nt) for nt in neighbors])
        
        # Статистика
        self.configurations_per_gold_tile = [0] * self.num_tiles
        self.configurations_per_gold_hint_tile = [0] * self.num_tiles
        self.remaining_configs_after_open_estimate = [0] * self.num_tiles
    
    def _get_tile_index(self, tile: Tile) -> int:
        """Получить индекс плитки"""
        return tile.col + tile.row * self.grid.cols
    
    def _get_possible_configurations(self, golds: int, num_tiles: int) -> List[int]:
        """Генерация всех возможных комбинаций золотых плиток"""
        configurations = []
        # Генерируем все комбинации из 4 золотых плиток на 30 позициях
        for p1 in range(num_tiles):
            for p2 in range(p1 + 1, num_tiles):
                for p3 in range(p2 + 1, num_tiles):
                    for p4 in range(p3 + 1, num_tiles):
                        config = p1 | (p2 << 8) | (p3 << 16) | (p4 << 24)
                        configurations.append(config)
        return configurations
    
    def _is_gold_in_configuration(self, configuration: int, tile_index: int) -> bool:
        """Проверить, есть ли плитка в конфигурации"""
        return ((configuration & 0xFF) == tile_index or
                ((configuration >> 8) & 0xFF) == tile_index or
                ((configuration >> 16) & 0xFF) == tile_index or
                ((configuration >> 24) & 0xFF) == tile_index)
    
    def _remove_configuration(self, index: int):
        """Удалить конфигурацию по индексу"""
        self.possible_configurations[index] = self.possible_configurations[self.possible_configurations_remaining - 1]
        self.possible_configurations_remaining -= 1
    
    def update_possible_configurations(self):
        """Обновить возможные конфигурации на основе открытых плиток"""
        # Начинаем со всех возможных конфигураций
        self.possible_configurations = self._get_possible_configurations(TOTAL_GOLD, self.num_tiles)
        self.possible_configurations_remaining = len(self.possible_configurations)
        
        # Фильтруем по открытым плиткам
        for tile in self.grid.tiles:
            if tile.opened:
                self._narrow_down_configurations(tile)
    
    def _narrow_down_configurations(self, open_tile: Tile):
        """Сужение конфигураций на основе информации о плитке"""
        is_gold = open_tile.category == Category.GOLD
        is_gold_hint = open_tile.neighbor_hint == HintType.GOLD
        tile_index = self._get_tile_index(open_tile)
        
        i = 0
        while i < self.possible_configurations_remaining:
            config = self.possible_configurations[i]
            
            # Проверяем соответствие типа плитки
            if is_gold != self._is_gold_in_configuration(config, tile_index):
                self._remove_configuration(i)
                continue
            
            # Проверяем соответствие подсказки о соседях
            if is_gold_hint:
                if not self._has_gold_neighbors(tile_index, config):
                    self._remove_configuration(i)
                    continue
            else:
                # Если нет золотых соседей, проверяем всех соседей
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
        """Проверить, есть ли у плитки золотые соседи"""
        for neighbor_idx in self.neighbors_index[tile_index]:
            if self._is_gold_in_configuration(configuration, neighbor_idx):
                return True
        return False
    
    def update_probabilities(self):
        """Обновить вероятности для всех плиток"""
        # Сброс статистики
        self.configurations_per_gold_tile = [0] * self.num_tiles
        self.configurations_per_gold_hint_tile = [0] * self.num_tiles
        
        # Подсчет статистики по всем конфигурациям
        for i in range(self.possible_configurations_remaining):
            config = self.possible_configurations[i]
            
            # Извлекаем индексы золотых плиток
            gold_indices = [
                config & 0xFF,
                (config >> 8) & 0xFF,
                (config >> 16) & 0xFF,
                (config >> 24) & 0xFF
            ]
            
            # Подсчитываем золотые плитки
            for gi in gold_indices:
                self.configurations_per_gold_tile[gi] += 1
            
            # Подсчитываем плитки с золотыми соседями
            gold_hint_bits = 0
            for gi in gold_indices:
                for neighbor_idx in self.neighbors_index[gi]:
                    gold_hint_bits |= (1 << neighbor_idx)
            
            # Для каждой плитки проверяем, есть ли она в gold_hint_bits
            for tile_idx in range(self.num_tiles):
                if (gold_hint_bits >> tile_idx) & 1:
                    self.configurations_per_gold_hint_tile[tile_idx] += 1
    
    def update_remaining_configs_estimate(self):
        """Оценить оставшиеся конфигурации после открытия каждой плитки"""
        for tile in self.grid.tiles:
            tile_idx = self._get_tile_index(tile)
            self.remaining_configs_after_open_estimate[tile_idx] = self._calc_remaining_configs_estimate(tile)
    
    def _calc_remaining_configs_estimate(self, tile: Tile) -> float:
        """Вычислить оценку оставшихся конфигураций"""
        tile_idx = self._get_tile_index(tile)
        
        if self.possible_configurations_remaining == 0:
            return 0
        
        gold_prob = self.configurations_per_gold_tile[tile_idx] / self.possible_configurations_remaining
        gold_hint_prob = self.configurations_per_gold_hint_tile[tile_idx] / self.possible_configurations_remaining
        
        weighted_avg = 0.0
        
        # Все 4 комбинации: (gold?, gold_hint?)
        for is_gold, is_gold_hint in [(False, False), (False, True), (True, False), (True, True)]:
            prob_scenario = (1.0 - gold_prob if not is_gold else gold_prob) * \
                           (1.0 - gold_hint_prob if not is_gold_hint else gold_hint_prob)
            remaining = self._get_configs_after_open(tile, is_gold, is_gold_hint)
            weighted_avg += remaining * prob_scenario
        
        return weighted_avg
    
    def _get_configs_after_open(self, tile: Tile, is_gold: bool, is_gold_hint: bool) -> int:
        """Подсчитать конфигурации после открытия плитки с заданными параметрами"""
        tile_idx = self._get_tile_index(tile)
        remaining = 0
        
        for i in range(self.possible_configurations_remaining):
            config = self.possible_configurations[i]
            
            # Проверяем соответствие типа плитки
            if is_gold != self._is_gold_in_configuration(config, tile_idx):
                continue
            
            # Проверяем соответствие подсказки о соседях
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
        """Получить приоритет плитки для открытия"""
        tile_idx = self._get_tile_index(tile)
        
        if self.possible_configurations_remaining == 0:
            return 0
        
        gold_prob = self.configurations_per_gold_tile[tile_idx] / self.possible_configurations_remaining
        excluded_share = 1.0 - (self.remaining_configs_after_open_estimate[tile_idx] / 
                               self.possible_configurations_remaining)
        
        # Формула приоритета (чем больше, тем лучше открывать)
        return 1.0 - ((1.0 - gold_prob) * (1.0 - excluded_share) ** 2)
    
    def get_next_tile_to_open(self) -> Tile:
        """Получить следующую плитку для открытия"""
        unopened_tiles = [t for t in self.grid.tiles if not t.opened]
        
        if not unopened_tiles:
            return None
        
        # Сортируем по приоритету
        unopened_tiles.sort(key=lambda t: self.get_tile_priority(t), reverse=True)
        return unopened_tiles[0]

class SnowmanSolverApp:
    """Главное приложение"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Snowman Solver - Решатель головоломки")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg='#1a1a1a')
        self.root.resizable(False, False)
        
        # Определяем лучшие шрифты для эмодзи
        self.emoji_font = self.get_emoji_font()
        self.ui_font = "Arial"  # Основной шрифт для текста
        
        # Инициализация данных
        self.tile_data = self._initialize_tile_data()
        self.current_edit = None
        
        # Создание интерфейса
        self.create_widgets()
        
        # Обновление подсказки
        self.update_suggestion()
        
        # Привязка горячих клавиш
        self.setup_keyboard_shortcuts()
    
    def get_emoji_font(self):
        """Получить лучший шрифт для эмодзи"""
        system = platform.system()
        available_fonts = font.families()
        
        # Приоритетный список шрифтов с поддержкой эмодзи
        emoji_font_candidates = [
            "Segoe UI Emoji",      # Windows 10/11
            "Segoe UI Symbol",     # Windows 8/10
            "Apple Color Emoji",   # macOS
            "Noto Color Emoji",    # Linux (часто устанавливается)
            "Symbola",            # Кроссплатформенный
            "DejaVu Sans",        # Хорошая поддержка Unicode
            "Arial Unicode MS",   # Windows
            "Arial"               # Запасной вариант
        ]
        
        for font_name in emoji_font_candidates:
            if font_name in available_fonts:
                print(f"Используем шрифт для эмодзи: {font_name}")
                return font_name
        
        print("Используем Arial (специальный шрифт для эмодзи не найден)")
        return "Arial"
    
    def _initialize_tile_data(self) -> List[List[TileData]]:
        """Инициализация данных плиток"""
        data = []
        for r in range(ROWS):
            row = []
            for c in range(COLS):
                row.append(TileData(r, c))
            data.append(row)
        return data
    
    def create_widgets(self):
        """Создание виджетов интерфейса"""
        # Главный контейнер
        self.main_container = tk.Frame(self.root, bg='#1a1a1a')
        self.main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Заголовок
        title_frame = tk.Frame(self.main_container, bg='#1a1a1a')
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = tk.Label(
            title_frame,
            text="❄️ Snowman Solver - Решатель головоломки",
            font=(self.emoji_font, 20, "bold"),
            bg='#1a1a1a',
            fg='#e0e0e0'
        )
        title_label.pack()
        
        # Контейнер для поля и панели
        self.container = tk.Frame(self.main_container, bg='#1a1a1a')
        self.container.pack(fill=tk.BOTH, expand=True)
        
        # Игровое поле (слева)
        board_frame = tk.Frame(self.container, bg='#1a1a1a')
        board_frame.pack(side=tk.LEFT, padx=(0, 20))
        
        # Создание плиток
        self.tile_buttons = []
        for r in range(ROWS):
            for c in range(COLS):
                btn = tk.Label(
                    board_frame,
                    text="?",
                    font=(self.emoji_font, 14, "bold"),
                    width=3,
                    height=1,
                    bg='#555555',
                    fg='#e0e0e0',
                    relief=tk.RAISED,
                    borderwidth=2,
                    cursor="hand2"
                )
                btn.grid(row=r, column=c, padx=2, pady=2)
                btn.bind('<Button-1>', lambda e, row=r, col=c: self.select_tile(row, col))
                self.tile_buttons.append(btn)
        
        # Панель информации (справа) - компактная
        self.panel_frame = tk.Frame(
            self.container, 
            bg='#2d2d2d', 
            relief=tk.RIDGE, 
            borderwidth=1,
            width=220,  # Уменьшенная ширина
            height=320  # Уменьшенная высота
        )
        self.panel_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.panel_frame.pack_propagate(False)
        
        # Содержимое панели
        panel_content = tk.Frame(self.panel_frame, bg='#2d2d2d', padx=12, pady=12)
        panel_content.pack(fill=tk.BOTH, expand=True)
        
        # Заголовок панели
        panel_title = tk.Label(
            panel_content,
            text="📝 Информация о плитке",
            font=(self.emoji_font, 12, "bold"),
            bg='#2d2d2d',
            fg='#e0e0e0'
        )
        panel_title.pack(pady=(0, 10))
        
        # Координаты плитки
        self.panel_coords = tk.Label(
            panel_content,
            text="Не выбрана",
            font=(self.ui_font, 10),
            bg='#2d2d2d',
            fg='#e0e0e0'
        )
        self.panel_coords.pack(pady=(0, 12))
        
        # Тип плитки
        type_frame = tk.LabelFrame(
            panel_content,
            text="Тип плитки:",
            bg='#2d2d2d',
            fg='#e0e0e0',
            font=(self.ui_font, 9, "bold")
        )
        type_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.tile_type_var = tk.StringVar(value="common")
        
        tk.Radiobutton(
            type_frame,
            text="🥇 Золотая",
            variable=self.tile_type_var,
            value="gold",
            bg='#2d2d2d',
            fg='#e0e0e0',
            selectcolor='#3d3d3d',
            activebackground='#2d2d2d',
            activeforeground='#e0e0e0',
            font=(self.emoji_font, 9),
            cursor="hand2"
        ).pack(anchor=tk.W, pady=2, padx=8)
        
        tk.Radiobutton(
            type_frame,
            text="🟫 Обычная",
            variable=self.tile_type_var,
            value="common",
            bg='#2d2d2d',
            fg='#e0e0e0',
            selectcolor='#3d3d3d',
            activebackground='#2d2d2d',
            activeforeground='#e0e0e0',
            font=(self.emoji_font, 9),
            cursor="hand2"
        ).pack(anchor=tk.W, pady=2, padx=8)
        
        # Подсказка о соседях
        hint_frame = tk.LabelFrame(
            panel_content,
            text="Подсказка о соседях:",
            bg='#2d2d2d',
            fg='#e0e0e0',
            font=(self.ui_font, 9, "bold")
        )
        hint_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.hint_type_var = tk.StringVar(value="common")
        
        tk.Radiobutton(
            hint_frame,
            text="⭐ Есть золотой сосед",
            variable=self.hint_type_var,
            value="gold",
            bg='#2d2d2d',
            fg='#e0e0e0',
            selectcolor='#3d3d3d',
            activebackground='#2d2d2d',
            activeforeground='#e0e0e0',
            font=(self.emoji_font, 9),
            cursor="hand2"
        ).pack(anchor=tk.W, pady=2, padx=8)
        
        tk.Radiobutton(
            hint_frame,
            text="🚫 Нет золотых соседей",
            variable=self.hint_type_var,
            value="common",
            bg='#2d2d2d',
            fg='#e0e0e0',
            selectcolor='#3d3d3d',
            activebackground='#2d2d2d',
            activeforeground='#e0e0e0',
            font=(self.emoji_font, 9),
            cursor="hand2"
        ).pack(anchor=tk.W, pady=2, padx=8)
        
        # Кнопки панели (компактные)
        button_frame = tk.Frame(panel_content, bg='#2d2d2d')
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        # Кнопка Сохранить
        self.save_btn = tk.Button(
            button_frame,
            text="💾 Сохранить",
            command=self.save_tile_info,
            bg='#45a049',
            fg='white',
            font=(self.emoji_font, 9, "bold"),
            padx=8,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.save_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # Кнопка Очистить
        self.clear_btn = tk.Button(
            button_frame,
            text="🧹 Очистить",
            command=self.clear_current_tile,
            bg='#ff9800',
            fg='white',
            font=(self.emoji_font, 9, "bold"),
            padx=8,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.clear_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # Кнопка Отмена
        self.cancel_btn = tk.Button(
            button_frame,
            text="❌ Отмена",
            command=self.cancel_selection,
            bg='#666666',
            fg='white',
            font=(self.emoji_font, 9, "bold"),
            padx=8,
            pady=4,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)
        
        # Кнопка сброса (под панелью)
        reset_btn = tk.Button(
            self.main_container,
            text="🔄 Начать заново",
            command=self.reset_game,
            bg='#45a049',
            fg='white',
            font=(self.emoji_font, 10, "bold"),
            padx=15,
            pady=6,
            cursor="hand2"
        )
        reset_btn.pack(side=tk.BOTTOM, pady=(10, 5))
        
        # Информационная метка (в самом низу)
        self.info_label = tk.Label(
            self.main_container,
            text="",
            font=(self.emoji_font, 10),
            bg='#1a1a1a',
            fg='#e0e0e0',
            pady=5
        )
        self.info_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def select_tile(self, row: int, col: int):
        """Выбрать плитку для редактирования"""
        self.current_edit = (row, col)
        self.panel_coords.config(text=f"Строка: {row+1}, Колонка: {col+1}")
        
        # Устанавливаем текущие значения
        data = self.tile_data[row][col]
        if data.opened:
            self.tile_type_var.set(data.value if data.value != 'unknown' else 'common')
            self.hint_type_var.set(data.hint if data.hint != 'unknown' else 'common')
        else:
            self.tile_type_var.set("common")
            self.hint_type_var.set("common")
        
        # Активируем кнопки
        self.save_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.NORMAL)
        
        # Подсвечиваем выбранную плитку
        self.update_tile_selection(row, col)
    
    def update_tile_selection(self, row: int, col: int):
        """Обновить выделение выбранной плитки"""
        # Сбрасываем все подсветки
        for i, btn in enumerate(self.tile_buttons):
            btn.config(relief=tk.RAISED)
        
        # Подсвечиваем выбранную плитку
        index = row * COLS + col
        self.tile_buttons[index].config(relief=tk.SUNKEN, borderwidth=3)
    
    def save_tile_info(self):
        """Сохранить информацию о плитке"""
        if not self.current_edit:
            return
        
        row, col = self.current_edit
        self.tile_data[row][col].opened = True
        self.tile_data[row][col].value = self.tile_type_var.get()
        self.tile_data[row][col].hint = self.hint_type_var.get()
        
        self.update_tile_ui(row, col)
        self.update_suggestion()
    
    def clear_current_tile(self):
        """Очистить текущую плитку"""
        if not self.current_edit:
            return
        
        row, col = self.current_edit
        self.tile_data[row][col] = TileData(row, col)
        
        self.update_tile_ui(row, col)
        self.update_suggestion()
        
        # Сбрасываем радиокнопки
        self.tile_type_var.set("common")
        self.hint_type_var.set("common")
    
    def cancel_selection(self):
        """Отменить выбор плитки"""
        self.current_edit = None
        self.panel_coords.config(text="Не выбрана")
        
        # Сбрасываем радиокнопки
        self.tile_type_var.set("common")
        self.hint_type_var.set("common")
        
        # Отключаем кнопки
        self.save_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.DISABLED)
        
        # Сбрасываем подсветку плиток
        for btn in self.tile_buttons:
            btn.config(relief=tk.RAISED)
    
    def update_tile_ui(self, row: int, col: int):
        """Обновить отображение плитки"""
        index = row * COLS + col
        btn = self.tile_buttons[index]
        data = self.tile_data[row][col]
        
        if data.opened:
            if data.value == 'gold':
                btn.config(text="🥇", bg='#ffd700', fg='#333333')
            else:
                btn.config(text="🟫", bg='#3d3d3d', fg='#e0e0e0')
            
            # Добавляем подсказку
            if data.hint == 'gold':
                btn.config(text=f"{btn.cget('text')} ⭐")
        else:
            btn.config(text="?", bg='#555555', fg='#e0e0e0')
    
    def update_suggestion(self):
        """Обновить подсказку"""
        # Создаем сетку
        grid = Grid(ROWS, COLS, TOTAL_GOLD)
        grid.init_from_tile_data(self.tile_data)
        
        # Проверяем, найдены ли все золотые плитки
        if grid.golds_found >= TOTAL_GOLD:
            self.info_label.config(text="🎉 Все золотые плитки найдены!")
            return
        
        # Создаем решатель
        solver = BruteforceProbabilitySolver(grid)
        solver.update_possible_configurations()
        
        if solver.possible_configurations_remaining == 0:
            self.info_label.config(text="⚠️ Невозможная конфигурация! Проверьте введённые данные.")
            return
        
        solver.update_probabilities()
        solver.update_remaining_configs_estimate()
        
        next_tile = solver.get_next_tile_to_open()
        self.show_suggestion(next_tile)
    
    def show_suggestion(self, next_tile):
        """Показать подсказку"""
        if not next_tile:
            self.info_label.config(text="ℹ️ Нет доступных подсказок.")
            return
        
        self.info_label.config(
            text=f"🎯 Рекомендуемая плитка: Строка {next_tile.row+1}, Колонка {next_tile.col+1}"
        )
    
    def reset_game(self):
        """Сбросить игру"""
        self.tile_data = self._initialize_tile_data()
        for r in range(ROWS):
            for c in range(COLS):
                self.update_tile_ui(r, c)
        self.cancel_selection()
        self.update_suggestion()
    
    def setup_keyboard_shortcuts(self):
        """Настройка горячих клавиш"""
        self.root.bind('<Escape>', lambda e: self.cancel_selection())
        self.root.bind('<Control-r>', lambda e: self.reset_game())

def main():
    """Точка входа в приложение"""
    root = tk.Tk()
    app = SnowmanSolverApp(root)
    
    # Центрирование окна
    root.update_idletasks()
    x = (root.winfo_screenwidth() // 2) - (WINDOW_WIDTH // 2)
    y = (root.winfo_screenheight() // 2) - (WINDOW_HEIGHT // 2)
    root.geometry(f'+{x}+{y}')
    
    root.mainloop()

if __name__ == "__main__":
    main()