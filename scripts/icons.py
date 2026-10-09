"""Simple line icons shown where an item has no product photo (one per item type), shared by the site's JS and static pages."""
_S = '<svg viewBox="0 0 48 48" width="40" height="40" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
ICONS = {
    "watch": _S + '<rect x="15" y="4" width="18" height="8" rx="2"/><rect x="15" y="36" width="18" height="8" rx="2"/><circle cx="24" cy="24" r="12"/><path d="M24 17v7l4 3"/></svg>',
    "sneakers": _S + '<path d="M5 30c0-5 1-12 3-14l7 3 5-5c3 4 7 8 14 10 6 2 9 4 9 8v2H5z"/><path d="M5 34h38"/><path d="M14 22l3 3M18 19l3 3"/></svg>',
    "shoes": _S + '<path d="M6 30c3-1 6-4 9-9l7 2c4 3 10 4 16 5 4 1 5 3 5 5v1H6z"/><path d="M6 34h37"/></svg>',
    "clothing": _S + '<path d="M17 6l7 5 7-5 11 6-4 9-5-2v23H15V19l-5 2-4-9z"/></svg>',
    "bag": _S + '<rect x="8" y="16" width="32" height="26" rx="3"/><path d="M17 16v-3a7 7 0 0 1 14 0v3"/></svg>',
    "jewelry": _S + '<path d="M10 8c2 14 8 20 14 20s12-6 14-20"/><path d="M24 28l-5 6 5 7 5-7z"/></svg>',
    "accessory": _S + '<circle cx="14" cy="28" r="8"/><circle cx="34" cy="28" r="8"/><path d="M22 27c1-1 3-1 4 0M6 26l-2-6M42 26l2-6"/></svg>',
}
