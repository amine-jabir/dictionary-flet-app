"""
Flet cross-version compatibility helpers supporting Flet <0.80, 0.80+, and 0.86+.
Provides robust, version-safe factories for icons, buttons, navigation, padding, margins,
dialog management, and safe area wrapping.
"""

from typing import Any, Callable, Optional, Union

try:
    import flet as ft
except ImportError:
    ft = None  # type: ignore


def get_icon(name: Optional[str]) -> Any:
    """Resolves an icon name string to an IconData object across all Flet versions."""
    if not name or not isinstance(name, str):
        return None

    clean = name.strip().upper()
    if ft is None:
        return clean.lower()

    IconsClass = getattr(ft, "Icons", None)
    if IconsClass and hasattr(IconsClass, clean):
        return getattr(IconsClass, clean)

    icons_mod = getattr(ft, "icons", None)
    if icons_mod and hasattr(icons_mod, clean):
        return getattr(icons_mod, clean)

    alias_map = {
        "FAVORITE_BORDER": "FAVORITE_OUTLINE",
        "CLEAR": "CLOSE",
        "DARK_MODE": "BRIGHTNESS_4",
        "LIGHT_MODE": "BRIGHTNESS_7",
    }
    alt_name = alias_map.get(clean)
    if alt_name:
        if IconsClass and hasattr(IconsClass, alt_name):
            return getattr(IconsClass, alt_name)
        if icons_mod and hasattr(icons_mod, alt_name):
            return getattr(icons_mod, alt_name)

    return clean.lower()


def create_icon(
    icon_name: str,
    size: Optional[Union[int, float]] = None,
    color: Optional[str] = None,
) -> Any:
    """Creates an ft.Icon control compatible across all Flet versions."""
    if ft is None:
        return None

    icon_data = get_icon(icon_name)
    kwargs: dict = {}
    if size is not None:
        kwargs["size"] = size
    if color is not None:
        kwargs["color"] = color

    try:
        return ft.Icon(icon_data, **kwargs)
    except TypeError:
        try:
            return ft.Icon(icon=icon_data, **kwargs)
        except TypeError:
            return ft.Icon(name=icon_data, **kwargs)


def create_icon_button(
    icon_name: str,
    on_click: Optional[Callable[[Any], None]] = None,
    icon_size: Optional[Union[int, float]] = None,
    icon_color: Optional[str] = None,
    bgcolor: Optional[str] = None,
    tooltip: Optional[str] = None,
) -> Any:
    """Creates an ft.IconButton control compatible across all Flet versions."""
    if ft is None:
        return None

    icon_data = get_icon(icon_name)
    kwargs: dict = {}
    if icon_size is not None:
        kwargs["icon_size"] = icon_size
    if icon_color is not None:
        kwargs["icon_color"] = icon_color
    if bgcolor is not None:
        kwargs["bgcolor"] = bgcolor
    if tooltip is not None:
        kwargs["tooltip"] = tooltip
    if on_click is not None:
        kwargs["on_click"] = on_click

    try:
        return ft.IconButton(icon=icon_data, **kwargs)
    except Exception:
        kwargs.pop("icon_size", None)
        kwargs.pop("icon_color", None)
        return ft.IconButton(
            content=create_icon(icon_name, size=icon_size, color=icon_color),
            **kwargs
        )


def create_text_button(
    text: str,
    icon_name: Optional[str] = None,
    on_click: Optional[Callable[[Any], None]] = None,
    color: Optional[str] = None,
) -> Any:
    """Creates an ft.TextButton compatible with modern Flet and legacy Flet."""
    if ft is None:
        return None

    icon_data = get_icon(icon_name) if icon_name else None
    text_kwargs = {"value": text}
    if color:
        text_kwargs["color"] = color

    if icon_data:
        content_widget = ft.Row(
            controls=[
                create_icon(icon_name, size=16, color=color),
                ft.Text(**text_kwargs),
            ],
            spacing=6,
            tight=True,
        )
    else:
        content_widget = ft.Text(**text_kwargs)

    kwargs: dict = {}
    if on_click is not None:
        kwargs["on_click"] = on_click

    try:
        return ft.TextButton(content=content_widget, **kwargs)
    except TypeError:
        try:
            return ft.TextButton(text=text, icon=icon_data, **kwargs)
        except Exception:
            return ft.TextButton(content=content_widget, **kwargs)


def create_elevated_button(
    text: str,
    icon_name: Optional[str] = None,
    on_click: Optional[Callable[[Any], None]] = None,
    bgcolor: Optional[str] = None,
    color: Optional[str] = None,
) -> Any:
    """Creates an ft.ElevatedButton compatible with modern Flet and legacy Flet."""
    if ft is None:
        return None

    icon_data = get_icon(icon_name) if icon_name else None
    text_color = color or "#FFFFFF"

    if icon_data:
        content_widget = ft.Row(
            controls=[
                create_icon(icon_name, size=16, color=text_color),
                ft.Text(text, color=text_color),
            ],
            spacing=6,
            tight=True,
        )
    else:
        content_widget = ft.Text(text, color=text_color)

    kwargs: dict = {}
    if on_click is not None:
        kwargs["on_click"] = on_click
    if bgcolor is not None:
        kwargs["bgcolor"] = bgcolor

    try:
        return ft.ElevatedButton(content=content_widget, **kwargs)
    except TypeError:
        try:
            return ft.ElevatedButton(text=text, icon=icon_data, color=color, **kwargs)
        except Exception:
            return ft.ElevatedButton(content=content_widget, **kwargs)


def create_outlined_button(
    text: str,
    icon_name: Optional[str] = None,
    on_click: Optional[Callable[[Any], None]] = None,
    tooltip: Optional[str] = None,
) -> Any:
    """Creates an ft.OutlinedButton compatible with modern Flet and legacy Flet."""
    if ft is None:
        return None

    icon_data = get_icon(icon_name) if icon_name else None

    if icon_data:
        content_widget = ft.Row(
            controls=[
                create_icon(icon_name, size=16),
                ft.Text(text, size=12),
            ],
            spacing=4,
            tight=True,
        )
    else:
        content_widget = ft.Text(text, size=12)

    kwargs: dict = {}
    if tooltip is not None:
        kwargs["tooltip"] = tooltip
    if on_click is not None:
        kwargs["on_click"] = on_click

    try:
        return ft.OutlinedButton(content=content_widget, **kwargs)
    except TypeError:
        try:
            return ft.OutlinedButton(text=text, icon=icon_data, **kwargs)
        except Exception:
            return ft.OutlinedButton(content=content_widget, **kwargs)


def create_nav_destination(
    icon_name: str,
    label: str,
    selected_icon_name: Optional[str] = None,
) -> Any:
    """Creates an ft.NavigationRailDestination control compatible across all Flet versions."""
    if ft is None:
        return None

    icon_data = get_icon(icon_name)
    selected_icon_data = get_icon(selected_icon_name) if selected_icon_name else icon_data
    return ft.NavigationRailDestination(
        icon=icon_data,
        selected_icon=selected_icon_data,
        label=label,
    )


def create_bottom_nav_destination(
    icon_name: str,
    label: str,
    selected_icon_name: Optional[str] = None,
) -> Any:
    """Creates an ft.NavigationDestination control compatible across all Flet versions."""
    if ft is None:
        return None

    icon_data = get_icon(icon_name)
    selected_icon_data = get_icon(selected_icon_name) if selected_icon_name else icon_data

    DestClass = getattr(ft, "NavigationDestination", None)
    if not DestClass:
        DestClass = getattr(ft, "NavigationBarDestination", None)

    if DestClass:
        try:
            return DestClass(
                icon=icon_data,
                selected_icon=selected_icon_data,
                label=label,
            )
        except Exception:
            try:
                return DestClass(icon=icon_data, label=label)
            except Exception:
                pass
    return None


def wrap_safe_area(control: Any) -> Any:
    """Wraps a control in ft.SafeArea for mobile notch, cutout, and system bar accommodation."""
    if ft is None or control is None:
        return control
    SafeAreaClass = getattr(ft, "SafeArea", None)
    if SafeAreaClass:
        try:
            return SafeAreaClass(content=control, expand=True)
        except Exception:
            pass
    return control


def open_dialog_compat(page: Any, dialog: Any) -> None:
    """Cross-version helper to display an AlertDialog on the active Page."""
    if not page or not dialog:
        return
    if hasattr(page, "open"):
        try:
            page.open(dialog)
            return
        except Exception:
            pass
    if hasattr(page, "open_dialog"):
        try:
            page.open_dialog(dialog)
            return
        except Exception:
            pass
    if hasattr(page, "show_dialog"):
        try:
            page.show_dialog(dialog)
            return
        except Exception:
            pass

    page.dialog = dialog
    dialog.open = True
    page.update()


def close_dialog_compat(page: Any, dialog: Any) -> None:
    """Cross-version helper to dismiss an AlertDialog from the active Page."""
    if not page:
        return
    if hasattr(page, "close"):
        try:
            page.close(dialog)
            return
        except Exception:
            pass
    if hasattr(page, "close_dialog"):
        try:
            page.close_dialog()
            return
        except Exception:
            pass
    if hasattr(page, "pop_dialog"):
        try:
            page.pop_dialog()
            return
        except Exception:
            pass

    if hasattr(page, "dialog") and page.dialog:
        page.dialog.open = False
        page.update()


def pad_all(val: Union[int, float]) -> Any:
    """Applies uniform padding on all sides."""
    if ft is None:
        return val
    PaddingClass = getattr(ft, "Padding", None)
    padding_mod = getattr(ft, "padding", None)
    if PaddingClass and hasattr(PaddingClass, "all"):
        return PaddingClass.all(val)
    if padding_mod and hasattr(padding_mod, "all"):
        return padding_mod.all(val)
    return val


def pad_symmetric(horizontal: Union[int, float] = 0, vertical: Union[int, float] = 0) -> Any:
    """Applies symmetric horizontal and vertical padding."""
    if ft is None:
        return None
    PaddingClass = getattr(ft, "Padding", None)
    padding_mod = getattr(ft, "padding", None)
    if PaddingClass:
        if hasattr(PaddingClass, "symmetric"):
            return PaddingClass.symmetric(vertical=vertical, horizontal=horizontal)
        try:
            return PaddingClass(vertical=vertical, horizontal=horizontal)
        except Exception:
            pass
    if padding_mod and hasattr(padding_mod, "symmetric"):
        return padding_mod.symmetric(horizontal=horizontal, vertical=vertical)
    if PaddingClass and hasattr(PaddingClass, "only"):
        return PaddingClass.only(left=horizontal, top=vertical, right=horizontal, bottom=vertical)
    if padding_mod and hasattr(padding_mod, "only"):
        return padding_mod.only(left=horizontal, top=vertical, right=horizontal, bottom=vertical)
    return None


def pad_only(
    left: Union[int, float] = 0,
    top: Union[int, float] = 0,
    right: Union[int, float] = 0,
    bottom: Union[int, float] = 0,
) -> Any:
    """Applies padding to specific sides."""
    if ft is None:
        return None
    PaddingClass = getattr(ft, "Padding", None)
    padding_mod = getattr(ft, "padding", None)
    if PaddingClass:
        if hasattr(PaddingClass, "only"):
            return PaddingClass.only(left=left, top=top, right=right, bottom=bottom)
        try:
            return PaddingClass(left=left, top=top, right=right, bottom=bottom)
        except Exception:
            pass
    if padding_mod and hasattr(padding_mod, "only"):
        return padding_mod.only(left=left, top=top, right=right, bottom=bottom)
    return None


def margin_only(
    left: Union[int, float] = 0,
    top: Union[int, float] = 0,
    right: Union[int, float] = 0,
    bottom: Union[int, float] = 0,
) -> Any:
    """Applies margin to specific sides."""
    if ft is None:
        return None
    MarginClass = getattr(ft, "Margin", None)
    margin_mod = getattr(ft, "margin", None)
    if MarginClass:
        if hasattr(MarginClass, "only"):
            return MarginClass.only(left=left, top=top, right=right, bottom=bottom)
        try:
            return MarginClass(left=left, top=top, right=right, bottom=bottom)
        except Exception:
            pass
    if margin_mod and hasattr(margin_mod, "only"):
        return margin_mod.only(left=left, top=top, right=right, bottom=bottom)
    return None


def border_all(width: float = 1, color: str = "#E2E8F0") -> Any:
    """Applies uniform border on all sides."""
    if ft is None:
        return None
    BorderClass = getattr(ft, "Border", None)
    border_mod = getattr(ft, "border", None)
    if BorderClass and hasattr(BorderClass, "all"):
        return BorderClass.all(width=width, color=color)
    if border_mod and hasattr(border_mod, "all"):
        return border_mod.all(width=width, color=color)
    return None


def border_radius_all(radius: Union[int, float]) -> Any:
    """Applies uniform border radius on all corners."""
    if ft is None:
        return radius
    BRClass = getattr(ft, "BorderRadius", None)
    br_mod = getattr(ft, "border_radius", None)
    if BRClass and hasattr(BRClass, "all"):
        return BRClass.all(radius)
    if br_mod and hasattr(br_mod, "all"):
        return br_mod.all(radius)
    return radius


def align_center() -> Any:
    """Returns center alignment."""
    if ft is None:
        return None
    AlignClass = getattr(ft, "Alignment", None)
    align_mod = getattr(ft, "alignment", None)
    if AlignClass and hasattr(AlignClass, "CENTER"):
        return AlignClass.CENTER
    if AlignClass:
        try:
            return AlignClass(0.0, 0.0)
        except Exception:
            pass
    if align_mod and hasattr(align_mod, "center"):
        return align_mod.center
    return None