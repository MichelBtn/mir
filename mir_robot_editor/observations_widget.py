from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QScrollArea, QGridLayout, QSizePolicy, QSplitter
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
import numpy as np
import pyqtgraph as pg
from typing import TypeVar, Generic
from mir_utils.ui.widgets import StateSavedView
from mir_utils.metrics import RollingArray

T_DATA = TypeVar("T_DATA")

class PlotWidget(QWidget, Generic[T_DATA]):
    def __init__(self, parent=None):
        super().__init__(parent)

    def update_plot(self, data: T_DATA): 
        raise NotImplementedError("update_plot is not implemented")

class PolarPlotControl(pg.PlotWidget):
    """
    Widget personnalisé pour tracer des données polaires (angle, distance)
    sous forme de nuage de points (scatter plot) avec une échelle fixe.
    Le 0° est placé en haut (style radar/boussole).
    """
    def __init__(self, max_range, show_distances: bool = True, show_angles: bool = True, parent=None):
        super().__init__(parent)
        self.max_range = max_range
        self._show_distances = show_distances
        self._show_angles = show_angles
        # --- Configuration de l'affichage ---
        self.setAspectLocked(True)          # Verrouille le ratio pour avoir des cercles ronds
        self.hideAxis('left')               # Cache les axes cartésiens
        self.hideAxis('bottom')
        self.setBackground((20,20,20))             # Fond blanc
        
        # --- Variables internes ---
        self.grid_items = []
        
        # --- Objet graphique pour le nuage de points ---
        self.scatter_item = pg.ScatterPlotItem(
            size=2,                         
            pen=pg.mkPen(None),             
            brush=pg.mkBrush(color=(255, 200, 0))     
        )
        self.addItem(self.scatter_item)
        
        # --- Initialisation de la grille fixe ---
        self._setup_grid()

    def update_plot(self, data: np.ndarray):
        """
        Met à jour le graphique avec un nouveau tableau numpy (N, 2).
        Colonne 0 : Angle en radians (0 = Haut, pi/2 = Droite)
        Colonne 1 : Distance (rayon)
        """
        if data.ndim != 2 or data.shape[1] != 2:
            raise ValueError("Les données doivent être un tableau numpy de forme (N, 2)")

        # Extraction et conversion polaire -> cartésien
        # Rotation de 90° pour que 0° soit en haut :
        # x = r * sin(theta)
        # y = r * cos(theta)
        #theta = -np.deg2rad(data[:, 0]) + 3*np.pi/2
        theta = -np.deg2rad(data[:, 0])
        r = data[:, 1]
        
        x = r * np.sin(theta)
        y = r * np.cos(theta)
        
        # Mise à jour des points uniquementsans toucher à la grille
        self.scatter_item.setData(x=x, y=y)

    def _setup_grid(self):
        """Dessine la grille polaire une seule fois (cercles, lignes, textes)."""
        range_max = self.max_range
        
        # Définir les limites de la vue de façon fixe (avec une petite marge pour les textes)
        margin = range_max * 0.01
        self.setXRange(-range_max - margin, range_max + margin)
        self.setYRange(-range_max - margin, range_max + margin)
        
        # --- Tracé des cercles concentriques et de leurs valeurs ---
        # Utilisation de linspace pour garantir que le dernier cercle est exactement à max_range
        num_circles = 5
        r_circles = np.linspace(0, range_max, num_circles + 1)[1:] # Exclut le 0
        
        theta_circle = np.linspace(0, 2 * np.pi, 100)
        for r in r_circles:
            x = r * np.cos(theta_circle)
            y = r * np.sin(theta_circle)
            circle_item = pg.PlotCurveItem(x, y, pen=pg.mkPen(color='gray', width=0.5, style=Qt.PenStyle.DashLine))
            self.addItem(circle_item)
            self.grid_items.append(circle_item)
            
            # Ajouter la valeur du cercle en gris, positionnée sur l'axe vertical
            # x légèrement décalé vers la droite pour ne pas chevaucher la ligne
            if self._show_distances:
                text_r = pg.TextItem(text=f"{r:g}", color=(200, 200, 200), anchor=(0, 0.5))
                text_r.setPos(range_max * 0.02, r)
                self.addItem(text_r)
                self.grid_items.append(text_r)

        # --- Tracé des lignes radiales ---
        angles_deg = np.arange(0, 360, 30)
        for angle in angles_deg:
            theta_rad = np.deg2rad(angle)
            
            # Calcul des coordonnées avec le 0° en haut
            x_end = range_max * np.sin(theta_rad)
            y_end = range_max * np.cos(theta_rad)
            
            line_item = pg.PlotCurveItem([0, x_end], [0, y_end], pen=pg.mkPen(color=(200, 200, 200), width=0.5, style=Qt.PenStyle.DashLine))
            self.addItem(line_item)
            self.grid_items.append(line_item)
            
            # Ajouter le texte des angles (0°, 30°, etc.) en gris
            if self._show_angles:
                text_x = (range_max + margin/2) * np.sin(theta_rad)
                text_y = (range_max + margin/2) * np.cos(theta_rad)
                text_item = pg.TextItem(text=f"{angle}°", color=(200, 200, 200), anchor=(0.5, 0.5))
                text_item.setPos(text_x, text_y)
                self.addItem(text_item)
                self.grid_items.append(text_item)

class PolarWidget(PlotWidget[np.ndarray]):
    def __init__(self, name:str, max_range: float, show_distances: bool = True, show_angles: bool = True, size:int=300, parent=None):
        super().__init__(parent)
        self.setFixedSize(size,size)
        self._max_range = max_range
        self._show_distances = show_distances
        self._show_angles = show_angles
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel(name)
        layout.addWidget(self.header)

        self._plot = PolarPlotControl(max_range, show_distances, show_angles)
        layout.addWidget(self._plot)

    def update_plot(self, data: np.ndarray):
        self._plot.update_plot(data)

class VideoWidget(PlotWidget[np.ndarray]):
    def __init__(self, name: str, width: int = 640, height: int = 480, parent=None):
        super().__init__(parent)
        
        self._widget_width = width
        self._widget_height = height

        self._header = QLabel(name)        
        self._image_render = QLabel()
        self._image_render.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._image_render.setMinimumSize(width, height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._header)
        layout.addWidget(self._image_render)
        
        # Initialiser avec une image noire
        black_frame = np.zeros((height, width, 3), dtype=np.uint8)
        self.update_plot(black_frame)

    def update_plot(self, data: np.ndarray):
        """
        Affiche une image RGB avec scaling intelligent.
        
        Args:
            frame: numpy array RGB (H, W, 3) uint8
        
        Comportement :
        - Si image plus grande que le widget : zoom fit (garder le ratio)
        - Si image plus petite : afficher en 1/1 et centrer
        """
        h, w, _ = data.shape
        qimg = QImage(data.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        
        # Si l'image est plus grande que le widget, la réduire avec fit
        pixmap = pixmap.scaled(
            self._widget_width, 
            self._widget_height, 
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        # Sinon, afficher à la résolution 1/1 (centrage assuré par setAlignment)
        
        self._image_render.setPixmap(pixmap)

class ScopeWidget(PlotWidget[float]):
    def __init__(self, name:str, min_value: float, max_value: float, width: int = 400, height: int = 130, history_size=1000):
        super().__init__()
        self._frames_scope = RollingArray(history_size)
        self._name = name
        self._min_value = min_value
        self._max_value = max_value
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.header = QLabel(name)
        layout.addWidget(self.header)
        self.plot = pg.PlotWidget()
        self.plot.showGrid(x=True, y=True)
        self.plot.setYRange(self._min_value, self._max_value)
        self.plot.setXRange(0, 1000)
        self.curve = self.plot.plot(pen='y')
        layout.addWidget(self.plot)
        self.setLayout(layout)
        self.setFixedSize(width, height)

    def update_plot(self, data: float):
        self._frames_scope.add(data)
        samples_count, samples = self._frames_scope.get_array()
        self.header.setText(f"{self._name:} {data:.1f}")
        if samples_count > 0:
            y = samples[-samples_count:]
            x = np.arange(len(samples))[-samples_count:]
            self.curve.setData(x, y)

class ResponsiveGridWidget(QWidget):
    """Widget qui organise ses enfants dans une grille adaptative en fonction
    de la largeur disponible. Utilisé pour disposer VideoWidget / PolarWidget.
    """
    def __init__(self, parent=None, min_column_width: int = 340, spacing: int = 8):
        super().__init__(parent)
        self.min_column_width = min_column_width
        self.spacing = spacing
        self._widgets: list[QWidget] = []

        self._layout = QGridLayout()
        self._layout.setSpacing(spacing)
        self._layout.setContentsMargins(0, 0, 0, 0)
        # Add a vertical stretch at the bottom to push widgets to the top
        self._layout.setRowStretch(1000, 1)
        self.setLayout(self._layout)

    def add_widget(self, w: QWidget) -> None:
        if w in self._widgets:
            return
        self._widgets.append(w)
        w.setParent(self)
        # ensure size policy expands horizontally so grid works well
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._relayout()

    def remove_widget(self, w: QWidget) -> None:
        if w not in self._widgets:
            return
        self._widgets.remove(w)
        self._layout.removeWidget(w)
        w.setParent(None)
        self._relayout()

    def clear(self) -> None:
        for w in list(self._widgets):
            self.remove_widget(w)

    def _relayout(self) -> None:
        # Clear layout
        while self._layout.count():
            self._layout.takeAt(0)
            # Do not delete widgets here; they are re-added

        width = max(1, self.width())
        columns = max(1, width // max(1, self.min_column_width))
        num_widgets = len(self._widgets)
        num_rows = (num_widgets + columns - 1) // columns if num_widgets > 0 else 1
        
        for idx, w in enumerate(self._widgets):
            row = idx // columns
            col = idx % columns
            self._layout.addWidget(w, row, col, alignment=Qt.AlignmentFlag.AlignTop)
        
        # Add stretch below the last row to push all widgets to the top
        self._layout.setRowStretch(num_rows, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()


class ObservationsWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        if isinstance(parent, StateSavedView):
            self._state_saved_view = parent
        self._plots: dict[str, PlotWidget] = {}

        # Left column: scopes inside a responsive grid (columns vary with width)
        self._left_grid = ResponsiveGridWidget(min_column_width=420, spacing=8)
        self._left_scroll = QScrollArea()
        self._left_scroll.setWidgetResizable(True)
        self._left_scroll.setWidget(self._left_grid)
        self._left_scroll.setMinimumWidth(240)

        # Right column: vertical stack for VideoWidget / PolarWidget (max ~3)
        self._right_layout = QVBoxLayout()
        self._right_layout.addStretch()

        self._right_inner = QWidget()
        self._right_inner.setLayout(self._right_layout)

        self._right_scroll = QScrollArea()
        self._right_scroll.setWidgetResizable(True)
        self._right_scroll.setWidget(self._right_inner)
        self._right_scroll.setMinimumWidth(240)

        # Splitter between left and right to allow user resizing
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self._left_scroll)
        self.splitter.addWidget(self._right_scroll)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        main_layout = QHBoxLayout()
        main_layout.addWidget(self.splitter, stretch=1)
        self.setLayout(main_layout)
        self.setStyleSheet(" background-color: #eeeeee;")

    def restore_state(self, _state_saved_view:StateSavedView):
        splitter_state = _state_saved_view.restore_custom_state("observations_widget_splitter")
        if splitter_state:
            self.splitter.restoreState(splitter_state)

    def save_state(self, _state_saved_view:StateSavedView):
        _state_saved_view.save_custom_state("observations_widget_splitter", self.splitter.saveState())

    def add_scope(self, key: str, min_value: float, max_value: float) -> ScopeWidget:
        if key in self._plots:
            raise KeyError(f"'{key}' already exists")
        scope = ScopeWidget(key, min_value, max_value)
        self._plots[key] = scope
        # Add to the responsive grid on the left
        self._left_grid.add_widget(scope)
        return scope

    def add_video(self, key: str) -> VideoWidget:
        if key in self._plots:
            raise KeyError(f"'{key}' already exists")
        video = VideoWidget(key, width=320, height=240)
        self._plots[key] = video
        # Insert before the stretch to keep widgets at top
        insert_index = max(0, self._right_layout.count() - 1)
        self._right_layout.insertWidget(insert_index, video, alignment=Qt.AlignmentFlag.AlignHCenter)
        return video

    def add_polar(self, key: str, max_range: float, show_distances: bool = True, show_angles: bool = True) -> PolarWidget:
        if key in self._plots:
            raise KeyError(f"'{key}' already exists")
        polar = PolarWidget(key, max_range, show_distances, show_angles, size=320)
        self._plots[key] = polar
        insert_index = max(0, self._right_layout.count() - 1)
        self._right_layout.insertWidget(insert_index, polar, alignment=Qt.AlignmentFlag.AlignHCenter)
        return polar

    def get_plot(self, key: str) -> PlotWidget:
        """Récupère un PlotWidget par clé"""
        if key not in self._plots:
            raise KeyError(f"Plot '{key}' not found")
        return self._plots[key]

    def clear(self) -> None:
        # Remove widgets from both containers
        for key, widget in list(self._plots.items()):
            # Try removing from left grid
            try:
                self._left_grid.remove_widget(widget)
            except Exception:
                pass
            # Try removing from right layout
            try:
                self._right_layout.removeWidget(widget)
            except Exception:
                pass
            widget.deleteLater()
        self._plots.clear()

