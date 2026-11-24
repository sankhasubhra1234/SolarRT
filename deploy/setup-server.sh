#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 VPS for SolarRT. Run as root:
#   bash setup-server.sh <your-username> "<your SSH public key>"
#
# What it does:
#  - creates a sudo user that logs in with your SSH key only
#  - disables root login and password logins over SSH
#  - firewall: only SSH (22), HTTP (80) and HTTPS (443) open
#  - automatic security updates; fail2ban against SSH brute force
#  - installs Docker Engine + Compose plugin from Docker's official repository
#
# Read it before running it. Keep your current SSH session open until you've confirmed
# that you can log in as the new user in a second terminal.
set -euo pipefail

USERNAME="${1:?usage: setup-server.sh <username> \"<ssh public key>\"}"
PUBKEY="${2:?usage: setup-server.sh <username> \"<ssh public key>\"}"

[[ $EUID -eq 0 ]] || { echo "Run as root"; exit 1; }
[[ "$PUBKEY" == ssh-* || "$PUBKEY" == ecdsa-* ]] || { echo "That doesn't look like an SSH public key"; exit 1; }

echo "==> Updating packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get upgrade -y
apt-get install -y ca-certificates curl gnupg ufw fail2ban unattended-upgrades

echo "==> Creating user $USERNAME"
if ! id "$USERNAME" &>/dev/null; then
  adduser --disabled-password --gecos "" "$USERNAME"
fi
usermod -aG sudo "$USERNAME"
install -d -m 700 -o "$USERNAME" -g "$USERNAME" "/home/$USERNAME/.ssh"
echo "$PUBKEY" > "/home/$USERNAME/.ssh/authorized_keys"
chown "$USERNAME:$USERNAME" "/home/$USERNAME/.ssh/authorized_keys"
chmod 600 "/home/$USERNAME/.ssh/authorized_keys"
echo "$USERNAME ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$USERNAME"
chmod 440 "/etc/sudoers.d/90-$USERNAME"

echo "==> Hardening SSH (keys only, no root login)"
cat > /etc/ssh/sshd_config.d/99-solarrt-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
MaxAuthTries 4
X11Forwarding no
EOF
sshd -t && systemctl reload ssh

echo "==> Firewall"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

echo "==> Automatic security updates + fail2ban"
dpkg-reconfigure -f noninteractive unattended-upgrades
systemctl enable --now fail2ban

echo "==> Installing Docker (official repository)"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
usermod -aG docker "$USERNAME"

# Docker publishes ports past ufw; only Caddy publishes ports (80/443), the app never does.
echo
echo "Done. Next, in a NEW terminal, check you can log in:  ssh $USERNAME@<server-ip>"
echo "Then follow docs/DEPLOY.md to upload SolarRT and start it."
