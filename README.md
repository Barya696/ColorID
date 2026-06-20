# Color ID Painter – Blender Addon

A lightweight Blender addon for painting solid Color IDs onto mesh faces using a **Face-Corner Color Attribute**, ready for FBX export to Substance Painter.

Built for **Blender 5.0+** — uses the modern `color_attributes` API since `vertex_colors` was removed in Blender 4.x.

## Features

- 12-slot color palette with one-click face assignment
- Custom color picker for unlimited colors
- Select faces by Color ID slot
- Fill entire mesh with a base color
- Attribute name is editable (default: `ColorID`)

## Installation

1. Download `color_id_painter.py`
2. In Blender: **Edit → Preferences → Add-ons → Install**
3. Select the file and enable **Color ID Painter**
4. Open the **N-panel** in the 3D Viewport → **Color ID** tab

## Workflow

1. Select faces in **Edit Mode**
2. Pick a color slot in the panel
3. Click **Assign Color to Faces**
4. Repeat for each region
5. Export as **FBX** with **Vertex Colors → sRGB**
6. In Substance Painter: bake **ID map** with **Color Source → Vertex Color**

## Requirements

- Blender 4.1 or later (fully tested on 5.0.1)
