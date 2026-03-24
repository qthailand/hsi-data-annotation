# HSI Data Annotation

A desktop GUI application for annotating hyperspectral imaging (HSI) datacubes with pixel-level classification masks.

## Features

- Load ENVI hyperspectral image files (`.hdr` format)
- Paint pixels with customizable class labels and colors
- View spectral reflectance curves at cursor position
- Flood-fill connected regions
- Save ground truth masks as PNG or TIFF files

## Requirements

- Python 3.7+
- [PyQt5](https://pypi.org/project/PyQt5/)
- [NumPy](https://numpy.org/)
- [spectral](https://www.spectralpython.net/)
- [pyqtgraph](https://www.pyqtgraph.org/)

## Installation

```bash
pip install PyQt5 numpy spectral pyqtgraph
```

## Usage

```bash
python -m __main__
```

### Toolbar Tools

| Tool | Shortcut | Description |
|------|----------|-------------|
| Open | Ctrl+O | Open a hyperspectral datacube (`.hdr` file) |
| Clear | Ctrl+N | Clear the current ground truth mask |
| Save | Ctrl+S | Save the ground truth mask as PNG/TIFF |
| Pen | P | Freehand drawing |
| Eraser | E | Erase annotations |
| Fill | F | Flood-fill connected region |
| Connect | L | Draw a line between clicked points |

### Navigation

- **Ctrl + Scroll Wheel** — Zoom in / out (5% – 5000%)
- **Middle-click drag** — Pan the canvas

## Output Format

Saved masks are 8-bit grayscale images where each pixel value represents a class ID:

| Pixel value | Meaning |
|-------------|---------|
| `0` | Background / unannotated |
| `1, 2, 3, …` | Class IDs assigned in the class manager |

## UI Layout

```
┌─────────────────┬───────────────────┬──────────────────┐
│  Annotation     │  Image Viewer     │  Class Manager   │
│  Canvas         │  + Spectral Plot  │  (labels/colors) │
└─────────────────┴───────────────────┴──────────────────┘
```
