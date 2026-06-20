"""
Color ID Painter – Blender 5.0+ Addon
======================================
Workflow:
  1. Select faces in Edit Mode
  2. Pick a color slot in the N-panel (View3D > Color ID tab)
  3. Click "Assign Color to Faces"
  4. Optionally "Select Faces by Color" to verify / re-select
  5. Export FBX → Substance Painter uses the 'ColorID' attribute as ID map

Blender 5.0 drops `mesh.vertex_colors` entirely.
This addon uses `mesh.color_attributes` with domain=CORNER, type=BYTE_COLOR
which is the correct modern API and exports cleanly in FBX.
"""

bl_info = {
    "name":        "Color ID Painter",
    "author":      "Custom",
    "version":     (1, 3, 0),
    "blender":     (4, 1, 0),   # minimum – tested on 5.0.1
    "location":    "View3D > Sidebar (N) > Color ID",
    "description": (
        "Paint solid Color IDs onto selected faces using a Face-Corner "
        "Color Attribute. Ready for FBX export → Substance Painter."
    ),
    "category":    "Mesh",
}

import bpy
from bpy.props import FloatVectorProperty, IntProperty, StringProperty, BoolProperty


# ─────────────────────────────────────────────────────────────────────────────
# Palette  (12 vivid, distinct hues – all in linear sRGB)
# ─────────────────────────────────────────────────────────────────────────────

PALETTE = [
    ("Red",        (1.000, 0.000, 0.000, 1.0)),
    ("Green",      (0.000, 1.000, 0.000, 1.0)),
    ("Blue",       (0.000, 0.000, 1.000, 1.0)),
    ("Yellow",     (1.000, 1.000, 0.000, 1.0)),
    ("Cyan",       (0.000, 1.000, 1.000, 1.0)),
    ("Magenta",    (1.000, 0.000, 1.000, 1.0)),
    ("Orange",     (1.000, 0.502, 0.000, 1.0)),
    ("Purple",     (0.502, 0.000, 1.000, 1.0)),
    ("Dark Green", (0.000, 0.502, 0.000, 1.0)),
    ("Brown",      (0.502, 0.251, 0.000, 1.0)),
    ("Teal",       (0.000, 0.502, 0.502, 1.0)),
    ("White",      (1.000, 1.000, 1.000, 1.0)),
]

ATTR_NAME_DEFAULT = "ColorID"


# ─────────────────────────────────────────────────────────────────────────────
# Per-object panel props (stored on WindowManager for simplicity)
# ─────────────────────────────────────────────────────────────────────────────

def register_props():
    bpy.types.Scene.cid_active_slot = IntProperty(
        name="Active Slot", default=0, min=0, max=len(PALETTE),
        description="0–11 = palette slot, 12 = custom color"
    )
    bpy.types.Scene.cid_custom_color = FloatVectorProperty(
        name="Custom Color", subtype="COLOR",
        size=4, min=0.0, max=1.0,
        default=(1.0, 0.5, 0.0, 1.0),
    )
    bpy.types.Scene.cid_attr_name = StringProperty(
        name="Attribute Name", default=ATTR_NAME_DEFAULT,
        description="Name of the Color Attribute written to the mesh"
    )
    bpy.types.Scene.cid_show_slots = BoolProperty(
        name="Show Palette", default=True
    )


def unregister_props():
    del bpy.types.Scene.cid_active_slot
    del bpy.types.Scene.cid_custom_color
    del bpy.types.Scene.cid_attr_name
    del bpy.types.Scene.cid_show_slots


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_attr(mesh, attr_name: str):
    """
    Return a CORNER / BYTE_COLOR attribute, creating it when absent.
    Sets it as the active & render color attribute.
    """
    attr = mesh.color_attributes.get(attr_name)
    if attr is None:
        attr = mesh.color_attributes.new(
            name=attr_name,
            type="BYTE_COLOR",
            domain="CORNER",
        )
    # Mark as active color attribute (render + viewport)
    keys = list(mesh.color_attributes.keys())
    idx = keys.index(attr_name)
    mesh.color_attributes.active_color_index = idx
    mesh.color_attributes.render_color_index  = idx
    return attr


def _active_color(scene):
    """Return (R,G,B,A) tuple for the currently active slot."""
    s = scene.cid_active_slot
    if s < len(PALETTE):
        return PALETTE[s][1]
    return tuple(scene.cid_custom_color)


# ─────────────────────────────────────────────────────────────────────────────
# Operator – Set active slot
# ─────────────────────────────────────────────────────────────────────────────

class CID_OT_SetSlot(bpy.types.Operator):
    """Activate a palette color slot"""
    bl_idname  = "color_id.set_slot"
    bl_label   = "Set Color Slot"
    slot: IntProperty(default=0)

    def execute(self, context):
        context.scene.cid_active_slot = self.slot
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Operator – Assign color to selected faces
# ─────────────────────────────────────────────────────────────────────────────

class CID_OT_Assign(bpy.types.Operator):
    """Paint the active Color ID onto every currently selected face"""
    bl_idname  = "color_id.assign"
    bl_label   = "Assign Color to Faces"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == "MESH" and obj.mode == "EDIT"

    def execute(self, context):
        scene = context.scene
        obj   = context.active_object
        mesh  = obj.data

        color     = _active_color(scene)
        attr_name = scene.cid_attr_name or ATTR_NAME_DEFAULT

        # Must switch to object mode to write attribute data
        bpy.ops.object.mode_set(mode="OBJECT")

        attr = _get_or_create_attr(mesh, attr_name)

        count = 0
        for poly in mesh.polygons:
            if poly.select:
                for loop_idx in poly.loop_indices:
                    attr.data[loop_idx].color = color
                count += 1

        bpy.ops.object.mode_set(mode="EDIT")

        if count == 0:
            self.report({"WARNING"}, "No faces selected.")
        else:
            slot_name = PALETTE[scene.cid_active_slot][0] if scene.cid_active_slot < len(PALETTE) else "Custom"
            self.report({"INFO"}, f"Assigned '{slot_name}' to {count} face(s) → '{attr_name}'")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Operator – Fill entire mesh
# ─────────────────────────────────────────────────────────────────────────────

class CID_OT_FillAll(bpy.types.Operator):
    """Fill ALL faces of the active mesh with the current Color ID"""
    bl_idname  = "color_id.fill_all"
    bl_label   = "Fill Entire Mesh"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == "MESH"

    def execute(self, context):
        scene = context.scene
        obj   = context.active_object
        mesh  = obj.data

        color     = _active_color(scene)
        attr_name = scene.cid_attr_name or ATTR_NAME_DEFAULT

        prev_mode = obj.mode
        bpy.ops.object.mode_set(mode="OBJECT")

        attr = _get_or_create_attr(mesh, attr_name)
        for item in attr.data:
            item.color = color

        bpy.ops.object.mode_set(mode=prev_mode)
        self.report({"INFO"}, "All faces filled.")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Operator – Select faces by active color
# ─────────────────────────────────────────────────────────────────────────────

class CID_OT_SelectByColor(bpy.types.Operator):
    """Select all faces whose stored Color ID matches the active slot"""
    bl_idname  = "color_id.select_by_color"
    bl_label   = "Select Faces by Color"
    bl_options = {"REGISTER", "UNDO"}

    threshold: bpy.props.FloatProperty(
        name="Threshold", default=0.02, min=0.0, max=1.0,
        description="Per-channel tolerance for color matching"
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == "MESH" and obj.mode == "EDIT"

    def execute(self, context):
        scene = context.scene
        obj   = context.active_object
        mesh  = obj.data

        target    = _active_color(scene)[:3]
        attr_name = scene.cid_attr_name or ATTR_NAME_DEFAULT
        thr       = self.threshold

        bpy.ops.object.mode_set(mode="OBJECT")

        attr = mesh.color_attributes.get(attr_name)
        if attr is None:
            bpy.ops.object.mode_set(mode="EDIT")
            self.report({"WARNING"}, f"Attribute '{attr_name}' not found on this mesh.")
            return {"CANCELLED"}

        # Deselect everything first
        for poly in mesh.polygons:
            poly.select = False
        for v in mesh.vertices:
            v.select = False
        for e in mesh.edges:
            e.select = False

        matched = 0
        for poly in mesh.polygons:
            fc = attr.data[poly.loop_start].color
            if all(abs(fc[i] - target[i]) <= thr for i in range(3)):
                poly.select = True
                matched += 1

        bpy.ops.object.mode_set(mode="EDIT")
        self.report({"INFO"}, f"Selected {matched} face(s) matching active color.")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Operator – Remove Color Attribute
# ─────────────────────────────────────────────────────────────────────────────

class CID_OT_Clear(bpy.types.Operator):
    """Remove the Color ID attribute from this mesh"""
    bl_idname  = "color_id.clear"
    bl_label   = "Remove Color Attribute"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not (obj and obj.type == "MESH"):
            return False
        name = context.scene.cid_attr_name or ATTR_NAME_DEFAULT
        return name in obj.data.color_attributes

    def execute(self, context):
        mesh = context.active_object.data
        name = context.scene.cid_attr_name or ATTR_NAME_DEFAULT
        attr = mesh.color_attributes.get(name)
        if attr:
            mesh.color_attributes.remove(attr)
            self.report({"INFO"}, f"Removed Color Attribute '{name}'.")
        return {"FINISHED"}


# ─────────────────────────────────────────────────────────────────────────────
# Panel
# ─────────────────────────────────────────────────────────────────────────────

class CID_PT_Main(bpy.types.Panel):
    bl_label      = "Color ID Painter"
    bl_idname     = "CID_PT_Main"
    bl_space_type = "VIEW_3D"
    bl_region_type= "UI"
    bl_category   = "Color ID"

    def draw(self, context):
        layout = self.layout
        scene  = context.scene
        obj    = context.active_object
        in_edit = obj is not None and obj.type == "MESH" and obj.mode == "EDIT"

        # ── Attribute name ──────────────────────────────────────────────────
        header_box = layout.box()
        row = header_box.row(align=True)
        row.label(text="Attribute:", icon="VPAINT_HLT")
        row.prop(scene, "cid_attr_name", text="")
        # Indicator
        if obj and obj.type == "MESH":
            name    = scene.cid_attr_name or ATTR_NAME_DEFAULT
            exists  = name in obj.data.color_attributes
            row.label(text="✓" if exists else "–")

        # ── Palette ─────────────────────────────────────────────────────────
        pal_box = layout.box()
        sub_header = pal_box.row()
        sub_header.prop(scene, "cid_show_slots",
                        icon="TRIA_DOWN" if scene.cid_show_slots else "TRIA_RIGHT",
                        icon_only=True, emboss=False)
        sub_header.label(text="Palette Slots", icon="COLOR")

        if scene.cid_show_slots:
            col = pal_box.column(align=True)
            for i, (name, color) in enumerate(PALETTE):
                row2 = col.row(align=True)
                is_active = (i == scene.cid_active_slot)
                # Highlight row if active
                row2.alert = is_active
                op = row2.operator(
                    "color_id.set_slot",
                    text=f"  {name}",
                    icon="LAYER_ACTIVE" if is_active else "LAYER_USED",
                    emboss=is_active,
                )
                op.slot = i
                # Hex label
                r = int(color[0] * 255)
                g = int(color[1] * 255)
                b = int(color[2] * 255)
                row2.label(text=f"#{r:02X}{g:02X}{b:02X}")

            # Custom color row
            pal_box.separator(factor=0.5)
            custom_row = pal_box.row(align=True)
            custom_row.alert = (scene.cid_active_slot == len(PALETTE))
            op = custom_row.operator(
                "color_id.set_slot",
                text="  Custom",
                icon="LAYER_ACTIVE" if scene.cid_active_slot == len(PALETTE) else "LAYER_USED",
                emboss=(scene.cid_active_slot == len(PALETTE)),
            )
            op.slot = len(PALETTE)
            custom_row.prop(scene, "cid_custom_color", text="")

        # Active color preview label
        s = scene.cid_active_slot
        if s < len(PALETTE):
            active_label = f"Active: {PALETTE[s][0]}"
        else:
            active_label = "Active: Custom"
        layout.label(text=active_label, icon="COLORSET_01_VEC")

        # ── Actions ─────────────────────────────────────────────────────────
        act_box = layout.box()
        act_box.label(text="Actions", icon="TOOL_SETTINGS")

        col = act_box.column(align=True)
        assign_row = col.row()
        assign_row.enabled = in_edit
        assign_row.scale_y = 1.4
        assign_row.operator("color_id.assign", icon="BRUSHES_ALL")

        col.separator(factor=0.5)
        sel_row = col.row()
        sel_row.enabled = in_edit
        sel_row.operator("color_id.select_by_color", icon="RESTRICT_SELECT_OFF")

        col.separator(factor=0.5)
        col.operator("color_id.fill_all", icon="SNAP_FACE")
        col.operator("color_id.clear",    icon="TRASH")

        if not in_edit:
            act_box.label(text="Enter Edit Mode to paint.", icon="INFO")

        # ── Export hint ─────────────────────────────────────────────────────
        hint = layout.column()
        hint.scale_y = 0.7
        hint.separator()
        hint.label(text="FBX Export: enable 'Vertex Colors'")
        hint.label(text="in FBX export options (Custom Props).")
        hint.label(text="Substance Painter → Mesh > ID Map.")


# ─────────────────────────────────────────────────────────────────────────────
# Registration
# ─────────────────────────────────────────────────────────────────────────────

CLASSES = [
    CID_OT_SetSlot,
    CID_OT_Assign,
    CID_OT_FillAll,
    CID_OT_SelectByColor,
    CID_OT_Clear,
    CID_PT_Main,
]


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    register_props()


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    unregister_props()


if __name__ == "__main__":
    register()
