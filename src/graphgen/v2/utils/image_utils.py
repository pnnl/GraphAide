"""Utilities for loading, processing, and visualizing image embeddings."""

import io
import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np


def load_and_preview_image(image_path: str, max_width: int = 200) -> Optional[str]:
    """Load an image and return HTML for notebook display (if PIL available).

    Args:
        image_path: Path to image file
        max_width: Max width for display in pixels

    Returns:
        HTML string for IPython.display.HTML() or None if PIL unavailable
    """
    try:
        from PIL import Image
        import base64
        from IPython.display import HTML

        if not os.path.exists(image_path):
            return None

        img = Image.open(image_path)

        # Resize if needed
        if img.width > max_width:
            scale = max_width / img.width
            new_height = int(img.height * scale)
            img = img.resize((max_width, new_height))

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode()

        html = f'<img src="data:image/png;base64,{img_base64}" style="max-width:{max_width}px"/>'
        return html

    except ImportError:
        print("PIL not available for image preview")
        return None
    except Exception as e:
        print(f"Error loading image {image_path}: {e}")
        return None


def batch_load_images(
    directory: str,
    extensions: Tuple[str, ...] = (".png", ".jpg", ".jpeg"),
    max_files: Optional[int] = None,
) -> List[str]:
    """Load all images from a directory.

    Args:
        directory: Directory path containing images
        extensions: Tuple of file extensions to load
        max_files: Maximum number of files to load (None = all)

    Returns:
        List of image file paths
    """
    image_files = []

    if not os.path.isdir(directory):
        print(f"Directory not found: {directory}")
        return image_files

    for file in os.listdir(directory):
        if file.lower().endswith(extensions):
            image_files.append(os.path.join(directory, file))
            if max_files and len(image_files) >= max_files:
                break

    return sorted(image_files)


def display_image_embeddings_on_plot(
    embeddings_2d: np.ndarray,
    image_paths: List[str],
    doc_types: List[str],
    ax=None,
) -> Optional[object]:
    """Plot image embeddings with colors by document type.

    Args:
        embeddings_2d: 2D UMAP/t-SNE projections (N x 2)
        image_paths: List of image file paths for hover text
        doc_types: List of document types ("text" or "image")
        ax: Matplotlib axis object (None for new figure)

    Returns:
        Matplotlib axis object or None if matplotlib unavailable
    """
    try:
        import matplotlib.pyplot as plt

        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 8))

        # Color by type
        colors = {"text": "blue", "image": "red"}
        color_map = [colors.get(dt, "gray") for dt in doc_types]

        # Plot points
        ax.scatter(
            embeddings_2d[:, 0],
            embeddings_2d[:, 1],
            c=color_map,
            alpha=0.6,
            s=50,
            edgecolors="k",
            linewidth=0.5,
        )

        # Add legend
        from matplotlib.patches import Patch

        legend_elements = [
            Patch(facecolor="blue", alpha=0.6, label="Text documents"),
            Patch(facecolor="red", alpha=0.6, label="Image embeddings"),
        ]
        ax.legend(handles=legend_elements, loc="upper right")

        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")
        ax.set_title("Document Embeddings (Text vs Image)")
        ax.grid(True, alpha=0.3)

        return ax

    except ImportError:
        print("Matplotlib not available for plotting")
        return None


def get_image_metadata_summary(image_paths: List[str]) -> dict:
    """Get summary of image properties.

    Args:
        image_paths: List of image file paths

    Returns:
        Dictionary with size and format statistics
    """
    try:
        from PIL import Image

        summary = {
            "total_images": len(image_paths),
            "formats": {},
            "sizes": [],
            "invalid_files": [],
        }

        for path in image_paths:
            try:
                if not os.path.exists(path):
                    summary["invalid_files"].append(path)
                    continue

                img = Image.open(path)
                fmt = img.format or "unknown"
                summary["formats"][fmt] = summary["formats"].get(fmt, 0) + 1
                summary["sizes"].append((img.width, img.height))

            except Exception as e:
                summary["invalid_files"].append(f"{path}: {e}")

        if summary["sizes"]:
            summary["avg_width"] = int(np.mean([s[0] for s in summary["sizes"]]))
            summary["avg_height"] = int(np.mean([s[1] for s in summary["sizes"]]))

        return summary

    except ImportError:
        print("PIL not available for image metadata")
        return {"error": "PIL not installed"}
