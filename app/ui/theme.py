"""Light/dark stylesheets for a consistent, professional business look.

One centralised stylesheet function rather than styling scattered across
widgets (rule 9's "centralised system" principle applied to the UI as well).
"""

from __future__ import annotations

from app.config.constants import ThemeMode

_LIGHT = {
    "bg": "#F4F6F8",
    "surface": "#FFFFFF",
    "border": "#DDE3EA",
    "text": "#1A2330",
    "text_muted": "#5B6675",
    "sidebar_bg": "#1C2733",
    "sidebar_text": "#C9D3DE",
    "sidebar_text_active": "#FFFFFF",
    "sidebar_active_bg": "#0F62FE",
}

_DARK = {
    "bg": "#141A22",
    "surface": "#1D2530",
    "border": "#2C3846",
    "text": "#E7ECF2",
    "text_muted": "#94A2B3",
    "sidebar_bg": "#0F151C",
    "sidebar_text": "#B7C2CF",
    "sidebar_text_active": "#FFFFFF",
    "sidebar_active_bg": "#2563EB",
}


def stylesheet(theme: str, accent: str = "#0F62FE") -> str:
    """Build the application-wide QSS for the given theme."""
    palette = _DARK if theme == ThemeMode.DARK.value else _LIGHT
    return f"""
    QWidget {{
        background: {palette['bg']};
        color: {palette['text']};
        font-size: 13px;
    }}
    QMainWindow {{ background: {palette['bg']}; }}

    #Sidebar {{
        background: {palette['sidebar_bg']};
        min-width: 220px;
        max-width: 220px;
    }}
    #Sidebar QPushButton {{
        color: {palette['sidebar_text']};
        background: transparent;
        border: none;
        text-align: left;
        padding: 10px 18px;
        font-size: 13px;
        border-radius: 6px;
        margin: 2px 10px;
    }}
    #Sidebar QPushButton:hover {{
        background: rgba(255, 255, 255, 0.08);
        color: {palette['sidebar_text_active']};
    }}
    #Sidebar QPushButton:checked {{
        background: {palette['sidebar_active_bg']};
        color: {palette['sidebar_text_active']};
        font-weight: 600;
    }}
    #SidebarTitle {{
        color: {palette['sidebar_text_active']};
        font-size: 16px;
        font-weight: 700;
        padding: 18px 18px 6px 18px;
    }}
    #SidebarSubtitle {{
        color: {palette['sidebar_text']};
        font-size: 11px;
        padding: 0 18px 14px 18px;
    }}

    QFrame#Card, QWidget#Card {{
        background: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 10px;
    }}
    QLabel#CardValue {{
        font-size: 26px;
        font-weight: 700;
    }}
    QLabel#CardLabel {{
        color: {palette['text_muted']};
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.4px;
    }}
    QLabel#PageTitle {{
        font-size: 20px;
        font-weight: 700;
        padding: 4px 0 2px 0;
    }}
    QLabel#PageSubtitle {{
        color: {palette['text_muted']};
        font-size: 12px;
        padding-bottom: 10px;
    }}

    QTableView {{
        background: {palette['surface']};
        alternate-background-color: {palette['bg']};
        gridline-color: {palette['border']};
        border: 1px solid {palette['border']};
        border-radius: 8px;
        selection-background-color: {accent};
        selection-color: white;
    }}
    QHeaderView::section {{
        background: {palette['surface']};
        color: {palette['text_muted']};
        border: none;
        border-bottom: 2px solid {palette['border']};
        padding: 6px;
        font-weight: 600;
    }}

    QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
        background: {palette['surface']};
        border: 1px solid {palette['border']};
        border-radius: 6px;
        padding: 5px 8px;
    }}
    QLineEdit:focus, QComboBox:focus {{
        border: 1px solid {accent};
    }}

    QPushButton#PrimaryButton {{
        background: {accent};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
        font-weight: 600;
    }}
    QPushButton#PrimaryButton:hover {{ background: {accent}; opacity: 0.9; }}

    QStatusBar {{
        background: {palette['surface']};
        border-top: 1px solid {palette['border']};
    }}
    QToolTip {{
        background: {palette['surface']};
        color: {palette['text']};
        border: 1px solid {palette['border']};
    }}
    """
