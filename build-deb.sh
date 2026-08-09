#!/bin/bash
# FragBASIC — Debian package builder
#
# Assembles a .deb containing the fragbasic_core interpreter, a /usr/bin/fragbasic
# CLI wrapper, an application icon, and a .desktop launcher (so file managers like
# Nemo can show the icon on .bas files and "Open With" FragBASIC). No compiled
# extensions are involved — this just stages pure-Python source plus metadata and
# calls dpkg-deb.
#
# Usage: ./build-deb.sh
# Output: dist/fragbasic_<version>_all.deb

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VERSION="$(grep -m1 '^version' pyproject.toml | sed -E 's/version *= *"(.*)"/\1/')"
PKG_NAME="fragbasic"
MAINTAINER="Chuck Finch <chuckcodes4cash@gmail.com>"
ARCH="all"

BUILD_ROOT="build/deb-root"
OUT_DIR="dist"
DEB_FILE="${OUT_DIR}/${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "=== Building ${PKG_NAME} ${VERSION} (${ARCH}) ==="

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"

# --- DEBIAN control metadata ---
mkdir -p "$BUILD_ROOT/DEBIAN"
cat > "$BUILD_ROOT/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: interpreters
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.8)
Maintainer: ${MAINTAINER}
Homepage: https://github.com/CFFinch62
Description: Standalone, dependency-free educational BASIC interpreter
 FragBASIC is a teaching-focused BASIC dialect with five value types,
 arrays up to 3 dimensions, IF/SELECT CASE/FOR/WHILE/DO/GOSUB control
 flow, SUB/FUNCTION, PRINT/INPUT/DATA/READ, and about 35 built-in
 math/string/conversion/system functions.
 .
 It ships as a CLI tool (run 'fragbasic' from a terminal or point any
 code editor / IDE at it as a subprocess runner for .bas files) and as
 an embeddable Python package with zero third-party dependencies.
EOF

cat > "$BUILD_ROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-mime-database >/dev/null 2>&1; then
    update-mime-database /usr/share/mime >/dev/null 2>&1 || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi
exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/postinst"

cat > "$BUILD_ROOT/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi
exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/postrm"

# --- Interpreter source (pure Python, zero third-party deps) ---
SRC_DEST="$BUILD_ROOT/usr/share/fragbasic/src/fragbasic_core"
mkdir -p "$SRC_DEST"
find src/fragbasic_core -name '*.py' -exec cp {} "$SRC_DEST/" \;

# --- CLI wrapper ---
mkdir -p "$BUILD_ROOT/usr/bin"
cat > "$BUILD_ROOT/usr/bin/fragbasic" <<'EOF'
#!/bin/sh
# Launches the FragBASIC interpreter installed under /usr/share/fragbasic.
exec env PYTHONPATH="/usr/share/fragbasic/src${PYTHONPATH:+:$PYTHONPATH}" python3 -m fragbasic_core "$@"
EOF
chmod 755 "$BUILD_ROOT/usr/bin/fragbasic"

# --- Icon (hicolor theme, all standard sizes + scalable source) ---
for size in 16 22 24 32 48 64 128 256 512; do
    ICON_DIR="$BUILD_ROOT/usr/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$ICON_DIR"
    cp "packaging/icons/fragbasic_${size}.png" "$ICON_DIR/fragbasic.png"
done
mkdir -p "$BUILD_ROOT/usr/share/icons/hicolor/scalable/apps"
cp "packaging/icons/fragbasic_icon.svg" "$BUILD_ROOT/usr/share/icons/hicolor/scalable/apps/fragbasic.svg"

# --- Desktop launcher (menu entry + "Open With" for .bas files) ---
mkdir -p "$BUILD_ROOT/usr/share/applications"
cp "packaging/fragbasic.desktop" "$BUILD_ROOT/usr/share/applications/fragbasic.desktop"

# --- Copyright / license ---
DOC_DEST="$BUILD_ROOT/usr/share/doc/${PKG_NAME}"
mkdir -p "$DOC_DEST"
cp LICENSE "$DOC_DEST/copyright"

# --- Permissions ---
find "$BUILD_ROOT" -type d -exec chmod 755 {} \;
find "$BUILD_ROOT" -type f -exec chmod 644 {} \;
chmod 755 "$BUILD_ROOT/usr/bin/fragbasic"
chmod 755 "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/postrm"

# --- Build ---
mkdir -p "$OUT_DIR"
dpkg-deb --root-owner-group --build "$BUILD_ROOT" "$DEB_FILE"

echo ""
echo "=== Built ${DEB_FILE} ==="
echo "Install with:   sudo apt install ./${DEB_FILE}"
echo "Or:             sudo dpkg -i ${DEB_FILE}"
echo "Then run:       fragbasic examples/hello.bas"
