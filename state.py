"""Warlock Mod Manager — shared application state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional
import xml.etree.ElementTree as ET

from project import GameScan


@dataclass
class ModManagerState:
    # Game and workspace
    scan: Optional[GameScan] = None
    workspace_dir: Optional[str] = None
    manifest: Dict[str, str] = field(default_factory=dict)

    # Currently open file
    current_orig: Optional[str] = None
    tree_xml: Optional[ET.ElementTree] = None
    dirty: bool = False

    # XML tree bookkeeping
    iid_to_node: Dict[str, ET.Element] = field(default_factory=dict)
    iid_to_parent: Dict[str, Optional[ET.Element]] = field(default_factory=dict)

    # Cross-file reference navigation
    workspace_index: Dict[str, Dict[str, ET.Element]] = field(default_factory=dict)
    pending_jump: Optional[str] = None

    # Localization
    localization: Dict[str, str] = field(default_factory=dict)

    # UI busy flag
    busy: bool = False