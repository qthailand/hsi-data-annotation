import re

import numpy as np
import spectral as spy
from PyQt5.QtGui import QImage


RGB_BANDS = (29, 19, 9)
RGB_TARGET_WAVELENGTHS_VIS = (645.0, 555.0, 465.0)
RGB_TARGET_WAVELENGTHS_SWIR = (1500.0, 1300.0, 1100.0)
RGB_TARGET_WAVELENGTHS = RGB_TARGET_WAVELENGTHS_VIS
COLOR_TOLERANCE = 3
DEFAULT_LOW_CUT = 2.0
DEFAULT_HIGH_CUT = 98.0


def load_datacube_preview(
    path,
    low_cut=DEFAULT_LOW_CUT,
    high_cut=DEFAULT_HIGH_CUT,
    target_wavelengths=None,
):
    datacube = spy.open_image(path)
    rgb, preview_info = build_rgb_preview(
        datacube,
        low_cut=low_cut,
        high_cut=high_cut,
        target_wavelengths=target_wavelengths,
    )
    rgb8 = np.ascontiguousarray((rgb * 255).clip(0, 255).astype(np.uint8))
    height, width, _ = rgb8.shape
    qimg = QImage(rgb8.data, width, height, width * 3, QImage.Format_RGB888)
    return datacube, qimg.convertToFormat(QImage.Format_ARGB32).copy(), preview_info


def _select_default_target_wavelengths(metadata):
    wavelengths = extract_wavelengths(metadata)
    if wavelengths is None or len(wavelengths) == 0:
        return RGB_TARGET_WAVELENGTHS_VIS

    # ถ้าคลื่นส่วนใหญ่เป็น SWIR สูงกว่า 1000 nm -> SWIR targets
    if np.nanmean(wavelengths) > 1000.0 or np.nanmin(wavelengths) > 900.0:
        return RGB_TARGET_WAVELENGTHS_SWIR

    return RGB_TARGET_WAVELENGTHS_VIS


def build_rgb_preview(
    datacube,
    low_cut=DEFAULT_LOW_CUT,
    high_cut=DEFAULT_HIGH_CUT,
    target_wavelengths=None,
):
    if target_wavelengths is None:
        target_wavelengths = _select_default_target_wavelengths(datacube.metadata)
    band_indices, actual_wavelengths = select_rgb_bands(datacube, target_wavelengths)
    rgb = np.asarray(datacube.read_bands(list(band_indices)), dtype=np.float32)
    rgb = _percentile_stretch_rgb(rgb, low_cut, high_cut)
    preview_info = {
        "band_indices": tuple(int(index) for index in band_indices),
        "target_wavelengths": tuple(float(value) for value in target_wavelengths),
        "actual_wavelengths": actual_wavelengths,
        "low_cut": float(low_cut),
        "high_cut": float(high_cut),
        "used_metadata_wavelengths": actual_wavelengths is not None,
    }
    return rgb, preview_info


def select_rgb_bands(datacube, target_wavelengths=None):
    if target_wavelengths is None:
        target_wavelengths = _select_default_target_wavelengths(datacube.metadata)

    wavelengths = extract_wavelengths(datacube.metadata)
    if wavelengths is None or len(wavelengths) == 0:
        return RGB_BANDS, None

    band_indices = []
    actual_wavelengths = []
    for target in target_wavelengths:
        index = int(np.argmin(np.abs(wavelengths - target)))
        band_indices.append(index)
        actual_wavelengths.append(float(wavelengths[index]))
    return tuple(band_indices), tuple(actual_wavelengths)


def extract_wavelengths(metadata):
    raw_wavelengths = metadata.get("wavelength") if metadata else None
    if raw_wavelengths is None:
        return None

    values = _coerce_wavelength_values(raw_wavelengths)
    if not values:
        return None

    wavelengths = np.asarray(values, dtype=np.float32)
    units = str(metadata.get("wavelength units", "")).strip().lower() if metadata else ""
    if _uses_micrometer_units(units, wavelengths):
        wavelengths = wavelengths * 1000.0
    return wavelengths


def compute_class_spectra(datacube, mask, classes, max_samples=300):
    if datacube is None:
        return [(name, color, None) for _, name, color in classes]

    mask_arr = _qimage_to_rgba_array(mask)
    class_data = []
    for _, name, color in classes:
        match = _match_color(mask_arr, color)
        ys, xs = np.where(match)
        if len(ys) == 0:
            class_data.append((name, color, None))
            continue
        if len(ys) > max_samples:
            idx = np.random.choice(len(ys), max_samples, replace=False)
            ys, xs = ys[idx], xs[idx]
        valid = (xs < datacube.ncols) & (ys < datacube.nrows)
        ys, xs = ys[valid], xs[valid]
        if len(ys) == 0:
            class_data.append((name, color, None))
            continue
        try:
            spectra = np.array(
                [
                    np.array(datacube[int(y), int(x), :], dtype=np.float32).flatten()
                    for y, x in zip(ys, xs)
                ]
            )
            class_data.append((name, color, spectra.mean(axis=0)))
        except Exception:
            class_data.append((name, color, None))
    return class_data


def build_class_id_mask(mask, classes):
    mask_arr = _qimage_to_rgba_array(mask)
    height, width = mask_arr.shape[:2]
    id_arr = np.zeros((height, width), dtype=np.uint8)

    for class_id, _, color in classes:
        id_arr[_match_color(mask_arr, color)] = class_id

    return np.ascontiguousarray(id_arr)


def _qimage_to_rgba_array(image):
    rgba = image.convertToFormat(QImage.Format_RGBA8888)
    width, height = rgba.width(), rgba.height()
    ptr = rgba.bits()
    ptr.setsize(height * width * 4)
    return np.frombuffer(ptr, np.uint8).reshape((height, width, 4)).copy()


def _match_color(mask_arr, color, tolerance=COLOR_TOLERANCE):
    return (
        (np.abs(mask_arr[:, :, 0].astype(int) - color.red()) <= tolerance)
        & (np.abs(mask_arr[:, :, 1].astype(int) - color.green()) <= tolerance)
        & (np.abs(mask_arr[:, :, 2].astype(int) - color.blue()) <= tolerance)
        & (mask_arr[:, :, 3] > 0)
    )


def _coerce_wavelength_values(raw_wavelengths):
    if isinstance(raw_wavelengths, str):
        cleaned = raw_wavelengths.strip().strip("{}").strip("[]")
        parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    else:
        parts = list(raw_wavelengths)

    values = []
    for part in parts:
        if isinstance(part, (float, int)):
            values.append(float(part))
            continue
        match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(part))
        if match is not None:
            values.append(float(match.group(0)))
    return values


def _uses_micrometer_units(units, wavelengths):
    if "mic" in units or "um" in units:
        return True
    if "nm" in units:
        return False
    return float(np.nanmedian(wavelengths)) < 20.0


def _percentile_stretch_rgb(rgb, low_cut, high_cut):
    if not 0.0 <= low_cut < high_cut <= 100.0:
        raise ValueError("Contrast cuts must satisfy 0 <= low_cut < high_cut <= 100")

    stretched = np.empty_like(rgb, dtype=np.float32)
    for channel_index in range(rgb.shape[2]):
        channel = rgb[:, :, channel_index].astype(np.float32, copy=False)
        low = float(np.percentile(channel, low_cut))
        high = float(np.percentile(channel, high_cut))
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            low = float(np.min(channel))
            high = float(np.max(channel))
        if high <= low:
            stretched[:, :, channel_index] = np.zeros_like(channel, dtype=np.float32)
            continue
        stretched[:, :, channel_index] = np.clip((channel - low) / (high - low), 0.0, 1.0)
    return stretched