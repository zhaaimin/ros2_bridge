#!/usr/bin/env bash
# 安装 WebSocket-ROS2 桥接服务
# 用法: bash install.sh [ROS2_DISTRO]
# 示例: bash install.sh humble

set -euo pipefail

ROS2_DISTRO="${1:-humble}"
ROS2_SETUP="/opt/ros/${ROS2_DISTRO}/setup.bash"
SERVICE_NAME="ros2-bridge"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="${SUDO_USER:-$(whoami)}"
WRAPPER="${PROJECT_DIR}/run_bridge.sh"

# ── 检查 ROS2 环境 ─────────────────────────────────────────────
if [[ ! -f "${ROS2_SETUP}" ]]; then
    echo "[ERROR] ROS2 setup not found: ${ROS2_SETUP}"
    echo "        请指定正确的 distro，例如: bash install.sh iron"
    exit 1
fi
echo "[INFO] Using ROS2: ${ROS2_SETUP}"

# ── 安装 Python 依赖 ───────────────────────────────────────────
echo "[INFO] Installing Python dependencies…"
pip3 install -r "${PROJECT_DIR}/requirements.txt"

# ── 生成启动包装脚本 ───────────────────────────────────────────
cat > "${WRAPPER}" << EOF
#!/usr/bin/env bash
source "${ROS2_SETUP}"
export PYTHONPATH="${PROJECT_DIR}:\${PYTHONPATH:-}"
exec python3 -m bridge.main "\$@"
EOF
chmod +x "${WRAPPER}"
echo "[INFO] Wrapper: ${WRAPPER}"

# ── 安装 systemd 服务（需要 root） ─────────────────────────────
if [[ $EUID -ne 0 ]]; then
    echo "[WARN] Not running as root — skipping systemd installation."
    echo "       Re-run with sudo to install the systemd service, or start manually:"
    echo "       ${WRAPPER}"
    exit 0
fi

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=WebSocket JSON-RPC to ROS2 Bridge
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${WRAPPER}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

echo "[OK] Service installed: ${SERVICE_NAME}"
echo "     Start:   sudo systemctl start ${SERVICE_NAME}"
echo "     Status:  sudo systemctl status ${SERVICE_NAME}"
echo "     Logs:    sudo journalctl -u ${SERVICE_NAME} -f"
